"""Check compiled ARM security invariants; read the Bicep build JSON from stdin."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any


def resources(template: dict[str, Any]) -> list[dict[str, Any]]:
    found = []
    declarations = template.get("resources", [])
    for resource in declarations.values() if isinstance(declarations, dict) else declarations:
        if not resource.get("existing", False):
            found.append(resource)
        nested = resource.get("properties", {}).get("template")
        if nested:
            found.extend(resources(nested))
    return found


def network_choice(public: str, perimeter: str) -> str:
    return f"[if(equals(parameters('networkMode'), 'public-demo'), '{public}', '{perimeter}')]"


def invariant_errors(template: dict[str, Any]) -> list[str]:
    found = resources(template)
    errors = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    def of_type(resource_type: str) -> list[dict[str, Any]]:
        return [item for item in found if item["type"].casefold() == resource_type.casefold()]

    require(
        "subscriptionDeploymentTemplate" in template.get("$schema", ""),
        "The entry point must be subscription-scoped.",
    )
    for parameter in ("securityExceptionExpiresOn", "securityExceptionOwner"):
        require(
            parameter in template.get("parameters", {})
            and "defaultValue" not in template["parameters"][parameter],
            f"{parameter} must be explicit, without a default.",
        )
    mode = template.get("parameters", {}).get("networkMode", {})
    require(
        mode.get("defaultValue") == "enforced-perimeter"
        and mode.get("allowedValues") == ["enforced-perimeter", "public-demo"],
        "Public networking must require the explicit public-demo mode; default remains enforced.",
    )

    groups = of_type("Microsoft.Resources/resourceGroups")
    require(len(groups) == 1, "Exactly one new demo resource group must be declared.")
    for group in groups:
        require(
            group.get("tags", {}).get("SecurityControl") == "Ignore",
            "The new group must use exactly SecurityControl=Ignore.",
        )
    for resource in found:
        if resource not in groups and isinstance(resource.get("tags"), dict):
            require(
                "SecurityControl" not in resource["tags"],
                "The policy-exception tag belongs on the resource group only.",
            )
    require(
        "SecurityControl" not in template.get("variables", {}).get("tags", {}),
        "Shared resource tags must not propagate the resource-group exception.",
    )
    servers = of_type("Microsoft.Sql/servers")
    require(len(servers) == 1, "Exactly one SQL logical server must be declared.")
    for server in servers:
        properties = server.get("properties", {})
        require(
            properties.get("administrators", {}).get("azureADOnlyAuthentication") is True,
            "SQL must enforce Entra-only authentication unconditionally.",
        )
        require(
            "administratorLogin" not in properties
            and "administratorLoginPassword" not in properties,
            "SQL password authentication must not be configured.",
        )
        require(
            properties.get("publicNetworkAccess")
            == network_choice("Enabled", "SecuredByPerimeter"),
            "SQL public networking must be conditional on public-demo mode.",
        )
    rules = of_type("Microsoft.Sql/servers/firewallRules")
    require(
        len(rules) == 1
        and rules[0].get("condition") == "[equals(parameters('networkMode'), 'public-demo')]"
        and rules[0].get("properties")
        == {"startIpAddress": "0.0.0.0", "endIpAddress": "255.255.255.255"},
        "The sole SQL public firewall rule must be gated on explicit public-demo mode.",
    )

    stores = of_type("Microsoft.Storage/storageAccounts")
    require(len(stores) == 1, "Exactly one synthetic data storage account must be declared.")
    for store in stores:
        properties = store.get("properties", {})
        require(
            properties.get("allowBlobPublicAccess") is False
            and properties.get("allowSharedKeyAccess") is False,
            "Storage must disable public blobs and shared-key authentication.",
        )
        require(
            properties.get("publicNetworkAccess") == network_choice("Enabled", "SecuredByPerimeter")
            and properties.get("networkAcls", {}).get("defaultAction")
            == network_choice("Allow", "Deny"),
            "Storage public networking must be conditional on public-demo mode.",
        )
        require(
            properties.get("supportsHttpsTrafficOnly") is True,
            "Storage must require HTTPS in either mode.",
        )
    foundries = of_type("Microsoft.CognitiveServices/accounts")
    require(len(foundries) == 1, "Exactly one Foundry account must be declared.")
    for foundry in foundries:
        properties = foundry.get("properties", {})
        require(
            properties.get("disableLocalAuth") is True, "Foundry must disable key authentication."
        )
        require(
            properties.get("publicNetworkAccess") == "Enabled"
            and properties.get("networkAcls", {}).get("defaultAction")
            == network_choice("Allow", "Deny"),
            "Foundry firewall bypass must be conditional on public-demo mode.",
        )
    searches = of_type("Microsoft.Search/searchServices")
    require(len(searches) == 1, "Exactly one Search service must be declared.")
    for search in searches:
        require(
            search.get("sku", {}).get("name") == "basic",
            "Search must use approved Basic capacity.",
        )
        require(
            search.get("properties", {}).get("disableLocalAuth") is True,
            "Search must disable API key authentication.",
        )
        require(
            search.get("properties", {}).get("publicNetworkAccess")
            == network_choice("enabled", "securedByPerimeter"),
            "Search public networking must be conditional on public-demo mode.",
        )
        require(
            search["properties"].get("replicaCount") == 1
            and search["properties"].get("partitionCount") == 1,
            "Search must use exactly one replica and partition.",
        )

    gateways = of_type("Microsoft.ApiManagement/service")
    require(len(gateways) == 1, "Exactly one isolated APIM instance must be declared.")
    for gateway in gateways:
        require(
            gateway.get("sku") == {"name": "Developer", "capacity": 1},
            "APIM must use one Developer unit for the nonproduction MCP gateway.",
        )
        require(
            gateway.get("identity", {}).get("type") == "SystemAssigned",
            "APIM requires managed identity for backends.",
        )
    associations = of_type("Microsoft.Network/networkSecurityPerimeters/resourceAssociations")
    require(bool(associations), "Perimeter associations must be declared.")
    for association in associations:
        require(
            association.get("properties", {}).get("accessMode") == "Enforced",
            "Perimeter associations must never default to learning mode.",
        )
        require(
            association.get("condition")
            in (
                "[equals(parameters('networkMode'), 'enforced-perimeter')]",
                "[and(equals(parameters('networkMode'), 'enforced-perimeter'), "
                "not(equals(parameters('protectedResourceIds')[copyIndex()], "
                "parameters('storageResourceId'))))]",
            ),
            "Perimeter associations must not be created in public-demo mode.",
        )
    return errors


def application_errors(template: dict[str, Any]) -> list[str]:
    errors = []
    applications = [
        resource
        for resource in resources(template)
        if resource["type"].casefold() == "microsoft.app/containerapps"
    ]
    if len(applications) != 1:
        return ["Exactly one application revision must be declared."]
    app = applications[0]
    for name in (
        "imageName",
        "tenantId",
        "apiAudience",
        "apiClientIds",
        "uiClientId",
        "runtimeIdentityId",
    ):
        if (
            name not in template.get("parameters", {})
            or "defaultValue" in template["parameters"][name]
        ):
            errors.append(f"{name} must be explicit; no deployment fallback is allowed.")
    identity = app.get("identity", {})
    identity_keys = {
        "[parameters('runtimeIdentityId')]",
        "[format('{0}', parameters('runtimeIdentityId'))]",
    }
    if identity.get("type") != "UserAssigned" or not identity_keys.intersection(
        identity.get("userAssignedIdentities", {})
    ):
        errors.append("The application must attach the explicit runtime identity.")
    configuration = app.get("properties", {}).get("configuration", {})
    ingress = configuration.get("ingress", {})
    if (
        ingress.get("allowInsecure") is not False
        or ingress.get("external") is not True
        or ingress.get("targetPort") != 8000
    ):
        errors.append("The public website requires HTTPS-only ingress on the application port.")
    registry = configuration.get("registries", [])
    if len(registry) != 1 or registry[0].get("identity") != "[parameters('runtimeIdentityId')]":
        errors.append("Registry pulls must use the runtime identity, not a password.")
    settings = template.get("variables", {}).get("runtimeSettings", {})
    if settings.get("CLAIMS_MODE") != "azure":
        errors.append("The deployed application must explicitly use Azure mode.")
    if settings.get("CLAIMS_UI_CLIENT_ID") != "[parameters('uiClientId')]":
        errors.append("Browser authentication must use the explicit SPA client ID.")
    containers = app.get("properties", {}).get("template", {}).get("containers", [])
    if len(containers) != 1 or containers[0].get("image") != "[parameters('imageName')]":
        errors.append("The revision must use the real azd-published image.")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--application", action="store_true", help="Check the standalone service template."
    )
    arguments = parser.parse_args()
    try:
        template = json.load(sys.stdin)
    except json.JSONDecodeError as error:
        print(json.dumps({"passed": False, "errors": [f"Invalid ARM JSON: {error.msg}"]}))
        return 1
    errors = application_errors(template) if arguments.application else invariant_errors(template)
    print(
        json.dumps(
            {
                "scope": "compiled-application-contract"
                if arguments.application
                else "compiled-infrastructure-contract",
                "passed": not errors,
                "errors": errors,
            },
            indent=2,
        )
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
