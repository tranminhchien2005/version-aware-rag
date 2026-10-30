"""Transport contract tests use stubs; they do not contact Google or spend tokens."""
import importlib.metadata
import os
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.llm_client import GeminiClient, LLMError
from tests.fixtures import CONFIG


class ServiceError(Exception):
    def __init__(self, code):
        super().__init__("Synthetic secret should never be echoed")
        self.code = code


def response(text='{"value":1}'):
    return SimpleNamespace(text=text, model_version="stub-model", usage_metadata=SimpleNamespace(
        prompt_token_count=10, candidates_token_count=5, thoughts_token_count=2, total_token_count=17))


def client(responses, attempts=2):
    value = GeminiClient.__new__(GeminiClient)
    value.config = CONFIG
    value.attempts = attempts
    value.model_id = "stub-model"
    value.types = SimpleNamespace(GenerateContentConfig=lambda **kwargs: kwargs)
    value.client = SimpleNamespace(models=SimpleNamespace(generate_content=Mock(side_effect=responses)))
    return value


class TransportTests(unittest.TestCase):
    def test_installed_sdk_accepts_client_and_schema_configuration(self):
        try:
            importlib.metadata.version("google-genai")
        except importlib.metadata.PackageNotFoundError:
            self.skipTest("google-genai chưa cài; chưa kiểm thử cấu hình SDK thực tế")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "synthetic-test-key-not-a-real-credential", "LLM_MODEL": "test-model"}):
            from google.genai import types
            from src.generate import SCHEMA
            c = GeminiClient(CONFIG)
            try:
                options = types.GenerateContentConfig(response_mime_type="application/json", response_json_schema=SCHEMA, automatic_continuation=False)
                self.assertEqual(options.response_mime_type, "application/json")
                self.assertEqual(c.model_id, "test-model")
            finally:
                c.close()

    def test_json_usage_and_no_forced_temperature(self):
        c = client([response()])
        reply = c.complete("sys", {"question": "q"}, {}, "generate")
        self.assertEqual(reply.data, {"value": 1})
        self.assertEqual(reply.usage["total_tokens"], 17)
        self.assertEqual(reply.usage["thought_tokens"], 2)
        self.assertNotIn("temperature", c.client.models.generate_content.call_args.kwargs["config"])
        self.assertFalse(c.client.models.generate_content.call_args.kwargs["config"]["automatic_continuation"])

    @patch("src.llm_client.time.sleep")
    def test_rate_limit_retries_are_bounded(self, sleep):
        c = client([ServiceError(429), ServiceError(429)])
        with self.assertRaises(LLMError) as caught:
            c.complete("sys", {}, {}, "generate")
        self.assertEqual(c.client.models.generate_content.call_count, 2)
        self.assertEqual(caught.exception.usage["calls"], 2)
        self.assertFalse(caught.exception.usage["usage_complete"])
        self.assertNotIn("secret", str(caught.exception))
        sleep.assert_called_once()

    @patch("src.llm_client.time.sleep")
    def test_unauthorized_is_not_retried(self, sleep):
        c = client([ServiceError(401)])
        with self.assertRaises(LLMError):
            c.complete("sys", {}, {}, "generate")
        self.assertEqual(c.client.models.generate_content.call_count, 1)
        sleep.assert_not_called()

    def test_provider_message_is_redacted(self):
        error = ServiceError(404)
        error.message = "Synthetic provider detail with test_secret_provider"
        c = client([error])
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test_secret_provider"}):
            with self.assertRaises(LLMError) as caught:
                c.complete("sys", {}, {}, "generate")
        self.assertIn("Synthetic provider detail", str(caught.exception))
        self.assertNotIn("test_secret_provider", str(caught.exception))

    @patch("src.llm_client.time.sleep")
    def test_retry_then_success_marks_unknown_failed_usage(self, sleep):
        c = client([TimeoutError(), response()])
        reply = c.complete("sys", {}, {}, "generate")
        self.assertEqual(reply.usage["calls"], 2)
        self.assertEqual(reply.usage["total_tokens"], 17)
        self.assertFalse(reply.usage["usage_complete"])

    def test_empty_and_invalid_json_preserve_recorded_usage(self):
        for text in ("", "not json", "[]"):
            with self.subTest(text=text):
                c = client([response(text)])
                with self.assertRaises(LLMError) as caught:
                    c.complete("sys", {}, {}, "generate")
                self.assertEqual(caught.exception.usage["total_tokens"], 17)
                self.assertEqual(c.client.models.generate_content.call_count, 1)


if __name__ == "__main__":
    unittest.main()
