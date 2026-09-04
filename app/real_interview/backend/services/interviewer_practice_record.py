import os
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from bson.errors import InvalidId
from pymongo.collection import Collection
from pymongo.errors import CollectionInvalid

from app.real_interview import logger
from app.real_interview.backend.services.interview_record import append_summary_text
from app.real_interview.backend.utils.mongodb import get_mongodb_database

_lock = threading.Lock()
_indexes_ready = False


def _get_db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "real_interview").strip()


def _get_practice_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_INTERVIEWER_PRACTICE", "interviewer_practice_sessions").strip()


def _as_object_id(value: str, field_name: str) -> ObjectId:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")
    try:
        return ObjectId(value.strip())
    except InvalidId as exc:
        raise ValueError(f"{field_name} is not a valid ObjectId") from exc


def _get_collection() -> Collection:
    global _indexes_ready
    db = get_mongodb_database(_get_db_name())
    coll_name = _get_practice_collection_name()
    if not _indexes_ready:
        with _lock:
            if not _indexes_ready:
                if coll_name not in db.list_collection_names():
                    try:
                        db.create_collection(coll_name)
                        logger.info("[interviewer_practice_record] created collection %r", coll_name)
                    except CollectionInvalid:
                        logger.warning(
                            "[interviewer_practice_record] collection %r already exists (race)", coll_name
                        )
                collection = db[coll_name]
                collection.create_index([("session_id", 1)], unique=True, name="unique_session_id")
                collection.create_index(
                    [("user_id", 1), ("interview_date", -1)],
                    name="user_interview_date",
                )
                _indexes_ready = True
    return db[coll_name]


def create_practice_session(
    *,
    session_id: str,
    user_id: str,
    resume_id: str,
    job_application_id: str,
    role_applied_for: str,
) -> Dict[str, Any]:
    logger.info("[interviewer_practice_record] create session_id=%s user_id=%s", session_id, user_id)
    user_oid = _as_object_id(user_id, "user_id")
    collection = _get_collection()
    interview_date = datetime.now(timezone.utc)
    doc = {
        "session_id": session_id,
        "user_id": user_oid,
        "resume_id": resume_id,
        "job_application_id": job_application_id or "",
        "interview_date": interview_date,
        "role_applied_for": role_applied_for or "",
        "interview_status": "active",
        "paused_at": None,
        "interview_summary": "",
        "interview_feedback": None,
        "messages": [],
        "last_summarized_message_count": 0,
    }
    result = collection.insert_one(doc)
    logger.info("[interviewer_practice_record] created practice_id=%s", result.inserted_id)
    return {
        "practice_id": str(result.inserted_id),
        "session_id": session_id,
        "interview_date": interview_date.isoformat(),
    }


def _incomplete_sessions_query(user_oid: ObjectId) -> Dict[str, Any]:
    return {
        "user_id": user_oid,
        "$nor": [
            {"interview_status": "completed"},
            {"interview_feedback": {"$exists": True, "$ne": None}},
        ],
    }


def list_incomplete_practice_session_ids_for_user(user_id: str) -> List[str]:
    user_oid = _as_object_id(user_id, "user_id")
    collection = _get_collection()
    cursor = collection.find(_incomplete_sessions_query(user_oid), {"session_id": 1})
    return [doc["session_id"] for doc in cursor if doc.get("session_id")]


def delete_incomplete_practice_sessions_for_user(user_id: str) -> tuple[int, int]:
    """Remove only active/paused practice sessions; completed sessions are retained."""
    user_oid = _as_object_id(user_id, "user_id")
    collection = _get_collection()
    retained = collection.count_documents(
        {
            "user_id": user_oid,
            "$or": [
                {"interview_status": "completed"},
                {"interview_feedback": {"$exists": True, "$ne": None}},
            ],
        }
    )
    result = collection.delete_many(_incomplete_sessions_query(user_oid))
    deleted = int(result.deleted_count)
    logger.info(
        "[interviewer_practice_record] delete_incomplete user_id=%s deleted=%s retained=%s",
        user_oid,
        deleted,
        retained,
    )
    return deleted, retained


def _serialize_session_summary(doc: Dict[str, Any]) -> Dict[str, Any]:
    interview_date = doc.get("interview_date")
    paused_at = doc.get("paused_at")
    return {
        "session_id": doc.get("session_id"),
        "resume_id": doc.get("resume_id"),
        "job_application_id": doc.get("job_application_id"),
        "role_applied_for": doc.get("role_applied_for") or "",
        "interview_status": doc.get("interview_status") or "active",
        "interview_date": interview_date.isoformat() if hasattr(interview_date, "isoformat") else interview_date,
        "paused_at": paused_at.isoformat() if hasattr(paused_at, "isoformat") else paused_at,
        "message_count": len(doc.get("messages") or []),
    }


def _completed_sessions_query(user_oid: ObjectId) -> Dict[str, Any]:
    return {
        "user_id": user_oid,
        "$or": [
            {"interview_status": "completed"},
            {"interview_feedback": {"$exists": True, "$ne": None}},
        ],
    }


def _paused_sessions_query(user_oid: ObjectId) -> Dict[str, Any]:
    return {
        "user_id": user_oid,
        "interview_status": "paused",
        "$or": [
            {"interview_feedback": None},
            {"interview_feedback": {"$exists": False}},
        ],
    }


