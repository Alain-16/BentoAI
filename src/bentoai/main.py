import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from bentoai.api.deps import SettingsDeps
from bentoai.config import get_settings
from bentoai.shared.database import get_engine
from bentoai.shared.http import get_http_client
from bentoai.api.routes import missions

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

    await get_engine().dispose()
    await get_http_client().aclose()


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

    app.include_router(missions.router, prefix=settings.app.api_prefix)

    @app.get("/health")
    async def health(settings: SettingsDeps) -> dict[str, str]:

        return {
            "status": "ok",
            "environment": settings.app.environment.value,
        }
    return app

app = create_app()