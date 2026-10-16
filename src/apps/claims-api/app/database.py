from __future__ import annotations

import json
import re
from collections.abc import Callable
from contextlib import closing
from typing import Protocol, Self
from uuid import UUID

from .models import Artifact, Claim, Policy


class Cursor(Protocol):
    def execute(self, sql: str, params: tuple[object, ...] = ()) -> Self: ...
    def fetchall(self) -> list[tuple[object, ...]]: ...
    def close(self) -> None: ...


class Connection(Protocol):
    def cursor(self) -> Cursor: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


Connect = Callable[[], Connection]


def connection_string(
    server: str, database: str, *, client_id: str | None = None, local_admin: bool = False
) -> str:
    if not re.fullmatch(r"[a-z0-9-]+\.database\.windows\.net", server):
        raise ValueError("SQL server must be an Azure SQL public-cloud hostname.")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,128}", database):
        raise ValueError("Invalid SQL database name.")
    if local_admin and client_id:
        raise ValueError("Local administrator mode cannot select a runtime identity.")
    if not local_admin and not client_id:
        raise ValueError("Azure SQL runtime requires an explicit managed-identity client ID.")
    identity = f"UID={UUID(client_id)};" if client_id else ""
    authentication = "ActiveDirectoryDefault" if local_admin else "ActiveDirectoryMSI"
    return (
        f"Server=tcp:{server},1433;Database={database};"
        f"Authentication={authentication};{identity}"
        "Encrypt=yes;TrustServerCertificate=no;"
    )


def connector(value: str) -> Connect:
    def connect() -> Connection:
        import mssql_python

        connection = mssql_python.connect(value, timeout=30)
        connection.timeout = 30
        return connection

    return connect


class SqlClaimsStore:
    """Fixed, parameterized data operations; no caller-supplied SQL."""

    def __init__(self, connect: Connect) -> None:
        self.connect = connect

    def _query(self, sql: str, params: tuple[object, ...] = ()) -> list[tuple[object, ...]]:
        with closing(self.connect()) as connection, closing(connection.cursor()) as cursor:
            cursor.execute(sql, params)
            return cursor.fetchall()

    def list_claims(self) -> list[Claim]:
        rows = self._query("SELECT TOP (100) payload FROM claims.Claim ORDER BY claim_id")
        return [Claim.model_validate_json(str(row[0])) for row in rows]

    def find_claim(self, claim_id: str) -> Claim | None:
        rows = self._query("SELECT payload FROM claims.Claim WHERE claim_id = ?", (claim_id,))
        return Claim.model_validate_json(str(rows[0][0])) if rows else None

    def find_policy(self, policy_id: str) -> Policy | None:
        rows = self._query("SELECT payload FROM claims.Policy WHERE policy_id = ?", (policy_id,))
        return Policy.model_validate_json(str(rows[0][0])) if rows else None

    def find_artifact(self, artifact_id: str) -> Artifact | None:
        rows = self._query(
            "SELECT payload FROM claims.Artifact WHERE artifact_id = ?", (artifact_id,)
        )
        return Artifact.model_validate_json(str(rows[0][0])) if rows else None

    def customer_history(self, customer_id: str) -> list[Claim]:
        rows = self._query(
            "SELECT TOP (20) payload FROM claims.Claim "
            "WHERE customer_id = ? ORDER BY loss_date DESC, claim_id",
            (customer_id,),
        )
        return [Claim.model_validate_json(str(row[0])) for row in rows]

    def add_review_note(self, claim_id: str, note: str) -> str:
        if not 1 <= len(note.strip()) <= 2000:
            raise ValueError("A review note must contain 1-2000 non-whitespace characters.")
        with closing(self.connect()) as connection, closing(connection.cursor()) as cursor:
            cursor.execute("EXEC claims.AddReviewNote @claim_id = ?, @note = ?", (claim_id, note))
            row = cursor.fetchall()[0]
            connection.commit()
            return str(row[0])

    def probe(self) -> None:
        rows = self._query("SELECT TOP (1) claim_id FROM claims.Claim ORDER BY claim_id")
        if not rows:
            raise RuntimeError("SQL is reachable but synthetic claims have not been initialized.")


def payload(record: Claim | Policy | Artifact) -> str:
    data = record.model_dump(mode="json", by_alias=True)
    if isinstance(record, Artifact) and record.provenance is None:
        # Preserve existing seed payloads when optional provenance was never supplied.
        data.pop("provenance", None)
    return json.dumps(data, sort_keys=True)
