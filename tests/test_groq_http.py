from __future__ import annotations

import unittest

from bot.groq_http import error_message


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


if __name__ == "__main__":
    unittest.main()
