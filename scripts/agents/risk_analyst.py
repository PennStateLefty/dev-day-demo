from __future__ import annotations

import argparse
import asyncio
import hashlib
import io
import json
import os
import re
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
SKILL_FILE = ROOT / "agents/risk-analyst/SKILL.md"
SCHEMA_FILE = ROOT / "data/schemas/risk-review.schema.json"
SKILL_NAME = "risk-analyst"
TOOLBOX_NAME = "risk-analyst-toolbox"
TOOL_NAMES = (
    "get_synthetic_claim",
    "assess_synthetic_claim",
    "synthetic_customer_history",
)


def _get_field(value: Any, name: str, default: Any = None) -> Any:
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


def _versioned_toolbox_url(value: str, project_endpoint: str, version: str) -> str:
    parsed = urlparse(value)
    project = urlparse(project_endpoint)
    if not re.fullmatch(r"[A-Za-z0-9._-]+", version):
        raise ValueError("The Toolbox version must be a simple explicit version identifier.")
    expected_path = (
        f"{project.path.rstrip('/')}/toolboxes/{TOOLBOX_NAME}/versions/{version}/mcp"
    )
    if (
        parsed.scheme != "https"
        or not parsed.netloc
        or parsed.username
        or parsed.password
        or parsed.netloc != project.netloc
        or parsed.path != expected_path
        or parsed.query != "api-version=v1"
        or parsed.fragment
    ):
        raise ValueError(
            "The Toolbox endpoint must be the explicit version endpoint ending in "
            f"{expected_path}?api-version=v1."
        )
    return value


def read_skill() -> tuple[str, str, str, str]:
    content = SKILL_FILE.read_text(encoding="utf-8")
    match = re.match(r"\A---\r?\n(.*?)\r?\n---\r?\n(.*)\Z", content, re.DOTALL)
    if match is None:
        raise ValueError("Risk Analyst SKILL.md must have a YAML front matter block.")

    front_matter, instructions = match.groups()
    fields: dict[str, str] = {}
    for line in front_matter.splitlines():
        key, separator, value = line.partition(":")
        if not separator or not key.strip() or not value.strip():
            raise ValueError("Risk Analyst SKILL.md front matter contains an invalid field.")
        fields[key.strip()] = value.strip()
    name = fields.get("name")
    description = fields.get("description")
    if name != SKILL_NAME or not description or not instructions.strip():
        raise ValueError(
            "Risk Analyst SKILL.md must define its name, description, and instructions."
        )
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return name, description, instructions.strip(), digest


def build_mcp_tool(claims_mcp_url: str, project_connection_id: str) -> Any:
    from azure.ai.projects.models import MCPToolboxTool

    if not project_connection_id.strip():
        raise ValueError(
            "A configured Entra-authenticated APIM MCP project connection is required."
        )
    return MCPToolboxTool(
        server_label="claims-api",
        server_url=_https_url(claims_mcp_url, "The claims MCP URL"),
        project_connection_id=project_connection_id,
        allowed_tools=list(TOOL_NAMES),
        require_approval="never",
    )


def _manifest_digest(archive: bytes) -> str | None:
    with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
        for filename in bundle.namelist():
            if filename.endswith("source-manifest.json"):
                manifest = json.loads(bundle.read(filename))
                value = manifest.get("sourceSha256")
                return value if isinstance(value, str) else None
    return None


def _existing_skill_version(project: Any, digest: str) -> str | None:
    skill = next(
        (item for item in project.beta.skills.list() if _get_field(item, "name") == SKILL_NAME),
        None,
    )
    if skill is None:
        return None
    for version in project.beta.skills.list_versions(SKILL_NAME):
        version_id = str(_get_field(version, "version") or "")
        if not version_id:
            raise RuntimeError("Foundry returned a Risk Analyst skill version without an ID.")
        archive = b"".join(project.beta.skills.download_version(SKILL_NAME, version_id))
        if _manifest_digest(archive) == digest:
            return version_id
    return None


