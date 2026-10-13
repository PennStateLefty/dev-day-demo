from __future__ import annotations

import os
from dataclasses import dataclass

from .models import Assessment, ResponseDraft, WorkflowResult
from .service import DemoService


@dataclass(frozen=True)
class PromptAgentReference:
    project_endpoint: str
    agent_name: str
    agent_version: str

    @classmethod
    def from_environment(cls, prefix: str) -> PromptAgentReference:
        values = {
            "project_endpoint": os.getenv("FOUNDRY_PROJECT_ENDPOINT", ""),
            "agent_name": os.getenv(f"{prefix}_AGENT_NAME", ""),
            "agent_version": os.getenv(f"{prefix}_AGENT_VERSION", ""),
        }
        missing = [key for key, value in values.items() if not value]
        if missing:
            raise ValueError(
                "Foundry prompt agents require explicit endpoint, name, and version; "
                f"missing {', '.join(missing)}."
            )
        return cls(**values)


class LocalDemoOrchestrator:
    """Deterministic local orchestration; it makes no model or coverage decision."""

    def __init__(self, service: DemoService) -> None:
        self.service = service

    def run(self, claim_id: str) -> WorkflowResult:
        assessment = self.service.assess_claim(claim_id)
        draft = ResponseDraft.model_validate(self.service.create_response_draft(assessment))
        return WorkflowResult(assessment=assessment, response_draft=draft)


async def invoke_foundry_prompt_agent(
    reference: PromptAgentReference,
    prompt: str,
) -> str:
    """Invoke a version-pinned Foundry prompt agent when the optional SDK is installed."""
    try:
        from agent_framework.foundry import FoundryAgent
        from azure.identity import DefaultAzureCredential
    except ImportError as error:
        raise RuntimeError(
            "Install the optional, target-validated Foundry Agent Framework dependencies "
            "before enabling live Foundry calls."
        ) from error

    credential = DefaultAzureCredential()
    try:
        agent = FoundryAgent(
            project_endpoint=reference.project_endpoint,
            agent_name=reference.agent_name,
            agent_version=reference.agent_version,
            credential=credential,
        )
        result = await agent.run(prompt)
        return result.text
    finally:
        credential.close()


def configured_specialists() -> tuple[PromptAgentReference, PromptAgentReference]:
    return (
        PromptAgentReference.from_environment("POLICY"),
        PromptAgentReference.from_environment("RESPONSE"),
    )


def workflow_prompt(assessment: Assessment) -> str:
    return (
        "Use the supplied synthetic assessment only. Do not decide coverage, approve, deny, "
        "settle, pay, or send a message. Return a response draft for a human to review.\n\n"
        + assessment.model_dump_json(by_alias=True)
    )
