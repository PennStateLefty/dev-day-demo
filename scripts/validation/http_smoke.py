"""Exercise authenticated REST and MCP over HTTPS, directly or through the gateway."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import re
import sys
from collections.abc import Awaitable, Callable
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from azure.core.exceptions import AzureError
from azure.identity import AzureCliCredential
from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.exceptions import ToolError
from mcp.shared.exceptions import McpError


class SmokeFailure(Exception):
    """A live HTTP requirement was not met."""


def validate_url(url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or not parsed.hostname.endswith((".azurecontainerapps.io", ".azure-api.net"))
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.query
        or parsed.fragment
        or not re.fullmatch(r"/[a-zA-Z0-9/_-]*|", parsed.path)
    ):
        raise ValueError("Use an explicit Azure Container Apps or APIM HTTPS base URL.")
    return url


async def check_http(
    base_url: str, token: str, mcp_url: str | None = None
) -> list[dict[str, object]]:
    base_url = validate_url(base_url).rstrip("/")
    mcp_url = validate_url(mcp_url) if mcp_url is not None else f"{base_url}/mcp/"
    if urlsplit(base_url).netloc != urlsplit(mcp_url).netloc:
        raise ValueError("REST and MCP smoke targets must share the same HTTPS gateway host.")
    checks: list[dict[str, object]] = []
    headers = {"Authorization": f"Bearer {token}"}

    async def execute(name: str, action: Callable[[], Awaitable[None]]) -> None:
        try:
            await action()
        except (
            SmokeFailure,
            httpx.HTTPError,
            McpError,
            ToolError,
            RuntimeError,
            ValueError,
        ) as error:
            logging.error("HTTP smoke check %s failed (%s).", name, type(error).__name__)
            checks.append({"name": name, "passed": False, "error": type(error).__name__})
        else:
            checks.append({"name": name, "passed": True})

    async with httpx.AsyncClient(timeout=60, follow_redirects=False) as http:

        async def unauthorized() -> None:
            rest = await http.get(f"{base_url}/api/claims")
            mcp = await http.post(mcp_url)
            if rest.status_code not in (401, 403) or mcp.status_code not in (401, 403):
                raise SmokeFailure("Unauthenticated REST or MCP was not denied.")

        async def ready() -> None:
            response = await http.get(f"{base_url}/ready", headers=headers)
            response.raise_for_status()
            if response.json() != {"status": "ready", "mode": "azure"}:
                raise SmokeFailure("The target is not the initialized Azure runtime.")

        async def tools() -> None:
            transport = StreamableHttpTransport(mcp_url, headers=headers)
            async with Client(transport, timeout=60, init_timeout=60) as client:
                available = {tool.name for tool in await client.list_tools()}
                expected = {
                    "lookup_policy",
                    "assess_synthetic_claim",
                    "synthetic_customer_history",
                    "add_synthetic_review_note",
                }
                if not expected.issubset(available):
                    raise SmokeFailure("The live MCP tool contract is incomplete.")
                policy = await client.call_tool(
                    "lookup_policy",
                    {
                        "policy_id": "pol-demo-auto",
                        "query": "animal strikes",
                    },
                )
                if (
                    not isinstance(policy.data, list)
                    or not policy.data
                    or any(
                        not isinstance(citation, dict)
                        or citation.get("policyId") != "pol-demo-auto"
                        or not isinstance(citation.get("citationId"), str)
                        or not citation["citationId"].startswith("cit-")
                        or not isinstance(citation.get("quotedText"), str)
                        or not citation["quotedText"].strip()
                        or not isinstance(citation.get("sourceDocument"), str)
                        or not citation["sourceDocument"].strip()
                        for citation in policy.data
                    )
                ):
                    raise SmokeFailure("Live MCP policy retrieval did not return cited evidence.")
                if not any("animal strikes" in citation["quotedText"] for citation in policy.data):
                    raise SmokeFailure("Known animal-strike evidence was not returned by MCP.")
                assessment = await client.call_tool(
                    "assess_synthetic_claim", {"claim_id": "clm-demo-001"}
                )
                if (
                    not isinstance(assessment.data, dict)
                    or assessment.data.get("claimId") != "clm-demo-001"
                    or assessment.data.get("humanReviewRequired") is not True
                    or assessment.data.get("policyBasis") != "grounded"
                    or not isinstance(assessment.data.get("policyCitations"), list)
                    or not assessment.data["policyCitations"]
                ):
                    raise SmokeFailure("Live MCP assessment was ungrounded or lacked human review.")

        await execute("unauthenticated-rest-and-mcp-denied", unauthorized)
        await execute("authenticated-azure-readiness", ready)
        await execute("authenticated-mcp-initialize-list-call", tools)
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", required=True, help="Explicit direct API or APIM base path.")
    parser.add_argument(
        "--mcp-url",
        help="Exact MCP endpoint when it is separate from the REST base; must use the same host.",
    )
    arguments = parser.parse_args()
    try:
        url = validate_url(arguments.base_url)
        tenant = str(UUID(os.environ["AZURE_TENANT_ID"]))
        audience = str(UUID(os.environ["CLAIMS_API_AUDIENCE"]))
        with AzureCliCredential(tenant_id=tenant, process_timeout=30) as credential:
            token = credential.get_token(f"{audience}/.default").token
        checks = asyncio.run(check_http(url, token, arguments.mcp_url))
    except (KeyError, ValueError, AzureError, OSError) as error:
        logging.error("HTTP smoke setup failed (%s).", type(error).__name__)
        checks = [{"name": "http-configuration", "passed": False, "error": type(error).__name__}]
    passed = all(check["passed"] for check in checks)
    print(
        json.dumps(
            {
                "scope": "authenticated-http-and-mcp",
                "passed": passed,
                "checks": checks,
                "limitations": [
                    "The CLI client needs an explicit caller grant; this script grants nothing.",
                    "Does not prove APIM model routing, specialists or NSP denied sources.",
                ],
            },
            indent=2,
        )
    )
    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
