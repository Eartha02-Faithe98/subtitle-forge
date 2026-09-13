import pytest
from httpx import ASGITransport, AsyncClient, Response

from subtitle_forge_api.app import create_app
from subtitle_forge_api.settings import Settings


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


async def get_health(origin: str | None = None) -> Response:
    transport = ASGITransport(app=create_app(Settings(_env_file=None)))
    headers = {"Origin": origin} if origin else None
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        return await client.get("/health", headers=headers)


@pytest.mark.anyio
async def test_health_endpoint_returns_ready_contract() -> None:
    response = await get_health()

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.anyio
async def test_public_config_exposes_only_safe_local_provider_metadata() -> None:
    application = create_app(
        Settings(_env_file=None, ollama_model="fixture-local:latest"),
        readiness_check=lambda settings: {"status": "ready", "dependencies": {}},
    )
    transport = ASGITransport(app=application)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/config")

    assert response.status_code == 200
    assert response.json() == {
        "api_version": "1",
        "speech_provider": "Local Whisper",
        "translation_provider": "Ollama-compatible",
        "summary_provider": "Ollama-compatible",
        "ollama_model": "fixture-local:latest",
    }
    assert "11434" not in response.text
    assert "path" not in response.text.lower()


@pytest.mark.anyio
async def test_cors_allows_configured_frontend_origin() -> None:
    response = await get_health("http://localhost:3000")

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.anyio
async def test_cors_omits_unconfigured_origin() -> None:
    response = await get_health("https://untrusted.example")

    assert "access-control-allow-origin" not in response.headers


@pytest.mark.anyio
async def test_cors_preflight_allows_phase_one_submission_from_configured_origin() -> None:
    app = create_app(
        Settings(_env_file=None),
        readiness_check=lambda settings: {"status": "ready", "dependencies": {}},
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.options(
            "/api/jobs",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type, Accept",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "POST" in response.headers["access-control-allow-methods"]
    assert "Content-Type" in response.headers["access-control-allow-headers"]


@pytest.mark.anyio
async def test_cors_preflight_denies_unconfigured_submission_origin() -> None:
    app = create_app(
        Settings(_env_file=None),
        readiness_check=lambda settings: {"status": "ready", "dependencies": {}},
    )
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.options(
            "/api/jobs",
            headers={
                "Origin": "https://untrusted.example",
                "Access-Control-Request-Method": "POST",
            },
        )

    assert "access-control-allow-origin" not in response.headers


@pytest.mark.anyio
async def test_readiness_reports_local_dependency_setup_without_changing_health() -> None:
    calls = 0

    def readiness_check(_: Settings) -> dict[str, object]:
        nonlocal calls
        calls += 1
        return {
            "status": "needs_setup",
            "dependencies": {
                "ffmpeg": {"available": True, "message": "Available"},
                "ffprobe": {"available": True, "message": "Available"},
                "whisper_model": {
                    "available": False,
                    "message": "Prepare the selected Local Whisper model.",
                },
                "ollama": {
                    "available": False,
                    "message": "Start the configured Ollama-compatible service.",
                },
            },
        }

    app = create_app(Settings(_env_file=None), readiness_check=readiness_check)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        health = await client.get("/health")
        first = await client.get("/readiness")
        second = await client.get("/readiness")

    assert health.json() == {"status": "ok"}
    assert first.status_code == 200
    assert first.json()["status"] == "needs_setup"
    assert first.json()["dependencies"]["whisper_model"]["available"] is False
    assert second.json() == first.json()
    assert calls == 1


@pytest.mark.anyio
async def test_default_readiness_checks_every_phase_one_local_dependency() -> None:
    app = create_app(Settings(_env_file=None))
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get("/readiness")

    payload = response.json()
    assert payload["status"] in {"ready", "needs_setup"}
    assert set(payload["dependencies"]) == {
        "ffmpeg",
        "ffprobe",
        "whisper_model",
        "ollama",
    }
    for dependency in payload["dependencies"].values():
        assert isinstance(dependency["available"], bool)
        assert dependency["message"]
