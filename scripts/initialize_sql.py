"""Apply reviewed migrations and synthetic seeds as the configured Entra SQL administrator."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
from contextlib import closing
from pathlib import Path
from uuid import UUID

from azure.core.exceptions import AzureError
from mssql_python import Error as SqlError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src/apps/claims-api"))

from app.database import Connect, connection_string, connector, payload  # noqa: E402
from app.service import DemoService  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def runtime_grants(client_id: str, legacy_principal_id: str | None = None) -> str:
    sid = "0x" + UUID(client_id).bytes_le.hex()
    repair = ""
    if legacy_principal_id is not None:
        legacy_sid = "0x" + UUID(legacy_principal_id).bytes_le.hex()
        if legacy_sid == sid:
            raise ValueError("Legacy object ID must differ from the client ID.")
        repair = f"""
IF EXISTS (
    SELECT 1 FROM sys.database_principals
    WHERE name = N'claims_runtime_identity' AND sid = {legacy_sid} AND type = 'E'
)
    DROP USER claims_runtime_identity;
"""
    return f"""
IF DATABASE_PRINCIPAL_ID(N'claims_runtime') IS NULL
    CREATE ROLE claims_runtime AUTHORIZATION dbo;
{repair}
IF DATABASE_PRINCIPAL_ID(N'claims_runtime_identity') IS NULL
    CREATE USER claims_runtime_identity WITH SID = {sid}, TYPE = E;
IF NOT EXISTS (
    SELECT 1 FROM sys.database_principals
    WHERE name = N'claims_runtime_identity' AND sid = {sid} AND type = 'E'
)
    THROW 50003, 'Runtime principal differs; explicit identity migration required.', 1;
IF NOT EXISTS (
    SELECT 1 FROM sys.database_role_members
    WHERE role_principal_id = DATABASE_PRINCIPAL_ID(N'claims_runtime')
      AND member_principal_id = DATABASE_PRINCIPAL_ID(N'claims_runtime_identity')
)
    ALTER ROLE claims_runtime ADD MEMBER claims_runtime_identity;
GRANT SELECT ON OBJECT::claims.Policy TO claims_runtime;
GRANT SELECT ON OBJECT::claims.Claim TO claims_runtime;
GRANT SELECT ON OBJECT::claims.Artifact TO claims_runtime;
GRANT EXECUTE ON OBJECT::claims.AddReviewNote TO claims_runtime;
"""


def initialize(
    connect: Connect,
    client_id: str,
    fixtures: DemoService,
    *,
    legacy_principal_id: str | None = None,
) -> dict[str, object]:
    grants = runtime_grants(client_id, legacy_principal_id)
    with closing(connect()) as connection, closing(connection.cursor()) as cursor:
        try:
            cursor.execute("SET XACT_ABORT ON; SET TRANSACTION ISOLATION LEVEL SERIALIZABLE;")
            cursor.execute("""
IF OBJECT_ID(N'dbo.ClaimsMigration', N'U') IS NULL
    CREATE TABLE dbo.ClaimsMigration (
        name nvarchar(200) NOT NULL PRIMARY KEY,
        sha256 char(64) NOT NULL,
        applied_at datetime2 NOT NULL DEFAULT SYSUTCDATETIME()
    );
""")
            applied = 0
            for migration in sorted((ROOT / "infrastructure/sql").glob("*.sql")):
                sql = migration.read_text(encoding="utf-8")
                digest = hashlib.sha256(sql.encode()).hexdigest()
                cursor.execute(
                    "SELECT sha256 FROM dbo.ClaimsMigration WHERE name = ?", (migration.name,)
                )
                existing = cursor.fetchall()
                if existing:
                    if existing[0][0] != digest:
                        raise ValueError(f"Applied migration changed: {migration.name}.")
                    continue
                cursor.execute(sql)
                cursor.execute(
                    "INSERT dbo.ClaimsMigration(name, sha256) VALUES (?, ?)",
                    (migration.name, digest),
                )
                applied += 1

            # Identifiers and statements are fixed here, never supplied by a tool caller.
            batches = (
                (
                    "SELECT payload FROM claims.Policy WHERE policy_id = ?",
                    "INSERT claims.Policy(policy_id, payload) VALUES (?, ?)",
                    [(record.policy_id, payload(record)) for record in fixtures.policies.values()],
                ),
                (
                    "SELECT payload FROM claims.Claim WHERE claim_id = ?",
                    "INSERT claims.Claim(claim_id, policy_id, customer_id, loss_date, payload) "
                    "VALUES (?, ?, ?, ?, ?)",
                    [
                        (
                            record.claim_id,
                            record.policy_id,
                            record.customer_id,
                            record.loss_date,
                            payload(record),
                        )
                        for record in fixtures.claims.values()
                    ],
                ),
                (
                    "SELECT payload FROM claims.Artifact WHERE artifact_id = ?",
                    "INSERT claims.Artifact(artifact_id, claim_id, payload) VALUES (?, ?, ?)",
                    [
                        (record.artifact_id, record.claim_id, payload(record))
                        for record in fixtures.artifacts.values()
                    ],
                ),
            )
            inserted = 0
            for select, insert, records in batches:
                for record in records:
                    cursor.execute(select, (record[0],))
                    existing = cursor.fetchall()
                    if existing:
                        if json.loads(str(existing[0][0])) != json.loads(str(record[-1])):
                            raise ValueError(
                                f"Synthetic seed drift for {record[0]}; no overwrite performed."
                            )
                    else:
                        cursor.execute(insert, record)
                        inserted += 1
            cursor.execute(grants)
            connection.commit()
            return {"passed": True, "migrations_applied": applied, "records_inserted": inserted}
        except (SqlError, AzureError, ValueError, OSError):
            connection.rollback()
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--managed-identity", action="store_true")
    parser.add_argument(
        "--repair-legacy-principal-sid",
        action="store_true",
        help="Explicitly approved recreation of this initializer's legacy object-ID-mapped user.",
    )
    arguments = parser.parse_args()
    try:
        values = {
            key: os.environ[key]
            for key in ("AZURE_SQL_SERVER", "AZURE_SQL_DATABASE", "AZURE_RUNTIME_CLIENT_ID")
        }
        result = initialize(
            connector(
                connection_string(
                    values["AZURE_SQL_SERVER"],
                    values["AZURE_SQL_DATABASE"],
                    client_id=os.environ["AZURE_BOOTSTRAP_CLIENT_ID"]
                    if arguments.managed_identity
                    else None,
                    local_admin=not arguments.managed_identity,
                )
            ),
            values["AZURE_RUNTIME_CLIENT_ID"],
            DemoService(),
            legacy_principal_id=os.environ["AZURE_RUNTIME_PRINCIPAL_ID"]
            if arguments.repair_legacy_principal_sid
            else None,
        )
    except (KeyError, ValueError, OSError, SqlError, AzureError) as error:
        logging.error("SQL initialization failed (%s); no runtime fallback.", type(error).__name__)
        print(json.dumps({"passed": False, "error": type(error).__name__}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
