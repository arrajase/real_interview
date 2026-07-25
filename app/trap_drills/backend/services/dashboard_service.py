"""
Category Dashboard support (v2 §9.4, Module 6): flags the weakest categories
within a role so the UI can visually highlight them.

Pure function, no DB access — takes the category rows already produced by
question_service.get_stats() and annotates them, so the "weak" rule has one
definition, shared by the API response and this module's unit test.
"""

from typing import Any, Dict, List

MIN_ACCURACY_PERCENT = 60.0


def is_weak_category(category_row: Dict[str, Any]) -> bool:
    """
    A category is "weak" once the user has actually attempted it and either:
      - accuracy is below MIN_ACCURACY_PERCENT, or
      - nothing has reached box 5 (mastered_count == 0) despite attempts.

    Categories never attempted, or with no questions in the bank yet, are not
    flagged — there is nothing to judge weak or strong about them yet.
    """
    attempted = category_row.get("attempted_count", 0)
    if attempted <= 0:
        return False
    accuracy = category_row.get("accuracy_percent", 0.0)
    mastered = category_row.get("mastered_count", 0)
    return accuracy < MIN_ACCURACY_PERCENT or mastered == 0


def annotate_weak_categories(categories: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [dict(row, is_weak=is_weak_category(row)) for row in categories]
