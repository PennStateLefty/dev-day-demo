from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import azure.ai.projects
import azure.identity
import pytest
from agents.claim_assessor import (
    AGENT_NAME,
    _agent_reference,
    _load_assessment_schema,
    build_definition,
    invoke_agent,
    publish_agent,
    source_digest,
)
from agents.synthetic_image import synthetic_damage_image
from azure.ai.projects.models import PromptAgentDefinition
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]


def test_agent_definition_uses_resolved_managed_identity_apim_tools() -> None:
    definition = build_definition(
        model="claims-chat",
        claims_gateway_url="https://apim.example.test/claims/",
        api_audience="api://00000000-0000-0000-0000-000000000001",
    )
    tool = definition["tools"][0]
    assert definition["kind"] == "prompt"
    assert definition["model"] == "claims-chat"
    assert tool["type"] == "openapi"
    assert tool["openapi"]["spec"]["servers"][0]["url"] == (
        "https://apim.example.test/claims"
    )
    assert tool["openapi"]["auth"] == {
        "type": "managed_identity",
        "security_scheme": {
            "audience": "api://00000000-0000-0000-0000-000000000001"
        },
    }
    methods = {
        method
        for path in tool["openapi"]["spec"]["paths"].values()
        for method in path
    }
    assert methods <= {"get", "post"}
    assert not any(
        "send" in operation.get("operationId", "").casefold()
        for path in tool["openapi"]["spec"]["paths"].values()
        for operation in path.values()
    )


def test_agent_definition_rejects_unresolved_configuration() -> None:
    with pytest.raises(ValueError, match="Unresolved agent definition values"):
        build_definition(
            model="${MODEL}",
            claims_gateway_url="https://apim.example.test/claims",
            api_audience="api://00000000-0000-0000-0000-000000000001",
        )


def test_agent_definition_is_accepted_by_locked_foundry_sdk() -> None:
    definition = build_definition(
        model="claims-chat",
        claims_gateway_url="https://apim.example.test/claims",
        api_audience="api://00000000-0000-0000-0000-000000000001",
    )
    encoded = PromptAgentDefinition(definition).as_dict()
    assert encoded == definition


def test_invoke_requires_an_explicit_agent_version() -> None:
    with pytest.raises(ValueError, match="explicit agent version"):
        invoke_agent(type("Args", (), {"agent_version": None})())


def test_invoke_agent_reference_uses_current_pinned_responses_contract() -> None:
    assert _agent_reference("claim-assessor", "2") == {
        "type": "agent_reference",
        "name": "claim-assessor",
        "version": "2",
    }


@pytest.mark.parametrize(
    ("url", "audience"),
    [
        ("http://apim.example.test/claims", "api://00000000-0000-0000-0000-000000000001"),
        ("https://apim.example.test/claims?key=value", "api://00000000-0000-0000-0000-000000000001"),
        ("https://apim.example.test/claims", "00000000-0000-0000-0000-000000000001"),
        ("https://apim.example.test/claims", "api://not-a-uuid"),
    ],
)
def test_agent_definition_rejects_unsafe_or_invalid_endpoints(url: str, audience: str) -> None:
    with pytest.raises(ValueError):
        build_definition(model="claims-chat", claims_gateway_url=url, api_audience=audience)


def test_generated_damage_fixture_is_png() -> None:
    image = synthetic_damage_image()
    assert image.startswith(b"\x89PNG\r\n\x1a\n")
    assert image[12:16] == b"IHDR"
    assert len(image) > 1000


def test_synthetic_evaluation_case_routes_image_analysis_to_api() -> None:
    dataset = json.loads(
        (ROOT / "evaluations/datasets/claim-assessor.json").read_text(encoding="utf-8")
    )
    assert dataset["claimId"] == "clm-demo-001"
    assert "not a real claimant photograph" in dataset["expectedEvidence"][0]
    assert dataset["imageAnalysisOwner"] == "claims-api"
    assert dataset["requiredInvariant"]["humanReviewRequired"] is True


def test_assessment_schema_resolves_policy_citation_references() -> None:
    validator = _load_assessment_schema()
    assert isinstance(validator, Draft202012Validator)
    assert source_digest(
        build_definition(
            model="claims-chat",
            claims_gateway_url="https://apim.example.test/claims",
            api_audience="api://00000000-0000-0000-0000-000000000001",
        )
    ) == source_digest(
        build_definition(
            model="claims-chat",
            claims_gateway_url="https://apim.example.test/claims/",
            api_audience="api://00000000-0000-0000-0000-000000000001",
        )
    )


def test_publish_reuses_matching_version_metadata_from_version_history(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = build_definition(
        model="claims-chat",
        claims_gateway_url="https://apim.example.test/claims",
        api_audience="api://00000000-0000-0000-0000-000000000001",
    )
    digest = source_digest(definition)

    class FakeCredential:
        def __enter__(self) -> FakeCredential:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class FakeAgentCollection:
        def list(self) -> list[SimpleNamespace]:
            return [SimpleNamespace(name=AGENT_NAME, versions={})]

        def list_versions(self, agent_name: str) -> list[SimpleNamespace]:
            assert agent_name == AGENT_NAME
            return [
                SimpleNamespace(version="2", metadata={"source_sha256": digest}),
                SimpleNamespace(version="1", metadata={"source_sha256": "old-digest"}),
            ]

        def create_version(self, **_: object) -> None:
            pytest.fail("A matching published version should be reused.")

    class FakeProject:
        agents = FakeAgentCollection()

        def __init__(self, **_: object) -> None:
            pass

        def __enter__(self) -> FakeProject:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    monkeypatch.setattr(azure.identity, "DefaultAzureCredential", FakeCredential)
    monkeypatch.setattr(azure.ai.projects, "AIProjectClient", FakeProject)

    result = publish_agent(
        Namespace(
            model="claims-chat",
            claims_gateway_url="https://apim.example.test/claims",
            api_audience="api://00000000-0000-0000-0000-000000000001",
            project_endpoint="https://project.example.test",
            environment=None,
        )
    )

    assert result == {
        "agentName": AGENT_NAME,
        "agentVersion": "2",
        "sourceSha256": digest,
        "created": "false",
    }
