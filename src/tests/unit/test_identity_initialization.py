from __future__ import annotations

import copy
from datetime import date
from unittest.mock import Mock
from uuid import UUID

import httpx
import pytest
from initialize_identity import Graph, identity_plan, initialize, matches, mutation_gate

VALUES = {
    "AZURE_ENV_NAME": "claims-demo",
    "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000001",
    "AZURE_SUBSCRIPTION_ID": "00000000-0000-0000-0000-000000000002",
}
REDIRECT = "https://ca-claims-demo.example.azurecontainerapps.io/"


def test_registration_plan_is_secretless_single_tenant_and_least_privilege() -> None:
    plan = identity_plan(VALUES, REDIRECT)
    assert plan == identity_plan(VALUES, REDIRECT)
    assert UUID(plan["scopeId"]) != UUID(plan["api"]["appRoles"][0]["id"])
    permission_values = [
        permission["value"].casefold()
        for permission in (
            plan["api"]["appRoles"] + plan["api"]["api"]["oauth2PermissionScopes"]
        )
    ]
    assert len(permission_values) == len(set(permission_values))
    assert plan["api"]["signInAudience"] == plan["spa"]["signInAudience"] == "AzureADMyOrg"
    assert plan["api"]["api"]["requestedAccessTokenVersion"] == 2
    assert plan["api"]["requiredResourceAccess"] == []
    assert plan["api"]["appRoles"][0]["allowedMemberTypes"] == ["Application"]
    assert plan["api"]["api"]["oauth2PermissionScopes"][0]["type"] == "Admin"
    assert plan["spa"]["spa"]["redirectUris"] == [REDIRECT]
    assert "passwordCredentials" not in plan["api"]
    assert plan["marker"] != identity_plan(VALUES | {"AZURE_ENV_NAME": "another"})["marker"]
    assert identity_plan(VALUES)["spa"]["spa"]["redirectUris"] == []


@pytest.mark.parametrize(
    "redirect",
    [
        "http://demo.azurecontainerapps.io/",
        "https://attacker.example/",
        "https://demo.azurecontainerapps.io.attacker.example/",
        "https://demo.azurecontainerapps.io/?token=secret",
        "https://demo.azurecontainerapps.io/callback",
        "https://user:pass@demo.azurecontainerapps.io/",
    ],
)
def test_redirect_registration_cannot_accept_unrelated_hosts_or_urls(redirect) -> None:
    with pytest.raises(ValueError):
        identity_plan(VALUES, redirect)


def test_identity_mutations_need_owner_and_future_expiry_without_cost_flag() -> None:
    complete = {
        "SECURITY_EXCEPTION_OWNER": "synthetic-operator",
        "SECURITY_EXCEPTION_EXPIRES_ON": "2026-11-01",
    }
    mutation_gate(complete, date(2026, 10, 14))
    for key in complete:
        with pytest.raises(ValueError):
            mutation_gate(complete | {key: ""}, date(2026, 10, 14))
    with pytest.raises(ValueError):
        mutation_gate(complete, date(2026, 11, 1))


def test_graph_replay_checks_ownership_and_drift_without_overwriting() -> None:
    body = identity_plan(VALUES, REDIRECT)["api"]
    existing = body | {
        "id": "00000000-0000-0000-0000-000000000003",
        "appId": "00000000-0000-0000-0000-000000000004",
    }
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={"value": [existing]})

    with httpx.Client(
        base_url="https://graph.microsoft.com", transport=httpx.MockTransport(handler)
    ) as http:
        graph = Graph(http)
        assert graph.application(body)["appId"] == existing["appId"]
        existing["notes"] = "belongs-to-another-project"
        with pytest.raises(ValueError, match="drifted"):
            graph.application(body)
    assert all(request.method == "GET" for request in calls)
    assert matches({"serverGenerated": True, "api": body["api"]}, {"api": body["api"]})


def test_initialization_has_no_consent_guest_or_role_assignment_operations() -> None:
    plan = identity_plan(VALUES, REDIRECT)
    graph = Mock()
    api_id = "00000000-0000-0000-0000-000000000003"
    spa_id = "00000000-0000-0000-0000-000000000004"
    graph.application.side_effect = [
        {"id": api_id, "appId": api_id, "identifierUris": []},
        {"id": spa_id, "appId": spa_id},
    ]
    outputs = initialize(graph, plan)
    assert outputs["CLAIMS_API_AUDIENCE"] == api_id
    assert outputs["CLAIMS_UI_CLIENT_ID"] == outputs["CLAIMS_API_CLIENT_IDS"] == spa_id
    graph.request.assert_called_once_with(
        "PATCH", f"/v1.0/applications/{api_id}", {"identifierUris": [f"api://{api_id}"]}
    )
    assert graph.application.call_args.args[0]["requiredResourceAccess"] == [
        {
            "resourceAppId": api_id,
            "resourceAccess": [{"id": plan["scopeId"], "type": "Scope"}],
        }
    ]
    assert graph.principal.call_count == 2


def test_only_initial_empty_redirect_can_be_completed_without_replacing_existing_uri() -> None:
    plan = identity_plan(VALUES, REDIRECT)
    existing = copy.deepcopy(plan["spa"]) | {
        "id": "00000000-0000-0000-0000-000000000005",
        "appId": "00000000-0000-0000-0000-000000000006",
    }
    existing["spa"]["redirectUris"] = []
    graph = Graph(Mock())
    graph.request = Mock(return_value={"value": [existing]})
    graph.application(plan["spa"])
    assert graph.request.call_args.args == (
        "PATCH",
        f"/v1.0/applications/{existing['id']}",
        {"spa": {"redirectUris": [REDIRECT]}},
    )
    existing["spa"]["redirectUris"] = ["https://another.azurecontainerapps.io/"]
    graph.request.reset_mock(return_value=True)
    graph.request.return_value = {"value": [existing]}
    with pytest.raises(ValueError, match="drifted"):
        graph.application(plan["spa"])
    assert graph.request.call_count == 1
