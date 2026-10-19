from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parents[2]
AGENT_NAME = "communication"
DEFINITION = ROOT / "agents/communication/definition.json"
INSTRUCTIONS = ROOT / "agents/communication/instructions.md"
OUTPUT_SCHEMA = ROOT / "data/schemas/communication-agent-output.schema.json"


def build_definition(model: str) -> dict[str, Any]:
    if not model.strip() or "${" in model:
        raise ValueError("A resolved Foundry model deployment name is required.")
    definition = json.loads(DEFINITION.read_text(encoding="utf-8"))
    definition["model"] = model
    definition["instructions"] = INSTRUCTIONS.read_text(encoding="utf-8").strip()
    unresolved = [
        value
        for value in _strings(definition)
        if value.startswith("${") and value.endswith("}")
    ]
    if unresolved:
        raise ValueError(f"Unresolved Communication definition values: {', '.join(unresolved)}")
    return definition


def _strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return [value] if isinstance(value, str) else []


def source_digest(definition: dict[str, Any]) -> str:
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def validate_output(text: str) -> dict[str, str]:
    payload = json.loads(text)
    Draft202012Validator(
        json.loads(OUTPUT_SCHEMA.read_text(encoding="utf-8")),
        format_checker=FormatChecker(),
    ).validate(payload)
    return payload


def _field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def publish_agent(args: argparse.Namespace) -> dict[str, str]:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import PromptAgentDefinition
    from azure.identity import DefaultAzureCredential

    definition = build_definition(args.model)
    agent_definition = PromptAgentDefinition(definition)
    digest = source_digest(definition)
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(
            endpoint=args.project_endpoint,
            credential=credential,
            allow_preview=True,
        ) as project,
    ):
        if any(_field(agent, "name") == AGENT_NAME for agent in project.agents.list()):
            for versioned_agent in project.agents.list_versions(AGENT_NAME):
                metadata = _field(versioned_agent, "metadata", {})
                if isinstance(metadata, dict) and metadata.get("source_sha256") == digest:
                    version = str(_field(versioned_agent, "version") or "")
                    if not version:
                        raise RuntimeError("Foundry returned a matching agent without a version.")
                    return {
                        "agentName": AGENT_NAME,
                        "agentVersion": version,
                        "sourceSha256": digest,
                        "created": "false",
                    }
        agent = project.agents.create_version(
            agent_name=AGENT_NAME,
            definition=agent_definition,
            metadata={"source_sha256": digest},
            description="Draft-only synthetic claims customer updates for human review.",
        )
    version = str(_field(agent, "version") or "")
    if not version:
        raise RuntimeError("Foundry created the Communication agent without a version.")
    return {
        "agentName": AGENT_NAME,
        "agentVersion": version,
        "sourceSha256": digest,
        "created": "true",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish the versioned Communication agent.")
    commands = parser.add_subparsers(dest="command", required=True)
    publish = commands.add_parser("publish")
    publish.add_argument("--project-endpoint", required=True)
    publish.add_argument("--model", default="claims-chat")
    publish.set_defaults(handler=publish_agent)
    return parser


def main() -> None:
    args = _parser().parse_args()
    print(json.dumps(args.handler(args), indent=2))


if __name__ == "__main__":
    main()
