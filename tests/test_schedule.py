from __future__ import annotations

import random
import unittest
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from bot.schedule_logic import (
    choose_random_datetime,
    clock_span_minutes,
    day_phrase,
    effective_schedule,
    finalize_schedule,
    normalize_clock,
    prepare_due,
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


class WeekScheduleTests(unittest.TestCase):
    def test_day_phrases(self) -> None:
        self.assertEqual(day_phrase(list(range(7))), "Every day")
        self.assertEqual(day_phrase([0, 1, 2, 3, 4]), "Weekdays")
        self.assertEqual(day_phrase([5, 6]), "Weekend")
        self.assertEqual(day_phrase([0, 2, 4]), "Mon, Wed, Fri")

    def test_random_bands_do_not_overlap(self) -> None:
        now = datetime(2026, 9, 28, 7, 0, tzinfo=UTC)
        schedule = finalize_schedule(
            now,
            [0, 2, 4],
            [{"kind": "random"}, {"kind": "exact", "time": "07:15"}, {"kind": "random"}],
            random.Random(1),
        )
        self.assertEqual(schedule["slots"][0]["start"], "08:00")
        self.assertEqual(schedule["slots"][0]["end"], "12:30")
        self.assertEqual(schedule["slots"][2]["start"], "13:30")
        self.assertEqual(schedule["slots"][2]["end"], "21:00")
        self.assertEqual(schedule["slots"][1]["time"], "07:15")

    def test_exact_slot_is_not_due_on_an_unselected_day(self) -> None:
        sunday = datetime(2026, 9, 27, 8, 10, tzinfo=UTC)
        schedule = {"weekdays": [0, 1, 2, 3, 4], "slots": [{"kind": "exact", "time": "08:00"}]}
        _updated, due, changed = prepare_due(sunday, schedule, {})
        self.assertEqual(due, [])
        self.assertFalse(changed)

        monday = datetime(2026, 9, 28, 8, 10, tzinfo=UTC)
        _updated, due, _changed = prepare_due(monday, schedule, {})
        self.assertEqual([name for name, _when in due], ["s0"])

    def test_sent_random_moves_to_the_next_selected_day(self) -> None:
        monday = datetime(2026, 9, 28, 10, 0, tzinfo=UTC)
        schedule = {
            "weekdays": [0],
            "slots": [{"kind": "random", "start": "08:00", "end": "21:00", "next": "2026-09-28T09:00+00:00"}],
        }
        updated, due, changed = prepare_due(monday, schedule, {"s0": ("sent", 1)}, rng=random.Random(0))
        self.assertTrue(changed)
        self.assertEqual(due, [])
        nxt = datetime.fromisoformat(updated["slots"][0]["next"])
        self.assertEqual(nxt.weekday(), 0)
        self.assertGreater(nxt.date(), monday.date())

    def test_legacy_plan_keeps_its_slot_names(self) -> None:
        plan = SimpleNamespace(
            schedule_json=None,
            schedule_mode="twice",
            time_1="08:00",
            time_2="20:00",
            window_start=None,
            window_end=None,
            next_random_at=None,
        )
        schedule = effective_schedule(plan)
        self.assertEqual(schedule["legacy_slots"], ["time_1", "time_2"])
        self.assertEqual(schedule["weekdays"], list(range(7)))
        now = datetime(2026, 9, 29, 8, 5, tzinfo=UTC)
        _updated, due, _changed = prepare_due(now, schedule, {})
        self.assertEqual([name for name, _when in due], ["time_1"])


if __name__ == "__main__":
    unittest.main()
