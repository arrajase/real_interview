from typing import Any, Dict, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.real_interview import logger
from app.real_interview.backend.graphs.interviewer_practice_graph import (
    get_practice_chat_graph,
    get_practice_feedback_graph,
    get_practice_start_graph,
    make_practice_thread_id,
)
from app.real_interview.backend.services import interviewer_practice_record as practice_db


def _config(thread_id: str) -> Dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _messages_from_record(record: Dict[str, Any]) -> List[BaseMessage]:
    out: List[BaseMessage] = []
    for m in record.get("messages") or []:
        content = m.get("content") or ""
        if m.get("role") == "user":
            out.append(HumanMessage(content=content))
        else:
            out.append(AIMessage(content=content))
    return out


def _message_to_dict(msg: BaseMessage) -> Dict[str, str]:
    role = "assistant"
    if isinstance(msg, HumanMessage):
        role = "user"
    elif isinstance(msg, AIMessage):
        role = "assistant"
    content = msg.content if isinstance(msg.content, str) else str(msg.content)
    return {"role": role, "content": content}


def _public_state(state: Dict[str, Any], record: Dict[str, Any] | None = None) -> Dict[str, Any]:
    messages = state.get("messages") or []
    if record and record.get("messages"):
        messages_out = record["messages"]
    else:
        messages_out = [_message_to_dict(m) for m in messages]

    summary = state.get("running_summary") or ""
    if record and record.get("interview_summary"):
        summary = record.get("interview_summary") or summary

    feedback = state.get("candidate_post_interview_feedback")
    if record and record.get("interview_feedback"):
        feedback = record.get("interview_feedback")

    interview_status = "active"
    if record:
        interview_status = record.get("interview_status") or "active"

    return {
        "session_id": state.get("session_id"),
        "practice_record_id": state.get("practice_record_id"),
        "customer_id": state.get("customer_id"),
        "resume_id": state.get("resume_id"),
        "job_application_id": state.get("job_application_id"),
        "target_role": state.get("target_role"),
        "running_summary": summary,
        "interview_status": interview_status,
        "question_count": int(state.get("question_count") or 0),
        "max_questions_soft_cap": state.get("max_questions_soft_cap"),
        "candidate_post_interview_feedback": feedback,
        "report_available": bool(feedback),
        "session_complete": bool(state.get("session_complete")),
        "step": state.get("step"),
        "error": state.get("error"),
        "messages": messages_out,
    }


def _get_merged_state(thread_id: str) -> Dict[str, Any]:
    graph = get_practice_start_graph()
    snapshot = graph.get_state(_config(thread_id))
    if snapshot and snapshot.values:
        return dict(snapshot.values)
    return {}


def _restore_checkpoint_if_missing(session_id: str) -> None:
    """Rebuild the LangGraph checkpoint from Mongo if it was cleared but the record survives."""
    state = _get_merged_state(session_id)
    if state.get("parsed_data"):
        return

    record = practice_db.get_practice_session_by_id(session_id)
    if not record or not (record.get("messages") or []):
        return

    try:
        from app.real_interview.backend.services.interview_context_loader import load_practice_context

        base: Dict[str, Any] = load_practice_context(
            customer_id=str(record.get("user_id") or ""),
            resume_id=record.get("resume_id") or "",
            job_application_id=record.get("job_application_id") or "",
        )
        base.update(
            {
                "session_id": session_id,
                "practice_record_id": record.get("interview_id"),
                "customer_id": str(record.get("user_id") or ""),
                "resume_id": record.get("resume_id") or "",
                "job_application_id": record.get("job_application_id") or "",
                "messages": _messages_from_record(record),
                "running_summary": record.get("interview_summary") or "",
                "last_summarized_message_count": int(record.get("last_summarized_message_count") or 0),
                "question_count": 0,
                "session_complete": bool(record.get("interview_feedback")),
            }
        )
        _patch_checkpoint(session_id, base)
        logger.info("[interviewer_practice_service] restored checkpoint from Mongo session_id=%s", session_id)
    except Exception:
        logger.exception("[interviewer_practice_service] checkpoint restore failed session_id=%s", session_id)


