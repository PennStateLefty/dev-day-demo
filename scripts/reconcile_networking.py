"""Retire only this demo's NSP after public-demo service settings are deployed."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Mapping
from typing import Any

from validation.azure_preflight import az_json, check_account

API_VERSION = "2024-07-01"


def perimeter_exists(identifier: str) -> bool:
    result = subprocess.run(
        [
            "az",
            "resource",
            "show",
            "--ids",
            identifier,
            "--api-version",
            API_VERSION,
            "--query",
            "id",
            "-o",
            "tsv",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 3 and (
        "(NotFound)" in result.stderr or "(ResourceNotFound)" in result.stderr
    ):
        return False
    print(result.stderr, file=sys.stderr)
    result.check_returncode()
    raise RuntimeError("Unexpected Azure resource lookup result.")


def association_ids(
    perimeter_id: str, expected_resources: set[str], associations: list[dict[str, Any]]
) -> list[str]:
    result = []
    for association in associations:
        resource_id = association["properties"]["privateLinkResource"]["id"]
        identifier = association["id"]
        if (
            resource_id.casefold() not in {item.casefold() for item in expected_resources}
            or identifier.rsplit("/", 1)[0].casefold()
            != perimeter_id.casefold() + "/resourceassociations"
            or identifier.rsplit("/", 1)[-1]
            not in {"resource-0", "resource-1", "resource-2", "resource-3-basic"}
        ):
            raise ValueError("Unexpected perimeter membership; refusing any association deletion.")
        result.append(identifier)
    return result


def reconcile(values: Mapping[str, str]) -> None:
    mode = values.get("AZURE_NETWORK_MODE", "enforced-perimeter")
    if mode == "enforced-perimeter":
        print(json.dumps({"network_mode": mode, "associations_removed": 0}))
        return
    if mode != "public-demo" or values.get("AZURE_DEPLOYED_NETWORK_MODE") != mode:
        raise ValueError("Requested and successfully deployed public-demo modes must match.")
    check_account(az_json(["account", "show"]), values)
    group_id = (
        f"/subscriptions/{values['AZURE_SUBSCRIPTION_ID']}"
        f"/resourceGroups/{values['AZURE_RESOURCE_GROUP']}"
    )
    group = az_json(["group", "show", "--name", values["AZURE_RESOURCE_GROUP"]])
    if (
        group["id"].casefold() != group_id.casefold()
        or group.get("tags", {}).get("azd-env-name") != values["AZURE_ENV_NAME"]
        or group.get("tags", {}).get("application") != "synthetic-claims-demo"
    ):
        raise ValueError("Resource group identity/tags do not match this demo.")
    expected = {
        f"{group_id}/providers/{kind}/{name}"
        for kind, name in (
            ("Microsoft.Sql/servers", values["AZURE_SQL_SERVER"].split(".", 1)[0]),
            ("Microsoft.Storage/storageAccounts", values["AZURE_STORAGE_ACCOUNT_NAME"]),
            ("Microsoft.Search/searchServices", values["AZURE_SEARCH_SERVICE_NAME"]),
            ("Microsoft.CognitiveServices/accounts", values["AZURE_AI_ACCOUNT_NAME"]),
        )
    }
    for resource_id in sorted(expected):
        resource = az_json(["resource", "show", "--ids", resource_id])
        if resource["properties"].get("publicNetworkAccess", "").casefold() != "enabled":
            raise ValueError("Public service settings must deploy before removing NSP membership.")
    perimeter_id = (
        f"{group_id}/providers/Microsoft.Network/networkSecurityPerimeters/"
        f"{values['AZURE_NETWORK_SECURITY_PERIMETER_NAME']}"
    )
    if not perimeter_exists(perimeter_id):
        print(json.dumps({"network_mode": mode, "perimeter_removed": True}))
        return
    url = f"https://management.azure.com{perimeter_id}/resourceAssociations"
    url += f"?api-version={API_VERSION}"
    associations = az_json(["rest", "--method", "get", "--url", url])["value"]
    identifiers = association_ids(perimeter_id, expected, associations)
    for identifier in identifiers:
        subprocess.run(
            ["az", "resource", "delete", "--ids", identifier, "--api-version", API_VERSION],
            check=True,
        )
    for _ in range(60):
        remaining = az_json(["rest", "--method", "get", "--url", url])["value"]
        if not remaining:
            subprocess.run(
                ["az", "resource", "delete", "--ids", perimeter_id, "--api-version", API_VERSION],
                check=True,
            )
            for _ in range(60):
                # ARM collection listings can lag the authoritative resource GET after deletion.
                if not perimeter_exists(perimeter_id):
                    break
                time.sleep(5)
            else:
                raise TimeoutError("NSP deletion did not complete within five minutes.")
            print(
                json.dumps(
                    {
                        "network_mode": mode,
                        "associations_removed": len(identifiers),
                        "perimeter_removed": True,
                    }
                )
            )
            return
        time.sleep(5)
    raise TimeoutError("Demo NSP associations still exist; inspect before retrying.")


if __name__ == "__main__":
    reconcile(os.environ)
