"""
Pure Leitner-box spaced-repetition logic (v2 §4). No DB access here —
keeps this independently unit-testable per Module 2's acceptance criteria.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

MIN_BOX = 1
MAX_BOX = 5

BOX_INTERVAL_DAYS = {
    1: 1,
    2: 3,
    3: 7,
    4: 14,
    5: 30,
}


def initial_box() -> int:
    """A question enters Box 1 on its first attempt (v2 §4)."""
    return MIN_BOX


def advance_box(box: int) -> int:
    """Correct answer: move up one box, capped at MAX_BOX."""
    return min(MAX_BOX, box + 1)


def reset_box(_box: int) -> int:
    """Incorrect answer: drop straight back to Box 1, regardless of prior box."""
    return MIN_BOX


def next_box(current_box: int, was_correct: bool) -> int:
    return advance_box(current_box) if was_correct else reset_box(current_box)


def compute_next_review_at(box: int, now: Optional[datetime] = None) -> datetime:
    reference = now or datetime.now(timezone.utc)
    days = BOX_INTERVAL_DAYS.get(box, BOX_INTERVAL_DAYS[MIN_BOX])
    return reference + timedelta(days=days)
