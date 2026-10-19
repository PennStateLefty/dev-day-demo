from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from azure.ai.projects.models import MCPToolboxTool
from policy_checker import (
    TOOL_NAMES,
    TOOLBOX_NAME,
    build_mcp_tool,
    load_instructions,
    validate_versioned_toolbox_endpoint,
    versioned_toolbox_endpoint,
)


def test_policy_checker_instructions_preserve_evidence_and_decision_boundaries() -> None:
    instructions = load_instructions().casefold()
    assert "lookup_policy" in instructions
    assert "citation id" in instructions
    assert "source document" in instructions
    assert "human review is required" in instructions
    for boundary in ("coverage", "eligibility", "liability", "approval", "denial", "payment"):
        assert boundary in instructions
    assert "from memory" in instructions


def test_policy_checker_toolbox_exposes_only_bounded_claims_policy_lookup() -> None:
    tool = build_mcp_tool(
        "https://apim.example.test/claims-tools/mcp/",
        "claims-policy-agent-identity",
    )
    assert isinstance(tool, MCPToolboxTool)
    assert tool.server_label == "claims-policy"
    assert tool.server_url == "https://apim.example.test/claims-tools/mcp/"
    assert tool.project_connection_id == "claims-policy-agent-identity"
    assert tool.allowed_tools == list(TOOL_NAMES) == ["lookup_policy"]
    assert tool.require_approval == "never"


@pytest.mark.parametrize(
    ("url", "connection"),
    [
        ("http://apim.example.test/claims-tools/mcp/", "agent-identity"),
        ("https://apim.example.test/claims-tools/mcp/?key=unsafe", "agent-identity"),
        ("https://claims.example.test/mcp/", "agent-identity"),
        ("https://apim.example.test/claims-tools/mcp/", ""),
    ],
)
def test_policy_checker_toolbox_rejects_unsafe_or_unbounded_connections(
    url: str,
    connection: str,
) -> None:
    with pytest.raises(ValueError):
        build_mcp_tool(url, connection)


def test_policy_checker_endpoint_is_pinned_to_the_exact_toolbox_version() -> None:
    project_endpoint = "https://foundry.example.test/api/projects/claims"
    endpoint = versioned_toolbox_endpoint(project_endpoint, "3")
    assert endpoint == (
        f"{project_endpoint}/toolboxes/{TOOLBOX_NAME}/versions/3/mcp?api-version=v1"
    )
    assert validate_versioned_toolbox_endpoint(endpoint, project_endpoint, "3") == endpoint

    with pytest.raises(ValueError, match="exact versioned endpoint"):
        validate_versioned_toolbox_endpoint(
            f"{project_endpoint}/toolboxes/{TOOLBOX_NAME}/mcp?api-version=v1",
            project_endpoint,
            "3",
        )
    with pytest.raises(ValueError):
        versioned_toolbox_endpoint(project_endpoint, "../default")


def test_hosted_agent_connects_directly_to_its_pinned_toolbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = Path(__file__).resolve().parents[2] / "apps/policy-checker/main.py"
    spec = importlib.util.spec_from_file_location("policy_checker_hosted_main", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    project_endpoint = "https://foundry.example.test/api/projects/claims"
    toolbox_endpoint = versioned_toolbox_endpoint(project_endpoint, "7")
    monkeypatch.setenv("AZURE_AI_PROJECT_ENDPOINT", project_endpoint)
    monkeypatch.setenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "claims-chat")
    monkeypatch.setenv("POLICY_CHECKER_TOOLBOX_VERSION", "7")
    monkeypatch.setenv("POLICY_CHECKER_TOOLBOX_ENDPOINT", toolbox_endpoint)
    monkeypatch.setattr(module, "credential", object())

    captured: dict[str, object] = {}

    def fake_client(**kwargs: object) -> object:
        captured["client"] = kwargs
        return object()

    def fake_toolbox(credential: object, *, url: str, name: str) -> object:
        captured["toolbox"] = {"credential": credential, "url": url, "name": name}
        return object()

    class FakeAgent:
        def __init__(self, **kwargs: object) -> None:
            captured["agent"] = kwargs

    monkeypatch.setattr(module, "FoundryChatClient", fake_client)
    monkeypatch.setattr(module, "FoundryToolbox", fake_toolbox)
    monkeypatch.setattr(module, "Agent", FakeAgent)

    module.create_agent()

    toolbox_config = captured["toolbox"]
    assert isinstance(toolbox_config, dict)
    assert toolbox_config["url"] == toolbox_endpoint
    assert toolbox_config["name"] == TOOLBOX_NAME
    assert toolbox_config["url"].startswith(project_endpoint)
    assert "apim" not in toolbox_config["url"]
    agent_config = captured["agent"]
    assert isinstance(agent_config, dict)
    assert agent_config["default_options"] == {"store": False}
