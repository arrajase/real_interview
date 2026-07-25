"""
"Report this question" (v2 §7.3, Module 11): a lightweight safety valve for
unreviewed ai_personalized content — just a status flip plus due-queue
exclusion, not a full moderation workflow (guardrails §7).
"""

from typing import Any, Dict

from bson import ObjectId
from bson.errors import InvalidId

from app.real_interview import logger
from app.trap_drills.backend.services.trick_questions_db import get_questions_collection


def report_question(question_id: str, user_id: str) -> Dict[str, Any]:
    try:
        oid = ObjectId((question_id or "").strip())
    except (InvalidId, TypeError):
        return {"status_code": 400, "error": "invalid question_id"}

    # Only reportable if it's this user's own personalized question — never
    # lets one user affect another user's or the shared bank's content.
    result = get_questions_collection().update_one(
        {"_id": oid, "source": "ai_personalized", "origin_user_id": user_id},
        {"$set": {"review_status": "pending_review"}},
    )
    if result.matched_count == 0:
        return {"status_code": 404, "error": "question not found"}

    logger.info("[trap_drills][report_service] reported question_id=%s user_id=%s", question_id, user_id)
    return {"status_code": 200, "message": "question reported and removed from your due queue"}
