"""LLM adapter. Gemini via the official google-genai SDK; swap by implementing `LLMClient`."""

import json
import logging
import time
from dataclasses import dataclass
from functools import lru_cache
from typing import Protocol

from django.conf import settings

logger = logging.getLogger(__name__)


class LLMError(Exception):
    """Generation failed or returned unusable output. Message is safe to log, never shown verbatim."""


@dataclass(frozen=True)
class LLMAnswer:
    answer: str
    sufficient_context: bool
    cited_source_ids: list[str]
    model: str


class LLMClient(Protocol):
    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMAnswer: ...


def parse_llm_json(raw: str, model: str) -> LLMAnswer:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        text = text.split("\n", 1)[1] if "\n" in text else text
        text = text.rsplit("```", 1)[0]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError("model returned non-JSON output") from exc
    if not isinstance(data, dict) or not isinstance(data.get("answer"), str):
        raise LLMError("model output missing 'answer'")
    cites = data.get("citations") or []
    if not isinstance(cites, list):
        raise LLMError("model output has malformed 'citations'")
    return LLMAnswer(
        answer=data["answer"].strip(),
        sufficient_context=bool(data.get("sufficient_context", True)),
        cited_source_ids=[str(c) for c in cites if isinstance(c, str | int)],
        model=model,
    )


class GeminiClient:
    # Only these are worth repeating: rate limit and transient server-side errors.
    _RETRYABLE = {429, 500, 502, 503, 504}

    def __init__(
        self,
        api_key: str,
        model: str,
        timeout_s: int,
        max_attempts: int,
        max_output_tokens: int,
        fallback_model: str = "",
    ):
        from google import genai
        from google.genai import types

        self._types = types
        self._client = genai.Client(
            api_key=api_key, http_options=types.HttpOptions(timeout=timeout_s * 1000, retry_options=None)
        )
        self.model = model
        self._fallback_model = fallback_model if fallback_model and fallback_model != model else ""
        self._max_attempts = max(1, max_attempts)
        self._max_output_tokens = max_output_tokens

    def generate(self, *, system_prompt: str, user_prompt: str) -> LLMAnswer:
        config = self._types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,
            max_output_tokens=self._max_output_tokens,
            response_mime_type="application/json",
        )
        try:
            return self._generate_with(self.model, user_prompt, config, self._max_attempts)
        except LLMError:
            if not self._fallback_model:
                raise
            logger.warning("gemini_fallback primary=%s fallback=%s", self.model, self._fallback_model)
            return self._generate_with(self._fallback_model, user_prompt, config, 2)

    def _generate_with(self, model: str, user_prompt: str, config, max_attempts: int) -> LLMAnswer:  # type: ignore[no-untyped-def]
        from google.genai import errors

        last: Exception | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                response = self._client.models.generate_content(model=model, contents=user_prompt, config=config)
                return parse_llm_json(response.text or "", model)
            except errors.APIError as exc:
                last = exc
                code = getattr(exc, "code", None)
                logger.warning("gemini_api_error attempt=%s code=%s", attempt, code)
                if code not in self._RETRYABLE:
                    break
            except LLMError:
                raise
            except Exception as exc:  # network/timeout from the HTTP layer
                last = exc
                logger.warning("gemini_call_failed attempt=%s type=%s", attempt, type(exc).__name__)
            if attempt < max_attempts:
                time.sleep(min(2**attempt, 8))
        raise LLMError("generation failed") from last


@lru_cache(maxsize=1)
def get_llm() -> LLMClient:
    if not settings.GEMINI_API_KEY:
        raise LLMError("GEMINI_API_KEY is not configured")
    return GeminiClient(
        api_key=settings.GEMINI_API_KEY,
        model=settings.GEMINI_MODEL,
        timeout_s=settings.GEMINI_TIMEOUT_SECONDS,
        max_attempts=settings.GEMINI_MAX_ATTEMPTS,
        max_output_tokens=settings.GEMINI_MAX_OUTPUT_TOKENS,
        fallback_model=settings.GEMINI_FALLBACK_MODEL,
    )
