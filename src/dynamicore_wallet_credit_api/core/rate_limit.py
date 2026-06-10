from time import monotonic

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        max_requests: int,
        window_seconds: int,
        excluded_paths: tuple[str, ...] = (),
    ) -> None:
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.excluded_paths = excluded_paths
        self._buckets: dict[str, tuple[float, int]] = {}

    async def dispatch(self, request: Request, call_next) -> Response:
        if request.url.path.startswith(self.excluded_paths):
            return await call_next(request)

        client_host = request.client.host if request.client else "unknown"
        now = monotonic()
        window_start, request_count = self._buckets.get(client_host, (now, 0))

        if now - window_start >= self.window_seconds:
            window_start = now
            request_count = 0

        request_count += 1
        self._buckets[client_host] = (window_start, request_count)

        if request_count > self.max_requests:
            retry_after = max(1, int(self.window_seconds - (now - window_start)))
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
                headers={"Retry-After": str(retry_after)},
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, self.max_requests - request_count))
        return response
