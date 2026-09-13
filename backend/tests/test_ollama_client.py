import json
from typing import Any

import httpx
import pytest

from subtitle_forge_api.ollama import OllamaClient, OllamaUnavailableError

SCHEMA = {
    "type": "object",
    "properties": {"segments": {"type": "array"}},
    "required": ["segments"],
}


def test_generate_json_uses_configured_local_model_and_non_streaming_schema() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={"response": json.dumps({"segments": [{"id": "s1"}]})},
        )

    result = OllamaClient(
        base_url="http://127.0.0.1:11434",
        model="qwen2.5:7b",
        timeout_seconds=17,
        transport=httpx.MockTransport(handler),
    ).generate_json("Translate one segment", SCHEMA)

    assert result == {"segments": [{"id": "s1"}]}
    request = requests[0]
    assert request.url == httpx.URL("http://127.0.0.1:11434/api/generate")
    payload: dict[str, Any] = json.loads(request.content)
    assert payload == {
        "model": "qwen2.5:7b",
        "prompt": "Translate one segment",
        "stream": False,
        "format": SCHEMA,
        "options": {"temperature": 0},
    }
    assert request.headers.get("authorization") is None


@pytest.mark.parametrize(
    ("handler", "message"),
    [
        (
            lambda request: (_ for _ in ()).throw(
                httpx.ConnectError("C:\\secret\\socket", request=request)
            ),
            "unreachable",
        ),
        (
            lambda request: (_ for _ in ()).throw(
                httpx.ReadTimeout("raw timeout", request=request)
            ),
            "timed out",
        ),
        (lambda request: httpx.Response(404, text="model missing"), "model is not available"),
        (lambda request: httpx.Response(200, content=b"not json"), "invalid response"),
        (
            lambda request: httpx.Response(200, json={"response": "not json"}),
            "invalid structured response",
        ),
        (lambda request: httpx.Response(200, content=b"x" * 200), "too large"),
    ],
)
def test_generate_json_maps_transport_protocol_and_size_failures_safely(
    handler,
    message: str,
) -> None:  # type: ignore[no-untyped-def]
    client = OllamaClient(
        base_url="http://127.0.0.1:11434",
        model="local-model",
        timeout_seconds=3,
        response_limit_bytes=128,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(OllamaUnavailableError, match=message) as captured:
        client.generate_json("safe prompt", SCHEMA)

    safe_message = str(captured.value)
    assert "secret" not in safe_message
    assert "raw timeout" not in safe_message
    assert "model missing" not in safe_message


def test_rejects_empty_or_oversized_prompts_before_http() -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"response": "{}"})

    client = OllamaClient(
        base_url="http://127.0.0.1:11434",
        model="local-model",
        max_prompt_chars=10,
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(ValueError, match="empty"):
        client.generate_json("   ", SCHEMA)
    with pytest.raises(ValueError, match="limit"):
        client.generate_json("x" * 11, SCHEMA)

    assert requests == []


def test_accepts_http_origin_with_implicit_default_port() -> None:
    OllamaClient(base_url="http://localhost", model="local-model")


@pytest.mark.parametrize(
    "base_url",
    [
        "https://user:password@example.com",
        "file:///tmp/socket",
        "http://127.0.0.1:11434/api/generate",
    ],
)
def test_rejects_unsafe_or_non_origin_base_urls(base_url: str) -> None:
    with pytest.raises(ValueError, match="HTTP.*origin"):
        OllamaClient(base_url=base_url, model="local-model")
