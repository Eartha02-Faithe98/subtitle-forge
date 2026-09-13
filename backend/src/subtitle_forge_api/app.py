"""FastAPI application factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from subtitle_forge_api.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the Subtitle Forge API application."""
    resolved_settings = settings or Settings()
    application = FastAPI(title="Subtitle Forge API")
    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["GET"],
        allow_headers=["Accept", "Content-Type"],
    )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
