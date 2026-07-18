from flask import Blueprint, g, jsonify, request

from app.real_interview import logger
from app.real_interview.backend.auth.jwt_auth import require_auth
from app.trap_drills.backend.services.question_service import (
    get_due_questions,
    get_stats,
    submit_answer,
)
from app.trap_drills.backend.services.role_service import (
    resolve_effective_role,
    set_role_override,
)

trap_drills_api_blueprint = Blueprint("trap_drills_api", __name__, url_prefix="/api/trap-drills")


def _response(result: dict):
    code = int(result.pop("status_code", 200))
    return jsonify(result), code


@trap_drills_api_blueprint.route("/ping", methods=["GET"])
@require_auth
def ping_route():
    logger.info("[trap_drills][GET /api/trap-drills/ping] user_id=%s", g.current_user_id)
    return jsonify({"ok": True, "user_id": g.current_user_id}), 200


@trap_drills_api_blueprint.route("/role", methods=["GET"])
@require_auth
def get_role_route():
    logger.info("[trap_drills][GET /api/trap-drills/role] user_id=%s", g.current_user_id)
    return jsonify(resolve_effective_role(g.current_user_id)), 200


@trap_drills_api_blueprint.route("/role", methods=["PUT"])
@require_auth
def put_role_route():
    logger.info("[trap_drills][PUT /api/trap-drills/role] user_id=%s", g.current_user_id)
    body = request.get_json(silent=True)
    if body is None or not isinstance(body, dict):
        return jsonify({"error": "invalid JSON body"}), 400

    role = body.get("role")
    if role is not None and not isinstance(role, str):
        return jsonify({"error": "role must be a string or null"}), 400

    result = set_role_override(g.current_user_id, role.strip() if isinstance(role, str) else None)
    return _response(result)


@trap_drills_api_blueprint.route("/questions/due", methods=["GET"])
@require_auth
def get_due_questions_route():
    logger.info("[trap_drills][GET /api/trap-drills/questions/due] user_id=%s", g.current_user_id)
    effective_role = resolve_effective_role(g.current_user_id).get("effective_role")
    if not effective_role:
        return jsonify({"effective_role": None, "questions": []}), 200

    limit_raw = request.args.get("limit", "15")
    try:
        limit = int(limit_raw)
    except ValueError:
        return jsonify({"error": "limit must be an integer"}), 400

    questions = get_due_questions(g.current_user_id, effective_role, limit=limit)
    return jsonify({"effective_role": effective_role, "questions": questions}), 200


@trap_drills_api_blueprint.route("/questions/answer", methods=["POST"])
@require_auth
def submit_answer_route():
    logger.info("[trap_drills][POST /api/trap-drills/questions/answer] user_id=%s", g.current_user_id)
    body = request.get_json(silent=True)
    if body is None or not isinstance(body, dict):
        return jsonify({"error": "invalid JSON body"}), 400

    question_id = body.get("question_id")
    was_correct = body.get("was_correct")
    if not isinstance(question_id, str) or not question_id.strip():
        return jsonify({"error": "question_id is required"}), 400
    if not isinstance(was_correct, bool):
        return jsonify({"error": "was_correct must be a boolean"}), 400

    result = submit_answer(g.current_user_id, question_id.strip(), was_correct)
    return _response(result)


@trap_drills_api_blueprint.route("/stats", methods=["GET"])
@require_auth
def get_stats_route():
    logger.info("[trap_drills][GET /api/trap-drills/stats] user_id=%s", g.current_user_id)
    effective_role = resolve_effective_role(g.current_user_id).get("effective_role")
    if not effective_role:
        return jsonify({"role": None, "categories": []}), 200

    result = get_stats(g.current_user_id, effective_role)
    return _response(result)
