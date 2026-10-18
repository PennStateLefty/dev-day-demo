from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

if TYPE_CHECKING:
    from azure.ai.projects.models import MCPToolboxTool

TOOLBOX_NAME = "policy-checker-toolbox"
TOOL_NAMES = ("lookup_policy",)
CLAIMS_MCP_PATH = "/claims-tools/mcp/"
INSTRUCTIONS_PATH = Path(__file__).with_name("instructions.md")


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


def build_mcp_tool(
    claims_mcp_url: str,
    project_connection_id: str,
) -> MCPToolboxTool:
    from azure.ai.projects.models import MCPToolboxTool

    parsed = urlparse(claims_mcp_url)
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.path != CLAIMS_MCP_PATH
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError(
            "The policy Toolbox must use the existing Entra-protected Claims MCP route."
        )
    if not project_connection_id.strip():
        raise ValueError("An Agent Identity MCP project connection is required.")
    return MCPToolboxTool(
        server_label="claims-policy",
        server_url=claims_mcp_url,
        project_connection_id=project_connection_id,
        allowed_tools=list(TOOL_NAMES),
        require_approval="never",
    )


def versioned_toolbox_endpoint(
    project_endpoint: str,
    version: str,
) -> str:
    endpoint = _https_url(project_endpoint, "The Foundry project endpoint")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", version):
        raise ValueError("The Toolbox version must be an explicit version identifier.")
    return f"{endpoint}/toolboxes/{TOOLBOX_NAME}/versions/{version}/mcp?api-version=v1"


def validate_versioned_toolbox_endpoint(
    toolbox_endpoint: str,
    project_endpoint: str,
    version: str,
) -> str:
    expected = urlparse(versioned_toolbox_endpoint(project_endpoint, version))
    actual = urlparse(toolbox_endpoint)
    if (
        actual.scheme != "https"
        or actual.netloc != expected.netloc
        or actual.path != expected.path
        or actual.query != "api-version=v1"
        or actual.username
        or actual.password
        or actual.fragment
    ):
        raise ValueError(
            "The Toolbox endpoint must be the exact versioned endpoint ending in "
            f"{expected.path}?api-version=v1."
        )
    return toolbox_endpoint


def load_instructions() -> str:
    instructions = INSTRUCTIONS_PATH.read_text(encoding="utf-8").strip()
    if not instructions:
        raise ValueError("Policy Checker instructions must not be empty.")
    return instructions
