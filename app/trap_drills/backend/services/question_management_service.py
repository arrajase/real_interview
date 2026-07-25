"""
Question management (v2 §9.5, Module 7): add/edit/delete + Phase 1 review queue.

Access control default (v1, §12 was left open): open to any signed-in user,
not restricted to ADMIN_EMAILS — matches the doc's non-goal of "no new admin
features specific to this module" (v2 §3). Flip this to an admin check later
by wrapping the routes with require_admin if that default changes.
"""

from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId

from app.real_interview import logger
from app.trap_drills.backend.config.roles_config import is_valid_role
from app.trap_drills.backend.services.trick_questions_db import (
    get_questions_collection,
    new_question_document,
)

_EDITABLE_FIELDS = ("role", "category", "prompt", "trap_answer", "correct_answer", "explanation")


def _to_object_id(raw: str) -> Optional[ObjectId]:
    try:
        return ObjectId((raw or "").strip())
    except (InvalidId, TypeError):
        return None


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "question_id": str(doc["_id"]),
        "role": doc.get("role", ""),
        "category": doc.get("category", ""),
        "prompt": doc.get("prompt", ""),
        "trap_answer": doc.get("trap_answer", ""),
        "correct_answer": doc.get("correct_answer", ""),
        "explanation": doc.get("explanation", ""),
        "active": bool(doc.get("active", True)),
        "source": doc.get("source", "manual"),
        "review_status": doc.get("review_status", "approved"),
        "origin_user_id": doc.get("origin_user_id"),
    }


def _require_non_empty(value: Any, field_name: str) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return f"{field_name} is required"
    return None


def _load_editable_question(question_id: str, user_id: str):
    """
    Fetch a question this user is allowed to edit/delete: global (origin_user_id
    is None) or their own personalized question — never someone else's private
    personalized content, even under the "open to any signed-in user" default
    (guardrails §4 — data isolation is a hard invariant, not just for the
    due-queue/answer endpoints).
    """
    oid = _to_object_id(question_id)
    if oid is None:
        return None
    doc = get_questions_collection().find_one({"_id": oid})
    if not doc:
        return None
    origin_user_id = doc.get("origin_user_id")
    if origin_user_id is not None and origin_user_id != user_id:
        return None
    return doc


def create_question(
    *,
    role: str,
    category: str,
    prompt: str,
    trap_answer: str,
    correct_answer: str,
    explanation: str,
) -> Dict[str, Any]:
    for value, name in (
        (role, "role"),
        (category, "category"),
        (prompt, "prompt"),
        (trap_answer, "trap_answer"),
        (correct_answer, "correct_answer"),
        (explanation, "explanation"),
    ):
        error = _require_non_empty(value, name)
        if error:
            return {"status_code": 400, "error": error}

    if not is_valid_role(role):
        return {"status_code": 400, "error": "role is not a recognized role"}

    doc = new_question_document(
        role=role.strip(),
        category=category.strip(),
        prompt=prompt.strip(),
        trap_answer=trap_answer.strip(),
        correct_answer=correct_answer.strip(),
        explanation=explanation.strip(),
        source="manual",
        review_status="approved",
        origin_user_id=None,
    )
    result = get_questions_collection().insert_one(doc)
    doc["_id"] = result.inserted_id
    logger.info("[trap_drills][question_management] created question_id=%s role=%s", result.inserted_id, role)
    return {"status_code": 201, "question": _serialize(doc)}


def update_question(question_id: str, user_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    doc = _load_editable_question(question_id, user_id)
    if not doc:
        return {"status_code": 404, "error": "question not found"}

    updates: Dict[str, Any] = {}
    for key in _EDITABLE_FIELDS:
        if key not in fields:
            continue
        value = fields[key]
        error = _require_non_empty(value, key)
        if error:
            return {"status_code": 400, "error": error}
        if key == "role" and not is_valid_role(value):
            return {"status_code": 400, "error": "role is not a recognized role"}
        updates[key] = value.strip()

    if not updates:
        return {"status_code": 400, "error": "no editable fields provided"}

    get_questions_collection().update_one({"_id": doc["_id"]}, {"$set": updates})
    doc.update(updates)
    logger.info("[trap_drills][question_management] updated question_id=%s fields=%s", question_id, list(updates))
    return {"status_code": 200, "question": _serialize(doc)}


def soft_delete_question(question_id: str, user_id: str) -> Dict[str, Any]:
    doc = _load_editable_question(question_id, user_id)
    if not doc:
        return {"status_code": 404, "error": "question not found"}

    get_questions_collection().update_one({"_id": doc["_id"]}, {"$set": {"active": False}})
    logger.info("[trap_drills][question_management] soft-deleted question_id=%s", question_id)
    return {"status_code": 200, "message": "question deleted"}


def list_questions(role: Optional[str] = None) -> Dict[str, Any]:
    """
    Management listing: global (shared) bank only, active or not, any review
    status — this is the authoring/editing view, not the due-queue, so
    answer content is included on purpose.
    """
    query: Dict[str, Any] = {"origin_user_id": None, "active": True}
    if role:
        query["role"] = role
    docs = list(get_questions_collection().find(query).sort("created_at", -1))
    return {"status_code": 200, "questions": [_serialize(d) for d in docs]}


def list_pending_review() -> Dict[str, Any]:
    docs = list(
        get_questions_collection()
        .find({"source": "ai_generated", "review_status": "pending_review", "active": True})
        .sort("created_at", 1)
    )
    return {"status_code": 200, "questions": [_serialize(d) for d in docs]}


def review_question(question_id: str, decision: str) -> Dict[str, Any]:
    if decision not in ("approve", "reject"):
        return {"status_code": 400, "error": "decision must be 'approve' or 'reject'"}

    oid = _to_object_id(question_id)
    if oid is None:
        return {"status_code": 400, "error": "invalid question_id"}

    new_status = "approved" if decision == "approve" else "rejected"
    # No review_status filter here: a previously-rejected item must still be
    # reachable for manual re-approval later (Module 7 acceptance criteria),
    # not just pending_review -> approved/rejected.
    result = get_questions_collection().update_one(
        {"_id": oid, "source": "ai_generated"},
        {"$set": {"review_status": new_status}},
    )
    if result.matched_count == 0:
        return {"status_code": 404, "error": "question not found"}

    logger.info("[trap_drills][question_management] reviewed question_id=%s decision=%s", question_id, decision)
    return {"status_code": 200, "message": "question " + new_status, "review_status": new_status}
