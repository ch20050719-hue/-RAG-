import asyncio

from starlette.responses import Response

import app.middleware.rate_limit_middleware as rate_module
from app.middleware.rate_limit_middleware import RateLimitMiddleware, RateLimitTier


def _middleware() -> RateLimitMiddleware:
    async def app(scope, receive, send):
        return None

    return RateLimitMiddleware(app)


def test_sliding_window_keeps_full_hour_history(monkeypatch):
    async def scenario():
        middleware = _middleware()
        tier = RateLimitTier(requests_per_minute=100, requests_per_hour=2)
        clock = [0.0]
        monkeypatch.setattr(rate_module.time, "time", lambda: clock[0])

        assert await middleware._check_sliding_window("user:1", tier) == (True, 0)
        clock[0] = 61.0
        assert await middleware._check_sliding_window("user:1", tier) == (True, 0)
        clock[0] = 62.0
        allowed, retry_after = await middleware._check_sliding_window("user:1", tier)

        assert allowed is False
        assert retry_after > 0

    asyncio.run(scenario())


def test_excluded_paths_match_segment_boundary_only():
    middleware = _middleware()

    assert middleware._is_excluded_path("/health", "GET") is True
    assert middleware._is_excluded_path("/api/v1/agent-task/status/123", "GET") is True
    assert middleware._is_excluded_path("/healthcheck-sensitive", "GET") is False


def test_rate_limit_response_does_not_expose_internal_identity_key():
    middleware = _middleware()
    tier = RateLimitTier(requests_per_minute=1, requests_per_hour=2)

    response = middleware._rate_limit_response(10, "user:sensitive-id", tier)
    normal_response = Response()
    middleware._add_rate_limit_headers(normal_response, "user:sensitive-id", tier)

    assert "X-RateLimit-Key" not in response.headers
    assert "X-RateLimit-Key" not in normal_response.headers
    assert b"sensitive-id" not in response.body
