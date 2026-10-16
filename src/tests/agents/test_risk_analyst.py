from __future__ import annotations

import json
from pathlib import Path

import pytest
from agents.risk_analyst import (
    TOOL_NAMES,
    _load_review_validator,
    _versioned_toolbox_url,
    build_mcp_tool,
    read_skill,
)
from azure.ai.projects.models import MCPToolboxTool, ToolboxSkillReference

ROOT = Path(__file__).resolve().parents[3]


def test_risk_analyst_skill_is_foundry_skill_source_and_advisory_only() -> None:
    name, description, instructions, digest = read_skill()
    assert name == "risk-analyst"
    assert description
    assert len(digest) == 64
    assert "synthetic_customer_history" in instructions
    assert "Do not infer intent" in instructions
    assert "fraud detection" in instructions


def test_risk_analyst_toolbox_mcp_configuration_is_https_and_bounded() -> None:
    tool = build_mcp_tool(
        "https://apim.example.test/claims/mcp/",
        "claims-api-connection",
    )
    assert isinstance(tool, MCPToolboxTool)
    assert tool.server_url == "https://apim.example.test/claims/mcp"
    assert tool.project_connection_id == "claims-api-connection"
    assert set(tool.allowed_tools) == set(TOOL_NAMES)
    assert tool.require_approval == "never"


@pytest.mark.parametrize(
    ("url", "connection"),
    [
        ("http://apim.example.test/claims/mcp", "claims-api"),
        ("https://user:password@apim.example.test/claims/mcp", "claims-api"),
        ("https://apim.example.test/claims/mcp?key=value", "claims-api"),
        ("https://apim.example.test/claims/mcp", ""),
    ],
)
def test_risk_analyst_toolbox_rejects_unsafe_or_missing_auth_config(
    url: str,
    connection: str,
) -> None:
    with pytest.raises(ValueError):
        build_mcp_tool(url, connection)


def test_toolbox_pins_the_exact_foundry_skill_version() -> None:
    reference = ToolboxSkillReference(name="risk-analyst", version="7")
    assert reference.as_dict() == {
        "type": "skill_reference",
        "name": "risk-analyst",
        "version": "7",
    }


def test_consumer_requires_the_exact_versioned_foundry_toolbox_endpoint() -> None:
    project_endpoint = "https://foundry.example.test/api/projects/claims"
    endpoint = (
        "https://foundry.example.test/api/projects/claims/"
        "toolboxes/risk-analyst-toolbox/versions/4/mcp?api-version=v1"
    )
    assert _versioned_toolbox_url(endpoint, project_endpoint, "4") == endpoint
    with pytest.raises(ValueError, match="explicit version endpoint"):
        _versioned_toolbox_url(
            "https://foundry.example.test/api/projects/claims/toolboxes/"
            "risk-analyst-toolbox/mcp?api-version=v1",
            project_endpoint,
            "4",
        )
    with pytest.raises(ValueError):
        _versioned_toolbox_url(endpoint, project_endpoint, "../latest")


def test_risk_review_schema_requires_human_review_and_forbids_extra_fields() -> None:
    validator = _load_review_validator()
    valid = {
        "claimId": "clm-demo-001",
        "findings": [],
        "limitations": ["Synthetic data only."],
        "humanReviewRequired": True,
        "recommendation": "human_review",
    }
    assert validator.is_valid(valid)
    assert not validator.is_valid({**valid, "riskScore": 0.8})
    assert not validator.is_valid({**valid, "humanReviewRequired": False})


def test_risk_review_schema_is_source_controlled() -> None:
    schema = json.loads(
        (ROOT / "data/schemas/risk-review.schema.json").read_text(encoding="utf-8")
    )
    assert schema["additionalProperties"] is False
    assert "humanReviewRequired" in schema["required"]
    assert "recommendation" in schema["required"]


def test_risk_analyst_regression_case_uses_only_fixture_claim_history() -> None:
    dataset = json.loads(
        (ROOT / "evaluations/datasets/risk-analyst.json").read_text(encoding="utf-8")
    )
    claims = {
        claim["claimId"]: claim
        for claim in json.loads(
            (ROOT / "data/claims/demo-claims.json").read_text(encoding="utf-8")
        )
    }
    case_claim = claims[dataset["claimId"]]
    expected = dataset["expectedContext"]

    assert case_claim["customerId"] == dataset["customerId"]
    assert set(expected["claimIds"]) == {
        claim_id
        for claim_id, claim in claims.items()
        if claim.get("customerId") == dataset["customerId"]
    }
    assert len(expected["claimIds"]) <= expected["claimCountAtMost"]
    assert all(
        claims[observation["claimId"]][observation["field"]] == observation["value"]
        for observation in expected["observations"]
    )
    assert dataset["requiredInvariant"] == {
        "humanReviewRequired": True,
        "recommendation": "human_review",
        "noRiskScore": True,
        "noClaimantClassification": True,
        "noCoverageDecision": True,
    }
