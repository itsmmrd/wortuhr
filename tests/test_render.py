from __future__ import annotations

import unittest
from datetime import date

from bot.render import activity_block, bar, lesson_html


class RenderTests(unittest.TestCase):
    def test_bar_fills_half(self) -> None:
        rendered = bar(1, 2, width=4)
        self.assertEqual(rendered, "██░░")

    def test_empty_bar(self) -> None:
        self.assertEqual(bar(0, 0, width=4), "░░░░")

    def test_activity_covers_seven_days(self) -> None:
        today = date(2026, 9, 29)
        text = activity_block({today.isoformat(): 2}, today)
        lines = text.splitlines()
        self.assertEqual(len(lines), 7)
        self.assertIn("2", lines[-1])

    def test_lesson_escapes_html_and_lists_examples(self) -> None:
        html = lesson_html(
            language="German",
            level="A2",
            topic="<script>",
            content_type="word",
            term="die Wohnung",
            translation="the apartment",
            payload={
                "note": "a <note>",
                "sentences": [
                    {"text": "Eins <a>.", "translation": "One."},
                    {"text": "Zwei.", "translation": "Two."},
                    {"text": "Drei.", "translation": "Three."},
                ],
            },
            footer="Plan: work",
        )
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("1. Eins &lt;a&gt;.", html)
        self.assertIn("2. Zwei.", html)
        self.assertIn("3. Drei.", html)
        self.assertIn("Plan: work", html)

    def test_idiom_lists_situations(self) -> None:
        html = lesson_html(
            language="English",
            level="B1",
            topic="Work and jobs",
            content_type="idiom",
            term="break the ice",
            translation="das Eis brechen",
            payload={
                "note": "",
                "contexts": [
                    {"situation": "A meeting", "text": "She told a joke.", "translation": "Sie erzählte einen Witz."},
                    {"situation": "A party", "text": "He asked a question.", "translation": "Er stellte eine Frage."},
                    {"situation": "New neighbors", "text": "I said hello.", "translation": "Ich sagte hallo."},
                ],
            },
        )
        self.assertIn("Where you can use it", html)
        self.assertIn("A meeting", html)
        self.assertIn("New neighbors", html)


if __name__ == "__main__":
    unittest.main()
