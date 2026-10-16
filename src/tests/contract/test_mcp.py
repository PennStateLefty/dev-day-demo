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


@pytest.mark.asyncio
async def test_mcp_get_synthetic_claim_reads_only_the_requested_record() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "get_synthetic_claim",
            {"claim_id": "clm-demo-001"},
        )

    assert result.data["claimId"] == "clm-demo-001"
    assert result.data["customerId"] == "cust-demo-one"


@pytest.mark.asyncio
async def test_mcp_policy_lookup_returns_citations() -> None:
    async with Client(mcp) as client:
        result = await client.call_tool(
            "lookup_policy",
            {"policy_id": "pol-demo-auto", "query": "deer animal strike"},
        )

    assert result.data[0]["section"].startswith("Section 2.3")