def _patch_checkpoint(session_id: str, values: Dict[str, Any]) -> None:
    if not values:
        return
    get_practice_start_graph().update_state(_config(session_id), values)


def _merge_summary_from_record(state: Dict[str, Any], record: Dict[str, Any]) -> Dict[str, Any]:
    db_summary = (record.get("interview_summary") or "").strip()
    running = (state.get("running_summary") or "").strip()
    if db_summary and len(db_summary) >= len(running):
        state = dict(state)
        state["running_summary"] = db_summary
    last_db = int(record.get("last_summarized_message_count") or 0)
    last_state = int(state.get("last_summarized_message_count") or 0)
    if last_db > last_state:
        state["last_summarized_message_count"] = last_db
    return state


def _force_summarize(session_id: str) -> str:
    from app.real_interview.backend.nodes.interviewer_practice_nodes import maybe_summarize_node

    record = practice_db.get_practice_session_by_id(session_id) or {}
    state = _get_merged_state(session_id)
    if not state and record:
        state = {
            "session_id": session_id,
            "messages": _messages_from_record(record),
            "running_summary": record.get("interview_summary") or "",
            "last_summarized_message_count": int(record.get("last_summarized_message_count") or 0),
        }
    elif state and not (state.get("messages") or []) and record.get("messages"):
        state = dict(state)
        state["messages"] = _messages_from_record(record)
    if state:
        state = _merge_summary_from_record(state, record)
    state["session_id"] = session_id
    state["force_summarize"] = True
    update = maybe_summarize_node(state)
    if update:
        state.update(update)
        _patch_checkpoint(session_id, update)
        _sync_summary_to_db(session_id, state)
        last_count = int(update.get("last_summarized_message_count") or 0)
        practice_db.set_last_summarized_message_count(session_id, last_count)
    record = practice_db.get_practice_session_by_id(session_id) or {}
    return (record.get("interview_summary") or state.get("running_summary") or "").strip()


def _require_active_session(record: Dict[str, Any]) -> Dict[str, Any] | None:
    status = record.get("interview_status") or "active"
    if status == "paused":
        return {
            "status_code": 409,
            "error": "Practice session is paused. Resume it to continue.",
            "interview_status": "paused",
        }
    if status == "completed" or record.get("interview_feedback"):
        return {
            "status_code": 409,
            "error": "Practice session is already completed.",
            "interview_status": "completed",
        }
    return None


def _sync_summary_to_db(session_id: str, state: Dict[str, Any]) -> str:
    summary = (state.get("running_summary") or "").strip()
    if not session_id:
        return summary
    record = practice_db.get_practice_session_by_id(session_id)
    if not record:
        return summary
    existing = (record.get("interview_summary") or "").strip()
    if summary and summary != existing:
        practice_db.set_practice_summary(session_id, summary)
        logger.info("[interviewer_practice_service] synced summary session_id=%s", session_id)
    return summary or existing


def _finalize_summary(session_id: str) -> str:
    from app.real_interview.backend.nodes.interviewer_practice_nodes import maybe_summarize_node

    state = _get_merged_state(session_id)
    if not state:
        record = practice_db.get_practice_session_by_id(session_id)
        return (record or {}).get("interview_summary") or ""
    state["session_id"] = session_id
    update = maybe_summarize_node(state)
    if update:
        state.update(update)
        _sync_summary_to_db(session_id, state)
        last_count = int(update.get("last_summarized_message_count") or 0)
        practice_db.set_last_summarized_message_count(session_id, last_count)
    record = practice_db.get_practice_session_by_id(session_id)
    return (record or {}).get("interview_summary") or state.get("running_summary") or ""


