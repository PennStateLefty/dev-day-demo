"""Plan or create isolated, secretless Entra API/SPA registrations; never grant consent."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import re
import sys
from collections.abc import Mapping
from datetime import UTC, date, datetime
from typing import Any
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

import httpx
from azure.core.exceptions import AzureError
from azure.identity import AzureCliCredential
from validation.azure_preflight import az_json, check_account


def identity_plan(values: Mapping[str, str], redirect_uri: str = "") -> dict[str, Any]:
    tenant = str(UUID(values["AZURE_TENANT_ID"]))
    subscription = str(UUID(values["AZURE_SUBSCRIPTION_ID"]))
    environment = values["AZURE_ENV_NAME"]
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,31}", environment):
        raise ValueError("Invalid environment name.")
    redirect = urlsplit(redirect_uri)
    if redirect_uri and (
        redirect.scheme != "https"
        or not redirect.hostname
        or not redirect.hostname.endswith(".azurecontainerapps.io")
        or redirect.username
        or redirect.password
        or redirect.port not in (None, 443)
        or redirect.path != "/"
        or redirect.query
        or redirect.fragment
    ):
        raise ValueError("The SPA redirect must be the explicit Container App HTTPS root URL.")
    marker = f"synthetic-claims-demo:{tenant}:{subscription}:{environment}"
    suffix = hashlib.sha256(marker.encode()).hexdigest()[:16]
    scope_id = str(uuid5(NAMESPACE_URL, marker + "/claims.invoke"))
    role_id = str(uuid5(NAMESPACE_URL, marker + "/Claims.Invoke.Application"))
    return {
        "marker": marker,
        "scopeId": scope_id,
        "api": {
            "uniqueName": f"synthetic-claims-{suffix}-api",
            "displayName": f"Synthetic Claims {environment} API",
            "notes": marker,
            "signInAudience": "AzureADMyOrg",
            "isFallbackPublicClient": False,
            "api": {
                "requestedAccessTokenVersion": 2,
                "oauth2PermissionScopes": [
                    {
                        "id": scope_id,
                        "value": "claims.invoke",
                        "type": "Admin",
                        "isEnabled": True,
                        "adminConsentDisplayName": "Invoke synthetic claims tools",
                        "adminConsentDescription": (
                            "Read synthetic claims and append review notes; cannot decide or send."
                        ),
                    }
                ],
            },
            "appRoles": [
                {
                    "id": role_id,
                    "value": "Claims.Invoke.Application",
                    "displayName": "Invoke synthetic claims tools",
                    "description": "Bounded synthetic claims access; human review required.",
                    "allowedMemberTypes": ["Application"],
                    "isEnabled": True,
                }
            ],
            "requiredResourceAccess": [],
        },
        "spa": {
            "uniqueName": f"synthetic-claims-{suffix}-spa",
            "displayName": f"Synthetic Claims {environment} Browser",
            "notes": marker,
            "signInAudience": "AzureADMyOrg",
            "isFallbackPublicClient": False,
            "spa": {"redirectUris": [redirect_uri] if redirect_uri else []},
            "web": {
                "implicitGrantSettings": {
                    "enableAccessTokenIssuance": False,
                    "enableIdTokenIssuance": False,
                }
            },
            "appRoles": [],
        },
    }


def matches(actual: object, expected: object) -> bool:
    """Compare declared fields while tolerating Graph's server-generated properties."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and matches(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(matches(left, right) for left, right in zip(actual, expected, strict=True))
        )
    return actual == expected


class Graph:
    def __init__(self, http: httpx.Client) -> None:
        self.http = http

    def request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        response = self.http.request(method, path, json=body, params=params)
        response.raise_for_status()
        if response.status_code == 204:
            return {}
        result = response.json()
        if not isinstance(result, dict):
            raise ValueError("Graph returned a non-object response.")
        return result

    def application(self, body: dict[str, Any]) -> dict[str, Any]:
        result = self.request(
            "GET",
            "/v1.0/applications",
            params={
                "$filter": f"uniqueName eq '{body['uniqueName']}'",
                "$select": (
                    "id,appId,uniqueName,displayName,notes,signInAudience,isFallbackPublicClient,"
                    "api,appRoles,spa,web,requiredResourceAccess,identifierUris,"
                    "passwordCredentials,keyCredentials"
                ),
            },
        )
        found = result.get("value")
        if not isinstance(found, list) or len(found) > 1 or result.get("@odata.nextLink"):
            raise ValueError("Ambiguous or malformed application lookup; no changes made.")
        if found:
            application = found[0]
            desired_redirects = body.get("spa", {}).get("redirectUris", [])
            bootstrap_redirect = desired_redirects and not application.get("spa", {}).get(
                "redirectUris"
            )
            comparable = application | {"spa": body["spa"]} if bootstrap_redirect else application
            if (
                not matches(comparable, body)
                or application.get("passwordCredentials")
                or application.get("keyCredentials")
            ):
                raise ValueError("Existing demo registration drifted; refusing to overwrite it.")
            if bootstrap_redirect:
                object_id = str(UUID(application["id"]))
                self.request("PATCH", f"/v1.0/applications/{object_id}", {"spa": body["spa"]})
                application = comparable
            return application
        return self.request("POST", "/v1.0/applications", body)

    def principal(self, application: dict[str, Any], marker: str) -> dict[str, Any]:
        app_id = str(UUID(application["appId"]))
        result = self.request(
            "GET",
            "/v1.0/servicePrincipals",
            params={
                "$filter": f"appId eq '{app_id}'",
                "$select": "id,appId,notes",
            },
        )
        found = result.get("value")
        if not isinstance(found, list) or len(found) > 1 or result.get("@odata.nextLink"):
            raise ValueError("Ambiguous or malformed service-principal lookup.")
        if found:
            if found[0].get("notes") != marker:
                raise ValueError("Existing principal is not owned by this demo; refusing adoption.")
            return found[0]
        return self.request("POST", "/v1.0/servicePrincipals", {"appId": app_id, "notes": marker})


