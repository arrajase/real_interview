import unittest
from datetime import datetime, timezone

from app.trap_drills.backend.services.leitner import (
    BOX_INTERVAL_DAYS,
    advance_box,
    compute_next_review_at,
    initial_box,
    next_box,
    reset_box,
)


class TestLeitner(unittest.TestCase):
    def test_new_question_enters_box_1(self):
        self.assertEqual(initial_box(), 1)

    def test_correct_answer_advances_one_box(self):
        self.assertEqual(advance_box(1), 2)
        self.assertEqual(advance_box(2), 3)
        self.assertEqual(advance_box(3), 4)
        self.assertEqual(advance_box(4), 5)

    def test_correct_answer_capped_at_box_5(self):
        self.assertEqual(advance_box(5), 5)

    def test_incorrect_answer_always_resets_to_box_1(self):
        for box in (1, 2, 3, 4, 5):
            self.assertEqual(reset_box(box), 1)

    def test_next_box_dispatches_correctly(self):
        self.assertEqual(next_box(3, was_correct=True), 4)
        self.assertEqual(next_box(3, was_correct=False), 1)

    def test_next_review_at_matches_box_interval(self):
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        for box, days in BOX_INTERVAL_DAYS.items():
            expected = now.replace(day=1)
            result = compute_next_review_at(box, now=now)
            delta = result - now
            self.assertEqual(delta.days, days, f"box {box} should be {days} days out")


if __name__ == "__main__":
    unittest.main()
