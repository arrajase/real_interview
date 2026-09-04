from typing import Any, Dict, Tuple

import io

from flask import Blueprint, g, jsonify, request, send_file

from app.real_interview import logger
from app.real_interview.backend.auth.jwt_auth import interviewer_practice_session_owned_by, require_auth
from app.real_interview.backend.services.interviewer_practice_service import (
    build_practice_report_pdf,
    complete_practice_session,
    get_practice_report,
    get_practice_session_state,
    list_user_practice_sessions,
    pause_practice_session,
    resume_practice_session,
    send_practice_message,
    start_practice_session,
)
from app.real_interview.backend.services.job_application import get_job_application_for_customer
from app.real_interview.backend.services.pdfreader import resume_reader

interviewer_practice_blueprint = Blueprint("interviewer_practice", __name__, url_prefix="/api")


def _parse_json_body() -> Dict[str, Any] | None:
    data = request.get_json(silent=True)
    if data is None or not isinstance(data, dict):
        return None
    return data


def _response(result: Dict[str, Any]):
    code = int(result.pop("status_code", 200))
    return jsonify(result), code


def _forbidden(message: str = "access denied"):
    return jsonify({"error": message}), 403


def _verify_practice_session(session_id: str) -> Tuple[bool, Any]:
    if not interviewer_practice_session_owned_by(session_id, g.current_user_id):
        return False, _forbidden("practice session not found or access denied")
    return True, None


def _verify_start_resources(resume_id: str, job_application_id: str) -> Tuple[bool, Any]:
    reader: resume_reader | None = None
    try:
        reader = resume_reader()
        reader.get_resume_for_user(g.current_user_id, resume_id)
        if job_application_id:
            get_job_application_for_customer(g.current_user_id, job_application_id)
        return True, None
    except ValueError as exc:
        logger.warning("[interviewer_practice] start resource check failed: %s", exc)
        return False, (jsonify({"error": str(exc)}), 404)
    finally:
        if reader is not None:
            reader.close()


@interviewer_practice_blueprint.route("/interviewer-practice/start", methods=["POST"])
@require_auth
def interviewer_practice_start_route():
    logger.info("[interviewer_practice][POST /api/interviewer-practice/start]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    resume_id = body.get("resume_id")
    job_application_id = body.get("job_application_id") or ""

    if not isinstance(resume_id, str) or not resume_id.strip():
        return jsonify({"error": "resume_id is required"}), 400
    if job_application_id and not isinstance(job_application_id, str):
        return jsonify({"error": "job_application_id must be a string"}), 400

    ok, err = _verify_start_resources(resume_id.strip(), job_application_id.strip() if job_application_id else "")
    if not ok:
        return err

    result = start_practice_session(
        customer_id=g.current_user_id,
        resume_id=resume_id.strip(),
        job_application_id=job_application_id.strip() if job_application_id else "",
    )
    return _response(result)


@interviewer_practice_blueprint.route("/interviewer-practice/message", methods=["POST"])
@require_auth
def interviewer_practice_message_route():
    logger.info("[interviewer_practice][POST /api/interviewer-practice/message]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id")
    message = body.get("message")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400
    if not isinstance(message, str) or not message.strip():
        return jsonify({"error": "message is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_practice_session(session_id)
    if not ok:
        return err

    result = send_practice_message(session_id=session_id, message=message)
    return _response(result)


@interviewer_practice_blueprint.route("/interviewer-practice/pause", methods=["POST"])
@require_auth
def interviewer_practice_pause_route():
    logger.info("[interviewer_practice][POST /api/interviewer-practice/pause]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_practice_session(session_id)
    if not ok:
        return err

    result = pause_practice_session(session_id=session_id)
    return _response(result)


@interviewer_practice_blueprint.route("/interviewer-practice/resume", methods=["POST"])
@require_auth
def interviewer_practice_resume_route():
    logger.info("[interviewer_practice][POST /api/interviewer-practice/resume]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_practice_session(session_id)
    if not ok:
        return err

    result = resume_practice_session(session_id=session_id)
    return _response(result)


@interviewer_practice_blueprint.route("/interviewer-practice/complete", methods=["POST"])
@require_auth
def interviewer_practice_complete_route():
    logger.info("[interviewer_practice][POST /api/interviewer-practice/complete]")
    body = _parse_json_body()
    if body is None:
        return jsonify({"error": "invalid JSON body"}), 400

    session_id = body.get("session_id")
    if not isinstance(session_id, str) or not session_id.strip():
        return jsonify({"error": "session_id is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_practice_session(session_id)
    if not ok:
        return err

    result = complete_practice_session(session_id=session_id)
    return _response(result)


@interviewer_practice_blueprint.route("/interviewer-practice/report", methods=["GET"])
@require_auth
def interviewer_practice_report_route():
    session_id = request.args.get("session_id")
    if not session_id or not session_id.strip():
        return jsonify({"error": "session_id query parameter is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_practice_session(session_id)
    if not ok:
        return err

    logger.info("[interviewer_practice][GET /api/interviewer-practice/report] session_id=%s", session_id)
    result = get_practice_report(session_id=session_id, customer_id=g.current_user_id)
    return _response(result)


@interviewer_practice_blueprint.route("/interviewer-practice/report/download", methods=["GET"])
@require_auth
def interviewer_practice_report_download_route():
    session_id = request.args.get("session_id")
    if not session_id or not session_id.strip():
        return jsonify({"error": "session_id query parameter is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_practice_session(session_id)
    if not ok:
        return err

    logger.info(
        "[interviewer_practice][GET /api/interviewer-practice/report/download] session_id=%s", session_id
    )
    status_code, meta, pdf_bytes = build_practice_report_pdf(
        session_id=session_id,
        customer_id=g.current_user_id,
    )
    if status_code != 200 or pdf_bytes is None:
        return jsonify(meta), status_code

    filename = meta.get("filename") or "interviewer-practice-report.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        as_attachment=True,
        download_name=filename,
        mimetype="application/pdf",
    )


@interviewer_practice_blueprint.route("/interviewer-practice/sessions", methods=["GET"])
@require_auth
def interviewer_practice_sessions_route():
    logger.info("[interviewer_practice][GET /api/interviewer-practice/sessions] user_id=%s", g.current_user_id)
    result = list_user_practice_sessions(customer_id=g.current_user_id)
    return _response(result)


@interviewer_practice_blueprint.route("/interviewer-practice/state", methods=["GET"])
@require_auth
def interviewer_practice_state_route():
    session_id = request.args.get("session_id")
    if not session_id or not session_id.strip():
        return jsonify({"error": "session_id query parameter is required"}), 400

    session_id = session_id.strip()
    ok, err = _verify_practice_session(session_id)
    if not ok:
        return err

    logger.info("[interviewer_practice][GET /api/interviewer-practice/state] session_id=%s", session_id)
    result = get_practice_session_state(session_id=session_id)
    return _response(result)
