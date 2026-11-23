import json
import unittest
import urllib.error
from unittest.mock import patch

from recovery_witness.narrator_openai import make_openai_narrator


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload

    def read(self):
        return self._payload

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class OpenAINarratorTests(unittest.TestCase):
    def test_missing_api_key_raises_without_leaking_anything(self):
        narrator = make_openai_narrator(api_key_env="ECU_TEST_MISSING_KEY")

        with patch.dict("os.environ", {}, clear=False):
            import os

            os.environ.pop("ECU_TEST_MISSING_KEY", None)
            with self.assertRaisesRegex(RuntimeError, "ECU_TEST_MISSING_KEY is not set"):
                narrator("some prompt")

    def test_successful_call_never_puts_the_key_in_the_body_or_url(self):
        narrator = make_openai_narrator(api_key_env="ECU_TEST_KEY")
        captured_requests = []

        def fake_urlopen(request, timeout=None):
            captured_requests.append(request)
            payload = json.dumps(
                {"choices": [{"message": {"content": "narrated text"}}]}
            ).encode("utf-8")
            return _FakeResponse(payload)

        with patch.dict("os.environ", {"ECU_TEST_KEY": "sk-canary-secret-value"}):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                result = narrator("case prompt body")

        self.assertEqual(result, "narrated text")
        self.assertEqual(len(captured_requests), 1)
        sent = captured_requests[0]
        self.assertNotIn("sk-canary-secret-value", sent.full_url)
        self.assertNotIn("sk-canary-secret-value", sent.data.decode("utf-8"))
        self.assertEqual(sent.headers["Authorization"], "Bearer sk-canary-secret-value")

    def test_http_error_does_not_leak_the_key(self):
        narrator = make_openai_narrator(api_key_env="ECU_TEST_KEY")

        def fake_urlopen(request, timeout=None):
            raise urllib.error.HTTPError(
                "https://api.openai.com/v1/chat/completions", 401,
                "Unauthorized", {}, None,
            )

        with patch.dict("os.environ", {"ECU_TEST_KEY": "sk-canary-secret-value"}):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                with self.assertRaises(RuntimeError) as ctx:
                    narrator("case prompt body")

        self.assertNotIn("sk-canary-secret-value", str(ctx.exception))

    def test_malformed_response_is_rejected(self):
        narrator = make_openai_narrator(api_key_env="ECU_TEST_KEY")

        def fake_urlopen(request, timeout=None):
            return _FakeResponse(b"not json")

        with patch.dict("os.environ", {"ECU_TEST_KEY": "sk-canary-secret-value"}):
            with patch("urllib.request.urlopen", side_effect=fake_urlopen):
                with self.assertRaisesRegex(RuntimeError, "malformed response"):
                    narrator("case prompt body")

    def test_backend_name_identifies_the_model_not_the_key(self):
        narrator = make_openai_narrator(model="gpt-4o-mini", api_key_env="ECU_TEST_KEY")

        self.assertEqual(narrator.__name__, "openai_narrator[gpt-4o-mini]")


if __name__ == "__main__":
    unittest.main()
