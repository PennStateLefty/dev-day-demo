from __future__ import annotations

import copy
import unittest
from pathlib import Path
from xml.etree import ElementTree

from check_infrastructure import application_errors, invariant_errors, network_choice, resources


def template() -> dict:
    return {
        "$schema": "subscriptionDeploymentTemplate",
        "parameters": {
            key: {"type": "string"}
            for key in ("securityExceptionExpiresOn", "securityExceptionOwner", "operatorIpv4Cidr")
        }
        | {
            "networkMode": {
                "type": "string",
                "defaultValue": "enforced-perimeter",
                "allowedValues": ["enforced-perimeter", "public-demo"],
            },
        },
        "resources": [
            {"type": "Microsoft.Resources/resourceGroups", "tags": {"SecurityControl": "Ignore"}},
            {
                "type": "Microsoft.Sql/servers",
                "properties": {
                    "administrators": {"azureADOnlyAuthentication": True},
                    "publicNetworkAccess": network_choice("Enabled", "SecuredByPerimeter"),
                },
            },
            {
                "type": "Microsoft.Storage/storageAccounts",
                "properties": {
                    "allowBlobPublicAccess": False,
                    "allowSharedKeyAccess": False,
                    "publicNetworkAccess": network_choice("Enabled", "SecuredByPerimeter"),
                    "networkAcls": {"defaultAction": network_choice("Allow", "Deny")},
                    "supportsHttpsTrafficOnly": True,
                },
            },
            {
                "type": "Microsoft.Search/searchServices",
                "sku": {"name": "basic"},
                "properties": {
                    "disableLocalAuth": True,
                    "publicNetworkAccess": network_choice("enabled", "securedByPerimeter"),
                    "replicaCount": 1,
                    "partitionCount": 1,
                },
            },
            {
                "type": "Microsoft.ApiManagement/service",
                "sku": {"name": "Developer", "capacity": 1},
                "identity": {"type": "SystemAssigned"},
            },
            {
                "type": "Microsoft.Network/networkSecurityPerimeters/resourceAssociations",
                "condition": "[equals(parameters('networkMode'), 'enforced-perimeter')]",
                "properties": {"accessMode": "Enforced"},
            },
            {
                "type": "Microsoft.Sql/servers/firewallRules",
                "condition": "[equals(parameters('networkMode'), 'public-demo')]",
                "properties": {
                    "startIpAddress": "0.0.0.0",
                    "endIpAddress": "255.255.255.255",
                },
            },
            {
                "type": "Microsoft.CognitiveServices/accounts",
                "properties": {
                    "disableLocalAuth": True,
                    "publicNetworkAccess": "Enabled",
                    "networkAcls": {"defaultAction": network_choice("Allow", "Deny")},
                },
            },
        ],
    }


class InfrastructureTests(unittest.TestCase):
    def test_valid_contract(self) -> None:
        self.assertEqual(invariant_errors(template()), [])

    def test_nested_symbolic_templates_and_existing_references(self) -> None:
        document = template()
        original = copy.deepcopy(document["resources"])
        document["resources"] = {
            "nested": {
                "type": "Microsoft.Resources/deployments",
                "properties": {
                    "template": {
                        "resources": {
                            "existing": {"type": "Microsoft.Sql/servers", "existing": True},
                            **{f"r{i}": value for i, value in enumerate(original)},
                        }
                    }
                },
            }
        }
        self.assertEqual(len(resources(document)), len(original) + 1)
        self.assertEqual(invariant_errors(document), [])

    def test_missing_resources_do_not_pass_vacuously(self) -> None:
        document = template()
        document["resources"] = []
        self.assertGreaterEqual(len(invariant_errors(document)), 6)

    def test_settings_cannot_be_weakened(self) -> None:
        for index, property_name, value in (
            (1, "publicNetworkAccess", "Enabled"),
            (1, "administratorLoginPassword", "not-a-real-password"),
            (2, "allowSharedKeyAccess", True),
            (2, "allowBlobPublicAccess", True),
            (3, "disableLocalAuth", False),
            (3, "replicaCount", 2),
            (3, "partitionCount", 2),
            (5, "accessMode", "Learning"),
        ):
            with self.subTest(property=property_name):
                document = template()
                document["resources"][index]["properties"][property_name] = value
                self.assertTrue(invariant_errors(document))

    def test_gateway_tier_and_identity(self) -> None:
        for key, value in (("sku", {"name": "Consumption", "capacity": 0}), ("identity", {})):
            with self.subTest(key=key):
                document = template()
                document["resources"][4][key] = value
                self.assertTrue(invariant_errors(document))

    def test_expiry_and_mode_cannot_default_to_unapproved_values(self) -> None:
        for parameter in ("securityExceptionExpiresOn", "securityExceptionOwner", "networkMode"):
            with self.subTest(parameter=parameter):
                document = template()
                document["parameters"][parameter]["defaultValue"] = "not-approved"
                self.assertTrue(invariant_errors(document))

    def test_public_networking_cannot_become_unconditional(self) -> None:
        for index in (5, 6):
            document = template()
            del document["resources"][index]["condition"]
            self.assertTrue(invariant_errors(document))
        for index in (2, 7):
            document = template()
            document["resources"][index]["properties"]["networkAcls"]["defaultAction"] = "Allow"
            self.assertTrue(invariant_errors(document))
        document = template()
        document["resources"][7]["properties"]["disableLocalAuth"] = False
        self.assertTrue(invariant_errors(document))
        document = template()
        document["parameters"]["networkMode"]["defaultValue"] = "public-demo"
        self.assertTrue(invariant_errors(document))

    def test_exception_is_not_propagated_to_resources(self) -> None:
        document = template()
        document["variables"] = {"tags": {"SecurityControl": "Ignore"}}
        self.assertTrue(invariant_errors(document))
        document = template()
        document["resources"][2]["tags"] = {"SecurityControl": "Ignore"}
        self.assertTrue(invariant_errors(document))


