from typing import Any, Dict

from app.real_interview import logger
from app.real_interview.backend.services.interview_record import (
    count_interviews_for_candidate,
    list_interviews_for_candidate_by_kind,
)
from app.real_interview.backend.services.interviewer_practice_record import (
    count_practice_sessions_for_user,
    list_practice_sessions_for_user_by_kind,
)
from app.real_interview.backend.services.user_interview_preferences import (
    build_interview_settings_payload,
)


def get_user_profile(*, customer_id: str, email: str) -> Dict[str, Any]:
    counts = count_interviews_for_candidate(customer_id)
    practice_counts = count_practice_sessions_for_user(customer_id)
    logger.info(
        "[user_profile] customer_id=%s completed=%s paused=%s practice_completed=%s practice_paused=%s",
        customer_id,
        counts["completed"],
        counts["paused"],
        practice_counts["completed"],
        practice_counts["paused"],
    )
    return {
        "status_code": 200,
        "email": email,
        "interview_counts": counts,
        "interviewer_practice_counts": practice_counts,
        "interview_settings": build_interview_settings_payload(customer_id),
    }


def list_profile_interviews(*, customer_id: str, kind: str) -> Dict[str, Any]:
    interviews = list_interviews_for_candidate_by_kind(customer_id, kind)
    return {
        "status_code": 200,
        "kind": kind.strip().lower(),
        "interviews": interviews,
        "count": len(interviews),
    }


def list_profile_practice_sessions(*, customer_id: str, kind: str) -> Dict[str, Any]:
    sessions = list_practice_sessions_for_user_by_kind(customer_id, kind)
    return {
        "status_code": 200,
        "kind": kind.strip().lower(),
        "interviews": sessions,
        "count": len(sessions),
    }
