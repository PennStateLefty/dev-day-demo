from __future__ import annotations

import unittest
from datetime import date
from unittest.mock import patch

from azure_preflight import (
    MODELS,
    RESOURCE_TYPES,
    PreflightError,
    az_json,
    check_models,
    check_offerings,
    check_providers,
    cloud_checks,
    configuration_errors,
)


def values() -> dict[str, str]:
    return {
        "AZURE_ENV_NAME": "claims-demo",
        "AZURE_TENANT_ID": "00000000-0000-0000-0000-000000000001",
        "AZURE_SUBSCRIPTION_ID": "00000000-0000-0000-0000-000000000002",
        "AZURE_LOCATION": "centralus",
        "AZURE_OPERATOR_IPV4_CIDR": "9.9.9.9/32",
        "AZURE_OPERATOR_PRINCIPAL_ID": "00000000-0000-0000-0000-000000000003",
        "AZURE_SQL_ADMINISTRATOR_NAME": "demo-operator",
        "AZURE_APIM_PUBLISHER_NAME": "Synthetic Demo",
        "AZURE_APIM_PUBLISHER_EMAIL": "operator@example.invalid",
        "SECURITY_EXCEPTION_OWNER": "demo-owner",
        "SECURITY_EXCEPTION_EXPIRES_ON": "2026-12-01",
        "CLAIMS_API_AUDIENCE": "00000000-0000-0000-0000-000000000004",
        "CLAIMS_API_CLIENT_IDS": "00000000-0000-0000-0000-000000000005",
        "FOUNDRY_PROJECT_CLIENT_ID": "00000000-0000-0000-0000-000000000006",
        "CLAIMS_UI_CLIENT_ID": "00000000-0000-0000-0000-000000000005",
    }


class ConfigurationTests(unittest.TestCase):
    def test_complete_configuration(self) -> None:
        self.assertEqual(configuration_errors(values(), date(2026, 10, 14)), [])

    def test_public_mode_does_not_require_a_nonfunctional_ip_rule(self) -> None:
        settings = values() | {"AZURE_NETWORK_MODE": "public-demo"}
        del settings["AZURE_OPERATOR_IPV4_CIDR"]
        self.assertEqual(configuration_errors(settings, date(2026, 10, 14)), [])
        settings["AZURE_NETWORK_MODE"] = "enforced-perimeter"
        self.assertIn("Missing AZURE_OPERATOR_IPV4_CIDR.", configuration_errors(settings))
        settings["AZURE_NETWORK_MODE"] = "typo"
        self.assertTrue(configuration_errors(settings))

    def test_missing_expiry_is_not_defaulted(self) -> None:
        settings = values()
        del settings["SECURITY_EXCEPTION_EXPIRES_ON"]
        self.assertIn(
            "Missing SECURITY_EXCEPTION_EXPIRES_ON.",
            configuration_errors(settings, date(2026, 10, 14)),
        )

    def test_expired_exception_fails(self) -> None:
        for expiry in ("2026-10-13", "2026-10-14", "not-a-date", "2026-10-99", "20261015"):
            with self.subTest(expiry=expiry):
                settings = values() | {"SECURITY_EXCEPTION_EXPIRES_ON": expiry}
                self.assertTrue(configuration_errors(settings, date(2026, 10, 14)))

    def test_no_broad_or_private_operator_rule(self) -> None:
        for network in ("0.0.0.0/0", "9.9.9.0/24", "10.0.0.1/32", "::/0", "invalid"):
            with self.subTest(network=network):
                settings = values() | {"AZURE_OPERATOR_IPV4_CIDR": network}
                self.assertTrue(configuration_errors(settings, date(2026, 10, 14)))

    def test_bad_identifiers_and_names_fail(self) -> None:
        for key, value in (
            ("AZURE_TENANT_ID", "not-a-uuid"),
            ("AZURE_SUBSCRIPTION_ID", "$(command)"),
            ("AZURE_ENV_NAME", "../outside"),
            ("AZURE_LOCATION", "Central US"),
            ("AZURE_SQL_ADMINISTRATOR_TYPE", "Owner"),
            ("AZURE_APIM_PUBLISHER_EMAIL", "invalid"),
            ("CLAIMS_API_AUDIENCE", "api://not-a-client-guid"),
            ("FOUNDRY_PROJECT_CLIENT_ID", "not-a-client-guid"),
            ("CLAIMS_API_CLIENT_IDS", "not-a-client-guid"),
            ("CLAIMS_API_CLIENT_IDS", "00000000-0000-0000-0000-000000000005,"),
        ):
            with self.subTest(key=key):
                self.assertTrue(configuration_errors(values() | {key: value}, date(2026, 10, 14)))