class GatewayPolicyTests(unittest.TestCase):
    def test_bearer_policy_is_scoped_and_streaming_safe(self) -> None:
        policy = ElementTree.fromstring(
            (Path(__file__).resolve().parents[2] / "infrastructure/policies/claims-auth.xml")
            .read_text()
            .replace("__CLIENTS__", "<value>explicit-client-id</value>")
        )
        jwt = policy.find("./inbound/validate-jwt")
        self.assertIsNotNone(jwt)
        for name, value in {
            "header-name": "Authorization",
            "require-scheme": "Bearer",
            "require-expiration-time": "true",
            "require-signed-tokens": "true",
            "failed-validation-httpcode": "401",
        }.items():
            self.assertEqual(jwt.get(name), value)
        self.assertEqual(jwt.findtext("./audiences/audience"), "__AUDIENCE__")
        self.assertEqual(
            jwt.findtext("./issuers/issuer"),
            "https://login.microsoftonline.com/__TENANT__/v2.0",
        )
        self.assertEqual(
            jwt.findtext("./required-claims/claim[@name='azp']/value"), "explicit-client-id"
        )
        self.assertEqual(jwt.findtext("./required-claims/claim[@name='tid']/value"), "__TENANT__")
        self.assertEqual(jwt.findtext("./required-claims/claim[@name='ver']/value"), "2.0")
        self.assertEqual(policy.find("./backend/forward-request").get("buffer-response"), "false")
        self.assertIsNone(policy.find(".//set-header[@name='Authorization']"))
        self.assertEqual(
            policy.find("./inbound/choose/when/return-response/set-status").get("code"), "403"
        )


class ApplicationTests(unittest.TestCase):
    def document(self) -> dict:
        return {
            "parameters": {
                name: {"type": "string"}
                for name in (
                    "imageName",
                    "tenantId",
                    "apiAudience",
                    "apiClientIds",
                    "foundryProjectClientId",
                    "uiClientId",
                    "runtimeIdentityId",
                )
            },
            "variables": {
                "authorizedClientIds": (
                    "[format('{0},{1}', parameters('apiClientIds'), "
                    "parameters('foundryProjectClientId'))]"
                ),
                "runtimeSettings": {
                    "CLAIMS_MODE": "azure",
                    "CLAIMS_API_CLIENT_IDS": "[variables('authorizedClientIds')]",
                    "CLAIMS_UI_CLIENT_ID": "[parameters('uiClientId')]",
                }
            },
            "resources": [
                {
                    "type": "Microsoft.App/containerApps",
                    "identity": {
                        "type": "UserAssigned",
                        "userAssignedIdentities": {
                            "[format('{0}', parameters('runtimeIdentityId'))]": {},
                        },
                    },
                    "properties": {
                        "configuration": {
                            "ingress": {
                                "allowInsecure": False,
                                "external": True,
                                "targetPort": 8000,
                            },
                            "registries": [{"identity": "[parameters('runtimeIdentityId')]"}],
                        },
                        "template": {"containers": [{"image": "[parameters('imageName')]"}]},
                    },
                }
            ],
        }

    def test_explicit_application_contract(self) -> None:
        self.assertEqual(application_errors(self.document()), [])
        self.assertTrue(application_errors({"resources": []}))

    def test_no_local_image_identity_or_auth_fallbacks(self) -> None:
        for name in self.document()["parameters"]:
            document = self.document()
            del document["parameters"][name]
            self.assertTrue(application_errors(document))
            document = self.document()
            document["parameters"][name]["defaultValue"] = "unsafe"
            self.assertTrue(application_errors(document))
        document = self.document()
        document["variables"]["runtimeSettings"]["CLAIMS_MODE"] = "local"
        self.assertTrue(application_errors(document))
        document = self.document()
        del document["variables"]["runtimeSettings"]["CLAIMS_UI_CLIENT_ID"]
        self.assertTrue(application_errors(document))
        document = self.document()
        document["resources"][0]["identity"] = {"type": "SystemAssigned"}
        self.assertTrue(application_errors(document))
        document = self.document()
        document["resources"][0]["properties"]["configuration"]["ingress"]["allowInsecure"] = True
        self.assertTrue(application_errors(document))


if __name__ == "__main__":
    unittest.main()
