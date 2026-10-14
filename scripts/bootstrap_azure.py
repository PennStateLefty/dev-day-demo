"""Run explicitly approved temporary Azure initialization, then restore and remove access."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from typing import Any


def cli(*arguments: str) -> Any:
    result = subprocess.run(
        [*arguments, "--output", "json", "--only-show-errors"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        print(result.stderr, file=sys.stderr)
        result.check_returncode()
    return json.loads(result.stdout) if result.stdout.strip() else None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Requires explicit operator approval.")
    parser.add_argument("--repair-legacy-principal-sid", action="store_true")
    arguments = parser.parse_args()
    values = json.loads(
        subprocess.check_output(["azd", "env", "get-values", "--output", "json"], text=True)
    )
    group = values["AZURE_RESOURCE_GROUP"]
    server = values["AZURE_SQL_SERVER"].removesuffix(".database.windows.net")
    account = cli("az", "account", "show")
    if (
        account["id"] != values["AZURE_SUBSCRIPTION_ID"]
        or account["tenantId"] != values["AZURE_TENANT_ID"]
    ):
        raise ValueError("Azure context does not match the selected environment.")
    administrators = cli("az", "sql", "server", "ad-admin", "list", "-g", group, "-s", server)
    if len(administrators) != 1 or (
        administrators[0]["sid"].lower() != values["AZURE_OPERATOR_PRINCIPAL_ID"].lower()
    ):
        raise ValueError(
            "SQL administrator differs; refusing to replace an unrecognized principal."
        )
    original = administrators[0]
    print(
        json.dumps(
            {
                "apply": arguments.apply,
                "resource_group": group,
                "temporary_job": "job-claims-bootstrap",
                "temporary_identity": "id-claims-bootstrap",
                "restore_sql_administrator": original["login"],
                "cleanup": "Delete only this job, its four scoped roles and bootstrap identity.",
            }
        ),
        flush=True,
    )
    if not arguments.apply:
        return
    for kind, name in (("job", "job-claims-bootstrap"), ("identity", "id-claims-bootstrap")):
        existing = (
            cli("az", "containerapp", "job", "list", "-g", group)
            if kind == "job"
            else cli("az", "identity", "list", "-g", group)
        )
        if any(resource["name"] == name for resource in existing):
            raise ValueError(f"{name} already exists; inspect before another bootstrap.")
    outputs: dict[str, Any] = {}
    try:
        parameters = {
            "location": values["AZURE_LOCATION"],
            "environmentResourceId": values["AZURE_CONTAINER_APPS_ENVIRONMENT_ID"],
            "imageName": values["SERVICE_CLAIMS_API_IMAGE_NAME"],
            "registryName": values["AZURE_CONTAINER_REGISTRY_NAME"],
            "storageName": values["AZURE_STORAGE_ACCOUNT_NAME"],
            "searchName": values["AZURE_SEARCH_SERVICE_NAME"],
            "sqlServerName": server,
            "sqlDatabase": values["AZURE_SQL_DATABASE"],
            "runtimePrincipalId": values["AZURE_RUNTIME_PRINCIPAL_ID"],
            "runtimeClientId": values["AZURE_RUNTIME_CLIENT_ID"],
            "repairLegacyPrincipalSid": str(arguments.repair_legacy_principal_sid).lower(),
        }
        deployment = cli(
            "az",
            "deployment",
            "group",
            "create",
            "-g",
            group,
            "-n",
            "claims-bootstrap",
            "--template-file",
            "infrastructure/bootstrap.bicep",
            "--parameters",
            *(f"{key}={value}" for key, value in parameters.items()),
        )
        outputs = deployment["properties"]["outputs"]
        job = outputs["jobName"]["value"]
        execution = cli("az", "containerapp", "job", "start", "-g", group, "-n", job)
        execution_name = execution["name"]
        for _ in range(60):
            executions = cli(
                "az", "containerapp", "job", "execution", "list", "-g", group, "-n", job
            )
            current = next(item for item in executions if item["name"] == execution_name)
            status = current["properties"]["status"]
            print(json.dumps({"execution": execution_name, "status": status}), flush=True)
            if status == "Succeeded":
                return
            if status in ("Failed", "Stopped", "Degraded"):
                raise RuntimeError(f"Bootstrap {execution_name} ended with {status}.")
            time.sleep(10)
        raise TimeoutError(f"Bootstrap {execution_name} did not finish within ten minutes.")
    finally:
        cli(
            "az",
            "sql",
            "server",
            "ad-admin",
            "update",
            "-g",
            group,
            "-s",
            server,
            "--object-id",
            original["sid"],
            "--display-name",
            original["login"],
        )
        restored = cli("az", "sql", "server", "ad-admin", "list", "-g", group, "-s", server)
        if len(restored) != 1 or restored[0]["sid"].lower() != original["sid"].lower():
            raise RuntimeError(
                "SQL administrator restoration could not be verified; retain identity."
            )
        # Read deployed outputs even if the original deployment request failed partway.
        if not outputs:
            deployment = cli(
                "az", "deployment", "group", "show", "-g", group, "-n", "claims-bootstrap"
            )
            outputs = deployment["properties"].get("outputs", {})
        if outputs:
            cli(
                "az",
                "containerapp",
                "job",
                "delete",
                "-g",
                group,
                "-n",
                outputs["jobName"]["value"],
                "--yes",
            )
            cli(
                "az",
                "role",
                "assignment",
                "delete",
                "--ids",
                *outputs["roleAssignmentIds"]["value"],
            )
            cli("az", "identity", "delete", "--ids", outputs["identityId"]["value"])
            print(
                json.dumps({"cleanup": "complete", "sql_administrator_restored": True}), flush=True
            )
        else:
            raise RuntimeError(
                "Bootstrap outputs unavailable; inspect partial resources for cleanup."
            )


if __name__ == "__main__":
    main()
