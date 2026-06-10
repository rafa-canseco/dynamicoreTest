from fastapi import FastAPI
from fastapi.testclient import TestClient

from dynamicore_wallet_credit_api.core.rate_limit import InMemoryRateLimitMiddleware


def test_rate_limit_returns_429_after_limit() -> None:
    app = FastAPI()
    app.add_middleware(
        InMemoryRateLimitMiddleware,
        max_requests=2,
        window_seconds=60,
        excluded_paths=("/health",),
    )

    @app.get("/limited")
    def limited() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    assert client.get("/limited").status_code == 200
    assert client.get("/limited").status_code == 200

    limited_response = client.get("/limited")

    assert limited_response.status_code == 429
    assert limited_response.json() == {"detail": "rate limit exceeded"}
    assert limited_response.headers["Retry-After"]


def test_rate_limit_excludes_health_paths() -> None:
    app = FastAPI()
    app.add_middleware(
        InMemoryRateLimitMiddleware,
        max_requests=1,
        window_seconds=60,
        excluded_paths=("/health",),
    )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/health").status_code == 200
