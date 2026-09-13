"""Bounded Ollama-compatible HTTP client for local structured generation."""

import json
import math
from collections.abc import Mapping
from typing import Any, cast
from urllib.parse import urlparse

import httpx


class OllamaUnavailableError(ValueError):
    """Safe local Ollama failure suitable for user-facing guidance."""


class OllamaClient:
    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 180,
        response_limit_bytes: int = 1_048_576,
        max_prompt_chars: int = 12_000,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._base_url = _validate_origin(base_url)
        if not model.strip():
            raise ValueError("Ollama model must not be empty")
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("Ollama timeout must be positive and finite")
        if response_limit_bytes < 1:
            raise ValueError("Ollama response limit must be positive")
        if max_prompt_chars < 1:
            raise ValueError("Ollama prompt limit must be positive")
        self._model = model.strip()
        self._timeout = httpx.Timeout(timeout_seconds)
        self._response_limit_bytes = response_limit_bytes
        self._max_prompt_chars = max_prompt_chars
        self._transport = transport

    def generate_json(
        self,
        prompt: str,
        schema: Mapping[str, object],
    ) -> dict[str, Any]:
        if not prompt.strip():
            raise ValueError("Ollama prompt must not be empty")
        if len(prompt) > self._max_prompt_chars:
            raise ValueError("Ollama prompt exceeds the configured limit")

        request_payload = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "format": dict(schema),
            "options": {"temperature": 0},
        }
        try:
            with (
                httpx.Client(
                    base_url=self._base_url,
                    timeout=self._timeout,
                    transport=self._transport,
                ) as client,
                client.stream(
                    "POST",
                    "/api/generate",
                    json=request_payload,
                ) as response,
            ):
                body = _read_bounded(response, self._response_limit_bytes)
                status_code = response.status_code
        except httpx.TimeoutException as error:
            raise OllamaUnavailableError("Local Ollama request timed out") from error
        except httpx.ConnectError as error:
            raise OllamaUnavailableError("Local Ollama endpoint is unreachable") from error
        except httpx.RequestError as error:
            raise OllamaUnavailableError("Local Ollama endpoint is unreachable") from error

        if status_code == 404:
            raise OllamaUnavailableError("Configured Ollama model is not available locally")
        if status_code < 200 or status_code >= 300:
            raise OllamaUnavailableError("Local Ollama request was not accepted")

        try:
            outer: Any = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as error:
            raise OllamaUnavailableError("Local Ollama returned an invalid response") from error
        if not isinstance(outer, dict) or not isinstance(outer.get("response"), str):
            raise OllamaUnavailableError("Local Ollama returned an invalid response")

        try:
            structured: Any = json.loads(outer["response"])
        except json.JSONDecodeError as error:
            raise OllamaUnavailableError(
                "Local Ollama returned an invalid structured response"
            ) from error
        if not isinstance(structured, dict):
            raise OllamaUnavailableError("Local Ollama returned an invalid structured response")
        return cast(dict[str, Any], structured)


def _read_bounded(response: httpx.Response, limit_bytes: int) -> bytes:
    body = bytearray()
    for chunk in response.iter_bytes():
        body.extend(chunk)
        if len(body) > limit_bytes:
            raise OllamaUnavailableError("Local Ollama response is too large")
    return bytes(body)


def _validate_origin(value: str) -> str:
    try:
        parsed = urlparse(value.strip())
        _port = parsed.port
    except ValueError as error:
        raise ValueError("Ollama base URL must be an HTTP(S) origin") from error
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Ollama base URL must be an HTTP(S) origin")
    return value.strip().rstrip("/")
