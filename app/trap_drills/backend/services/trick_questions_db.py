"""
Mongo collection access for Interview Trap Drills (v2 §6).

Three collections, all in the same database/cluster real_interview already
uses (reused via get_mongodb_database — see
trap-drills-implementation-guardrails.md §2, never a new database).
"""

import os
import threading
from typing import Any, Dict, Optional

from pymongo.collection import Collection
from pymongo.errors import CollectionInvalid

from app.real_interview import logger
from app.real_interview.backend.utils.mongodb import get_mongodb_database

_lock = threading.Lock()
_indexes_ready = False


def _get_db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "real_interview").strip()


def _questions_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_TRICK_QUESTIONS", "trick_questions").strip()


def _progress_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_TRICK_QUESTION_PROGRESS", "trick_question_progress").strip()


def _attempts_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_TRICK_QUESTION_ATTEMPTS", "trick_question_attempts").strip()


def _create_collection_if_missing(db, name: str) -> None:
    if name in db.list_collection_names():
        return
    try:
        db.create_collection(name)
        logger.info("[trap_drills][trick_questions_db] created collection %r", name)
    except CollectionInvalid:
        logger.warning("[trap_drills][trick_questions_db] collection %r already exists (race)", name)


def _ensure_indexes() -> None:
    global _indexes_ready
    if _indexes_ready:
        return
    with _lock:
        if _indexes_ready:
            return

        db = get_mongodb_database(_get_db_name())

        questions_name = _questions_collection_name()
        progress_name = _progress_collection_name()
        attempts_name = _attempts_collection_name()

        _create_collection_if_missing(db, questions_name)
        _create_collection_if_missing(db, progress_name)
        _create_collection_if_missing(db, attempts_name)

        questions = db[questions_name]
        questions.create_index([("role", 1), ("category", 1)], name="role_category")
        questions.create_index(
            [("origin_user_id", 1), ("role", 1), ("review_status", 1)],
            name="origin_user_role_review_status",
        )

        progress = db[progress_name]
        progress.create_index([("user_id", 1), ("question_id", 1)], unique=True, name="unique_user_question")
        progress.create_index([("user_id", 1), ("next_review_at", 1)], name="user_next_review")

        attempts = db[attempts_name]
        attempts.create_index([("user_id", 1), ("answered_at", -1)], name="user_answered_at")

        logger.info("[trap_drills][trick_questions_db] indexes ensured")
        _indexes_ready = True


def get_questions_collection() -> Collection:
    _ensure_indexes()
    return get_mongodb_database(_get_db_name())[_questions_collection_name()]


def get_progress_collection() -> Collection:
    _ensure_indexes()
    return get_mongodb_database(_get_db_name())[_progress_collection_name()]


def get_attempts_collection() -> Collection:
    _ensure_indexes()
    return get_mongodb_database(_get_db_name())[_attempts_collection_name()]


def new_question_document(
    *,
    role: str,
    category: str,
    prompt: str,
    trap_answer: str,
    correct_answer: str,
    explanation: str,
    source: str = "manual",
    review_status: str = "approved",
    origin_user_id: Optional[str] = None,
    source_session_id: Optional[Any] = None,
) -> Dict[str, Any]:
    from datetime import datetime, timezone

    return {
        "role": role,
        "category": category,
        "prompt": prompt,
        "trap_answer": trap_answer,
        "correct_answer": correct_answer,
        "explanation": explanation,
        "created_at": datetime.now(timezone.utc),
        "active": True,
        "source": source,
        "review_status": review_status,
        "origin_user_id": origin_user_id,
        "source_session_id": source_session_id,
    }
