from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock

import jwt
import pytest
from app.auth import EntraAuthMiddleware, EntraTokenValidator
from app.settings import Settings
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import FastAPI
from fastapi.testclient import TestClient

SETTINGS = Settings(
    mode="azure",
    tenant_id="00000000-0000-0000-0000-000000000001",
    audience="00000000-0000-0000-0000-000000000002",
    client_ids=("00000000-0000-0000-0000-000000000003",),
)


def claims() -> dict:
    now = datetime.now(UTC)
    return {
        "aud": SETTINGS.audience,
        "iss": f"https://login.microsoftonline.com/{SETTINGS.tenant_id}/v2.0",
        "tid": SETTINGS.tenant_id,
        "azp": SETTINGS.client_ids[0],
        "ver": "2.0",
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=5),
        "roles": ["Claims.Invoke.Application"],
    }


def client(validate) -> TestClient:
    application = FastAPI()
    application.add_middleware(EntraAuthMiddleware, settings=SETTINGS, validate=validate)

    @application.api_route("/{path:path}", methods=["GET", "POST", "DELETE"])
    def endpoint(path: str):
        return {"path": path}

    return TestClient(application)


@pytest.mark.parametrize(
    "path",
    [
        "/api/claims",
        "/mcp",
        "/mcp/",
        "/docs",
        "/openapi.json",
        "/ready",
    ],
)
def test_every_business_and_mcp_http_surface_requires_authentication(path: str) -> None:
    validate = Mock()
    with client(validate) as http:
        response = http.get(path)
    assert response.status_code == 401
    validate.assert_not_called()


def test_public_liveness_and_ui_are_accessible_without_data_access() -> None:
    with client(Mock()) as http:
        assert http.get("/health").status_code == 200
        assert http.get("/").status_code == 200


@pytest.mark.parametrize(
    "change",
    [
        {"tid": "another-tenant"},
        {"azp": "another-client"},
        {"ver": "1.0"},
        {"roles": []},
        {"roles": "Claims.Invoke.Application"},
        {"scp": "claims.read", "roles": []},
    ],
)
def test_wrong_tenant_client_or_permission_is_denied(change: dict) -> None:
    with client(lambda token: claims() | change) as http:
        assert http.get("/api/claims", headers={"Authorization": "Bearer token"}).status_code == 403


@pytest.mark.parametrize(
    "permission",
    [
        {"roles": ["Claims.Invoke.Application"]},
        {
            "roles": [],
            "scp": "openid claims.invoke",
        },
    ],
)
def test_authorized_application_or_delegated_call(permission: dict) -> None:
    with client(lambda token: claims() | permission) as http:
        assert http.post("/mcp/", headers={"Authorization": "Bearer token"}).status_code == 200


def test_key_discovery_failure_is_unavailable_not_authenticated() -> None:
    def unavailable(token: str) -> dict:
        raise jwt.PyJWKClientConnectionError("network failure")

    with client(unavailable) as http:
        response = http.get("/api/claims", headers={"Authorization": "Bearer token"})
    assert response.status_code == 503
    assert "network failure" not in response.text


def test_actual_signature_issuer_audience_and_expiry_validation() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    validator = EntraTokenValidator(SETTINGS)
    validator.keys = Mock()
    validator.keys.get_signing_key_from_jwt.return_value = SimpleNamespace(key=key.public_key())
    assert validator(jwt.encode(claims(), key, algorithm="RS256"))["tid"] == SETTINGS.tenant_id
    for change in (
        {"iss": "https://attacker.example"},
        {"aud": "wrong"},
        {"exp": datetime.now(UTC) - timedelta(minutes=1)},
        {"nbf": datetime.now(UTC) + timedelta(minutes=5)},
    ):
        with pytest.raises(jwt.InvalidTokenError):
            validator(jwt.encode(claims() | change, key, algorithm="RS256"))
    with pytest.raises(jwt.InvalidTokenError):
        validator(jwt.encode(claims(), "not-an-RSA-key-but-at-least-32-bytes", algorithm="HS256"))
