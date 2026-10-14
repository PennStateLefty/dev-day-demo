"""Run positive and negative data-plane checks from the deployed runtime identity."""

from __future__ import annotations

import json
import logging
import os
import re
import sys
from collections.abc import Callable
from contextlib import closing
from pathlib import Path

import httpx
from azure.core.exceptions import AzureError
from azure.storage.blob import BlobServiceClient
from mssql_python import Error as SqlError
from mssql_python import ProgrammingError

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/apps/claims-api"))

from app.runtime import Runtime  # noqa: E402
from app.search_rest import KnowledgeError  # noqa: E402
from app.settings import Settings  # noqa: E402


class SmokeFailure(Exception):
    """A measurable deployment requirement was not satisfied."""


def check_data_plane(runtime: Runtime, account: str) -> list[dict[str, object]]:
    if runtime.store is None or runtime.credential is None:
        raise ValueError("Data-plane smoke tests require Azure mode and its runtime identity.")
    if not re.fullmatch(r"[a-z0-9]{3,24}", account):
        raise ValueError("Invalid storage account.")
    store = runtime.store
    checks: list[dict[str, object]] = []

    def execute(name: str, action: Callable[[], None]) -> None:
        try:
            action()
        except (
            SmokeFailure,
            RuntimeError,
            ValueError,
            AzureError,
            SqlError,
            httpx.HTTPError,
            KnowledgeError,
        ) as error:
            logging.error("Smoke check %s failed (%s).", name, type(error).__name__)
            checks.append({"name": name, "passed": False, "error": type(error).__name__})
        else:
            checks.append({"name": name, "passed": True})

    def history() -> None:
        claims = store.customer_history("cust-demo-one")
        if {claim.claim_id for claim in claims} != {"clm-demo-001", "clm-demo-002"}:
            raise SmokeFailure("SQL synthetic history did not match the seeded records.")

    def allowed_write() -> None:
        note = store.add_review_note("clm-demo-001", "Synthetic managed-identity smoke-test note.")
        if not note:
            raise SmokeFailure("The allowed SQL write did not return a note ID.")

    def denied_update() -> None:
        with closing(store.connect()) as connection, closing(connection.cursor()) as cursor:
            try:
                # No rows change even if UPDATE was accidentally granted.
                cursor.execute("UPDATE claims.Claim SET payload = payload WHERE 1 = 0")
            except ProgrammingError as error:
                # This driver exposes the SQLSTATE category and message, not native number 229.
                if error.driver_error != "Syntax error or access violation" or not re.fullmatch(
                    r"\[Microsoft\](?:\[SQL Server\])?The UPDATE permission "
                    r"was denied on the object "
                    r"'Claim', database '[A-Za-z0-9_-]{1,128}', schema 'claims'\.",
                    error.ddbc_error.strip(),
                ):
                    raise SmokeFailure("SQL failed without the expected UPDATE denial.") from error
            else:
                raise SmokeFailure("Runtime identity unexpectedly has claim UPDATE permission.")
            finally:
                connection.rollback()

    def cited_blob() -> None:
        citations = runtime.service.lookup_policy("pol-demo-auto", "animal strikes vehicle damage")
        if not citations:
            raise SmokeFailure("IQ retrieval returned no citations for known policy evidence.")
        with BlobServiceClient(
            f"https://{account}.blob.core.windows.net",
            credential=runtime.credential,
            connection_timeout=10,
            read_timeout=30,
        ) as blobs:
            content = (
                blobs.get_blob_client("policies", "pol-demo-auto.md").download_blob().readall()
            )
        text = content.decode("utf-8")
        if any(citation.quoted_text not in text for citation in citations):
            raise SmokeFailure("IQ citations do not resolve to the seeded Blob policy.")
        if not any("animal strikes" in citation.quoted_text for citation in citations):
            raise SmokeFailure("Known animal-strike policy evidence was not retrieved.")

    execute("runtime-sql-read", store.probe)
    execute("bounded-customer-history", history)
    execute("allowed-review-note-write", allowed_write)
    execute("denied-claim-update", denied_update)
    execute("iq-citations-and-blob-managed-identity", cited_blob)
    return checks


def main() -> int:
    runtime: Runtime | None = None
    try:
        settings = Settings.from_environment()
        if settings.mode != "azure":
            raise ValueError("Runtime smoke tests cannot use local fixtures.")
        runtime = Runtime(settings)
        checks = check_data_plane(runtime, os.environ["AZURE_STORAGE_ACCOUNT_NAME"])
    except (KeyError, ValueError, OSError, AzureError) as error:
        logging.error("Runtime smoke setup failed (%s).", type(error).__name__)
        checks = [{"name": "runtime-configuration", "passed": False, "error": type(error).__name__}]
    finally:
        if runtime is not None:
            runtime.close()
    passed = all(check["passed"] for check in checks)
    print(
        json.dumps(
            {
                "scope": "runtime-managed-identity-data-plane",
                "passed": passed,
                "checks": checks,
                "limitations": [
                    "Does not prove NSP denied-source enforcement, gateway routing or specialists.",
                    "Each successful write check appends one synthetic review note.",
                ],
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
