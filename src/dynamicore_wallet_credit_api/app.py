from fastapi import FastAPI

from dynamicore_wallet_credit_api.api.auth import router as auth_router
from dynamicore_wallet_credit_api.api.credits import router as credits_router
from dynamicore_wallet_credit_api.api.health import router as health_router
from dynamicore_wallet_credit_api.api.transactions import router as transactions_router
from dynamicore_wallet_credit_api.api.wallets import router as wallets_router
from dynamicore_wallet_credit_api.core.config import get_settings
from dynamicore_wallet_credit_api.core.rate_limit import InMemoryRateLimitMiddleware


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name)
    app.add_middleware(
        InMemoryRateLimitMiddleware,
        max_requests=settings.rate_limit_requests,
        window_seconds=settings.rate_limit_window_seconds,
        excluded_paths=("/health",),
    )

    app.include_router(auth_router)
    app.include_router(wallets_router)
    app.include_router(transactions_router)
    app.include_router(credits_router)
    app.include_router(health_router)

    return app
