from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bot.db import Database
from bot.timezones import resolve_timezone


class TimezoneTests(unittest.TestCase):
    def test_known_names(self) -> None:
        self.assertEqual(resolve_timezone("Europe/Berlin"), "Europe/Berlin")
        self.assertEqual(resolve_timezone("tehran"), "Asia/Tehran")
        self.assertEqual(resolve_timezone("Berlin"), "Europe/Berlin")

    def test_unknown_name(self) -> None:
        self.assertIsNone(resolve_timezone("Not/AZone"))
        self.assertIsNone(resolve_timezone(""))


class DatabaseTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.db = Database(Path(self._tmp.name) / "wortuhr.db")
        self.db.init()

    def tearDown(self) -> None:
        self.db.close()
        self._tmp.cleanup()

    def test_plans_items_and_progress(self) -> None:
        user = self.db.upsert_user(10, "Ada")
        self.assertEqual(user.ready, 0)
        self.assertEqual(self.db.list_active_plans(), [])
        self.db.set_timezone(10, "Europe/Berlin")
        self.db.set_translation_language(10, "English")
        self.db.set_ready(10)

        plan = self.db.create_plan(
            user_id=10,
            language="German",
            level="A2",
            content_type="word",
            topic="Work and jobs",
            schedule_mode="twice",
            time_1="08:00",
            time_2="20:00",
            window_start=None,
            window_end=None,
            next_random_at=None,
        )
        self.assertEqual(len(self.db.list_active_plans()), 1)
        self.assertEqual(plan.time_2, "20:00")

        item = self.db.add_item(
            user_id=10,
            plan_id=plan.id,
            content_type="word",
            language="German",
            level="A2",
            topic="Work and jobs",
            term="die Besprechung",
            translation="the meeting",
            payload_json=json.dumps({"note": "", "sentences": []}),
            local_day="2026-09-29",
        )
        self.assertTrue(self.db.set_item_status(item.id, 10, "learned"))
        self.assertFalse(self.db.set_item_status(item.id, 99, "repeat"))
        stats = self.db.counts(10)
        self.assertEqual(stats["learned"], 1)
        self.assertEqual(stats["words_learned"], 1)
        self.assertEqual(self.db.recent_terms(10, "German", "word"), ["die Besprechung"])
        self.assertEqual(self.db.activity_counts(10, "2026-09-23")["2026-09-29"], 1)

        self.assertTrue(self.db.delete_plan(plan.id, 10))
        self.assertEqual(self.db.list_plans(10), [])
        self.assertIsNotNone(self.db.get_item(item.id, 10))

    def test_delivery_claim_is_single_use_until_released(self) -> None:
        first = self.db.claim_delivery(1, "time_1", "2026-09-29")
        second = self.db.claim_delivery(1, "time_1", "2026-09-29")
        self.assertEqual(first, 1)
        self.assertIsNone(second)
        self.db.release_delivery(1, "time_1", "2026-09-29")
        third = self.db.claim_delivery(1, "time_1", "2026-09-29")
        self.assertEqual(third, 2)
        self.db.finish_delivery(1, "time_1", "2026-09-29", 5)
        self.assertIsNone(self.db.claim_delivery(1, "time_1", "2026-09-29"))
        status, attempts = self.db.delivery_info(1, "time_1", "2026-09-29")
        self.assertEqual(status, "sent")
        self.assertEqual(attempts, 2)


if __name__ == "__main__":
    unittest.main()
