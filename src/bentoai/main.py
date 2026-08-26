import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from bentoai.api.deps import SettingsDeps
from bentoai.config import get_settings

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):

    settings = get_settings()
    logger.info(
        "Starting %s in %s mode",
        settings.app.name,
        settings.app.environment.value,
    )

    yield

    logger.info("Shutting down %s", settings.app.name)


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app.name,
        debug=settings.app.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.app.debug else None,
        redoc_url=None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.app.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.get("/health")
    async def health(settings: SettingsDeps) -> dict[str, str]:

        return {
            "status": "ok",
            "environment": settings.app.environment.value,
        }
    return app