from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import health, inspections, templates
from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.logging import configure_logging, get_logger
from app.storage.local import LocalStorage


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    log = get_logger(__name__)

    app = FastAPI(
        title="Drone Inspection Reporting API",
        version="0.1.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    storage = LocalStorage(settings.storage_dir)
    app.dependency_overrides[LocalStorage] = lambda: storage

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(templates.router)
    app.include_router(inspections.router)

    log.info(
        "app.start",
        storage_dir=str(settings.storage_dir),
        templates_dir=str(settings.templates_dir),
        whisper_endpoint=settings.azure_openai_whisper_endpoint,
        whisper_deployment=settings.azure_openai_whisper_deployment,
        gpt_endpoint=settings.azure_openai_gpt_endpoint,
        gpt_deployment=settings.azure_openai_gpt_deployment,
    )
    return app


app = create_app()
