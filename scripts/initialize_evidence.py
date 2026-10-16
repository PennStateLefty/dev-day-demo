"""Plan or apply reviewed synthetic image uploads and expected-before SQL fixture updates."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from contextlib import closing
from pathlib import Path

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.identity import AzureCliCredential
from azure.storage.blob import BlobServiceClient, ContentSettings

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/apps/claims-api"))

from app.database import connection_string, connector, payload  # noqa: E402
from app.evidence import LocalEvidenceReader, evidence_key, validate_image  # noqa: E402
from app.service import DemoService  # noqa: E402


def image_manifest(fixtures: DemoService) -> list[dict[str, object]]:
    reader = LocalEvidenceReader()
    images = []
    for claim in fixtures.list_claims():
        for artifact in fixtures.list_artifacts(claim.claim_id):
            if artifact.artifact_type != "damage_photo":
                continue
            content = reader.read(artifact)
            images.append({
                "artifactId": artifact.artifact_id, "claimId": claim.claim_id,
                "container": "evidence", "blob": evidence_key(artifact),
                "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
                "contentType": validate_image(content),
            })
    return images


def desired_rows(fixtures: DemoService) -> list[dict[str, object]]:
    return [
        {"table": table, "id": identifier, "after": json.loads(payload(record))}
        for table, records, key in (
            ("Claim", fixtures.claims.values(), "claim_id"),
            ("Artifact", fixtures.artifacts.values(), "artifact_id"),
        )
        for record in records for identifier in [getattr(record, key)]
    ]


def snapshot(cursor, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    changes = []
    for row in rows:
        table = row["table"]
        sql = {
            "Claim": "SELECT payload FROM claims.Claim WHERE claim_id = ?",
            "Artifact": "SELECT payload FROM claims.Artifact WHERE artifact_id = ?",
        }[table]
        cursor.execute(sql, (row["id"],))
        found = cursor.fetchall()
        before = json.loads(str(found[0][0])) if found else None
        if before != row["after"]:
            changes.append({**row, "before": before})
    return changes


def apply_rows(cursor, changes: list[dict[str, object]], fixtures: DemoService) -> None:
    allowed = {(row["table"], row["id"]): row["after"] for row in desired_rows(fixtures)}
    if len({(row["table"], row["id"]) for row in changes}) != len(changes):
        raise ValueError("Duplicate fixture updates are not allowed.")
    for row in changes:
        if allowed.get((row["table"], row["id"])) != row["after"]:
            raise ValueError("Reviewed SQL target differs from current synthetic fixtures.")
    actual = snapshot(cursor, changes)
    if actual != [row for row in changes if row["before"] != row["after"]]:
        # Already-applied rows are safe to replay, but changed preconditions are not.
        for row in actual:
            expected = next(item for item in changes if (
                item["table"], item["id"]
            ) == (row["table"], row["id"]))
            if row["before"] != expected["before"]:
                raise ValueError("SQL seed changed since review; no overwrite performed.")
    for row in actual:
        after = row["after"]
        encoded = json.dumps(after, sort_keys=True)
        if row["table"] == "Claim":
            record = fixtures.get_claim(str(row["id"]))
            values = (
                record.policy_id, record.customer_id, record.loss_date, encoded, record.claim_id,
            )
            if row["before"] is None:
                cursor.execute(
                    "INSERT claims.Claim(policy_id,customer_id,loss_date,payload,claim_id) "
                    "VALUES (?,?,?,?,?)", values,
                )
            else:
                cursor.execute(
                    "UPDATE claims.Claim SET policy_id=?,customer_id=?,loss_date=?,payload=? "
                    "WHERE claim_id=?", values,
                )
        else:
            values = (after["claimId"], encoded, row["id"])
            if row["before"] is None:
                cursor.execute(
                    "INSERT claims.Artifact(claim_id,payload,artifact_id) VALUES (?,?,?)", values,
                )
            else:
                cursor.execute(
                    "UPDATE claims.Artifact SET claim_id=?,payload=? WHERE artifact_id=?", values,
                )


def upload_verified(blobs: BlobServiceClient, images, fixtures: DemoService) -> None:
    reader = LocalEvidenceReader()
    for image in images:
        artifact = fixtures.get_artifact(image["claimId"], image["artifactId"])
        content = reader.read(artifact)
        if hashlib.sha256(content).hexdigest() != image["sha256"]:
            raise ValueError("Local image changed since review.")
        blob = blobs.get_blob_client("evidence", evidence_key(artifact))
        try:
            existing = blob.download_blob(offset=0, length=len(content) + 1).readall()
        except ResourceNotFoundError:
            try:
                blob.upload_blob(
                    content, overwrite=False,
                    content_settings=ContentSettings(content_type=image["contentType"]),
                    metadata={"sha256": image["sha256"], "synthetic": "true"},
                )
            except ResourceExistsError:
                existing = blob.download_blob(offset=0, length=len(content) + 1).readall()
                if existing != content:
                    raise ValueError("Concurrent Blob content differs; no overwrite.") from None
        else:
            if existing != content:
                raise ValueError("Blob content differs; no overwrite performed.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-sql", action="store_true")
    parser.add_argument("--apply", type=Path, help="Apply this explicitly reviewed manifest.")
    args = parser.parse_args()
    fixtures = DemoService()
    account = os.environ.get("AZURE_STORAGE_ACCOUNT_NAME", "")
    if not re.fullmatch(r"[a-z0-9]{3,24}", account):
        raise ValueError("Set the existing AZURE_STORAGE_ACCOUNT_NAME explicitly.")
    manifest = {"storageAccount": account, "images": image_manifest(fixtures), "sqlChanges": []}
    if args.apply or args.include_sql:
        connect = connector(connection_string(
            os.environ["AZURE_SQL_SERVER"], os.environ["AZURE_SQL_DATABASE"], local_admin=True,
        ))
        with closing(connect()) as connection, closing(connection.cursor()) as cursor:
            try:
                cursor.execute(
                    "SET XACT_ABORT ON; SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;"
                )
                if args.apply:
                    reviewed = json.loads(args.apply.read_text())
                    if any(reviewed[key] != manifest[key] for key in ("storageAccount", "images")):
                        raise ValueError("Reviewed manifest differs from local images or storage.")
                    with AzureCliCredential() as credential, BlobServiceClient(
                        f"https://{account}.blob.core.windows.net", credential=credential,
                        connection_timeout=10, read_timeout=30, retry_total=0,
                    ) as blobs:
                        upload_verified(blobs, reviewed["images"], fixtures)
                    apply_rows(cursor, reviewed["sqlChanges"], fixtures)
                    connection.commit()
                    print(json.dumps({"applied": True, "images": len(reviewed["images"])}))
                    return
                manifest["sqlChanges"] = snapshot(cursor, desired_rows(fixtures))
            finally:
                connection.rollback()
    encoded = json.dumps(manifest, indent=2) + "\n"
    if args.output:
        args.output.write_text(encoded)
    else:
        print(encoded)


if __name__ == "__main__":
    main()
