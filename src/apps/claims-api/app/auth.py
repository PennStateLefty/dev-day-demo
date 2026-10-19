from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

import jwt
from jwt import PyJWKClient
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .settings import Settings

logger = logging.getLogger(__name__)


class EntraTokenValidator:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.issuer = f"https://login.microsoftonline.com/{settings.tenant_id}/v2.0"
        self.keys = PyJWKClient(
            f"https://login.microsoftonline.com/{settings.tenant_id}/discovery/v2.0/keys",
            timeout=10,
        )

    def __call__(self, token: str) -> dict[str, Any]:
        if jwt.get_unverified_header(token).get("alg") != "RS256":
            raise jwt.InvalidAlgorithmError("Only RS256 bearer tokens are accepted.")
        key = self.keys.get_signing_key_from_jwt(token).key
        return jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            issuer=[
                self.issuer,
                f"https://sts.windows.net/{self.settings.tenant_id}/",
            ],
            options={
                "verify_aud": False,
                "require": ["exp", "iss", "tid"],
            },
        )


class EntraAuthMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        settings: Settings,
        validate: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.app = app
        self.settings = settings
        self.validate = validate or EntraTokenValidator(settings)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        protected = any(
            path == prefix or path.startswith(prefix + "/")
            for prefix in ("/api", "/mcp", "/docs", "/redoc", "/openapi.json", "/ready")
        )
        if scope["type"] != "http" or not protected:
            await self.app(scope, receive, send)
            return
        headers = [
            value.decode("latin1")
            for key, value in scope.get("headers", [])
            if key.lower() == b"authorization"
        ]
        scheme, _, token = headers[0].partition(" ") if len(headers) == 1 else ("", "", "")
        if scheme.casefold() != "bearer" or not 1 <= len(token) <= 16384:
            await self._reject(401, scope, receive, send)
            return
        try:
            claims = await run_in_threadpool(self.validate, token)
        except jwt.PyJWKClientConnectionError:
            logger.error("Entra signing-key discovery unavailable.")
            await self._reject(503, scope, receive, send)
            return
        except (jwt.InvalidTokenError, jwt.PyJWKClientError):
            logger.warning("Rejected invalid API bearer token.")
            await self._reject(401, scope, receive, send)
            return
        if claims.get("tid") != self.settings.tenant_id:
            logger.warning("Rejected bearer token from another tenant.")
            await self._reject(403, scope, receive, send)
            return
        await self.app(scope, receive, send)

    async def _reject(self, status: int, scope: Scope, receive: Receive, send: Send) -> None:
        detail = {
            401: "A valid Entra bearer token is required.",
            403: "The caller does not have permission to invoke claims tools.",
            503: "Authentication service is temporarily unavailable.",
        }[status]
        response = JSONResponse(
            {"detail": detail},
            status_code=status,
            headers={"WWW-Authenticate": "Bearer"} if status == 401 else None,
        )
        await response(scope, receive, send)
