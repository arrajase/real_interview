from pathlib import Path

from flask import Blueprint, send_from_directory

from app.real_interview import logger

trap_drills_pages_blueprint = Blueprint("trap_drills_pages", __name__, url_prefix="/trapdrills")

_FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@trap_drills_pages_blueprint.route("/", methods=["GET"])
def serve_trap_drills_index():
    logger.info("[trap_drills] GET /trapdrills (UI index)")
    return send_from_directory(str(_FRONTEND_DIR), "index.html")


@trap_drills_pages_blueprint.route("/app.js", methods=["GET"])
def serve_trap_drills_script():
    return send_from_directory(str(_FRONTEND_DIR), "app.js")
