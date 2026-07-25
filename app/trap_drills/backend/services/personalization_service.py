"""
AI-assisted seeding — Phase 2: personalized generation from a user's own
completed interviews, plus the due-queue weighting signal (v2 §7.2, §7.4).

Trigger is wired into GET /api/trap-drills/role (called once per Trap Drills
"open" via the frontend's boot sequence), never into the due-question or
answer-submission endpoints — that split is deliberate so no LLM call ever
sits on the due-queue/answer hot path (guardrails §5), even though this
module's whole purpose is "generate before showing the due queue."
"""

import os
from typing import Any, Dict, List, Optional

from app.real_interview import logger
from app.real_interview.backend.auth.email_utils import find_user_by_id
from app.real_interview.backend.services import interview_record
from app.real_interview.backend.services.interview_qa_extract import extract_interview_qa_pairs
from app.real_interview.backend.utils.mongodb import get_mongodb_database
from app.trap_drills.backend.agents.trick_question_agent import TrickQuestionAgent
from app.trap_drills.backend.config.roles_config import (
    detect_role_from_text,
    get_categories_for_role,
    is_valid_role,
)
from app.trap_drills.backend.services.trick_questions_db import (
    get_questions_collection,
    new_question_document,
)

PROCESSED_SESSIONS_FIELD = "trap_drills_processed_session_ids"
MAX_PERSONALIZED_FRACTION = 0.5
PERSONALIZED_FRACTION_PER_WEAK_AREA = 0.1
QUESTIONS_PER_SESSION = 5


def _get_db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "real_interview").strip()


def _get_users_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_USERS", "authentications").strip()


def _users_collection():
    return get_mongodb_database(_get_db_name())[_get_users_collection_name()]


def get_processed_session_ids(user_id: str) -> List[str]:
    doc = find_user_by_id(_users_collection(), user_id)
    if not doc:
        return []
    return list(doc.get(PROCESSED_SESSIONS_FIELD) or [])


def _mark_session_processed(user_id: str, session_id: str) -> None:
    doc = find_user_by_id(_users_collection(), user_id)
    if not doc:
        return
    _users_collection().update_one(
        {"_id": doc["_id"]},
        {"$addToSet": {PROCESSED_SESSIONS_FIELD: session_id}},
    )


def _completed_sessions_for_role(user_id: str, effective_role: str) -> List[Dict[str, Any]]:
    """Completed real_interview sessions whose role_applied_for maps to effective_role."""
    summaries = interview_record.list_interviews_for_candidate_by_kind(user_id, "completed")
    matches = []
    for summary in summaries:
        detected = detect_role_from_text(summary.get("role_applied_for") or "")
        if detected == effective_role:
            matches.append(summary)
    return matches


def compute_weak_area_signal(user_id: str, effective_role: str) -> int:
    """Distinct areas_to_improve across this user's completed sessions for this role."""
    if not effective_role:
        return 0
    weak_areas: set = set()
    for summary in _completed_sessions_for_role(user_id, effective_role):
        record = interview_record.get_interview_by_session(summary["session_id"])
        if not record:
            continue
        feedback = record.get("interview_feedback") or {}
        for area in feedback.get("areas_to_improve") or []:
            normalized = (area or "").strip().lower()
            if normalized:
                weak_areas.add(normalized)
    return len(weak_areas)


def compute_personalized_fraction(user_id: str, effective_role: str) -> float:
    """
    Default weighting formula (v2 §7.4, flagged there as a tunable first
    guess): personalized_fraction = min(0.5, 0.1 * distinct_weak_areas).
    """
    distinct_weak_areas = compute_weak_area_signal(user_id, effective_role)
    return min(MAX_PERSONALIZED_FRACTION, PERSONALIZED_FRACTION_PER_WEAK_AREA * distinct_weak_areas)


def _normalize_category(raw_category: str, categories: List[str]) -> str:
    """
    The LLM is asked to pick one of the role's fixed categories, but structured
    output isn't a hard constraint — it can still invent its own label (seen in
    practice). Phase 2 has no human review gate, so enforce the fixed list here
    in code rather than trusting the prompt alone: fall back to the role's
    first category on any mismatch, so Category Dashboard grouping never
    fragments into ad hoc categories no one configured.
    """
    candidate = (raw_category or "").strip().lower()
    for category in categories:
        if category.strip().lower() == candidate:
            return category
    return categories[0] if categories else ""


def generate_personalized_questions_for_user(
    user_id: str,
    effective_role: str,
    agent: Optional[TrickQuestionAgent] = None,
) -> int:
    """
    Process any of this user's completed sessions (matching effective_role) not
    already in their processed-sessions list. Returns count of new questions
    inserted. Never raises — a failed generation should not break the caller
    (the /role endpoint).
    """
    if not effective_role or not is_valid_role(effective_role):
        return 0

    processed = set(get_processed_session_ids(user_id))
    sessions = _completed_sessions_for_role(user_id, effective_role)
    new_sessions = [s for s in sessions if s["session_id"] not in processed]
    if not new_sessions:
        return 0

    agent = agent or TrickQuestionAgent()
    categories = get_categories_for_role(effective_role)
    questions_coll = get_questions_collection()
    total_inserted = 0

    for summary in new_sessions:
        session_id = summary["session_id"]
        try:
            record = interview_record.get_interview_by_session(session_id)
            if not record:
                _mark_session_processed(user_id, session_id)
                continue

            qa_pairs = extract_interview_qa_pairs(record.get("messages") or [])
            feedback = record.get("interview_feedback") or {}

            items = agent.generate_personalized_questions(
                role=effective_role,
                categories=categories,
                qa_pairs=qa_pairs,
                feedback=feedback,
                count=QUESTIONS_PER_SESSION,
            )

            docs = [
                new_question_document(
                    role=effective_role,
                    category=_normalize_category(item.category, categories),
                    prompt=item.prompt.strip(),
                    trap_answer=item.trap_answer.strip(),
                    correct_answer=item.correct_answer.strip(),
                    explanation=item.explanation.strip(),
                    source="ai_personalized",
                    review_status="approved",
                    origin_user_id=user_id,
                    source_session_id=session_id,
                )
                for item in items
                if item.prompt.strip() and item.trap_answer.strip() and item.correct_answer.strip()
            ]
            if docs:
                questions_coll.insert_many(docs)
                total_inserted += len(docs)
                logger.info(
                    "[trap_drills][personalization] inserted %s question(s) user_id=%s session_id=%s",
                    len(docs),
                    user_id,
                    session_id,
                )

            _mark_session_processed(user_id, session_id)
        except Exception:
            # Never let a single failed session block the /role endpoint or
            # prevent other sessions from being processed.
            logger.exception(
                "[trap_drills][personalization] failed to process session_id=%s user_id=%s",
                session_id,
                user_id,
            )

    return total_inserted


def maybe_generate_personalized_questions(user_id: str, effective_role: Optional[str]) -> None:
    """Best-effort lazy trigger, called from GET /api/trap-drills/role. Swallows all errors."""
    if not effective_role:
        return
    try:
        generate_personalized_questions_for_user(user_id, effective_role)
    except Exception:
        logger.exception(
            "[trap_drills][personalization] maybe_generate_personalized_questions failed user_id=%s",
            user_id,
        )
