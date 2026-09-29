from __future__ import annotations

import io
import unittest

from bot.groq_http import chat_model_ids, error_message, preferred_model_index, read_model_choice


class GroqErrorTests(unittest.TestCase):
    def test_reads_groq_permission_message(self) -> None:
        body = '{"error": {"message": "The model is blocked at the project level.", "type": "permissions_error"}}'
        self.assertIn("blocked at the project level", error_message(403, body))

    def test_rejected_key(self) -> None:
        self.assertEqual(error_message(401, ""), "Groq rejected the API key.")

    def test_plain_403_stays_short(self) -> None:
        message = error_message(403, "<html>cloudflare</html>")
        self.assertIn("403", message)
        self.assertNotIn("cloudflare", message)


class ModelListTests(unittest.TestCase):
    def test_keeps_chat_models_and_skips_audio(self) -> None:
        payload = {
            "data": [
                {"id": "whisper-large-v3", "active": True},
                {"id": "llama-3.1-8b-instant", "active": True},
                {"id": "old-model", "active": False},
                {"id": "openai/gpt-oss-20b", "active": True},
                {"id": "canopylabs/orpheus-v1", "active": True},
            ]
        }
        self.assertEqual(
            chat_model_ids(payload),
            ["llama-3.1-8b-instant", "openai/gpt-oss-20b"],
        )

    def test_prefers_the_saved_model(self) -> None:
        models = ["llama-3.1-8b-instant", "openai/gpt-oss-20b"]
        self.assertEqual(preferred_model_index(models, "openai/gpt-oss-20b"), 1)

    def test_suggests_a_larger_chat_model(self) -> None:
        models = ["llama-3.1-8b-instant", "meta-llama/llama-3.3-70b", "openai/gpt-oss-20b"]
        self.assertEqual(preferred_model_index(models, ""), 1)

    def test_enter_keeps_the_suggested_model(self) -> None:
        models = ["llama-3.1-8b-instant", "openai/gpt-oss-20b"]
        output = io.StringIO()
        chosen = read_model_choice(models, "", io.StringIO("\n"), output)
        self.assertEqual(chosen, "llama-3.1-8b-instant")
        self.assertIn("1. llama-3.1-8b-instant  (suggested)", output.getvalue())
        self.assertIn("2. openai/gpt-oss-20b", output.getvalue())


if __name__ == "__main__":
    unittest.main()
