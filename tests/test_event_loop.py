from __future__ import annotations

import asyncio
import unittest

from bot.main import ensure_event_loop


class EventLoopTests(unittest.TestCase):
    def test_ensure_event_loop_leaves_a_loop_in_place(self) -> None:
        previous = None
        try:
            previous = asyncio.get_event_loop()
        except RuntimeError:
            previous = None
        try:
            if previous is not None:
                asyncio.set_event_loop(None)
            ensure_event_loop()
            loop = asyncio.get_event_loop()
            self.assertFalse(loop.is_closed())
        finally:
            asyncio.set_event_loop(previous)


if __name__ == "__main__":
    unittest.main()
