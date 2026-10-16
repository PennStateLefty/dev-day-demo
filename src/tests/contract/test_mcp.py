import pytest
from app.main import mcp
from fastmcp import Client


@pytest.mark.asyncio
async def test_mcp_assessment_tool_uses_shared_service() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "assess_synthetic_claim",
            {"claim_id": "clm-demo-002"},
        )

    assert result.data["claimId"] == "clm-demo-002"
    assert result.data["humanReviewRequired"] is True
    assert result.data["policyCitations"]
    exclusion = next(
        finding
        for finding in result.data["completenessFindings"]
        if finding["findingCode"] == "possible_policy_exclusion"
    )
    citation = next(
        citation
        for citation in result.data["policyCitations"]
        if citation["citationId"] in exclusion["supportingCitationIds"]
    )
    assert citation["section"].startswith("Section 3")
    assert "commercial ride-share or delivery" in citation["quotedText"]


@pytest.mark.asyncio
async def test_mcp_policy_lookup_returns_citations() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "lookup_policy",
            {"policy_id": "pol-demo-auto", "query": "deer animal strike"},
        )

    assert result.data[0]["section"].startswith("Section 2.3")
