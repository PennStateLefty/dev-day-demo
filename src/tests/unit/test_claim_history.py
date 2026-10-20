from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest
from app.service import DemoService
from initialize_sql import initialize, migration_batches, risk_grants

ROOT = Path(__file__).resolve().parents[3]
SQL = (ROOT / "infrastructure/sql/003_claim_history.sql").read_text()


def test_seed_has_two_customer_histories_mostly_small_amounts_and_one_outlier() -> None:
    rows = re.findall(r"\(N'(hist-[^']+)', N'([^']+)', '([^']+)', ([\d.]+)\)", SQL)
    assert len(rows) == 13
    assert len({row[0] for row in rows}) == len(rows)
    assert {row[1] for row in rows} == {"cust-demo-one", "cust-demo-four"}
    amounts = [Decimal(row[3]) for row in rows]
    assert sum(amount < 2000 for amount in amounts) == 12
    assert max(amounts) == 32000
    review = datetime(2026, 10, 19)
    one = [row for row in rows if row[1] == "cust-demo-one"]
    window = [
        row for row in one if datetime(2024, 10, 19) < datetime.fromisoformat(row[2]) <= review
    ]
    assert len(window) == 8
    assert sum(Decimal(row[3]) for row in window) == 40450
    assert sum(datetime.fromisoformat(row[2]) > datetime(2025, 10, 19) for row in window) == 4
    assert max(row[2] for row in one) == "2026-10-01T17:00:00"


def test_migration_has_fixed_queries_explicit_errors_and_bounded_detail_not_aggregates() -> None:
    batches = migration_batches(SQL)
    assert len(batches) == 2
    assert batches[1].startswith("CREATE OR ALTER PROCEDURE claims.GetClaimRiskFacts")
    assert "sp_executesql" not in SQL
    assert not re.search(r"\bEXEC(?:UTE)?\s*\(", SQL, re.IGNORECASE)
    assert "customer_id = @customer_id" in SQL
    assert "history_claim_id <> @claim_id" in SQL
    assert "claimed_at <= @review_at" in SQL
    assert "claimed_at > DATEADD(month, -24, @review_at)" in SQL
    assert "SELECT TOP (20)" in SQL
    assert "COUNT_BIG(*) > 20" in SQL
    assert "history is unavailable, not zero" in SQL
    assert "TRY_CONVERT" in SQL and "DATALENGTH(@as_of) <> 40" in SQL


def test_empty_window_fix_is_append_only_and_preserves_procedure_contract() -> None:
    fix = (ROOT / "infrastructure/sql/004_claim_history_empty_window.sql").read_text()
    assert len(migration_batches(fix)) == 1
    assert "N'[]'" in fix
    assert "COUNT_BIG(*) AS claim_count_24_months" in fix
    assert "history_claim_id <> @claim_id" in fix
    assert "CREATE OR ALTER PROCEDURE claims.GetClaimRiskFacts" in fix


def test_dab_exposes_only_the_named_authenticated_procedure() -> None:
    config = json.loads((ROOT / "src/apps/claims-risk-data/dab-config.json").read_text())
    runtime = config["runtime"]
    assert runtime["mcp"]["dml-tools"] is False
    assert runtime["rest"]["enabled"] is False
    assert runtime["graphql"]["enabled"] is False
    assert "*" not in runtime["mcp"]["allowed-hosts"]
    assert runtime["host"]["authentication"]["provider"] == "EntraID"
    assert set(config["entities"]) == {"GetClaimRiskFacts"}
    entity = config["entities"]["GetClaimRiskFacts"]
    assert entity["source"]["object"] == "claims.GetClaimRiskFacts"
    assert entity["mcp"] == {"custom-tool": True}
    assert entity["permissions"] == [{"role": "authenticated", "actions": ["execute"]}]
    assert {item["name"] for item in entity["source"]["parameters"]} == {"claim_id", "as_of"}
    assert all(item["required"] and item["description"] for item in entity["source"]["parameters"])


def test_risk_identity_is_object_scoped_and_rejects_injection() -> None:
    grants = risk_grants("00112233-4455-6677-8899-aabbccddeeff")
    assert "0x33221100554477668899aabbccddeeff" in grants
    assert "GRANT EXECUTE ON OBJECT::claims.GetClaimRiskFacts" in grants
    assert "GRANT VIEW DEFINITION ON OBJECT::claims.GetClaimRiskFacts" in grants
    assert "GRANT SELECT" not in grants
    assert "db_owner" not in grants and "db_datareader" not in grants
    with pytest.raises(ValueError):
        risk_grants("'; DROP TABLE claims.Claim;--")


def test_studio_gateway_requires_subscription_and_exchanges_backend_identity() -> None:
    template = (ROOT / "infrastructure/claims-risk-apim.bicep").read_text()
    assert "subscriptionRequired: false" not in template
    assert template.count("subscriptionRequired: true") == 2
    assert "scope: studioProduct.id" in template
    assert "name: mcp.name" in template
    assert "allowTracing: false" in template
    assert "claims-risk-subscription.xml" in template
    assert "claims-auth.xml" not in template
    assert "primaryKey:" not in template and "secondaryKey:" not in template
    application = (ROOT / "infrastructure/claims-risk-data.bicep").read_text()
    assert "module studioGateway './claims-risk-apim.bicep'" in application
    policy = ET.parse(ROOT / "infrastructure/policies/claims-risk-subscription.xml")
    inbound = policy.getroot().find("inbound")
    assert inbound is not None
    assert inbound.find("validate-jwt") is None
    identity = inbound.find("authentication-managed-identity")
    assert identity is not None
    assert identity.attrib == {"resource": "__API_AUDIENCE__", "ignore-error": "false"}
    headers = {item.attrib["name"]: item for item in inbound.findall("set-header")}
    assert headers["Authorization"].attrib["exists-action"] == "delete"
    assert headers["Ocp-Apim-Subscription-Key"].attrib["exists-action"] == "delete"
    query = inbound.find("set-query-parameter")
    assert query is not None
    assert query.attrib == {"name": "subscription-key", "exists-action": "delete"}
    assert list(inbound).index(headers["Authorization"]) < list(inbound).index(identity)
    forward = policy.getroot().find("backend/forward-request")
    assert forward is not None and forward.attrib["buffer-response"] == "false"


def test_optional_risk_grants_commit_in_the_existing_initialization_transaction() -> None:
    connection = Mock()
    connection.cursor.return_value.fetchall.return_value = []
    initialize(
        lambda: connection,
        "00000000-0000-0000-0000-000000000001",
        DemoService(),
        risk_client_id="00000000-0000-0000-0000-000000000002",
    )
    statements = [call.args[0] for call in connection.cursor.return_value.execute.call_args_list]
    assert any("CREATE USER claims_risk_identity" in statement for statement in statements)
    connection.commit.assert_called_once()
    with pytest.raises(ValueError, match="dedicated identity"):
        initialize(
            lambda: connection,
            "00000000-0000-0000-0000-000000000001",
            DemoService(),
            risk_client_id="00000000-0000-0000-0000-000000000001",
        )
