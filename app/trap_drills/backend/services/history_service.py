"""
History (v2 §9.6, Module 8): paginated past-attempt log, filterable by role.
"""

import math
from typing import Any, Dict, Optional

from app.real_interview import logger
from app.trap_drills.backend.services.trick_questions_db import (
    get_attempts_collection,
    get_questions_collection,
)

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


def get_history(
    user_id: str,
    *,
    role: Optional[str] = None,
    page: int = 1,
    page_size: int = DEFAULT_PAGE_SIZE,
) -> Dict[str, Any]:
    page = max(1, page)
    page_size = max(1, min(MAX_PAGE_SIZE, page_size))

    query: Dict[str, Any] = {"user_id": user_id}
    if role:
        query["role"] = role

    attempts_coll = get_attempts_collection()
    total = attempts_coll.count_documents(query)
    skip = (page - 1) * page_size

    rows = list(attempts_coll.find(query).sort("answered_at", -1).skip(skip).limit(page_size))

    question_ids = [r["question_id"] for r in rows]
    questions_by_id = {}
    if question_ids:
        questions_by_id = {
            d["_id"]: d
            for d in get_questions_collection().find({"_id": {"$in": question_ids}}, {"prompt": 1})
        }

    items = []
    for r in rows:
        question_doc = questions_by_id.get(r["question_id"], {})
        answered_at = r.get("answered_at")
        items.append(
            {
                "question_id": str(r["question_id"]),
                "prompt": question_doc.get("prompt", ""),
                "role": r.get("role", ""),
                "category": r.get("category", ""),
                "was_correct": bool(r.get("was_correct")),
                "box_after": r.get("box_after"),
                "answered_at": answered_at.isoformat() if hasattr(answered_at, "isoformat") else str(answered_at),
            }
        )

    total_pages = max(1, math.ceil(total / page_size))
    logger.info(
        "[trap_drills][history_service] get_history user_id=%s role=%s page=%s total=%s",
        user_id,
        role,
        page,
        total,
    )
    return {
        "status_code": 200,
        "items": items,
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }
