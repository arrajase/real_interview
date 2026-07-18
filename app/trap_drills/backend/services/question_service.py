"""
Core question API logic (v2 §8, Module 3): due queue, answer submission, stats.

Module 3 scope is global-only (origin_user_id=None) — Module 11 adds the
personalized mix on top of get_due_questions. No LLM calls anywhere in this
file (guardrails §5: no AI on the due-question or answer-submission hot path).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId

from app.real_interview import logger
from app.trap_drills.backend.services import leitner
from app.trap_drills.backend.services.trick_questions_db import (
    get_attempts_collection,
    get_progress_collection,
    get_questions_collection,
)

_GLOBAL_ELIGIBLE_FILTER = {"active": True, "review_status": "approved", "origin_user_id": None}


def _to_object_id(raw: str) -> Optional[ObjectId]:
    try:
        return ObjectId((raw or "").strip())
    except (InvalidId, TypeError):
        return None


def get_due_questions(user_id: str, role: str, limit: int = 15) -> List[Dict[str, Any]]:
    """
    Global-only due queue for this user's effective role (Module 11 adds the
    personalized mix). Never returns trap_answer/correct_answer/explanation
    (guardrails §4 — content-leak concern, not just UI nicety).
    """
    # PyMongo returns stored datetimes as timezone-naive (BSON has no tz),
    # so compare against a naive "now" here to avoid aware/naive TypeErrors.
    now_naive = datetime.now(timezone.utc).replace(tzinfo=None)
    questions_coll = get_questions_collection()
    progress_coll = get_progress_collection()

    all_progress = list(
        progress_coll.find({"user_id": user_id, "role": role}, {"question_id": 1, "box": 1, "next_review_at": 1})
    )
    seen_ids = {row["question_id"] for row in all_progress}
    due_seen = {
        row["question_id"]: row["box"]
        for row in all_progress
        if row["next_review_at"] <= now_naive
    }

    unseen_docs = list(
        questions_coll.find(
            {**_GLOBAL_ELIGIBLE_FILTER, "role": role, "_id": {"$nin": list(seen_ids)}},
            {"_id": 1, "category": 1, "prompt": 1},
        )
    )
    unseen_ids = {doc["_id"] for doc in unseen_docs}

    due_seen_ids = list(due_seen.keys())
    due_seen_docs = (
        list(
            questions_coll.find(
                {**_GLOBAL_ELIGIBLE_FILTER, "_id": {"$in": due_seen_ids}},
                {"_id": 1, "category": 1, "prompt": 1},
            )
        )
        if due_seen_ids
        else []
    )

    items: List[Dict[str, Any]] = []
    for doc in unseen_docs:
        items.append({"question_id": doc["_id"], "category": doc.get("category", ""), "prompt": doc.get("prompt", ""), "box": 0})
    for doc in due_seen_docs:
        items.append(
            {
                "question_id": doc["_id"],
                "category": doc.get("category", ""),
                "prompt": doc.get("prompt", ""),
                "box": due_seen[doc["_id"]],
            }
        )

    items.sort(key=lambda item: item["box"])
    limited = items[: max(0, limit)]
    for item in limited:
        item["question_id"] = str(item["question_id"])
    logger.info(
        "[trap_drills][question_service] get_due_questions user_id=%s role=%s unseen=%s due_seen=%s returned=%s",
        user_id,
        role,
        len(unseen_ids),
        len(due_seen),
        len(limited),
    )
    return limited


def submit_answer(user_id: str, question_id: str, was_correct: bool) -> Dict[str, Any]:
    question_oid = _to_object_id(question_id)
    if question_oid is None:
        return {"status_code": 400, "error": "invalid question_id"}

    questions_coll = get_questions_collection()
    question = questions_coll.find_one({"_id": question_oid, "active": True, "review_status": "approved"})
    if not question:
        return {"status_code": 404, "error": "question not found"}

    # Data isolation (guardrails §4): a personalized question belongs only to
    # the user it was generated for, even though Module 3 doesn't create any yet.
    origin_user_id = question.get("origin_user_id")
    if origin_user_id is not None and origin_user_id != user_id:
        return {"status_code": 404, "error": "question not found"}

    progress_coll = get_progress_collection()
    existing = progress_coll.find_one({"user_id": user_id, "question_id": question_oid})
    current_box = existing["box"] if existing else 0
    new_box = leitner.next_box(current_box, was_correct)
    now = datetime.now(timezone.utc)
    next_review_at = leitner.compute_next_review_at(new_box, now=now)
    total_attempts = (existing["total_attempts"] + 1) if existing else 1

    progress_coll.update_one(
        {"user_id": user_id, "question_id": question_oid},
        {
            "$set": {
                "user_id": user_id,
                "question_id": question_oid,
                "role": question.get("role", ""),
                "category": question.get("category", ""),
                "box": new_box,
                "next_review_at": next_review_at,
                "last_answered_at": now,
                "last_result": "correct" if was_correct else "incorrect",
                "total_attempts": total_attempts,
            }
        },
        upsert=True,
    )

    get_attempts_collection().insert_one(
        {
            "user_id": user_id,
            "question_id": question_oid,
            "role": question.get("role", ""),
            "category": question.get("category", ""),
            "was_correct": bool(was_correct),
            "box_after": new_box,
            "answered_at": now,
        }
    )

    logger.info(
        "[trap_drills][question_service] submit_answer user_id=%s question_id=%s was_correct=%s new_box=%s",
        user_id,
        question_id,
        was_correct,
        new_box,
    )

    return {
        "status_code": 200,
        "question_id": question_id,
        "was_correct": bool(was_correct),
        "box": new_box,
        "next_review_at": next_review_at.isoformat(),
        "trap_answer": question.get("trap_answer", ""),
        "correct_answer": question.get("correct_answer", ""),
        "explanation": question.get("explanation", ""),
    }


def get_stats(user_id: str, role: str) -> Dict[str, Any]:
    questions_coll = get_questions_collection()
    progress_coll = get_progress_collection()
    attempts_coll = get_attempts_collection()

    total_by_category: Dict[str, int] = {}
    for doc in questions_coll.aggregate(
        [
            {"$match": {**_GLOBAL_ELIGIBLE_FILTER, "role": role}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
        ]
    ):
        total_by_category[doc["_id"] or ""] = doc["count"]

    attempted_by_category: Dict[str, int] = {}
    mastered_by_category: Dict[str, int] = {}
    for doc in progress_coll.aggregate(
        [
            {"$match": {"user_id": user_id, "role": role}},
            {
                "$group": {
                    "_id": "$category",
                    "attempted": {"$sum": 1},
                    "mastered": {"$sum": {"$cond": [{"$eq": ["$box", leitner.MAX_BOX]}, 1, 0]}},
                }
            },
        ]
    ):
        attempted_by_category[doc["_id"] or ""] = doc["attempted"]
        mastered_by_category[doc["_id"] or ""] = doc["mastered"]

    accuracy_by_category: Dict[str, float] = {}
    for doc in attempts_coll.aggregate(
        [
            {"$match": {"user_id": user_id, "role": role}},
            {
                "$group": {
                    "_id": "$category",
                    "total": {"$sum": 1},
                    "correct": {"$sum": {"$cond": ["$was_correct", 1, 0]}},
                }
            },
        ]
    ):
        total = doc["total"] or 0
        accuracy_by_category[doc["_id"] or ""] = round((doc["correct"] / total) * 100, 1) if total else 0.0

    categories = sorted(set(total_by_category) | set(attempted_by_category) | set(accuracy_by_category))
    rows = [
        {
            "category": category,
            "total_questions": total_by_category.get(category, 0),
            "attempted_count": attempted_by_category.get(category, 0),
            "mastered_count": mastered_by_category.get(category, 0),
            "accuracy_percent": accuracy_by_category.get(category, 0.0),
        }
        for category in categories
    ]
    logger.info("[trap_drills][question_service] get_stats user_id=%s role=%s categories=%s", user_id, role, len(rows))
    return {"status_code": 200, "role": role, "categories": rows}