def publish_skill(project: Any) -> tuple[str, str]:
    from azure.ai.projects.models import CreateSkillVersionFromFilesBody

    name, description, _, digest = read_skill()
    existing = _existing_skill_version(project, digest)
    if existing:
        return existing, digest

    content = SKILL_FILE.read_bytes()
    manifest = json.dumps(
        {"name": name, "sourceSha256": digest},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    skill = project.beta.skills.create_from_files(
        name=SKILL_NAME,
        content=CreateSkillVersionFromFilesBody(
            files=[
                ("SKILL.md", content),
                ("source-manifest.json", manifest),
            ],
            default=False,
        ),
    )
    version = str(_get_field(skill, "version") or "")
    if not version:
        raise RuntimeError("Foundry created a Risk Analyst skill without a version.")
    if _get_field(skill, "description") not in (None, description):
        raise RuntimeError("Foundry returned a different Risk Analyst skill description.")
    return version, digest


def publish_toolbox(
    project: Any,
    *,
    claims_mcp_url: str,
    project_connection_id: str,
    skill_version: str,
    skill_digest: str,
) -> tuple[str, str]:
    from azure.ai.projects.models import ToolboxSkillReference

    tool = build_mcp_tool(claims_mcp_url, project_connection_id)
    digest_input = {
        "claimsMcpUrl": tool.server_url,
        "projectConnectionId": project_connection_id,
        "skillName": SKILL_NAME,
        "skillSourceSha256": skill_digest,
        "skillVersion": skill_version,
        "toolNames": TOOL_NAMES,
    }
    digest = hashlib.sha256(
        json.dumps(digest_input, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    toolbox_exists = any(
        _get_field(item, "name") == TOOLBOX_NAME for item in project.toolboxes.list()
    )
    if toolbox_exists:
        for existing in project.toolboxes.list_versions(TOOLBOX_NAME):
            metadata = _get_field(existing, "metadata", {})
            if isinstance(metadata, dict) and metadata.get("source_sha256") == digest:
                version = str(_get_field(existing, "version") or "")
                if not version:
                    raise RuntimeError("Foundry returned a matching Toolbox without a version.")
                return version, digest

    toolbox = project.toolboxes.create_version(
        name=TOOLBOX_NAME,
        description="Read-only synthetic claim consistency and bounded history tools plus skill.",
        metadata={"source_sha256": digest, "skill_version": skill_version},
        tools=[tool],
        skills=[ToolboxSkillReference(name=SKILL_NAME, version=skill_version)],
    )
    version = str(_get_field(toolbox, "version") or "")
    if not version:
        raise RuntimeError("Foundry created a Risk Analyst Toolbox without a version.")
    return version, digest


def publish(args: argparse.Namespace) -> dict[str, str]:
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    endpoint = _https_url(args.project_endpoint, "The Foundry project endpoint")
    claims_mcp_url = _https_url(args.claims_mcp_url, "The claims MCP URL")
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=endpoint, credential=credential) as project,
    ):
        skill_version, skill_digest = publish_skill(project)
        toolbox_version, toolbox_digest = publish_toolbox(
            project,
            claims_mcp_url=claims_mcp_url,
            project_connection_id=args.project_connection_id,
            skill_version=skill_version,
            skill_digest=skill_digest,
        )
    return {
        "skillName": SKILL_NAME,
        "skillVersion": skill_version,
        "skillSourceSha256": skill_digest,
        "toolboxName": TOOLBOX_NAME,
        "toolboxVersion": toolbox_version,
        "toolboxSourceSha256": toolbox_digest,
    }


def publish_skill_command(args: argparse.Namespace) -> dict[str, str]:
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    endpoint = _https_url(args.project_endpoint, "The Foundry project endpoint")
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=endpoint, credential=credential) as project,
    ):
        version, digest = publish_skill(project)
    return {
        "skillName": SKILL_NAME,
        "skillVersion": version,
        "skillSourceSha256": digest,
    }


def _load_review_validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=FormatChecker())


async def _invoke(
    *,
    project_endpoint: str,
    model: str,
    toolbox_endpoint: str,
    toolbox_version: str,
    claim_id: str,
) -> dict[str, Any]:
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient, FoundryToolbox
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    if not toolbox_version.strip():
        raise ValueError("An explicit Risk Analyst Toolbox version is required.")
    if not re.fullmatch(r"clm-[a-z0-9-]+", claim_id):
        raise ValueError("A valid synthetic claim ID is required.")
    endpoint = _https_url(project_endpoint, "The Foundry project endpoint")
    toolbox_url = _versioned_toolbox_url(toolbox_endpoint, endpoint, toolbox_version)
    if not model.strip():
        raise ValueError("A Foundry model deployment name is required.")

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
            skills_provider = toolbox.as_skills_provider()
            async with Agent(
                client=client,
                name="risk-analyst-consumer",
                instructions=(
                    "Use the Risk Analyst skill and only its bounded read-only synthetic claims "
                    "tools. Return exactly one JSON object matching its required schema."
                ),
                tools=toolbox,
                context_providers=[skills_provider],
            ) as agent:
                response = await agent.run(
                    f"Review synthetic claim {claim_id} for consistency and relevant bounded "
                    "history. Return the advisory JSON review."
                )

    text = response.text
    if not isinstance(text, str) or not text.strip():
        raise ValueError("The Risk Analyst Toolbox consumer returned no review.")
    try:
        result = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError("The Risk Analyst did not return valid JSON.") from error
    errors = sorted(
        _load_review_validator().iter_errors(result),
        key=lambda error: list(error.absolute_path),
    )
    if errors:
        details = "; ".join(
            f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: "
            f"{error.message}"
            for error in errors
        )
        raise ValueError(f"The Risk Analyst review failed schema validation: {details}")
    if result["claimId"] != claim_id:
        raise ValueError("The Risk Analyst returned a review for a different claim.")
    return result


def invoke(args: argparse.Namespace) -> dict[str, Any]:
    return asyncio.run(
        _invoke(
            project_endpoint=args.project_endpoint,
            model=args.model,
            toolbox_endpoint=args.toolbox_endpoint,
            toolbox_version=args.toolbox_version,
            claim_id=args.claim_id,
        )
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish the versioned Risk Analyst skill/Toolbox or invoke a pinned Toolbox."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    publish_command = commands.add_parser("publish")
    publish_command.add_argument("--project-endpoint", required=True)
    publish_command.add_argument("--claims-mcp-url", required=True)
    publish_command.add_argument(
        "--project-connection-id",
        default=os.getenv("CLAIMS_MCP_PROJECT_CONNECTION_ID"),
        required=os.getenv("CLAIMS_MCP_PROJECT_CONNECTION_ID") is None,
    )
    publish_command.set_defaults(handler=publish)

    skill_command = commands.add_parser("publish-skill")
    skill_command.add_argument("--project-endpoint", required=True)
    skill_command.set_defaults(handler=publish_skill_command)

    invoke_command = commands.add_parser("invoke")
    invoke_command.add_argument("--project-endpoint", required=True)
    invoke_command.add_argument("--model", required=True)
    invoke_command.add_argument("--toolbox-endpoint", required=True)
    invoke_command.add_argument("--toolbox-version", required=True)
    invoke_command.add_argument("--claim-id", default="clm-demo-001")
    invoke_command.set_defaults(handler=invoke)
    return parser


def main() -> None:
    args = _parser().parse_args()
    print(json.dumps(args.handler(args), indent=2))


if __name__ == "__main__":
    main()
