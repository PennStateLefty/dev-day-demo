"""Read-only live acceptance for the synthetic DAB MCP service and its APIM proxy."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from urllib.parse import urlparse

import httpx
from azure.identity import AzureCliCredential
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport


async def verify(url: str, token: str, unrelated_token: str) -> dict[str, object]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("Acceptance targets must be HTTPS URLs without credentials.")
    initialize = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-03-26",
            "capabilities": {},
            "clientInfo": {"name": "risk-acceptance", "version": "1"},
        },
    }
    headers = {"Accept": "application/json, text/event-stream"}
    async with httpx.AsyncClient(timeout=90) as http:
        anonymous = await http.post(url, json=initialize, headers=headers)
        if anonymous.status_code == 200:
            # Native DAB permits protocol discovery, but must deny every anonymous data call.
            async with Client(url, timeout=90) as client:
                denied = await client.call_tool(
                    "get_claim_risk_facts",
                    {"claim_id": "clm-demo-001", "as_of": "2026-10-19T00:00:00Z"},
                    raise_on_error=False,
                )
                assert denied.is_error
                error = json.loads(denied.content[0].text)
                assert error["error"]["type"] == "PermissionDenied"
        elif anonymous.status_code not in (401, 403):
            raise AssertionError(f"Unexpected anonymous response: HTTP {anonymous.status_code}")
        response = await http.post(
            url, json=initialize, headers={**headers, "Authorization": "Bearer invalid-token"}
        )
        if response.status_code not in (401, 403):
            raise AssertionError(f"Invalid token admitted: HTTP {response.status_code}")
        response = await http.post(
            url,
            json=initialize,
            headers={**headers, "Authorization": f"Bearer {unrelated_token}"},
        )
        if response.status_code not in (401, 403):
            raise AssertionError(f"Unrelated audience admitted: HTTP {response.status_code}")

    return await verify_tools(url, StreamableHttpTransport(url, auth=token))


async def verify_gateway(url: str, key: str) -> dict[str, object]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.query:
        raise ValueError("Gateway target must be an HTTPS URL without credentials or query.")
    headers = {"Accept": "application/json, text/event-stream"}
    request = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    async with httpx.AsyncClient(timeout=90) as http:
        for credentials in (
            {},
            {"Ocp-Apim-Subscription-Key": "invalid-subscription-key"},
            {"Authorization": "Bearer invalid"},
        ):
            response = await http.post(url, json=request, headers={**headers, **credentials})
            if response.status_code not in (401, 403):
                raise AssertionError(f"Missing/invalid key admitted: HTTP {response.status_code}")
    result = await verify_tools(
        url,
        StreamableHttpTransport(
            url,
            headers={"Ocp-Apim-Subscription-Key": key},
        ),
    )
    async with Client(
        StreamableHttpTransport(
            url,
            headers={
                "Ocp-Apim-Subscription-Key": key,
                "Authorization": "Bearer invalid",
            },
        ),
        timeout=90,
    ) as client:
        replaced = await client.call_tool(
            "get_claim_risk_facts",
            {"claim_id": "clm-demo-001", "as_of": "2026-10-19T00:00:00Z"},
        )
        assert json.loads(replaced.content[0].text)["status"] == "success"
    result["subscription_key_denials"] = 3
    result["caller_bearer_replaced"] = True
    return result


async def verify_tools(url: str, transport: StreamableHttpTransport) -> dict[str, object]:
    async with Client(transport, timeout=90) as client:
        tools = await client.list_tools()
        assert [tool.name for tool in tools] == ["get_claim_risk_facts"]
        assert set(tools[0].inputSchema["required"]) == {"claim_id", "as_of"}
        assert all(item["type"] == "string" for item in tools[0].inputSchema["properties"].values())
        arguments = {"claim_id": "clm-demo-001", "as_of": "2026-10-19T00:00:00Z"}
        result = await client.call_tool("get_claim_risk_facts", arguments)
        envelope = json.loads(result.content[0].text)
        assert envelope["status"] == "success"
        facts = envelope["value"]["value"][0]
        assert facts["claim_count_24_months"] == 8
        assert facts["claim_count_12_months"] == 4
        assert facts["total_claimed_amount_24_months"] == 40450
        assert facts["average_claimed_amount_24_months"] == 5056.25
        assert facts["largest_claimed_amount_24_months"] == 32000
        assert facts["last_prior_claim_at_utc"] == "2026-10-01T17:00:00Z"
        assert facts["human_review_required"] and facts["synthetic"]
        assert len(json.loads(facts["recent_claim_amounts_json"])) == 8
        empty = await client.call_tool(
            "get_claim_risk_facts", {**arguments, "as_of": "2030-01-01T00:00:00Z"}
        )
        empty_facts = json.loads(empty.content[0].text)["value"]["value"][0]
        assert empty_facts["claim_count_24_months"] == 0
        assert json.loads(empty_facts["recent_claim_amounts_json"]) == []
        assert empty_facts["last_prior_claim_at_utc"] == "2026-10-01T17:00:00Z"
        invalid = [
            {**arguments, "claim_id": "clm-demo-003"},
            {**arguments, "claim_id": "clm-missing"},
            {**arguments, "claim_id": "clm-demo-001'; SELECT 1;--"},
            {**arguments, "as_of": "not-a-date"},
            {**arguments, "sql": "SELECT * FROM claims.Claim"},
            {"claim_id": "clm-demo-001"},
        ]
        for request in invalid:
            error = await client.call_tool("get_claim_risk_facts", request, raise_on_error=False)
            assert error.is_error, f"Invalid arguments admitted: {request}"
    return {"url": url, "passed": True, "negative_argument_cases": len(invalid)}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", action="append", default=[], help="Direct DAB URL.")
    parser.add_argument("--audience", required=True, help="Existing Entra API application ID.")
    parser.add_argument("--apim-url", help="Subscription-protected gateway MCP URL.")
    parser.add_argument(
        "--apim-subscription-resource-id",
        help="Approved APIM subscription ARM ID; retrieve its key in memory via listSecrets.",
    )
    args = parser.parse_args()
    if bool(args.apim_url) != bool(args.apim_subscription_resource_id):
        parser.error("--apim-url and --apim-subscription-resource-id must be supplied together.")
    if not args.url and not args.apim_url:
        parser.error("Supply --url or --apim-url.")
    credential = AzureCliCredential()
    if args.url:
        token = credential.get_token(f"api://{args.audience}/.default").token
        unrelated = credential.get_token("https://management.azure.com/.default").token
        for url in args.url:
            print(json.dumps(await verify(url, token, unrelated)))
    if args.apim_url:
        resource_id = args.apim_subscription_resource_id
        if not re.fullmatch(
            r"/subscriptions/[0-9a-fA-F-]+/resourceGroups/[^/]+/providers/"
            r"Microsoft\.ApiManagement/service/[^/]+/subscriptions/[^/]+",
            resource_id,
        ):
            parser.error("Expected a complete APIM subscription ARM resource ID.")
        management_token = credential.get_token("https://management.azure.com/.default").token
        async with httpx.AsyncClient(timeout=90) as http:
            response = await http.post(
                f"https://management.azure.com{resource_id}/listSecrets?api-version=2024-05-01",
                headers={"Authorization": f"Bearer {management_token}"},
            )
            response.raise_for_status()
            key = response.json()["primaryKey"]
        print(json.dumps(await verify_gateway(args.apim_url, key)))


if __name__ == "__main__":
    asyncio.run(main())