def _persist_new_messages(session_id: str, state: Dict[str, Any], record: Dict[str, Any]) -> None:
    stored = record.get("messages") or []
    stored_count = len(stored)
    all_msgs = [_message_to_dict(m) for m in (state.get("messages") or [])]
    if len(all_msgs) > stored_count:
        practice_db.append_practice_messages(session_id, all_msgs[stored_count:])
        logger.info(
            "[interviewer_practice_service] persisted %s new message(s) session_id=%s",
            len(all_msgs) - stored_count,
            session_id,
        )


def start_practice_session(
    *,
    customer_id: str,
    resume_id: str,
    job_application_id: str = "",
) -> Dict[str, Any]:
    session_id = make_practice_thread_id(customer_id, resume_id)
    logger.info("[interviewer_practice_service] start session_id=%s", session_id)

    role = ""
    try:
        from app.real_interview.backend.services.interview_context_loader import load_practice_context

        ctx = load_practice_context(
            customer_id=customer_id,
            resume_id=resume_id,
            job_application_id=job_application_id,
        )
        role = ctx.get("target_role") or ""
    except Exception as exc:
        logger.warning("[interviewer_practice_service] could not pre-load role: %s", exc)
        return {"status_code": 404, "error": str(exc), "session_id": session_id}

    record_meta = practice_db.create_practice_session(
        session_id=session_id,
        user_id=customer_id,
        resume_id=resume_id,
        job_application_id=job_application_id,
        role_applied_for=role,
    )

    initial = {
        "customer_id": customer_id,
        "resume_id": resume_id,
        "job_application_id": job_application_id or "",
        "session_id": session_id,
        "practice_record_id": record_meta["practice_id"],
        "messages": [],
        "running_summary": "",
        "last_summarized_message_count": 0,
    }
    try:
        get_practice_start_graph().invoke(initial, _config(session_id))
    except Exception as exc:
        logger.exception("[interviewer_practice_service] start graph failed session_id=%s", session_id)
        return {"status_code": 500, "error": str(exc), "session_id": session_id}

    state = _get_merged_state(session_id)
    state["session_id"] = session_id
    state["practice_record_id"] = record_meta["practice_id"]

    if state.get("error"):
        logger.warning("[interviewer_practice_service] start completed with error: %s", state.get("error"))
        return {"status_code": 400, "error": state["error"], "session_id": session_id}

    record = practice_db.get_practice_session_by_id(session_id) or {}
    _persist_new_messages(session_id, state, record)
    _sync_summary_to_db(session_id, state)

    record = practice_db.get_practice_session_by_id(session_id) or {}
    logger.info("[interviewer_practice_service] start complete session_id=%s", session_id)
    return {
        "status_code": 200,
        "session_id": session_id,
        "practice_record_id": record_meta["practice_id"],
        "state": _public_state(state, record),
        "message": "Practice session started.",
    }


def send_practice_message(*, session_id: str, message: str) -> Dict[str, Any]:
    if not message or not message.strip():
        logger.warning("[interviewer_practice_service] message rejected: empty body")
        return {"status_code": 400, "error": "message is required"}

    logger.info("[interviewer_practice_service] message session_id=%s chars=%s", session_id, len(message))
    record = practice_db.get_practice_session_by_id(session_id)
    if not record:
        logger.warning("[interviewer_practice_service] unknown session_id=%s", session_id)
        return {"status_code": 404, "error": "practice session not found", "session_id": session_id}

    _restore_checkpoint_if_missing(session_id)

    blocked = _require_active_session(record)
    if blocked:
        blocked["session_id"] = session_id
        return blocked

    practice_db.append_practice_messages(session_id, [{"role": "user", "content": message.strip()}])

    try:
        get_practice_chat_graph().invoke(
            {"messages": [HumanMessage(content=message.strip())]},
            _config(session_id),
        )
    except Exception as exc:
        logger.exception("[interviewer_practice_service] message graph failed session_id=%s", session_id)
        return {"status_code": 500, "error": str(exc), "session_id": session_id}

    state = _get_merged_state(session_id)
    state["session_id"] = session_id

    record = practice_db.get_practice_session_by_id(session_id) or {}
    _persist_new_messages(session_id, state, record)
    _sync_summary_to_db(session_id, state)
    last_count = int(state.get("last_summarized_message_count") or 0)
    practice_db.set_last_summarized_message_count(session_id, last_count)

    record = practice_db.get_practice_session_by_id(session_id) or {}
    return {
        "status_code": 200,
        "session_id": session_id,
        "state": _public_state(state, record),
    }


