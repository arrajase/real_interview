import unittest

from app.trap_drills.backend.services.dashboard_service import (
    annotate_weak_categories,
    is_weak_category,
)


class TestDashboardService(unittest.TestCase):
    def test_known_weak_category_low_accuracy(self):
        row = {
            "category": "Role Boundaries",
            "total_questions": 5,
            "attempted_count": 4,
            "mastered_count": 1,
            "accuracy_percent": 25.0,
        }
        self.assertTrue(is_weak_category(row))

    def test_known_weak_category_never_mastered(self):
        row = {
            "category": "Estimation/Velocity",
            "total_questions": 3,
            "attempted_count": 3,
            "mastered_count": 0,
            "accuracy_percent": 80.0,
        }
        self.assertTrue(is_weak_category(row))

    def test_strong_category_not_flagged(self):
        row = {
            "category": "Ceremony Ownership",
            "total_questions": 4,
            "attempted_count": 4,
            "mastered_count": 2,
            "accuracy_percent": 90.0,
        }
        self.assertFalse(is_weak_category(row))

    def test_never_attempted_category_not_flagged(self):
        row = {
            "category": "SAFe/Scaling",
            "total_questions": 6,
            "attempted_count": 0,
            "mastered_count": 0,
            "accuracy_percent": 0.0,
        }
        self.assertFalse(is_weak_category(row))

    def test_annotate_weak_categories_adds_flag_per_row(self):
        rows = [
            {"category": "Weak", "attempted_count": 2, "mastered_count": 0, "accuracy_percent": 40.0},
            {"category": "Strong", "attempted_count": 2, "mastered_count": 1, "accuracy_percent": 95.0},
        ]
        annotated = annotate_weak_categories(rows)
        self.assertTrue(annotated[0]["is_weak"])
        self.assertFalse(annotated[1]["is_weak"])
        # original rows must be untouched (pure function)
        self.assertNotIn("is_weak", rows[0])


if __name__ == "__main__":
    unittest.main()
