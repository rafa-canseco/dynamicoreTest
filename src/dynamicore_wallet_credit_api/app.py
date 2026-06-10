from fastapi import FastAPI

from dynamicore_wallet_credit_api.api.health import router as health_router
from dynamicore_wallet_credit_api.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)

    app.include_router(health_router)

    return app
