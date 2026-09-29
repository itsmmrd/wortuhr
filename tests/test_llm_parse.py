from __future__ import annotations

import json
import unittest

from bot.llm import load_json_object, parse_card


WORD = {
    "term": "die Wohnung",
    "translation": "the apartment",
    "note": "feminine noun",
    "sentences": [
        {"text": "Die Wohnung ist hell.", "translation": "The apartment is bright."},
        {"text": "Ich suche eine Wohnung.", "translation": "I am looking for an apartment."},
        {"text": "Die Wohnung hat einen Balkon.", "translation": "The apartment has a balcony."},
    ],
}

IDIOM = {
    "term": "jemandem die Daumen drücken",
    "translation": "to keep one's fingers crossed for someone",
    "note": "literally: to press one's thumbs for someone",
    "contexts": [
        {
            "situation": "Before an exam",
            "text": "Ich drücke dir die Daumen.",
            "translation": "I'll keep my fingers crossed for you.",
        },
        {
            "situation": "A job interview",
            "text": "Wir drücken dir die Daumen für das Gespräch.",
            "translation": "We'll keep our fingers crossed for the interview.",
        },
        {
            "situation": "A friend traveling",
            "text": "Drück mir die Daumen, der Zug ist spät.",
            "translation": "Keep your fingers crossed, the train is late.",
        },
    ],
}


class ParseTests(unittest.TestCase):
    def test_word_card_keeps_three_sentences(self) -> None:
        card = parse_card("word", json.dumps(WORD))
        self.assertEqual(card["term"], "die Wohnung")
        self.assertEqual(len(card["sentences"]), 3)
        self.assertEqual(card["sentences"][0]["translation"], "The apartment is bright.")

    def test_idiom_card_keeps_three_contexts(self) -> None:
        card = parse_card("idiom", json.dumps(IDIOM))
        self.assertEqual(len(card["contexts"]), 3)
        self.assertIn("exam", card["contexts"][0]["situation"].lower())

    def test_fenced_json_is_accepted(self) -> None:
        raw = "```json\n" + json.dumps(WORD) + "\n```"
        self.assertEqual(load_json_object(raw)["term"], "die Wohnung")
        self.assertEqual(len(parse_card("word", raw)["sentences"]), 3)

    def test_word_card_requires_three_sentences(self) -> None:
        short = dict(WORD)
        short["sentences"] = WORD["sentences"][:2]
        with self.assertRaises(ValueError):
            parse_card("word", json.dumps(short))

    def test_idiom_card_requires_complete_contexts(self) -> None:
        broken = json.loads(json.dumps(IDIOM))
        broken["contexts"][1].pop("translation")
        with self.assertRaises(ValueError):
            parse_card("idiom", json.dumps(broken))


if __name__ == "__main__":
    unittest.main()
