"""Unified LLM client: provider-agnostic interface for Anthropic, Gemini, and Groq."""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional

import anthropic
from groq import Groq
from pydantic import BaseModel
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

try:
    import google.genai as genai
except ImportError:  # pragma: no cover - compatibility fallback
    from google import genai

from config.settings import settings


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


FALLBACK_CHAIN: dict[str, list[str]] = {
    "gemini-2.5-flash": [
        "gemini-2.5-flash-lite",
        "llama-3.3-70b-versatile",
        "claude-sonnet-4-5",
    ],
    "gemini-2.5-flash-lite": ["llama-3.3-70b-versatile", "claude-sonnet-4-5"],
    "gemini-2.5-pro": ["llama-3.3-70b-versatile", "claude-sonnet-4-5"],
    "llama-3.3-70b-versatile": ["claude-sonnet-4-5"],
    "llama-3.1-8b-instant": ["llama-3.3-70b-versatile", "claude-sonnet-4-5"],
    "claude-sonnet-4-5": [],
    "claude-opus-4-5": [],
    "claude-haiku-4-5": [],
    # Smoke-test-only entry to verify cross-model fallback behavior.
    "gemini-fake-doesnt-exist": ["claude-sonnet-4-5"],
}


def _get_fallbacks(model: str) -> list[str]:
    """Return ordered list of fallback models for a given primary model."""
    return FALLBACK_CHAIN.get(model, [])


def _is_retryable_error(err: Exception) -> bool:
    """
    Return True if the error should trigger fallback to the next model.

    Covers transient failures such as quota, rate limits, overload, timeouts,
    and generic provider-side internal errors. Authentication and permanent
    client-side request errors should not trigger fallback.
    """
    err_str = str(err).lower()
    retryable_markers = [
        "429",
        "resource_exhausted",
        "rate limit",
        "quota",
        "timeout",
        "timed out",
        "too many requests",
        "overloaded_error",
        "service unavailable",
        "service_unavailable",
        "capacity_exceeded",
        "503",
        "500",
        "internal error",
    ]
    non_retryable_markers = [
        "authentication",
        "invalid api key",
        "permission_denied",
        "invalid_argument",
    ]
    if any(marker in err_str for marker in non_retryable_markers):
        return False
    return any(marker in err_str for marker in retryable_markers)


@dataclass
class LLMResponse:
    """Normalized response object shared across Anthropic and Gemini calls."""

    content: str
    raw_json: Optional[dict]
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    fallback_used: bool = False


