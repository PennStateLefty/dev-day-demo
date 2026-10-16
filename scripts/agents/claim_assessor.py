from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from jsonschema import Draft202012Validator, FormatChecker
from referencing import Registry, Resource

ROOT = Path(__file__).resolve().parents[2]
AGENT_NAME = "claim-assessor"
MANIFEST = ROOT / "agents/claim-assessor/definition.json"
SCHEMA_ROOT = ROOT / "data/schemas"


def build_definition(
    *,
    model: str,
    claims_gateway_url: str,
    api_audience: str,
) -> dict[str, Any]:
    parsed_url = urlparse(claims_gateway_url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.netloc
        or parsed_url.username
        or parsed_url.password
        or parsed_url.query
        or parsed_url.fragment
    ):
        raise ValueError("The claims gateway URL must be an absolute HTTPS URL.")
    if not api_audience.startswith("api://"):
        raise ValueError("The API audience must be an api:// application URI.")
    try:
        UUID(api_audience.removeprefix("api://"))
    except ValueError as error:
        raise ValueError("The API audience must contain a valid application UUID.") from error
    if not model.strip():
        raise ValueError("A Foundry model deployment name is required.")

    definition = json.loads(MANIFEST.read_text(encoding="utf-8"))
    replacements = {
        "${AZURE_AI_MODEL_DEPLOYMENT_NAME}": model,
        "${CLAIMS_GATEWAY_REST_URL}": claims_gateway_url.rstrip("/"),
        "${CLAIMS_API_AUDIENCE}": api_audience,
    }

    def replace_values(value: Any) -> Any:
        if isinstance(value, dict):
            return {key: replace_values(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace_values(item) for item in value]
        if isinstance(value, str):
            return replacements.get(value, value)
        return value

    resolved = replace_values(definition)
    unresolved = [
        value
        for value in _strings(resolved)
        if value.startswith("${") and value.endswith("}")
    ]
    if unresolved:
        raise ValueError(f"Unresolved agent definition values: {', '.join(unresolved)}")
    return resolved


def _strings(value: Any) -> list[str]:
    if isinstance(value, dict):
        return [text for item in value.values() for text in _strings(item)]
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return [value] if isinstance(value, str) else []


def source_digest(definition: dict[str, Any]) -> str:
    canonical = json.dumps(definition, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _get_field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _agent_reference(agent_name: str, agent_version: str) -> dict[str, str]:
    if not agent_name.strip() or not agent_version.strip():
        raise ValueError("Agent invocation requires an explicit name and version.")
    return {
        "type": "agent_reference",
        "name": agent_name,
        "version": agent_version,
    }


def publish_agent(args: argparse.Namespace) -> dict[str, str]:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import PromptAgentDefinition
    from azure.identity import DefaultAzureCredential

    definition_dict = build_definition(
        model=args.model,
        claims_gateway_url=args.claims_gateway_url,
        api_audience=args.api_audience,
    )
    digest = source_digest(definition_dict)

    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(endpoint=args.project_endpoint, credential=credential) as project,
    ):
        if any(_get_field(agent, "name") == AGENT_NAME for agent in project.agents.list()):
            for versioned_agent in project.agents.list_versions(AGENT_NAME):
                metadata = _get_field(versioned_agent, "metadata", {})
                if isinstance(metadata, dict) and metadata.get("source_sha256") == digest:
                    version = str(_get_field(versioned_agent, "version") or "")
                    if not version:
                        raise RuntimeError("Foundry returned a matching agent without a version.")
                    _pin_local_environment(args.environment, version)
                    return {
                        "agentName": AGENT_NAME,
                        "agentVersion": version,
                        "sourceSha256": digest,
                        "created": "false",
                    }

        agent = project.agents.create_version(
            agent_name=AGENT_NAME,
            definition=PromptAgentDefinition(definition_dict),
            metadata={"source_sha256": digest},
            description="Advisory synthetic claim and damage review; human decision required.",
        )
        version = str(_get_field(agent, "version"))
        _pin_local_environment(args.environment, version)
        return {
            "agentName": AGENT_NAME,
            "agentVersion": version,
            "sourceSha256": digest,
            "created": "true",
        }


def _pin_local_environment(environment: str | None, version: str) -> None:
    if environment is None:
        return
    for key, value in (
        ("CLAIM_ASSESSOR_AGENT_NAME", AGENT_NAME),
        ("CLAIM_ASSESSOR_AGENT_VERSION", version),
    ):
        result = subprocess.run(
            ["azd", "env", "set", key, value, "--environment", environment],
            cwd=ROOT,
            text=True,
            capture_output=True,
        )
        if result.returncode:
            raise RuntimeError(
                f"Could not pin {key} in azd environment {environment}: "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )


def _load_assessment_schema() -> Draft202012Validator:
    schemas = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in SCHEMA_ROOT.glob("*.schema.json")
    ]
    registry = Registry().with_resources(
        (schema["$id"], Resource.from_contents(schema)) for schema in schemas
    )
    schema = next(
        item for item in schemas if item.get("title") == "Synthetic claim assessment"
    )
    return Draft202012Validator(
        schema,
        registry=registry,
        format_checker=FormatChecker(),
    )


