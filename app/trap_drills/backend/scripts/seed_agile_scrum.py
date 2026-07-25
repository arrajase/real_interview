"""
One-time (idempotent) seed script for the Agile/Scrum starter set (Module 9).

Run with:
    python -m app.trap_drills.backend.scripts.seed_agile_scrum

Safe to re-run: dedupes on (role, prompt) so it never inserts a duplicate.
"""

from app.real_interview import logger
from app.trap_drills.backend.seed_data.agile_scrum_seed import AGILE_SCRUM_QUESTIONS, ROLE_NAME
from app.trap_drills.backend.services.trick_questions_db import (
    get_questions_collection,
    new_question_document,
)


def seed_agile_scrum_questions() -> int:
    """Insert any seed questions not already present for this role. Returns count inserted."""
    collection = get_questions_collection()
    existing_prompts = {
        doc["prompt"]
        for doc in collection.find({"role": ROLE_NAME}, {"prompt": 1})
    }

    to_insert = []
    for item in AGILE_SCRUM_QUESTIONS:
        if item["prompt"] in existing_prompts:
            continue
        to_insert.append(
            new_question_document(
                role=ROLE_NAME,
                category=item["category"],
                prompt=item["prompt"],
                trap_answer=item["trap_answer"],
                correct_answer=item["correct_answer"],
                explanation=item["explanation"],
                source="manual",
                review_status="approved",
                origin_user_id=None,
            )
        )

    if not to_insert:
        logger.info("[trap_drills][seed_agile_scrum] nothing to insert; already seeded")
        return 0

    collection.insert_many(to_insert)
    logger.info("[trap_drills][seed_agile_scrum] inserted %s question(s)", len(to_insert))
    return len(to_insert)


if __name__ == "__main__":
    count = seed_agile_scrum_questions()
    print(f"Inserted {count} new Agile/Scrum question(s).")