class MetadataTests(unittest.TestCase):
    def test_current_and_nested_offerings_schemas(self) -> None:
        for sku in ({"name": "basic"}, {"sku": {"name": "basic"}}):
            with self.subTest(sku=sku):
                check_offerings(
                    {"regions": [{"regionName": "Central US", "skus": [sku]}]}, "centralus"
                )

    def test_missing_region_or_basic_fails(self) -> None:
        for regions in (
            [],
            [{"regionName": "centralus", "skus": [{"name": "serverless"}]}],
            [{"regionName": "eastus2", "skus": [{"name": "basic"}]}],
        ):
            with self.subTest(regions=regions), self.assertRaises(PreflightError):
                check_offerings({"regions": regions}, "centralus")

    def test_provider_registration_and_region(self) -> None:
        providers = [
            {
                "namespace": namespace,
                "registrationState": "Registered",
                "resourceTypes": [{"resourceType": resource_type, "locations": ["Central US"]}],
            }
            for namespace, resource_type in RESOURCE_TYPES.items()
        ]
        check_providers(providers, "centralus")
        for provider in providers:
            provider["namespace"] = provider["namespace"].lower()
        check_providers(providers, "centralus")
        providers[0]["registrationState"] = "NotRegistered"
        with self.assertRaisesRegex(PreflightError, "not registered"):
            check_providers(providers, "centralus")
        providers[0]["registrationState"] = "Registered"
        with self.assertRaisesRegex(PreflightError, "does not list"):
            check_providers(providers, "eastus2")

    def test_model_version_and_exact_quota_threshold(self) -> None:
        models = [
            {
                "model": {
                    "name": name,
                    "version": version,
                    "capabilities": {capability: "true"},
                    "skus": [{"name": "GlobalStandard"}],
                }
            }
            for name, version, capability, _ in MODELS
        ]
        quotas = [
            {"name": {"value": quota_name}, "limit": 20, "currentValue": 10}
            for _, _, _, quota_name in MODELS
        ]
        check_models(models, quotas)
        quotas[0]["currentValue"] = 11
        with self.assertRaisesRegex(PreflightError, "Insufficient"):
            check_models(models, quotas)
        with self.assertRaisesRegex(PreflightError, "No quota"):
            check_models(models, [])
        with self.assertRaisesRegex(PreflightError, "capability"):
            check_models([], quotas)

    def test_wrong_tenant_stops_before_other_discovery(self) -> None:
        with patch("azure_preflight.az_json") as run:
            run.return_value = {"id": values()["AZURE_SUBSCRIPTION_ID"], "tenantId": "wrong"}
            result = cloud_checks(values(), run)
        self.assertFalse(result[0]["passed"])
        self.assertEqual(run.call_count, 1)

    def test_redeployment_does_not_require_double_model_quota(self) -> None:
        from azure_preflight import DEPLOYMENT_NAMES

        models = [
            {
                "model": {
                    "name": name,
                    "version": version,
                    "capabilities": {capability: "true"},
                    "skus": [{"name": "GlobalStandard"}],
                }
            }
            for name, version, capability, _ in MODELS
        ]
        quotas = [
            {"name": {"value": quota_name}, "limit": 10, "currentValue": 10}
            for _, _, _, quota_name in MODELS
        ]
        existing = [
            {
                "name": DEPLOYMENT_NAMES[name],
                "sku": {"name": "GlobalStandard", "capacity": 10},
                "properties": {
                    "model": {"name": name, "version": version},
                    "provisioningState": "Succeeded",
                },
            }
            for name, version, _, _ in MODELS
        ]
        check_models(models, quotas, existing)
        with self.assertRaisesRegex(PreflightError, "Insufficient"):
            check_models(models, quotas)
        for changed in (
            existing[0] | {"name": "unrelated-model"},
            existing[0]
            | {"properties": existing[0]["properties"] | {"provisioningState": "Failed"}},
            existing[0] | {"sku": {"name": "GlobalStandard", "capacity": 9}},
        ):
            with (
                self.subTest(changed=changed),
                self.assertRaisesRegex(PreflightError, "Insufficient"),
            ):
                check_models(models, quotas, [changed, existing[1]])

    def test_cli_failure_is_not_converted_to_empty_success(self) -> None:
        with patch("azure_preflight.subprocess.run") as run:
            run.return_value.returncode = 1
            run.return_value.stderr = "AuthorizationFailed"
            with self.assertRaisesRegex(PreflightError, "AuthorizationFailed"):
                az_json(["account", "show"])
            self.assertIsInstance(run.call_args.args[0], list)
            self.assertNotIn("shell", run.call_args.kwargs)

    def test_all_commands_remain_read_only_and_subscription_scoped(self) -> None:
        calls = []

        def run(arguments: list[str]) -> object:
            calls.append(arguments)
            if arguments[0] == "account":
                return {
                    "id": values()["AZURE_SUBSCRIPTION_ID"],
                    "tenantId": values()["AZURE_TENANT_ID"],
                    "state": "Enabled",
                }
            if arguments[0] == "provider":
                return []
            if arguments[0] == "rest":
                return {"regions": []}
            return []

        results = cloud_checks(values(), run)
        self.assertEqual(len(results), 4)
        self.assertFalse(all(item["passed"] for item in results))
        for arguments in calls:
            self.assertIn(values()["AZURE_SUBSCRIPTION_ID"], arguments)
            self.assertFalse({"create", "update", "delete", "set", "register"} & set(arguments))


if __name__ == "__main__":
    unittest.main()
