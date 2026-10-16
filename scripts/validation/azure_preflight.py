"""Read-only deployment gates. Never changes Azure context or creates resources."""

from __future__ import annotations

import argparse
import ipaddress
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

REQUIRED = (
    "AZURE_ENV_NAME",
    "AZURE_TENANT_ID",
    "AZURE_SUBSCRIPTION_ID",
    "AZURE_LOCATION",
    "AZURE_OPERATOR_PRINCIPAL_ID",
    "AZURE_SQL_ADMINISTRATOR_NAME",
    "AZURE_APIM_PUBLISHER_NAME",
    "AZURE_APIM_PUBLISHER_EMAIL",
    "SECURITY_EXCEPTION_OWNER",
    "SECURITY_EXCEPTION_EXPIRES_ON",
    "CLAIMS_API_AUDIENCE",
    "CLAIMS_API_CLIENT_IDS",
    "FOUNDRY_PROJECT_CLIENT_ID",
    "CLAIMS_UI_CLIENT_ID",
)
RESOURCE_TYPES = {
    "Microsoft.App": "managedEnvironments",
    "Microsoft.ApiManagement": "service",
    "Microsoft.ApiCenter": "services",
    "Microsoft.CognitiveServices": "accounts",
    "Microsoft.Search": "searchServices",
    "Microsoft.Sql": "servers",
    "Microsoft.Storage": "storageAccounts",
    "Microsoft.ContainerRegistry": "registries",
    "Microsoft.OperationalInsights": "workspaces",
    "Microsoft.Insights": "components",
    "Microsoft.ManagedIdentity": "userAssignedIdentities",
    "Microsoft.Network": "networkSecurityPerimeters",
}
MODELS = (
    ("gpt-4.1-mini", "2025-04-14", "agentsV2", "OpenAI.GlobalStandard.gpt4.1-mini"),
    ("text-embedding-3-small", "1", "embeddings", "OpenAI.GlobalStandard.text-embedding-3-small"),
)
DEPLOYMENT_NAMES = {
    "gpt-4.1-mini": "claims-chat",
    "text-embedding-3-small": "claims-embedding",
}


class PreflightError(Exception):
    """An explicit configuration, CLI or capability failure."""


def configuration_errors(values: Mapping[str, str], today: date | None = None) -> list[str]:
    errors = [f"Missing {key}." for key in REQUIRED if not values.get(key, "").strip()]
    mode = values.get("AZURE_NETWORK_MODE", "enforced-perimeter")
    if mode not in ("enforced-perimeter", "public-demo"):
        errors.append("AZURE_NETWORK_MODE must be enforced-perimeter or public-demo.")
    if mode == "enforced-perimeter" and not values.get("AZURE_OPERATOR_IPV4_CIDR", "").strip():
        errors.append("Missing AZURE_OPERATOR_IPV4_CIDR.")
    for key in (
        "AZURE_TENANT_ID",
        "AZURE_SUBSCRIPTION_ID",
        "AZURE_OPERATOR_PRINCIPAL_ID",
        "CLAIMS_API_AUDIENCE",
        "FOUNDRY_PROJECT_CLIENT_ID",
        "CLAIMS_UI_CLIENT_ID",
    ):
        if values.get(key):
            try:
                UUID(values[key])
            except ValueError:
                errors.append(f"{key} must be a UUID.")
    if values.get("CLAIMS_API_CLIENT_IDS"):
        try:
            for client_id in values["CLAIMS_API_CLIENT_IDS"].split(","):
                UUID(client_id.strip())
        except ValueError:
            errors.append("CLAIMS_API_CLIENT_IDS must contain comma-separated caller client UUIDs.")
        if values.get("CLAIMS_UI_CLIENT_ID", "").lower() not in {
            item.strip().lower() for item in values["CLAIMS_API_CLIENT_IDS"].split(",")
        }:
            errors.append(
                "CLAIMS_UI_CLIENT_ID must be explicitly allowed in CLAIMS_API_CLIENT_IDS."
            )
    if values.get("AZURE_ENV_NAME") and not re.fullmatch(
        r"[a-z][a-z0-9-]{0,31}", values["AZURE_ENV_NAME"]
    ):
        errors.append("AZURE_ENV_NAME must be 1-32 lowercase letters, digits or hyphens.")
    if values.get("AZURE_LOCATION") and not re.fullmatch(r"[a-z0-9]+", values["AZURE_LOCATION"]):
        errors.append("AZURE_LOCATION must be an ARM region name such as centralus.")
    if values.get("AZURE_OPERATOR_IPV4_CIDR"):
        try:
            network = ipaddress.ip_network(values["AZURE_OPERATOR_IPV4_CIDR"], strict=True)
            if network.version != 4 or network.prefixlen != 32 or not network.is_global:
                raise ValueError("not a public IPv4 /32")
        except ValueError:
            errors.append("AZURE_OPERATOR_IPV4_CIDR must be one public IPv4 /32, not a range.")
    expiry = values.get("SECURITY_EXCEPTION_EXPIRES_ON", "")
    if expiry:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", expiry):
                raise ValueError("not YYYY-MM-DD")
            if date.fromisoformat(expiry) <= (today or datetime.now(UTC).date()):
                errors.append("The security exception deadline must be in the future.")
        except ValueError:
            errors.append("SECURITY_EXCEPTION_EXPIRES_ON must be a valid YYYY-MM-DD.")
    if values.get("AZURE_SQL_ADMINISTRATOR_TYPE", "User") not in ("User", "Group", "Application"):
        errors.append("AZURE_SQL_ADMINISTRATOR_TYPE must be User, Group or Application.")
    email = values.get("AZURE_APIM_PUBLISHER_EMAIL")
    if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        errors.append("AZURE_APIM_PUBLISHER_EMAIL must be an email address.")
    return errors


