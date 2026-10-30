"""Provider boundary: real Gemini client, with bounded attempts and safe errors."""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

from .common import DataError, empty_usage, redact


@dataclass
class LLMReply:
    data: dict
    usage: dict
    model_id: str


class LLMError(RuntimeError):
    def __init__(self, message, usage=None):
        super().__init__(message)
        self.usage = usage or empty_usage()


class GeminiClient:
    """Uses documented google-genai models.generate_content, not guessed SDK APIs."""

    def __init__(self, config):
        self.model_id = os.environ.get("LLM_MODEL", "").strip()
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key or not self.model_id:
            raise DataError("Điền GEMINI_API_KEY và LLM_MODEL trong .env trên máy rồi chạy lại.")
        try:
            from google import genai
            from google.genai import types
        except ImportError as exc:
            raise DataError("Chưa cài google-genai. Chạy pip install -r requirements.txt trong Python 3.11+.") from exc
        timeout = float(os.environ.get("LLM_TIMEOUT_SECONDS", "60"))
        self.attempts = int(os.environ.get("LLM_MAX_ATTEMPTS", "2"))
        if not 1 <= self.attempts <= 4 or not 1 <= timeout <= 300:
            raise DataError("Timeout phải 1..300 giây; số lần gọi phải 1..4")
        self.types = types
        self.config = config
        self.client = genai.Client(api_key=api_key, http_options=types.HttpOptions(
            timeout=int(timeout * 1000), retry_options=types.HttpRetryOptions(attempts=1)))

    def close(self):
        self.client.close()

    def complete(self, system, payload, schema, purpose):
        usage = empty_usage()
        generation_options = dict(system_instruction=system, response_mime_type="application/json",
                       response_json_schema=schema, max_output_tokens=self.config["llm_max_output_tokens"],
                       automatic_continuation=False)
        if self.config.get("llm_temperature") is not None:
            generation_options["temperature"] = self.config["llm_temperature"]
        for attempt in range(self.attempts):
            usage["calls"] += 1
            try:
                response = self.client.models.generate_content(
                    model=self.model_id, contents=json.dumps(payload, ensure_ascii=False),
                    config=self.types.GenerateContentConfig(**generation_options))
            except Exception as exc:
                usage["usage_complete"] = False
                code = getattr(exc, "code", None)
                retryable = code in (429, 500, 502, 503, 504) or isinstance(exc, (TimeoutError, ConnectionError)) or "Timeout" in type(exc).__name__
                if retryable and attempt + 1 < self.attempts:
                    time.sleep(min(2 ** attempt, 4))
                    continue
                # Expose only the provider's message field, redacted and bounded;
                # never stringify request objects, headers or the full exception.
                detail = redact(getattr(exc, "message", ""))
                detail = detail[:800] if isinstance(detail, str) else ""
                raise LLMError("Lỗi dịch vụ LLM ({}, mã {}). {}".format(type(exc).__name__, code,
                               detail or "Kiểm tra mạng, khóa, model ID và hạn mức."), usage) from None
            usage_metadata = getattr(response, "usage_metadata", None)
            if usage_metadata is None:
                usage["usage_complete"] = False
            else:
                for usage_field, provider_field in (("input_tokens", "prompt_token_count"),
                                       ("output_tokens", "candidates_token_count"),
                                       ("thought_tokens", "thoughts_token_count"), ("total_tokens", "total_token_count")):
                    usage[usage_field] += getattr(usage_metadata, provider_field, 0) or 0
            try:
                response_text = getattr(response, "text", None)
            except (ValueError, TypeError):
                raise LLMError("Không đọc được nội dung trả về của LLM.", usage) from None
            if not response_text or not response_text.strip():
                raise LLMError("LLM trả nội dung rỗng hoặc bị chặn.", usage)
            try:
                data = json.loads(response_text)
            except (TypeError, json.JSONDecodeError):
                raise LLMError("LLM trả JSON không hợp lệ.", usage) from None
            if not isinstance(data, dict):
                raise LLMError("Đầu ra LLM phải là JSON object.", usage)
            return LLMReply(data, usage, getattr(response, "model_version", None) or self.model_id)
        raise LLMError("Không nhận được phản hồi LLM.", usage)
