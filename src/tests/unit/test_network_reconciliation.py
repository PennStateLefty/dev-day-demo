from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest
from reconcile_networking import association_ids, perimeter_exists, reconcile

PERIMETER = (
    "/subscriptions/demo/resourceGroups/demo/providers/Microsoft.Network/"
    "networkSecurityPerimeters/demo"
)
STORAGE = "/subscriptions/demo/resourceGroups/demo/providers/Microsoft.Storage/storageAccounts/demo"


def association(resource: str = STORAGE, identifier: str | None = None) -> dict:
    return {
        "id": identifier or PERIMETER + "/resourceAssociations/resource-1",
        "properties": {"privateLinkResource": {"id": resource}},
    }


def test_retirement_is_limited_to_this_perimeter_and_its_exact_resources() -> None:
    expected = [PERIMETER + "/resourceAssociations/resource-1"]
    assert association_ids(PERIMETER, {STORAGE}, [association()]) == expected
    assert association_ids(PERIMETER, {STORAGE}, []) == []
    for item in (
        association(resource=STORAGE + "-unrelated"),
        association(identifier=PERIMETER + "-other/resourceAssociations/resource-1"),
        association(identifier=PERIMETER + "/resourceAssociations/unrecognized"),
        association(identifier=PERIMETER + "/resourceAssociations/nested/resource-1"),
    ):
        with pytest.raises(ValueError, match="Unexpected perimeter membership"):
            association_ids(PERIMETER, {STORAGE}, [item])


def test_enforced_mode_never_deletes_or_calls_azure() -> None:
    with (
        patch("reconcile_networking.az_json") as read,
        patch("reconcile_networking.subprocess.run") as mutate,
    ):
        reconcile({})
    read.assert_not_called()
    mutate.assert_not_called()


def test_unvalidated_public_mode_never_mutates() -> None:
    with patch("reconcile_networking.subprocess.run") as mutate:
        with pytest.raises(ValueError, match="successfully deployed"):
            reconcile({"AZURE_NETWORK_MODE": "public-demo"})
    mutate.assert_not_called()


@pytest.mark.parametrize("already_retired", [False, True])
def test_public_reconciliation_is_scoped_and_idempotent(already_retired: bool) -> None:
    values = {
        "AZURE_NETWORK_MODE": "public-demo",
        "AZURE_DEPLOYED_NETWORK_MODE": "public-demo",
        "AZURE_SUBSCRIPTION_ID": "demo",
        "AZURE_TENANT_ID": "tenant",
        "AZURE_RESOURCE_GROUP": "demo",
        "AZURE_ENV_NAME": "claims-demo",
        "AZURE_SQL_SERVER": "demo.database.windows.net",
        "AZURE_STORAGE_ACCOUNT_NAME": "demo",
        "AZURE_SEARCH_SERVICE_NAME": "demo",
        "AZURE_AI_ACCOUNT_NAME": "demo",
        "AZURE_NETWORK_SECURITY_PERIMETER_NAME": "demo",
    }
    reads = [
        {"id": "demo", "tenantId": "tenant", "state": "Enabled"},
        {
            "id": "/subscriptions/demo/resourceGroups/demo",
            "tags": {"azd-env-name": "claims-demo", "application": "synthetic-claims-demo"},
        },
        *[{"properties": {"publicNetworkAccess": "Enabled"}} for _ in range(4)],
        {"value": [association()]},
        {"value": []},
    ]
    with (
        patch("reconcile_networking.az_json", side_effect=reads),
        patch("reconcile_networking.subprocess.run") as mutate,
        patch(
            "reconcile_networking.perimeter_exists",
            side_effect=[False] if already_retired else [True, True, False],
        ),
        patch("reconcile_networking.time.sleep"),
    ):
        reconcile(values)
    if already_retired:
        mutate.assert_not_called()
    else:
        assert mutate.call_count == 2
        assert mutate.call_args_list[0].args[0][4] == PERIMETER + "/resourceAssociations/resource-1"
        assert mutate.call_args_list[1].args[0][4] == PERIMETER


def test_only_authoritative_not_found_is_successful_deletion() -> None:
    with patch("reconcile_networking.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess([], 3, "", "ERROR: (NotFound) deleted")
        assert perimeter_exists(PERIMETER) is False
        run.return_value = subprocess.CompletedProcess([], 0, PERIMETER, "")
        assert perimeter_exists(PERIMETER) is True
        for code, message in (
            (3, "ERROR: (AuthorizationFailed) denied"),
            (1, "ERROR: (NotFound) unrelated CLI failure"),
        ):
            run.return_value = subprocess.CompletedProcess([], code, "", message)
            with pytest.raises(subprocess.CalledProcessError):
                perimeter_exists(PERIMETER)
