from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from backend.security import SESSION_COOKIE, get_session, redact_secrets

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path == "/health" or path.startswith("/api/auth"):
            return await call_next(request)
        if path.startswith("/api") or path.startswith("/ws"):
            token = request.cookies.get(SESSION_COOKIE)
            if not get_session(token):
                if path.startswith("/ws"):
                    return JSONResponse({"detail": "unauthorized"}, status_code=401)
                return JSONResponse({"detail": "unauthorized"}, status_code=401)
        return await call_next(request)


class RedactSecretsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.msg = redact_secrets(str(record.msg))
            if record.args:
                record.args = tuple(redact_secrets(str(a)) if isinstance(a, str) else a for a in record.args)
        except Exception:
            pass
        return True


def install_log_redaction() -> None:
    root = logging.getLogger()
    f = RedactSecretsFilter()
    for h in root.handlers:
        h.addFilter(f)
    root.addFilter(f)
