from __future__ import annotations

import random
import unittest
from datetime import datetime
from zoneinfo import ZoneInfo

from bot.schedule_logic import (
    choose_random_datetime,
    clock_span_minutes,
    normalize_clock,
    roll_forward_random,
    slot_needs_send,
)

UTC = ZoneInfo("UTC")


class ClockTests(unittest.TestCase):
    def test_normalizes_common_forms(self) -> None:
        self.assertEqual(normalize_clock("8:05"), "08:05")
        self.assertEqual(normalize_clock("08.30"), "08:30")
        self.assertEqual(normalize_clock("23:59"), "23:59")

    def test_rejects_impossible_times(self) -> None:
        self.assertIsNone(normalize_clock("24:00"))
        self.assertIsNone(normalize_clock("8:60"))
        self.assertIsNone(normalize_clock("morning"))

    def test_window_span(self) -> None:
        self.assertEqual(clock_span_minutes("09:00", "09:30"), 30)
        self.assertLess(clock_span_minutes("18:00", "09:00"), 0)


class DueTests(unittest.TestCase):
    def test_exact_time_inside_grace(self) -> None:
        scheduled = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)
        now = datetime(2026, 9, 29, 8, 10, tzinfo=UTC)
        self.assertTrue(
            slot_needs_send(now, scheduled, sent=False, attempts=0, grace_minutes=20, retry_minutes=120)
        )

    def test_missed_slot_is_not_started_late(self) -> None:
        scheduled = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)
        now = datetime(2026, 9, 29, 8, 30, tzinfo=UTC)
        self.assertFalse(
            slot_needs_send(now, scheduled, sent=False, attempts=0, grace_minutes=20, retry_minutes=120)
        )

    def test_failed_attempt_retries_inside_two_hours(self) -> None:
        scheduled = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)
        now = datetime(2026, 9, 29, 9, 0, tzinfo=UTC)
        self.assertTrue(
            slot_needs_send(now, scheduled, sent=False, attempts=1, grace_minutes=20, retry_minutes=120)
        )
        later = datetime(2026, 9, 29, 11, 0, tzinfo=UTC)
        self.assertFalse(
            slot_needs_send(later, scheduled, sent=False, attempts=1, grace_minutes=20, retry_minutes=120)
        )

    def test_sent_slot_is_finished(self) -> None:
        scheduled = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)
        now = datetime(2026, 9, 29, 8, 5, tzinfo=UTC)
        self.assertFalse(
            slot_needs_send(now, scheduled, sent=True, attempts=1, grace_minutes=20, retry_minutes=120)
        )


class RandomScheduleTests(unittest.TestCase):
    def test_picks_inside_the_remaining_window(self) -> None:
        now = datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
        picked = choose_random_datetime(now, "09:00", "12:00", random.Random(1))
        self.assertEqual(picked.date(), now.date())
        self.assertGreater(picked, now)
        minutes = picked.hour * 60 + picked.minute
        self.assertLessEqual(minutes, 12 * 60)

    def test_moves_to_tomorrow_after_the_window(self) -> None:
        now = datetime(2026, 9, 29, 18, 30, tzinfo=UTC)
        picked = choose_random_datetime(now, "09:00", "12:00", random.Random(2))
        self.assertEqual(picked.date().isoformat(), "2026-09-30")
        minutes = picked.hour * 60 + picked.minute
        self.assertGreaterEqual(minutes, 9 * 60)
        self.assertLessEqual(minutes, 12 * 60)

    def test_roll_forward_keeps_a_future_time(self) -> None:
        now = datetime(2026, 9, 29, 8, 0, tzinfo=UTC)
        upcoming = datetime(2026, 9, 29, 15, 0, tzinfo=UTC)
        self.assertIsNone(
            roll_forward_random(now, upcoming, "09:00", "18:00", False, random.Random(1), 120)
        )

    def test_roll_forward_skips_a_long_miss(self) -> None:
        now = datetime(2026, 9, 29, 18, 0, tzinfo=UTC)
        missed = datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
        picked = roll_forward_random(now, missed, "09:00", "18:00", False, random.Random(1), 120)
        self.assertIsNotNone(picked)
        assert picked is not None
        self.assertEqual(picked.date().isoformat(), "2026-09-30")


if __name__ == "__main__":
    unittest.main()