_PRACTICE_LIST_PROJECTION = {
    "session_id": 1,
    "resume_id": 1,
    "job_application_id": 1,
    "role_applied_for": 1,
    "interview_status": 1,
    "interview_date": 1,
    "paused_at": 1,
    "messages": 1,
}


def count_practice_sessions_for_user(user_id: str) -> Dict[str, int]:
    user_oid = _as_object_id(user_id, "user_id")
    collection = _get_collection()
    return {
        "completed": collection.count_documents(_completed_sessions_query(user_oid)),
        "paused": collection.count_documents(_paused_sessions_query(user_oid)),
    }


def list_practice_sessions_for_user_by_kind(user_id: str, kind: str) -> List[Dict[str, Any]]:
    normalized = (kind or "").strip().lower()
    user_oid = _as_object_id(user_id, "user_id")
    collection = _get_collection()
    if normalized == "completed":
        query = _completed_sessions_query(user_oid)
        sort_keys = [("interview_date", -1)]
    elif normalized == "paused":
        query = _paused_sessions_query(user_oid)
        sort_keys = [("paused_at", -1), ("interview_date", -1)]
    else:
        raise ValueError("kind must be completed or paused")

    cursor = collection.find(query, _PRACTICE_LIST_PROJECTION).sort(sort_keys)
    return [_serialize_session_summary(doc) for doc in cursor if doc.get("session_id")]


def list_open_practice_sessions_for_user(user_id: str) -> List[Dict[str, Any]]:
    user_oid = _as_object_id(user_id, "user_id")
    collection = _get_collection()
    query: Dict[str, Any] = {
        "user_id": user_oid,
        "interview_status": {"$in": ["paused", "active"]},
        "$or": [
            {"interview_feedback": None},
            {"interview_feedback": {"$exists": False}},
        ],
    }
    cursor = collection.find(query, _PRACTICE_LIST_PROJECTION).sort("interview_date", -1)
    return [_serialize_session_summary(doc) for doc in cursor if doc.get("session_id")]


def get_practice_session_by_id(session_id: str) -> Optional[Dict[str, Any]]:
    logger.info("[interviewer_practice_record] get_by_session session_id=%s", session_id)
    collection = _get_collection()
    doc = collection.find_one({"session_id": session_id})
    if not doc:
        logger.warning("[interviewer_practice_record] no record for session_id=%s", session_id)
        return None
    return _serialize_doc(doc)


def append_practice_messages(session_id: str, messages: List[Dict[str, str]]) -> None:
    if not messages:
        return
    logger.info("[interviewer_practice_record] append %s message(s) session_id=%s", len(messages), session_id)
    collection = _get_collection()
    now = datetime.now(timezone.utc)
    stamped = [{"role": m.get("role", "user"), "content": m.get("content", ""), "ts": now} for m in messages]
    collection.update_one(
        {"session_id": session_id},
        {"$push": {"messages": {"$each": stamped}}},
    )


def set_practice_summary(session_id: str, summary: str) -> None:
    logger.info("[interviewer_practice_record] set summary session_id=%s chars=%s", session_id, len(summary or ""))
    collection = _get_collection()
    collection.update_one(
        {"session_id": session_id},
        {"$set": {"interview_summary": summary or ""}},
    )


def set_last_summarized_message_count(session_id: str, count: int) -> None:
    collection = _get_collection()
    collection.update_one(
        {"session_id": session_id},
        {"$set": {"last_summarized_message_count": count}},
    )


def set_practice_status(session_id: str, status: str) -> None:
    """Set interview_status to active, paused, or completed."""
    logger.info("[interviewer_practice_record] set status session_id=%s status=%s", session_id, status)
    collection = _get_collection()
    update: Dict[str, Any] = {"interview_status": status}
    if status == "paused":
        update["paused_at"] = datetime.now(timezone.utc)
    elif status == "active":
        update["paused_at"] = None
    collection.update_one({"session_id": session_id}, {"$set": update})


def save_practice_feedback(session_id: str, feedback: Dict[str, Any]) -> None:
    logger.info("[interviewer_practice_record] save feedback session_id=%s", session_id)
    collection = _get_collection()
    collection.update_one(
        {"session_id": session_id},
        {"$set": {"interview_feedback": feedback}},
    )


def _serialize_doc(doc: Dict[str, Any]) -> Dict[str, Any]:
    interview_date = doc.get("interview_date")
    paused_at = doc.get("paused_at")
    return {
        "interview_id": str(doc["_id"]),
        "session_id": doc.get("session_id"),
        "user_id": str(doc.get("user_id", "")),
        "resume_id": doc.get("resume_id"),
        "job_application_id": doc.get("job_application_id"),
        "interview_date": interview_date.isoformat() if hasattr(interview_date, "isoformat") else interview_date,
        "role_applied_for": doc.get("role_applied_for") or "",
        "interview_status": doc.get("interview_status") or "active",
        "paused_at": paused_at.isoformat() if hasattr(paused_at, "isoformat") else paused_at,
        "interview_summary": doc.get("interview_summary") or "",
        "interview_feedback": doc.get("interview_feedback"),
        "messages": [
            {
                "role": m.get("role"),
                "content": m.get("content"),
                "ts": m.get("ts").isoformat() if hasattr(m.get("ts"), "isoformat") else m.get("ts"),
            }
            for m in (doc.get("messages") or [])
        ],
        "last_summarized_message_count": int(doc.get("last_summarized_message_count") or 0),
    }
