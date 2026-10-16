from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .models import AgentRecommendation, Claim, EnrichedAssessment, HandlerResult

ASSESS_OPERATION = "getClaimAssessment"


class HandlerError(Exception):
    """The agent did not return a verifiable handler-check result."""


def handler_result(
    response: Any, claim: Claim, agent_name: str, agent_version: str,
) -> HandlerResult:
    if response.status != "completed":
        raise HandlerError("The pinned agent did not complete.")
    items = [item.model_dump() for item in response.output]
    calls = set()
    for item in items:
        if item.get("type") != "function_call" or not str(
            item.get("name", "")
        ).endswith(ASSESS_OPERATION):
            continue
        arguments = json.loads(item.get("arguments") or "{}")
        if not isinstance(arguments, dict) or arguments.get("claim_id") != claim.claim_id:
            raise HandlerError("Assessment tool arguments do not match the selected claim.")
        calls.add(item.get("call_id"))
    outputs = [
        item["output"] for item in items
        if item.get("type") == "function_call_output" and item.get("call_id") in calls
    ]
    if len(calls) != 1 or len(outputs) != 1:
        raise HandlerError("Expected one actual assessment-tool result; no substitute was used.")
    assessment = EnrichedAssessment.model_validate_json(outputs[0])
    recommendation = AgentRecommendation.model_validate_json(response.output_text)
    if assessment.claim_id != claim.claim_id or recommendation.claim_id != claim.claim_id:
        raise HandlerError("The agent or tool returned a different claim.")
    if not set(assessment.image_analysis.artifact_ids) <= set(claim.artifact_ids):
        raise HandlerError("Tool evidence refers to an unrelated artifact.")
    if not set(recommendation.supporting_artifact_ids) <= set(claim.artifact_ids):
        raise HandlerError("The recommendation refers to an unrelated artifact.")
    citations = {citation.citation_id for citation in assessment.policy_citations}
    if not set(recommendation.supporting_citation_ids) <= citations:
        raise HandlerError("The recommendation refers to an unverified policy citation.")
    if assessment.image_analysis.status == "unavailable":
        if recommendation.triage_recommendation != "human_review":
            raise HandlerError("Unavailable image analysis must be routed to human review.")
    if (
        assessment.image_analysis.status == "no_evidence"
        and recommendation.triage_recommendation != "request_information"
    ):
        raise HandlerError("Missing photo evidence requires a request for information.")
    return HandlerResult(
        assessment=assessment, recommendation=recommendation, agent_name=agent_name,
        agent_version=agent_version, response_id=response.id,
    )


class ClaimHandler:
    def __init__(self, client: OpenAI, name: str, version: str) -> None:
        self.client = client
        self.name = name
        self.version = version

    def run(self, claim: Claim) -> HandlerResult:
        response = self.client.responses.create(
            input=f"Review synthetic claim {claim.claim_id}. Return the required recommendation.",
            text={"format": {
                "type": "json_schema", "name": "handler_recommendation", "strict": True,
                "schema": AgentRecommendation.model_json_schema(by_alias=True),
            }},
            extra_body={"agent_reference": {
                "type": "agent_reference", "name": self.name, "version": self.version,
            }},
        )
        return handler_result(response, claim, self.name, self.version)
