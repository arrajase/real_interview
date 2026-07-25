from flask import Blueprint, g, jsonify, request

from app.real_interview import logger
from app.real_interview.backend.auth.jwt_auth import require_auth
from app.trap_drills.backend.services.dashboard_service import annotate_weak_categories
from app.trap_drills.backend.services.history_service import get_history
from app.trap_drills.backend.services.question_management_service import (
    create_question,
    list_pending_review,
    list_questions,
    review_question,
    soft_delete_question,
    update_question,
)
from app.trap_drills.backend.services.personalization_service import (
    maybe_generate_personalized_questions,
)
from app.trap_drills.backend.services.question_service import (
    get_due_questions,
    get_stats,
    submit_answer,
)
from app.trap_drills.backend.services.role_service import (
    resolve_effective_role,
    set_role_override,
)
from app.trap_drills.backend.services.report_service import report_question

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
    result = resolve_effective_role(g.current_user_id)
    # Lazy Phase 2 trigger (v2 §7.2): deliberately here, not on the due-queue
    # or answer-submission routes, so no LLM call ever sits on that hot path
    # (guardrails §5). GET /role is called exactly once per Trap Drills
    # "open" in the frontend's boot sequence, before the due queue loads.
    maybe_generate_personalized_questions(g.current_user_id, result.get("effective_role"))
    return jsonify(result), 200


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
    if "categories" in result:
        result["categories"] = annotate_weak_categories(result["categories"])
    return _response(result)


# ---- Question management (Module 7) — open to any signed-in user (v2 §12
# default; see question_management_service module docstring). ----

_QUESTION_FIELDS = ("role", "category", "prompt", "trap_answer", "correct_answer", "explanation")


@trap_drills_api_blueprint.route("/questions", methods=["GET"])
@require_auth
def list_questions_route():
    role = request.args.get("role") or None
    logger.info("[trap_drills][GET /api/trap-drills/questions] user_id=%s role=%s", g.current_user_id, role)
    result = list_questions(role=role)
    return _response(result)


@trap_drills_api_blueprint.route("/questions", methods=["POST"])
@require_auth
def create_question_route():
    logger.info("[trap_drills][POST /api/trap-drills/questions] user_id=%s", g.current_user_id)
    body = request.get_json(silent=True)
    if body is None or not isinstance(body, dict):
        return jsonify({"error": "invalid JSON body"}), 400

    result = create_question(**{field: body.get(field) for field in _QUESTION_FIELDS})
    return _response(result)


@trap_drills_api_blueprint.route("/questions/<question_id>", methods=["PUT"])
@require_auth
def update_question_route(question_id: str):
    logger.info("[trap_drills][PUT /api/trap-drills/questions/%s] user_id=%s", question_id, g.current_user_id)
    body = request.get_json(silent=True)
    if body is None or not isinstance(body, dict):
        return jsonify({"error": "invalid JSON body"}), 400

    fields = {field: body[field] for field in _QUESTION_FIELDS if field in body}
    result = update_question(question_id, g.current_user_id, fields)
    return _response(result)


@trap_drills_api_blueprint.route("/questions/<question_id>", methods=["DELETE"])
@require_auth
def delete_question_route(question_id: str):
    logger.info("[trap_drills][DELETE /api/trap-drills/questions/%s] user_id=%s", question_id, g.current_user_id)
    result = soft_delete_question(question_id, g.current_user_id)
    return _response(result)


@trap_drills_api_blueprint.route("/questions/pending-review", methods=["GET"])
@require_auth
def list_pending_review_route():
    logger.info("[trap_drills][GET /api/trap-drills/questions/pending-review] user_id=%s", g.current_user_id)
    result = list_pending_review()
    return _response(result)


@trap_drills_api_blueprint.route("/questions/<question_id>/review", methods=["POST"])
@require_auth
def review_question_route(question_id: str):
    logger.info("[trap_drills][POST /api/trap-drills/questions/%s/review] user_id=%s", question_id, g.current_user_id)
    body = request.get_json(silent=True)
    if body is None or not isinstance(body, dict):
        return jsonify({"error": "invalid JSON body"}), 400

    decision = body.get("decision")
    if not isinstance(decision, str):
        return jsonify({"error": "decision is required"}), 400

    result = review_question(question_id, decision.strip().lower())
    return _response(result)


@trap_drills_api_blueprint.route("/history", methods=["GET"])
@require_auth
def get_history_route():
    logger.info("[trap_drills][GET /api/trap-drills/history] user_id=%s", g.current_user_id)
    role = request.args.get("role") or None
    try:
        page = int(request.args.get("page", "1"))
        page_size = int(request.args.get("page_size", "20"))
    except ValueError:
        return jsonify({"error": "page and page_size must be integers"}), 400

    result = get_history(g.current_user_id, role=role, page=page, page_size=page_size)
    return _response(result)


@trap_drills_api_blueprint.route("/questions/<question_id>/report", methods=["POST"])
@require_auth
def report_question_route(question_id: str):
    logger.info("[trap_drills][POST /api/trap-drills/questions/%s/report] user_id=%s", question_id, g.current_user_id)
    result = report_question(question_id, g.current_user_id)
    return _response(result)
