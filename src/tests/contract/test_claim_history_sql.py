"""Opt-in, read-only acceptance checks against an initialized synthetic SQL database."""

from __future__ import annotations

import json
import os
from contextlib import closing
from decimal import Decimal

import pytest

CONNECTION = os.getenv("CLAIMS_RISK_TEST_SQL_CONNECTION_STRING")
pytestmark = pytest.mark.skipif(
    not CONNECTION, reason="No synthetic SQL acceptance target selected."
)


def facts(claim_id: str, as_of: str) -> dict[str, object]:
    import mssql_python

    with closing(mssql_python.connect(CONNECTION)) as connection:
        with closing(connection.cursor()) as cursor:
            cursor.execute(
                "EXEC claims.GetClaimRiskFacts @claim_id = ?, @as_of = ?",
                (claim_id, as_of),
            )
            names = [column[0] for column in cursor.description]
            return dict(zip(names, cursor.fetchone(), strict=True))


def test_seeded_customer_frequency_amounts_and_latest_timestamp() -> None:
    result = facts("clm-demo-001", "2026-10-19T00:00:00Z")
    assert result["claim_count_24_months"] == 8
    assert result["claim_count_12_months"] == 4
    assert result["total_claimed_amount_24_months"] == Decimal("40450")
    assert result["largest_claimed_amount_24_months"] == Decimal("32000")
    assert result["average_claimed_amount_24_months"] == Decimal("5056.25")
    assert result["last_prior_claim_at_utc"] == "2026-10-01T17:00:00Z"
    assert result["human_review_required"]
    assert not result["history_truncated"]
    details = json.loads(result["recent_claim_amounts_json"])
    assert len(details) == 8
    assert details[0]["history_claim_id"] == "hist-one-009"
    assert all(row["history_claim_id"] != "hist-one-001" for row in details)


def test_same_customer_resolves_from_current_claim_without_customer_input() -> None:
    first = facts("clm-demo-001", "2026-10-19T00:00:00Z")
    second = facts("clm-demo-002", "2026-10-19T00:00:00Z")
    assert first["customer_id"] == second["customer_id"]
    assert first["recent_claim_amounts_json"] == second["recent_claim_amounts_json"]
    other = facts("clm-demo-004", "2026-10-19T00:00:00Z")
    assert other["claim_count_24_months"] == 4
    assert other["largest_claimed_amount_24_months"] == Decimal("1450")


def test_window_edges_and_future_records_are_not_counted() -> None:
    before_history = facts("clm-demo-001", "2022-01-01T00:00:00Z")
    assert before_history["claim_count_24_months"] == 0
    assert before_history["total_claimed_amount_24_months"] == 0
    assert before_history["last_prior_claim_at_utc"] is None
    at_submission = facts("clm-demo-001", "2024-11-04T10:00:00Z")
    assert at_submission["claim_count_24_months"] == 2
    assert at_submission["last_prior_claim_at_utc"] == "2024-11-04T10:00:00Z"
    at_lower_boundary = facts("clm-demo-001", "2025-08-01T10:00:00Z")
    assert at_lower_boundary["claim_count_24_months"] == 3
    assert at_lower_boundary["largest_claimed_amount_24_months"] == Decimal("1650")
    older_only = facts("clm-demo-001", "2030-01-01T00:00:00Z")
    assert older_only["claim_count_24_months"] == 0
    assert older_only["average_claimed_amount_24_months"] is None
    assert older_only["last_prior_claim_at_utc"] == "2026-10-01T17:00:00Z"
    assert json.loads(older_only["recent_claim_amounts_json"]) == []


@pytest.mark.parametrize(
    ("claim_id", "as_of"),
    [
        ("clm-demo-003", "2026-10-19T00:00:00Z"),
        ("clm-missing", "2026-10-19T00:00:00Z"),
        ("clm-demo-001'; DROP TABLE claims.Claim;--", "2026-10-19T00:00:00Z"),
        ("clm-" + "a" * 100, "2026-10-19T00:00:00Z"),
        ("clm-demo-001", "not-a-date"),
        ("clm-demo-001", "2026-10-19T00:00:00"),
        ("clm-demo-001", "2026-10-19T00:00:00+03:00"),
    ],
)
def test_invalid_or_unavailable_evidence_is_an_error(claim_id: str, as_of: str) -> None:
    from mssql_python import Error

    with pytest.raises(Error, match="5001[0-3]|synthetic|Synthetic|customer|as_of"):
        facts(claim_id, as_of)


@pytest.mark.skipif(
    os.getenv("CLAIMS_RISK_TEST_DISPOSABLE") != "true",
    reason="Temporary rows are only permitted in the explicitly disposable acceptance database.",
)
def test_detail_limit_does_not_truncate_aggregates_and_current_claim_is_excluded() -> None:
    import mssql_python

    with closing(mssql_python.connect(CONNECTION)) as connection:
        try:
            with closing(connection.cursor()) as cursor:
                for index in range(21):
                    cursor.execute(
                        "INSERT claims.ClaimHistory"
                        "(history_claim_id, customer_id, claimed_at, claimed_amount) "
                        "VALUES (?, 'cust-demo-four', '2026-10-01T00:00:00', 1)",
                        (f"hist-acceptance-{index:02d}",),
                    )
                cursor.execute(
                    "INSERT claims.ClaimHistory"
                    "(history_claim_id, customer_id, claimed_at, claimed_amount) "
                    "VALUES ('clm-demo-004', 'cust-demo-four', '2026-10-02T00:00:00', 99999)"
                )
                cursor.execute(
                    "EXEC claims.GetClaimRiskFacts @claim_id = ?, @as_of = ?",
                    ("clm-demo-004", "2026-10-19T00:00:00Z"),
                )
                names = [column[0] for column in cursor.description]
                result = dict(zip(names, cursor.fetchone(), strict=True))
                assert result["claim_count_24_months"] == 25
                assert result["total_claimed_amount_24_months"] == Decimal("4071")
                assert result["largest_claimed_amount_24_months"] == Decimal("1450")
                assert result["history_truncated"]
                assert len(json.loads(result["recent_claim_amounts_json"])) == 20
        finally:
            connection.rollback()
