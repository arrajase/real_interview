from typing import Any, Dict

from langchain_core.messages import AIMessage

from app.real_interview import logger
from app.real_interview.backend.agents.candidate_avatar_agent import CandidateAvatarAgent
from app.real_interview.backend.agents.feedback_agent import FeedbackAgent
from app.real_interview.backend.config.configuration import get_interviewer_practice_limits_config
from app.real_interview.backend.services.interview_context_loader import load_practice_context
from app.real_interview.backend.state.interviewer_practice_state import InterviewerPracticeState

# Reused unmodified — role-agnostic, only touch generic messages/running_summary/error keys.
from app.real_interview.backend.nodes.interview_nodes import (  # noqa: F401
    maybe_summarize_node,
    route_after_start,
    should_summarize,
)


def load_practice_context_node(state: InterviewerPracticeState) -> Dict[str, Any]:
    logger.info("[interviewer_practice_nodes] load_practice_context customer_id=%s", state.get("customer_id"))
    try:
        ctx = load_practice_context(
            customer_id=state["customer_id"],
            resume_id=state["resume_id"],
            job_application_id=state.get("job_application_id") or "",
        )
        soft_cap = int(get_interviewer_practice_limits_config().get("max_questions_soft_cap", 12))
        return {
            **ctx,
            "step": "loaded",
            "running_summary": state.get("running_summary") or "",
            "summary_snapshots": state.get("summary_snapshots") or [],
            "last_summarized_message_count": int(state.get("last_summarized_message_count") or 0),
            "question_count": 0,
            "max_questions_soft_cap": soft_cap,
            "session_complete": False,
        }
    except Exception as exc:
        logger.exception("[interviewer_practice_nodes] load_practice_context failed")
        return {"error": str(exc), "step": "failed"}


def avatar_opening_node(state: InterviewerPracticeState) -> Dict[str, Any]:
    logger.info("[interviewer_practice_nodes] avatar_opening")
    if state.get("error"):
        return {}
    role = (state.get("target_role") or "").strip()
    greeting = (
        f"Hi, thanks for taking the time to interview me for the {role} role. "
        "I'm ready whenever you'd like to start."
        if role
        else "Hi, thanks for taking the time to interview me. I'm ready whenever you'd like to start."
    )
    return {
        "messages": [AIMessage(content=greeting)],
        "session_complete": False,
        "step": "opened",
    }


def avatar_turn_node(state: InterviewerPracticeState) -> Dict[str, Any]:
    logger.info("[interviewer_practice_nodes] avatar_turn")
    if state.get("error"):
        return {}
    agent = CandidateAvatarAgent()
    reply = agent.answer_as_candidate(
        parsed_data=state.get("parsed_data") or {},
        job_role=state.get("target_role") or "",
        job_description=state.get("job_description") or "",
        messages=list(state.get("messages") or []),
    )
    return {
        "messages": [reply],
        "question_count": int(state.get("question_count") or 0) + 1,
        "step": "practice_turn",
    }


def feedback_node(state: InterviewerPracticeState) -> Dict[str, Any]:
    logger.info("[interviewer_practice_nodes] feedback")
    if state.get("error"):
        return {}
    agent = FeedbackAgent()
    feedback = agent.generate_feedback(
        interview_summary=state.get("running_summary") or "",
        role_applied_for=state.get("target_role") or "",
        messages=list(state.get("messages") or []),
    )
    return {
        "candidate_post_interview_feedback": feedback,
        "session_complete": True,
        "step": "complete",
    }
