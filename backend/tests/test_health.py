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
async def test_cors_allows_configured_frontend_origin() -> None:
    response = await get_health("http://localhost:3000")

    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


@pytest.mark.anyio
async def test_cors_omits_unconfigured_origin() -> None:
    response = await get_health("https://untrusted.example")

    assert "access-control-allow-origin" not in response.headers