def initialize(graph: Graph, plan: dict[str, Any]) -> dict[str, str]:
    api = graph.application(plan["api"])
    api_id, object_id = str(UUID(api["appId"])), str(UUID(api["id"]))
    identifier = f"api://{api_id}"
    identifiers = api.get("identifierUris", [])
    if not identifiers:
        graph.request("PATCH", f"/v1.0/applications/{object_id}", {"identifierUris": [identifier]})
    elif identifiers != [identifier]:
        raise ValueError("API identifier URI drifted; refusing replacement.")
    spa_body = plan["spa"] | {
        "requiredResourceAccess": [
            {
                "resourceAppId": api_id,
                "resourceAccess": [{"id": plan["scopeId"], "type": "Scope"}],
            }
        ],
    }
    spa = graph.application(spa_body)
    graph.principal(api, plan["marker"])
    graph.principal(spa, plan["marker"])
    return {
        "CLAIMS_API_AUDIENCE": api_id,
        "CLAIMS_UI_CLIENT_ID": str(UUID(spa["appId"])),
        "CLAIMS_API_CLIENT_IDS": str(UUID(spa["appId"])),
    }


def mutation_gate(values: Mapping[str, str], today: date | None = None) -> None:
    expiry = values.get("SECURITY_EXCEPTION_EXPIRES_ON", "")
    if (
        not re.fullmatch(r"\d{4}-\d{2}-\d{2}", expiry)
        or date.fromisoformat(expiry) <= (today or datetime.now(UTC).date())
        or not values.get("SECURITY_EXCEPTION_OWNER", "").strip()
    ):
        raise ValueError("An explicit future exception expiry and owner are required.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--redirect-uri",
        default="",
        help="Explicit Container App HTTPS root; omit to bootstrap before its domain exists.",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Create only the isolated demo registrations."
    )
    arguments = parser.parse_args()
    try:
        plan = identity_plan(os.environ, arguments.redirect_uri)
        if not arguments.apply:
            print(
                json.dumps(
                    {"scope": "identity-plan-only", "plan": plan, "cloud_writes": False}, indent=2
                )
            )
            return 0
        mutation_gate(os.environ)
        check_account(
            az_json(["account", "show", "--subscription", os.environ["AZURE_SUBSCRIPTION_ID"]]),
            os.environ,
        )
        with (
            AzureCliCredential(
                tenant_id=os.environ["AZURE_TENANT_ID"], process_timeout=30
            ) as credential,
            httpx.Client(
                base_url="https://graph.microsoft.com",
                timeout=60,
                follow_redirects=False,
                headers={
                    "Authorization": "Bearer "
                    + credential.get_token("https://graph.microsoft.com/.default").token
                },
            ) as http,
        ):
            outputs = initialize(Graph(http), plan)
        print(
            json.dumps(
                {
                    "scope": "identity-registration-only",
                    "passed": True,
                    "outputs": outputs,
                    "limitations": [
                        "No consent, caller assignments, invitations or unrelated-app edits.",
                        "An administrator must grant the SPA claims.invoke delegated permission.",
                        "Set these nonsecret outputs in the selected ignored azd environment.",
                        "Empty SPA redirects mean bootstrap only, not a working browser login.",
                    ],
                },
                indent=2,
            )
        )
        return 0
    except httpx.HTTPStatusError as error:
        logging.error(
            "Identity initialization failed (HTTP %s, %s %s).",
            error.response.status_code,
            error.request.method,
            error.request.url.path,
        )
        print(
            json.dumps(
                {
                    "scope": "identity-initialization",
                    "passed": False,
                    "error": type(error).__name__,
                    "status": error.response.status_code,
                    "method": error.request.method,
                    "path": error.request.url.path,
                    "requestId": error.response.headers.get("request-id"),
                    "detail": (
                        "Graph rejected the operation; inspect its request ID and configuration."
                    ),
                }
            )
        )
        return 1
    except (KeyError, ValueError, AzureError, httpx.HTTPError) as error:
        logging.error("Identity initialization failed (%s).", type(error).__name__)
        print(
            json.dumps(
                {
                    "scope": "identity-initialization",
                    "passed": False,
                    "error": type(error).__name__,
                    "detail": "Inspect configuration, Graph permissions and registration drift.",
                }
            )
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