def pause_practice_session(*, session_id: str) -> Dict[str, Any]:
    logger.info("[interviewer_practice_service] pause session_id=%s", session_id)
    record = practice_db.get_practice_session_by_id(session_id)
    if not record:
        return {"status_code": 404, "error": "practice session not found", "session_id": session_id}

    _restore_checkpoint_if_missing(session_id)

    status = record.get("interview_status") or "active"
    if status == "paused":
        state = _get_merged_state(session_id)
        return {
            "status_code": 200,
            "session_id": session_id,
            "interview_status": "paused",
            "state": _public_state(state, record) if state else _public_state({"session_id": session_id}, record),
            "message": "Practice session is already paused.",
        }
    if status == "completed" or record.get("interview_feedback"):
        return {"status_code": 409, "error": "Practice session is already completed.", "session_id": session_id}

    try:
        summary = _force_summarize(session_id)
        practice_db.set_practice_status(session_id, "paused")
        _patch_checkpoint(session_id, {"running_summary": summary, "force_summarize": False})
    except Exception as exc:
        logger.exception("[interviewer_practice_service] pause failed session_id=%s", session_id)
        return {"status_code": 500, "error": str(exc), "session_id": session_id}

    record = practice_db.get_practice_session_by_id(session_id) or {}
    state = _get_merged_state(session_id)
    if state:
        state = _merge_summary_from_record(state, record)
    logger.info("[interviewer_practice_service] paused session_id=%s", session_id)
    return {
        "status_code": 200,
        "session_id": session_id,
        "interview_status": "paused",
        "state": _public_state(state, record) if state else _public_state({"session_id": session_id}, record),
        "message": "Practice session paused. A summary was saved for when you resume.",
    }


def resume_practice_session(*, session_id: str) -> Dict[str, Any]:
    logger.info("[interviewer_practice_service] resume session_id=%s", session_id)
    record = practice_db.get_practice_session_by_id(session_id)
    if not record:
        return {"status_code": 404, "error": "practice session not found", "session_id": session_id}

    _restore_checkpoint_if_missing(session_id)

    status = record.get("interview_status") or "active"
    if status != "paused":
        return {
            "status_code": 409,
            "error": "Practice session is not paused.",
            "session_id": session_id,
            "interview_status": status,
        }

    summary = (record.get("interview_summary") or "").strip()
    last_count = int(record.get("last_summarized_message_count") or 0)
    try:
        practice_db.set_practice_status(session_id, "active")
        _patch_checkpoint(
            session_id,
            {
                "running_summary": summary,
                "last_summarized_message_count": last_count,
                "force_summarize": False,
            },
        )
    except Exception as exc:
        logger.exception("[interviewer_practice_service] resume failed session_id=%s", session_id)
        return {"status_code": 500, "error": str(exc), "session_id": session_id}

    record = practice_db.get_practice_session_by_id(session_id) or {}
    state = _get_merged_state(session_id)
    if state:
        state = _merge_summary_from_record(state, record)
    logger.info("[interviewer_practice_service] resumed session_id=%s", session_id)
    return {
        "status_code": 200,
        "session_id": session_id,
        "interview_status": "active",
        "state": _public_state(state, record) if state else _public_state({"session_id": session_id}, record),
        "message": "Practice session resumed.",
    }


