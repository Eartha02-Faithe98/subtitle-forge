from fastapi import FastAPI

from subtitle_forge_api.app import create_app
from subtitle_forge_api.settings import Settings


def test_application_factory_returns_fastapi_app() -> None:
    app = create_app(Settings(_env_file=None))

    assert isinstance(app, FastAPI)
    assert app.title == "Subtitle Forge API"