def az_json(arguments: list[str]) -> Any:
    try:
        process = subprocess.run(
            ["az", *arguments, "--output", "json", "--only-show-errors"],
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise PreflightError(f"Azure CLI could not complete {arguments[0]}.") from error
    if process.returncode:
        # These calls read metadata only; never call token/key commands or enable debug logging.
        raise PreflightError(
            f"Azure CLI {arguments[0]} failed ({process.returncode}): {process.stderr.strip()}"
        )
    try:
        return json.loads(process.stdout)
    except json.JSONDecodeError as error:
        raise PreflightError(f"Azure CLI {arguments[0]} returned invalid JSON.") from error


def check_account(account: Mapping[str, Any], values: Mapping[str, str]) -> None:
    if (
        account.get("id") != values["AZURE_SUBSCRIPTION_ID"]
        or account.get("tenantId") != values["AZURE_TENANT_ID"]
        or account.get("state") != "Enabled"
    ):
        raise PreflightError("The requested subscription is disabled or belongs to another tenant.")


def check_offerings(offerings: Mapping[str, Any], location: str) -> None:
    for region in offerings.get("regions", []):
        region_name = region.get("regionName", "").replace(" ", "").lower()
        if region_name != location:
            continue
        skus = {sku.get("name") or sku.get("sku", {}).get("name") for sku in region.get("skus", [])}
        if "basic" in skus:
            return
        raise PreflightError(f"Search Basic is not offered in {location}.")
    raise PreflightError(f"Search did not advertise region {location}.")


def check_providers(providers: list[dict[str, Any]], location: str) -> None:
    indexed = {provider["namespace"].casefold(): provider for provider in providers}
    failures = []
    for namespace, resource_type in RESOURCE_TYPES.items():
        provider = indexed.get(namespace.casefold(), {})
        if provider.get("registrationState") != "Registered":
            failures.append(f"{namespace} is not registered")
            continue
        matching = [
            item
            for item in provider.get("resourceTypes", [])
            if item.get("resourceType", "").casefold() == resource_type.casefold()
        ]
        locations = {
            region.replace(" ", "").lower()
            for item in matching
            for region in item.get("locations", [])
        }
        if location not in locations:
            failures.append(f"{namespace}/{resource_type} does not list {location}")
    if failures:
        raise PreflightError("; ".join(failures))


def check_models(
    models: list[dict[str, Any]],
    quotas: list[dict[str, Any]],
    existing_deployments: list[dict[str, Any]] | None = None,
) -> None:
    for name, version, capability, quota_name in MODELS:
        matching = [
            item["model"]
            for item in models
            if item.get("model", {}).get("name") == name and item["model"].get("version") == version
        ]
        if not any(
            str(model.get("capabilities", {}).get(capability)).lower() == "true"
            and any(sku.get("name") == "GlobalStandard" for sku in model.get("skus", []))
            for model in matching
        ):
            raise PreflightError(f"{name} {version} lacks the required capability or SKU.")
        quota = next(
            (item for item in quotas if item.get("name", {}).get("value") == quota_name), None
        )
        if quota is None:
            raise PreflightError(f"No quota record for {name}; capacity cannot be assumed.")
        allocated = sum(
            deployment.get("sku", {}).get("capacity", 0)
            for deployment in existing_deployments or []
            if deployment.get("name") == DEPLOYMENT_NAMES[name]
            and deployment.get("sku", {}).get("name") == "GlobalStandard"
            and deployment.get("properties", {}).get("provisioningState") == "Succeeded"
            and deployment["properties"].get("model", {}).get("name") == name
            and deployment["properties"]["model"].get("version") == version
        )
        credit = min(10, quota["currentValue"], allocated)
        if quota["limit"] - quota["currentValue"] + credit < 10:
            raise PreflightError(
                f"Insufficient quota for the requested 10 capacity units of {name}."
            )


def cloud_checks(
    values: Mapping[str, str], run: Callable[[list[str]], Any] = az_json
) -> list[dict[str, Any]]:
    subscription = values["AZURE_SUBSCRIPTION_ID"]
    location = values["AZURE_LOCATION"]
    checks = []

    def execute(name: str, action: Callable[[], None]) -> bool:
        try:
            action()
        except PreflightError as error:
            checks.append({"name": name, "passed": False, "detail": str(error)})
            return False
        checks.append({"name": name, "passed": True})
        return True

    if not execute(
        "azure-context",
        lambda: check_account(run(["account", "show", "--subscription", subscription]), values),
    ):
        return checks
    execute(
        "providers-and-regions",
        lambda: check_providers(
            run(["provider", "list", "--subscription", subscription]), location
        ),
    )
    execute(
        "search-basic-offerings",
        lambda: check_offerings(
            run(
                [
                    "rest",
                    "--subscription",
                    subscription,
                    "--method",
                    "post",
                    "--url",
                    "https://management.azure.com/providers/Microsoft.Search/"
                    "fetchOfferings?api-version=2026-09-01-preview",
                ]
            ),
            location,
        ),
    )

    def models_and_quota() -> None:
        existing = []
        if values.get("AZURE_AI_ACCOUNT_NAME") and values.get("AZURE_RESOURCE_GROUP"):
            existing = run(
                [
                    "cognitiveservices",
                    "account",
                    "deployment",
                    "list",
                    "--subscription",
                    subscription,
                    "--resource-group",
                    values["AZURE_RESOURCE_GROUP"],
                    "--name",
                    values["AZURE_AI_ACCOUNT_NAME"],
                ]
            )
        check_models(
            run(
                [
                    "cognitiveservices",
                    "model",
                    "list",
                    "--subscription",
                    subscription,
                    "--location",
                    location,
                ]
            ),
            run(
                [
                    "cognitiveservices",
                    "usage",
                    "list",
                    "--subscription",
                    subscription,
                    "--location",
                    location,
                ]
            ),
            existing,
        )

    execute("models-and-quota", models_and_quota)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--configuration-only", action="store_true", help="No Azure calls.")
    arguments = parser.parse_args()
    errors = configuration_errors(os.environ)
    checks = [{"name": "configuration", "passed": not errors, "errors": errors}]
    if not errors and not arguments.configuration_only:
        try:
            checks.extend(cloud_checks(os.environ))
        except (KeyError, TypeError, ValueError) as error:
            checks.append(
                {
                    "name": "azure-response-schema",
                    "passed": False,
                    "detail": f"Unexpected Azure metadata shape: {type(error).__name__}.",
                }
            )
    passed = all(item["passed"] for item in checks)
    print(
        json.dumps(
            {
                "scope": "platform-provisioning-preflight",
                "passed": passed,
                "live_metadata_checked": not errors and not arguments.configuration_only,
                "checks": checks,
                "limitations": [
                    "Metadata does not prove live service capacity or perimeter compatibility.",
                    "ARM what-if and live identity/network smoke tests are still required.",
                    "Application deployment is separate; agent connections remain unwired.",
                ],
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
