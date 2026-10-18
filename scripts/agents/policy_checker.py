from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = ROOT / "src/apps/policy-checker"
sys.path.insert(0, str(APP_ROOT))

from policy_checker import (  # noqa: E402
    TOOL_NAMES,
    TOOLBOX_NAME,
    build_mcp_tool,
    load_instructions,
    validate_versioned_toolbox_endpoint,
    versioned_toolbox_endpoint,
)


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _https_url(value: str, label: str) -> str:
    parsed = urlparse(value)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(f"{label} must be an absolute HTTPS URL without credentials or query.")
    return value.rstrip("/")


def publish_toolbox(
    project: Any,
    *,
    project_endpoint: str,
    claims_mcp_url: str,
    project_connection_id: str,
) -> tuple[str, str]:
    _https_url(project_endpoint, "The Foundry project endpoint")
    tool = build_mcp_tool(claims_mcp_url, project_connection_id)
    source = {
        "claimsMcpUrl": tool.server_url,
        "projectConnectionId": project_connection_id,
        "toolNames": TOOL_NAMES,
    }
    digest = hashlib.sha256(
        json.dumps(source, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    exists = any(_field(item, "name") == TOOLBOX_NAME for item in project.toolboxes.list())
    if exists:
        for item in project.toolboxes.list_versions(TOOLBOX_NAME):
            metadata = _field(item, "metadata", {})
            if isinstance(metadata, dict) and metadata.get("source_sha256") == digest:
                version = str(_field(item, "version") or "")
                if not version:
                    raise RuntimeError("Foundry returned a matching Toolbox without a version.")
                return version, digest

    toolbox = project.toolboxes.create_version(
        name=TOOLBOX_NAME,
        description="Read-only synthetic policy evidence lookup with source citations.",
        metadata={"source_sha256": digest},
        tools=[tool],
    )
    version = str(_field(toolbox, "version") or "")
    if not version:
        raise RuntimeError("Foundry created the Policy Checker Toolbox without a version.")
    return version, digest


def publish(args: argparse.Namespace) -> dict[str, str]:
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    endpoint = _https_url(args.project_endpoint, "The Foundry project endpoint")
    claims_mcp_url = args.claims_mcp_url
    build_mcp_tool(claims_mcp_url, args.project_connection_id)
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=endpoint, credential=credential) as project,
    ):
        version, digest = publish_toolbox(
            project,
            project_endpoint=endpoint,
            claims_mcp_url=claims_mcp_url,
            project_connection_id=args.project_connection_id,
        )
    toolbox_endpoint = versioned_toolbox_endpoint(endpoint, version)
    validate_versioned_toolbox_endpoint(toolbox_endpoint, endpoint, version)
    return {
        "toolboxName": TOOLBOX_NAME,
        "toolboxVersion": version,
        "toolboxSourceSha256": digest,
        "toolboxEndpoint": toolbox_endpoint,
    }


async def _invoke(
    *,
    project_endpoint: str,
    model: str,
    toolbox_endpoint: str,
    toolbox_version: str,
    policy_id: str,
    query: str,
) -> str:
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient
    from agent_framework_foundry_hosting import FoundryToolbox
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    if not model.strip():
        raise ValueError("A Foundry model deployment name is required.")
    if not re.fullmatch(r"pol-[a-z0-9-]+", policy_id) or not 1 <= len(query.strip()) <= 1000:
        raise ValueError("A policy ID and focused policy question are required.")
    endpoint = _https_url(project_endpoint, "The Foundry project endpoint")
    toolbox_url = validate_versioned_toolbox_endpoint(
        toolbox_endpoint,
        endpoint,
        toolbox_version,
    )
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=endpoint, credential=credential) as project,
    ):
        project.toolboxes.get_version(TOOLBOX_NAME, toolbox_version)
        client = FoundryChatClient(
            project_endpoint=endpoint,
            model=model,
            credential=credential,
        )
        async with FoundryToolbox(
            credential,
            url=toolbox_url,
            name=TOOLBOX_NAME,
        ) as toolbox:
            async with Agent(
                client=client,
                name="policy-checker-consumer",
                instructions=load_instructions(),
                tools=toolbox,
                default_options={"store": False},
            ) as agent:
                response = await agent.run(f"Policy ID: {policy_id}\nQuestion: {query}")
    text = response.text
    if not isinstance(text, str) or not text.strip():
        raise ValueError("The Policy Checker returned no response.")
    return text.strip()


def invoke(args: argparse.Namespace) -> dict[str, str]:
    text = asyncio.run(
        _invoke(
            project_endpoint=args.project_endpoint,
            model=args.model,
            toolbox_endpoint=args.toolbox_endpoint,
            toolbox_version=args.toolbox_version,
            policy_id=args.policy_id,
            query=args.query,
        )
    )
    return {"policyId": args.policy_id, "response": text}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish or locally invoke the version-pinned Policy Checker Toolbox."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    publish_command = commands.add_parser("publish")
    publish_command.add_argument("--project-endpoint", required=True)
    publish_command.add_argument("--claims-mcp-url", required=True)
    publish_command.add_argument(
        "--project-connection-id",
        default=os.getenv("CLAIMS_POLICY_MCP_CONNECTION_ID"),
        required=os.getenv("CLAIMS_POLICY_MCP_CONNECTION_ID") is None,
    )
    publish_command.set_defaults(handler=publish)

    invoke_command = commands.add_parser("invoke")
    invoke_command.add_argument("--project-endpoint", required=True)
    invoke_command.add_argument("--model", required=True)
    invoke_command.add_argument("--toolbox-endpoint", required=True)
    invoke_command.add_argument("--toolbox-version", required=True)
    invoke_command.add_argument("--policy-id", required=True)
    invoke_command.add_argument("--query", required=True)
    invoke_command.set_defaults(handler=invoke)
    return parser


def main() -> None:
    args = _parser().parse_args()
    print(json.dumps(args.handler(args), indent=2))


if __name__ == "__main__":
    main()
