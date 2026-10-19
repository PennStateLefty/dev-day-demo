from __future__ import annotations

from argparse import Namespace
from pathlib import Path
from types import SimpleNamespace

import azure.ai.projects
import azure.identity
import pytest
from azure.ai.projects.models import PromptAgentDefinition
from jsonschema import ValidationError

from agents.communication import (
    AGENT_NAME,
    build_definition,
    publish_agent,
    source_digest,
    validate_output,
)

ROOT = Path(__file__).resolve().parents[3]


def test_communication_definition_is_demo_focused_prompt_without_tools() -> None:
    definition = build_definition("claims-chat")
    assert definition["kind"] == "prompt"
    assert definition["model"] == "claims-chat"
    assert "tools" not in definition
    assert "Never send" in definition["instructions"]
    assert "Do not say a handler has already reviewed" in definition["instructions"]
    assert "promise that anyone will contact or follow up" in definition["instructions"]
    assert "coverage" in definition["instructions"]
    assert PromptAgentDefinition(definition).as_dict() == definition
    assert source_digest(definition) == source_digest(build_definition("claims-chat"))
    with pytest.raises(ValueError, match="resolved"):
        build_definition("${AZURE_AI_MODEL_DEPLOYMENT_NAME}")


def test_communication_output_schema_is_strict() -> None:
    assert validate_output('{"body":"A handler will review the information."}') == {
        "body": "A handler will review the information."
    }
    with pytest.raises(ValidationError):
        validate_output('{"body":"Draft","citationIds":["cit-demo-001"]}')


def test_publish_reuses_matching_immutable_version(monkeypatch: pytest.MonkeyPatch) -> None:
    definition = build_definition("claims-chat")
    digest = source_digest(definition)

    class FakeCredential:
        def __enter__(self) -> FakeCredential:
            return self

        def __exit__(self, *_: object) -> None:
            return None

    class FakeAgentCollection:
        def list(self) -> list[SimpleNamespace]:
            return [SimpleNamespace(name=AGENT_NAME)]

        def list_versions(self, agent_name: str) -> list[SimpleNamespace]:
            assert agent_name == AGENT_NAME
            return [SimpleNamespace(version="1", metadata={"source_sha256": digest})]

        def create_version(self, **_: object) -> None:
            pytest.fail("A matching immutable version should be reused.")

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
    result = publish_agent(Namespace(
        project_endpoint="https://project.example.test",
        model="claims-chat",
    ))
    assert result == {
        "agentName": AGENT_NAME,
        "agentVersion": "1",
        "sourceSha256": digest,
        "created": "false",
    }
