"""
AI-assisted seeding orchestration — Phase 1 (v2 §7.1, Module 10).

No LLM calls anywhere on the due-question or answer-submission hot path
(guardrails §5) — this module is only ever invoked from the operator-triggered
script (scripts/generate_global_questions.py), never from a request handler
that a signed-in user's browser can reach.
"""

from typing import Any, Dict, Optional

from app.real_interview import logger
from app.trap_drills.backend.agents.trick_question_agent import TrickQuestionAgent
from app.trap_drills.backend.config.roles_config import is_valid_role
from app.trap_drills.backend.services.trick_questions_db import (
    get_questions_collection,
    new_question_document,
)


def generate_global_questions(
    role: str,
    category: str,
    count: int = 5,
    agent: Optional[TrickQuestionAgent] = None,
) -> Dict[str, Any]:
    if not is_valid_role(role):
        return {"status_code": 400, "error": "role is not a recognized role"}
    category = (category or "").strip()
    if not category:
        return {"status_code": 400, "error": "category is required"}

    agent = agent or TrickQuestionAgent()
    items = agent.generate_questions(role=role, category=category, count=count)

    docs = [
        new_question_document(
            role=role,
            category=category,
            prompt=item.prompt.strip(),
            trap_answer=item.trap_answer.strip(),
            correct_answer=item.correct_answer.strip(),
            explanation=item.explanation.strip(),
            source="ai_generated",
            review_status="pending_review",
            origin_user_id=None,
        )
        for item in items
        if item.prompt.strip() and item.trap_answer.strip() and item.correct_answer.strip()
    ]

    if not docs:
        logger.info("[trap_drills][ai_seeding] no valid questions generated role=%s category=%s", role, category)
        return {"status_code": 200, "message": "no questions generated", "inserted": 0}

    get_questions_collection().insert_many(docs)
    logger.info(
        "[trap_drills][ai_seeding] inserted %s pending_review question(s) role=%s category=%s",
        len(docs),
        role,
        category,
    )
    return {
        "status_code": 201,
        "message": f"inserted {len(docs)} pending-review question(s)",
        "inserted": len(docs),
    }
