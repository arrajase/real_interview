import os
from typing import Any, Dict, Optional

from app.real_interview import logger
from app.real_interview.backend.auth.email_utils import find_user_by_id
from app.real_interview.backend.utils.mongodb import get_mongodb_database
from app.trap_drills.backend.config.roles_config import (
    ROLE_NAMES,
    detect_role_from_text,
    is_valid_role,
)

ROLE_OVERRIDE_FIELD = "trap_drills_role_override"


def _get_db_name() -> str:
    return os.getenv("MONGODB_DB_NAME", "real_interview").strip()


def _get_users_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_USERS", "authentications").strip()


def _get_job_application_collection_name() -> str:
    return os.getenv("MONGODB_COLLECTION_JOB_APPLICATIONS", "job_application").strip()


def _users_collection():
    return get_mongodb_database(_get_db_name())[_get_users_collection_name()]


def _job_application_collection():
    return get_mongodb_database(_get_db_name())[_get_job_application_collection_name()]


def get_latest_job_role_text(user_id: str) -> str:
    """Most recent job_application.job_role for this user, or '' if none exists."""
    from bson import ObjectId
    from bson.errors import InvalidId

    try:
        customer_oid = ObjectId((user_id or "").strip())
    except InvalidId:
        return ""

    doc = (
        _job_application_collection()
        .find({"customer_id": customer_oid}, {"job_role": 1})
        .sort("job_application_ts", -1)
        .limit(1)
    )
    for item in doc:
        return (item.get("job_role") or "").strip()
    return ""


def get_detected_role(user_id: str) -> Optional[str]:
    job_role_text = get_latest_job_role_text(user_id)
    if not job_role_text:
        return None
    return detect_role_from_text(job_role_text)


def get_role_override(user_id: str) -> Optional[str]:
    doc = find_user_by_id(_users_collection(), user_id)
    if not doc:
        return None
    override = doc.get(ROLE_OVERRIDE_FIELD)
    if not override or not isinstance(override, str):
        return None
    return override


def resolve_effective_role(user_id: str) -> Dict[str, Any]:
    """Effective role resolution order: override, else detected, else None (v2 §5.2)."""
    detected = get_detected_role(user_id)
    override = get_role_override(user_id)
    effective = override if override else detected
    return {
        "detected_role": detected,
        "role_override": override,
        "effective_role": effective,
        "roles": ROLE_NAMES,
    }


def set_role_override(user_id: str, role: Optional[str]) -> Dict[str, Any]:
    """Set or clear the user's role override. role=None clears it (use auto-detection)."""
    collection = _users_collection()
    doc = find_user_by_id(collection, user_id)
    if not doc:
        return {"status_code": 404, "error": "user not found"}

    if role is None:
        collection.update_one({"_id": doc["_id"]}, {"$unset": {ROLE_OVERRIDE_FIELD: ""}})
        logger.info("[trap_drills][role_service] cleared role override user_id=%s", user_id)
        return {"status_code": 200, "message": "role override cleared", **resolve_effective_role(user_id)}

    if not is_valid_role(role):
        return {"status_code": 400, "error": f"role must be one of {ROLE_NAMES}"}

    collection.update_one({"_id": doc["_id"]}, {"$set": {ROLE_OVERRIDE_FIELD: role}})
    logger.info("[trap_drills][role_service] set role override=%s user_id=%s", role, user_id)
    return {"status_code": 200, "message": "role override saved", **resolve_effective_role(user_id)}
