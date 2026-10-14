from __future__ import annotations

from unittest.mock import Mock

import pytest
from app import main
from app.auth import EntraAuthMiddleware
from app.search_rest import KnowledgeError
from app.settings import Settings
from fastapi.testclient import TestClient

SETTINGS = Settings(
    mode="azure",
    tenant_id="00000000-0000-0000-0000-000000000001",
    audience="00000000-0000-0000-0000-000000000002",
    client_ids=("00000000-0000-0000-0000-000000000003",),
)


def test_mounted_http_mcp_is_protected_not_just_rest() -> None:
    wrapper = EntraAuthMiddleware(main.app, SETTINGS, validate=Mock())
    with TestClient(wrapper) as client:
        response = client.post(
            "/mcp/",
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {},
            },
        )
    assert response.status_code == 401


def test_cloud_dependency_failure_cannot_return_fixture_success(monkeypatch) -> None:
    service = Mock()
    service.lookup_policy.side_effect = KnowledgeError("internal dependency details")
    monkeypatch.setattr(main, "service", service)
    with TestClient(main.app) as client:
        response = client.get(
            "/api/policies/pol-demo-auto/lookup", params={"query": "animal strikes"}
        )
    assert response.status_code == 503
    assert "no fixture fallback" in response.json()["detail"]
    assert "internal dependency" not in response.text


def test_cloud_mode_does_not_offer_the_fixture_orchestrator(monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", SETTINGS)
    with TestClient(main.app) as client:
        response = client.post("/api/claims/clm-demo-001/workflow")
    assert response.status_code == 409


def test_public_auth_configuration_only_exposes_selected_nonsecret_browser_settings(
    monkeypatch,
) -> None:
    from dataclasses import replace

    monkeypatch.setattr(main, "settings", replace(SETTINGS, ui_client_id=SETTINGS.client_ids[0]))
    with TestClient(main.app) as client:
        response = client.get("/auth-config")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    assert response.json() == {
        "mode": "azure",
        "tenantId": SETTINGS.tenant_id,
        "clientId": SETTINGS.client_ids[0],
        "scope": f"api://{SETTINGS.audience}/claims.invoke",
    }


def test_local_browser_configuration_cannot_claim_cloud_authentication(monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", Settings())
    with TestClient(main.app) as client:
        assert client.get("/auth-config").json() == {"mode": "local"}


def test_empty_cloud_seed_is_unready_not_healthy(monkeypatch) -> None:
    runtime = Mock()
    runtime.probe.side_effect = RuntimeError("SQL is empty")
    monkeypatch.setattr(main, "runtime", runtime)
    with TestClient(main.app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").status_code == 503


@pytest.mark.asyncio
async def test_bounded_history_tool_preserves_human_review() -> None:
    from fastmcp import Client

    async with Client(main.mcp) as client:
        result = await client.call_tool(
            "synthetic_customer_history", {"customer_id": "cust-demo-one"}
        )
    assert result.data["humanReviewRequired"] is True
    assert len(result.data["claims"]) == 2