class UnifiedLLMClient:
    """One interface, three providers. Routes calls based on model name prefix."""

    def __init__(self) -> None:
        """Initialize lazy client handles for Anthropic, Gemini, and Groq."""
        self._anthropic_client = None
        self._gemini_client = None
        self._groq_client = None

    def _get_anthropic(self) -> anthropic.Anthropic:
        """Return a lazily initialized Anthropic client."""
        if self._anthropic_client is None:
            self._anthropic_client = anthropic.Anthropic(
                api_key=settings.anthropic_api_key
            )
        return self._anthropic_client

    def _get_gemini(self) -> genai.Client:
        """Return a lazily initialized Gemini client."""
        if self._gemini_client is None:
            self._gemini_client = genai.Client(api_key=settings.gemini_api_key)
        return self._gemini_client

    def _get_groq(self) -> Groq:
        """Return a lazily initialized Groq client."""
        if self._groq_client is None:
            self._groq_client = Groq(api_key=settings.groq_api_key)
        return self._groq_client

    @staticmethod
    def _parse_json_content(content: str) -> Optional[dict]:
        """Parse model output as JSON, stripping code fences if necessary."""
        cleaned = content.strip()
        if cleaned.startswith("```"):
            parts = cleaned.split("```")
            if len(parts) >= 2:
                cleaned = parts[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            logger.warning("json_mode failed to parse: %s. Content: %s", exc, content[:200])
            return None
        return parsed if isinstance(parsed, dict) else {"value": parsed}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((Exception,)),
        reraise=True,
    )
    def _chat_single(
        self,
        model: str,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int = 2048,
        temperature: float = 0.2,
        response_schema: Optional[Any] = None,
    ) -> LLMResponse:
        """
        Execute one provider call against one model.

        Retries are scoped to the same model only. Cross-model fallback belongs
        in the public chat() wrapper.
        """
        provider: Literal["anthropic", "gemini", "groq"] = settings.provider_for_model(model)

        import time

        t0 = time.perf_counter()

        if provider == "anthropic":
            client = self._get_anthropic()
            sys_text = system
            if json_mode:
                sys_text += (
                    "\n\nReturn ONLY valid JSON. No prose, no code fences, no commentary."
                )
            resp = client.messages.create(
                model=model,
                system=sys_text,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[{"role": "user", "content": user}],
            )
            text_blocks: List[str] = [
                block.text
                for block in resp.content
                if getattr(block, "type", "") == "text" and getattr(block, "text", "")
            ]
            content = "\n".join(text_blocks).strip()
            input_tokens = resp.usage.input_tokens
            output_tokens = resp.usage.output_tokens

        elif provider == "gemini":
            client = self._get_gemini()
            types = genai.types
            sys_text = system
            if json_mode:
                sys_text += (
                    "\n\nReturn ONLY valid JSON. No prose, no code fences, no commentary."
                )
            config = types.GenerateContentConfig(
                systemInstruction=sys_text,
                temperature=temperature,
                maxOutputTokens=max_tokens,
                responseMimeType="application/json" if json_mode else "text/plain",
                responseSchema=response_schema if json_mode else None,
            )
            resp = client.models.generate_content(
                model=model,
                contents=user,
                config=config,
            )
            content = (resp.text or "").strip()
            usage = getattr(resp, "usage_metadata", None)
            input_tokens = int(getattr(usage, "prompt_token_count", 0) or 0) if usage else 0
            output_tokens = (
                int(getattr(usage, "candidates_token_count", 0) or 0) if usage else 0
            )

        elif provider == "groq":
            client = self._get_groq()
            sys_text = system
            if json_mode:
                sys_text += (
                    "\n\nReturn ONLY valid JSON. No prose, no code fences, no commentary."
                )

            messages = [
                {"role": "system", "content": sys_text},
                {"role": "user", "content": user},
            ]
            kwargs: Dict[str, Any] = {
                "model": model,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            resp = client.chat.completions.create(**kwargs)
            content = resp.choices[0].message.content or ""
            input_tokens = getattr(resp.usage, "prompt_tokens", 0) if resp.usage else 0
            output_tokens = getattr(resp.usage, "completion_tokens", 0) if resp.usage else 0

        else:
            raise ValueError(f"Unknown provider: {provider}")

        latency_ms = int((time.perf_counter() - t0) * 1000)
        raw_json = None
        if json_mode:
            parsed = None
            if provider == "gemini" and response_schema is not None:
                parsed = getattr(resp, "parsed", None)
            if isinstance(parsed, BaseModel):
                raw_json = parsed.model_dump()
            elif isinstance(parsed, dict):
                raw_json = parsed
            else:
                raw_json = self._parse_json_content(content)

        return LLMResponse(
            content=content,
            raw_json=raw_json,
            model=model,
            provider=provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
        )

    def chat(
        self,
        model: str,
        system: str,
        user: str,
        json_mode: bool = False,
        max_tokens: int = 2048,
        temperature: float = 0.2,
        response_schema: Optional[Any] = None,
    ) -> LLMResponse:
        """
        Unified chat call with cascading model fallback.

        The requested model is attempted first. If it fails with a retryable
        provider error, or if JSON mode succeeds without valid JSON and another
        fallback is available, the client advances through the configured
        fallback chain automatically.
        """
        cascade = [model, *_get_fallbacks(model)]
        attempted_models: List[str] = []
        last_error: Optional[Exception] = None

        for index, current_model in enumerate(cascade):
            attempted_models.append(current_model)
            has_more_fallbacks = index < len(cascade) - 1

            try:
                response = self._chat_single(
                    model=current_model,
                    system=system,
                    user=user,
                    json_mode=json_mode,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    response_schema=response_schema,
                )
            except Exception as err:
                last_error = err
                if _is_retryable_error(err) and has_more_fallbacks:
                    logger.warning(
                        "%s failed with retryable error: %s, trying fallback",
                        current_model,
                        str(err)[:120],
                    )
                    continue
                raise

            if json_mode and response.raw_json is None and has_more_fallbacks:
                logger.warning(
                    "JSON parse failed on %s, trying fallback",
                    current_model,
                )
                continue

            response.fallback_used = current_model != model
            if response.fallback_used:
                logger.info(
                    "LLM call requested %s but succeeded with fallback %s",
                    model,
                    current_model,
                )
            else:
                logger.info("LLM call succeeded using primary model %s", current_model)
            return response

        chain_text = " -> ".join(attempted_models)
        raise RuntimeError(
            f"Exhausted model fallback chain without success: {chain_text}"
        ) from last_error


llm_client = UnifiedLLMClient()


def _print_summary_table(rows: List[Dict[str, Any]]) -> None:
    """Render a compact smoke-test summary table."""
    print(
        "| Provider  | Model                         | Latency | In Tokens | Out Tokens | JSON OK | Fallback? |"
    )
    print(
        "|-----------|-------------------------------|---------|-----------|------------|---------|-----------|"
    )
    for row in rows:
        print(
            f"| {row['provider']:<9} | {row['model']:<29} | {row['latency']:<7} | "
            f"{row['input_tokens']:<9} | {row['output_tokens']:<10} | {row['json_ok']:<7} | "
            f"{row['fallback_used']:<9} |"
        )


if __name__ == "__main__":
    import sys
    from config.logging_setup import configure_logging
    from config.settings import settings

    configure_logging(settings.log_level)

    failures = 0
    summary_rows: List[Dict[str, Any]] = []

    def _record_summary(response: Optional[LLMResponse], json_expected: bool) -> None:
        """Append one smoke-test result row when a response is available."""
        if response is None:
            return
        summary_rows.append(
            {
                "provider": response.provider.title(),
                "model": response.model,
                "latency": f"{response.latency_ms}ms",
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "json_ok": "YES" if (not json_expected or response.raw_json is not None) else "NO",
                "fallback_used": "YES" if response.fallback_used else "NO",
            }
        )

    try:
        anthropic_text = llm_client.chat(
            model=settings.writer_model,
            system="You are concise.",
            user="Say 'Anthropic OK' and nothing else.",
        )
        assert "Anthropic OK" in anthropic_text.content
        print(f"[OK] Test 1: Anthropic plain text - {anthropic_text.content!r}")
    except Exception as exc:
        failures += 1
        print(f"[FAIL] Test 1: Anthropic plain text - {exc}")
        anthropic_text = None
    _record_summary(anthropic_text, json_expected=False)

    try:
        gemini_text = llm_client.chat(
            model=settings.researcher_model,
            system="You are concise.",
            user="Say 'Gemini OK' and nothing else.",
        )
        assert "Gemini OK" in gemini_text.content
        print(f"[OK] Test 2: Gemini plain text - {gemini_text.content!r}")
    except Exception as exc:
        failures += 1
        print(f"[FAIL] Test 2: Gemini plain text - {exc}")
        gemini_text = None
    _record_summary(gemini_text, json_expected=False)

    try:
        anthropic_json = llm_client.chat(
            model=settings.writer_model,
            system="You output JSON.",
            user='Return JSON {"status": "ok", "model": "claude"}',
            json_mode=True,
        )
        assert anthropic_json.raw_json is not None
        print(f"[OK] Test 3: Anthropic JSON mode - {anthropic_json.raw_json}")
    except Exception as exc:
        failures += 1
        print(f"[FAIL] Test 3: Anthropic JSON mode - {exc}")
        anthropic_json = None
    _record_summary(anthropic_json, json_expected=True)

    try:
        gemini_json = llm_client.chat(
            model=settings.researcher_model,
            system="You output JSON.",
            user='Return JSON {"status": "ok", "model": "gemini"}',
            json_mode=True,
        )
        assert gemini_json.raw_json is not None
        print(f"[OK] Test 4: Gemini JSON mode - {gemini_json.raw_json}")
    except Exception as exc:
        failures += 1
        print(f"[FAIL] Test 4: Gemini JSON mode - {exc}")
        gemini_json = None
    _record_summary(gemini_json, json_expected=True)

    original_chat_single = llm_client._chat_single
    fallback_test_response: Optional[LLMResponse] = None
    try:
        def _chat_single_with_forced_failure(
            model: str,
            system: str,
            user: str,
            json_mode: bool = False,
            max_tokens: int = 2048,
            temperature: float = 0.2,
            response_schema: Optional[Any] = None,
        ) -> LLMResponse:
            if model == "gemini-fake-doesnt-exist":
                raise RuntimeError("429 simulated retryable failure for fallback smoke test")
            return original_chat_single(
                model=model,
                system=system,
                user=user,
                json_mode=json_mode,
                max_tokens=max_tokens,
                temperature=temperature,
                response_schema=response_schema,
            )

        llm_client._chat_single = _chat_single_with_forced_failure  # type: ignore[method-assign]
        fallback_test_response = llm_client.chat(
            model="gemini-fake-doesnt-exist",
            system="You are concise.",
            user="Say 'Fallback OK' and nothing else.",
        )
        assert "Fallback OK" in fallback_test_response.content
        assert fallback_test_response.fallback_used is True
        print(
            "[OK] Test 5: Fallback chain works - "
            f"gemini-fake-doesnt-exist -> {fallback_test_response.model} "
            f"(fallback_used={fallback_test_response.fallback_used})"
        )
    except Exception as exc:
        failures += 1
        print(f"[FAIL] Test 5: Fallback chain works - {exc}")
    finally:
        llm_client._chat_single = original_chat_single  # type: ignore[method-assign]
    _record_summary(fallback_test_response, json_expected=False)

    try:
        groq_text = llm_client.chat(
            model=settings.groq_primary_model,
            system="You are concise.",
            user="Say 'Groq OK' and nothing else.",
        )
        assert "groq ok" in groq_text.content.lower()
        print(f"[OK] Test 6: Groq plain text - {groq_text.content!r}")
    except Exception as exc:
        failures += 1
        print(f"[FAIL] Test 6: Groq plain text - {exc}")
        groq_text = None
    _record_summary(groq_text, json_expected=False)

    try:
        groq_json = llm_client.chat(
            model=settings.groq_primary_model,
            system="You output JSON.",
            user='Return JSON {"status": "ok", "model": "groq"}',
            json_mode=True,
        )
        assert groq_json.raw_json is not None
        print(f"[OK] Test 7: Groq JSON mode - {groq_json.raw_json}")
    except Exception as exc:
        failures += 1
        print(f"[FAIL] Test 7: Groq JSON mode - {exc}")
        groq_json = None
    _record_summary(groq_json, json_expected=True)

    if summary_rows:
        print()
        _print_summary_table(summary_rows)

    sys.exit(1 if failures else 0)
