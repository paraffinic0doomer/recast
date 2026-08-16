"""Shared-secret gate for a publicly reachable instance.

When the pipeline runs on a laptop and is exposed through a tunnel so a hosted
frontend can reach it, the API is on the open internet. Without a gate anyone
who learns the URL can list every project, download the source videos and the
rendered clips, and start new uploads that spend the owner's API tokens.

Set ACCESS_KEY to require a secret on every request. Leaving it unset keeps
local development exactly as it was, which is the common case.

Two ways to present the key, because browsers do not let a <video src> or an
<img src> carry custom headers:

  * ``X-Access-Key`` header  -- used by fetch() for the JSON API
  * ``?k=`` query parameter -- used by media URLs

Health stays open so a monitor can check liveness; it exposes no user content.
"""

import hmac
import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

HEADER_NAME = "x-access-key"
QUERY_NAME = "k"
# Liveness only. Reports no project data, so it is safe to leave reachable.
PUBLIC_PATHS = frozenset({"/api/health", "/docs", "/openapi.json", "/redoc"})


def _presented(request: Request) -> str:
    return request.headers.get(HEADER_NAME) or request.query_params.get(QUERY_NAME, "")


class AccessKeyMiddleware(BaseHTTPMiddleware):
    """Reject anything that cannot present the shared secret."""

    def __init__(self, app, access_key: str) -> None:
        super().__init__(app)
        self._key = access_key

    async def dispatch(self, request: Request, call_next):
        # Preflight carries no custom headers by design; the real request that
        # follows is still checked, so allowing OPTIONS is safe.
        if request.method == "OPTIONS" or request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # compare_digest keeps the check constant-time.
        if not hmac.compare_digest(_presented(request), self._key):
            logger.warning(
                "Rejected unauthenticated %s %s", request.method, request.url.path
            )
            return JSONResponse(
                {"detail": "Access key required."}, status_code=401
            )

        return await call_next(request)