def invoke_agent(args: argparse.Namespace) -> dict[str, Any]:
    if not args.agent_version:
        raise ValueError(
            "An explicit agent version is required; set CLAIM_ASSESSOR_AGENT_VERSION "
            "or pass --agent-version."
        )

    import httpx
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    sys.path.insert(0, str(ROOT / "src/apps/claims-api"))
    from app.handler import ClaimHandler
    from app.models import Claim

    build_definition(
        model="claims-chat", claims_gateway_url=args.claims_gateway_url,
        api_audience=args.api_audience,
    )
    if not args.claim_id.startswith("clm-") or "/" in args.claim_id:
        raise ValueError("A valid claim identifier is required.")
    with (
        DefaultAzureCredential() as credential,
        AIProjectClient(
            endpoint=args.project_endpoint, credential=credential, allow_preview=True,
        ) as project,
        project.get_openai_client(
            agent_name=args.agent_name, timeout=180, max_retries=0,
        ) as openai_client,
    ):
        token = credential.get_token(f"{args.api_audience}/.default").token
        response = httpx.get(
            f"{args.claims_gateway_url.rstrip('/')}/api/claims/{args.claim_id}",
            headers={"Authorization": f"Bearer {token}"}, timeout=30, follow_redirects=False,
        )
        response.raise_for_status()
        claim = Claim.model_validate(response.json())
        if claim.claim_id != args.claim_id:
            raise ValueError("The getClaim tool returned a different claim.")
        return ClaimHandler(openai_client, args.agent_name, args.agent_version).run(
            claim,
        ).model_dump(mode="json", by_alias=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish or invoke the Claim Assessor.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    publish = subparsers.add_parser("publish")
    publish.add_argument("--project-endpoint", required=True)
    publish.add_argument("--model", required=True)
    publish.add_argument("--claims-gateway-url", required=True)
    publish.add_argument("--api-audience", required=True)
    publish.add_argument("--environment")
    publish.set_defaults(handler=publish_agent)

    invoke = subparsers.add_parser("invoke")
    invoke.add_argument("--project-endpoint", required=True)
    invoke.add_argument("--agent-name", default=os.getenv("CLAIM_ASSESSOR_AGENT_NAME", AGENT_NAME))
    invoke.add_argument("--agent-version", default=os.getenv("CLAIM_ASSESSOR_AGENT_VERSION"))
    invoke.add_argument("--claim-id", default="clm-demo-001")
    invoke.add_argument("--claims-gateway-url", required=True)
    invoke.add_argument("--api-audience", required=True)
    invoke.set_defaults(handler=invoke_agent)
    return parser


def main() -> None:
    args = _parser().parse_args()
    result = args.handler(args)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