def complete_practice_session(*, session_id: str) -> Dict[str, Any]:
    logger.info("[interviewer_practice_service] complete session_id=%s", session_id)
    record = practice_db.get_practice_session_by_id(session_id)
    if not record:
        return {"status_code": 404, "error": "practice session not found", "session_id": session_id}

    _restore_checkpoint_if_missing(session_id)

    if (record.get("interview_status") or "active") == "paused":
        return {
            "status_code": 409,
            "error": "Practice session is paused. Resume before ending.",
            "session_id": session_id,
        }

    try:
        summary = _finalize_summary(session_id)
        get_practice_feedback_graph().invoke(
            {"running_summary": summary},
            _config(session_id),
        )
    except Exception as exc:
        logger.exception("[interviewer_practice_service] complete failed session_id=%s", session_id)
        return {"status_code": 500, "error": str(exc), "session_id": session_id}

    state = _get_merged_state(session_id)
    feedback = state.get("candidate_post_interview_feedback") or {}
    if feedback:
        practice_db.save_practice_feedback(session_id, feedback)
        practice_db.set_practice_status(session_id, "completed")
        logger.info(
            "[interviewer_practice_service] feedback saved decision=%s",
            feedback.get("interview_decision"),
        )

    record = practice_db.get_practice_session_by_id(session_id) or {}
    return {
        "status_code": 200,
        "session_id": session_id,
        "state": _public_state(state, record),
        "message": "Practice session complete. Your report is ready to download.",
        "report_available": bool(feedback),
    }


def get_practice_report(*, session_id: str, customer_id: str) -> Dict[str, Any]:
    """Return the structured report payload for a completed practice session."""
    from app.real_interview.backend.services.interview_report_service import build_report_payload

    record = practice_db.get_practice_session_by_id(session_id)
    if not record:
        return {"status_code": 404, "error": "practice session not found", "session_id": session_id}
    if str(record.get("user_id", "")) != str(customer_id):
        return {"status_code": 403, "error": "access denied", "session_id": session_id}
    if not record.get("interview_feedback"):
        return {
            "status_code": 404,
            "error": "report is available after the practice session is completed",
            "session_id": session_id,
        }

    payload = build_report_payload(record)
    return {"status_code": 200, "session_id": session_id, "report": payload}


def build_practice_report_pdf(*, session_id: str, customer_id: str) -> tuple[int, Dict[str, Any], bytes | None]:
    """Build PDF bytes for a completed practice session report."""
    from app.real_interview.backend.services.interview_report_service import (
        build_report_pdf,
        report_download_filename,
    )

    result = get_practice_report(session_id=session_id, customer_id=customer_id)
    code = int(result.get("status_code", 200))
    if code != 200:
        return code, result, None
    payload = result["report"]
    return 200, {"filename": report_download_filename(payload), "session_id": session_id}, build_report_pdf(payload)


def list_user_practice_sessions(*, customer_id: str) -> Dict[str, Any]:
    """List paused or in-progress practice sessions for the signed-in user."""
    sessions = practice_db.list_open_practice_sessions_for_user(customer_id)
    logger.info(
        "[interviewer_practice_service] list_sessions customer_id=%s count=%s",
        customer_id,
        len(sessions),
    )
    return {"status_code": 200, "interviews": sessions, "count": len(sessions)}


def get_practice_session_state(*, session_id: str) -> Dict[str, Any]:
    logger.info("[interviewer_practice_service] get_state session_id=%s", session_id)
    record = practice_db.get_practice_session_by_id(session_id)
    if record:
        _restore_checkpoint_if_missing(session_id)
    state = _get_merged_state(session_id)
    if not record and not state:
        return {"status_code": 404, "error": "practice session not found", "session_id": session_id}
    if state:
        state["session_id"] = session_id
    return {
        "status_code": 200,
        "session_id": session_id,
        "record": record,
        "state": _public_state(state, record) if state else None,
    }
