from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from openai import OpenAI
from pydantic import ValidationError

from .models import (
    Assessment,
    Claim,
    CommunicationRecord,
    CommunicationText,
    HandlerResult,
)
from .telemetry import log_demo_content


class CommunicationError(Exception):
    """The Communication agent did not return safe, verifiable customer wording."""


_CUSTOMER_TEXT_FORBIDDEN = re.compile(
    r"https?://|"
    r"\b(?:agent|citation|artifact)\b|"
    r"\b(?:clm|asm|cit|art|com)-[a-z0-9-]+\b|"
    r"\b(?:in touch|contact you|reach out|follow[- ]?up|next steps|soon)\b|"
    r"\b(?:have|has|had) been reviewed\b|"
    r"\b(?:reviewed|assessed)\s+(?:your|the)\s+(?:claim|information|submission|images?)\b",
    re.IGNORECASE,
)


def validate_customer_wording(text: str) -> CommunicationText:
    if not isinstance(text, str) or not text.strip():
        raise CommunicationError("Customer wording cannot be empty.")
    try:
        content = CommunicationText(body=text)
    except ValidationError as error:
        raise CommunicationError(
            "The Communication agent returned invalid customer text."
        ) from error
    if _CUSTOMER_TEXT_FORBIDDEN.search(content.body):
        raise CommunicationError(
            "Customer wording must not include evidence-link references or unsupported "
            "review/follow-up claims."
        )
    return content


def communication_prompt(claim: Claim, result: HandlerResult) -> str:
    if (
        result.assessment.claim_id != claim.claim_id
        or result.recommendation.claim_id != claim.claim_id
    ):
        raise CommunicationError("Verified assessment and recommendation must match the claim.")
    verified_artifacts = set(claim.artifact_ids)
    assessment_artifacts = set(result.assessment.image_analysis.artifact_ids)
    recommendation_artifacts = set(result.recommendation.supporting_artifact_ids)
    if not (assessment_artifacts | recommendation_artifacts) <= verified_artifacts:
        raise CommunicationError("Verified evidence refers to an unrelated claim artifact.")
    citations = {citation.citation_id for citation in result.assessment.policy_citations}
    if not set(result.recommendation.supporting_citation_ids) <= citations:
        raise CommunicationError("Recommendation refers to an unverified policy citation.")
    evidence = {
        "claim": claim.model_dump(mode="json", by_alias=True),
        "assessment": result.assessment.model_dump(mode="json", by_alias=True),
        "recommendation": result.recommendation.model_dump(mode="json", by_alias=True),
    }
    return (
        "Draft a customer update from this verified synthetic claims evidence. "
        "Return only a JSON object with a single string field named body.\n\n"
        + json.dumps(evidence, ensure_ascii=True, separators=(",", ":"))
    )


def create_communication_record(
    claim: Claim,
    assessment: Assessment,
    body: str,
    *,
    recommendation_artifact_ids: list[str] | None = None,
) -> CommunicationRecord:
    if assessment.claim_id != claim.claim_id:
        raise CommunicationError("The assessment does not match the selected claim.")
    citation_ids = [citation.citation_id for citation in assessment.policy_citations]
    artifact_ids = list(dict.fromkeys([
        *claim.artifact_ids,
        *getattr(getattr(assessment, "image_analysis", None), "artifact_ids", []),
        *(recommendation_artifact_ids or []),
    ]))
    if len(citation_ids) != len(set(citation_ids)):
        raise CommunicationError("Assessment contains duplicate citation IDs.")
    if not set(artifact_ids) <= set(claim.artifact_ids):
        raise CommunicationError("Communication record refers to an unrelated artifact.")
    try:
        return CommunicationRecord(
            communication_id=f"com-{uuid4()}",
            claim_id=claim.claim_id,
            assessment_id=assessment.assessment_id,
            citation_ids=citation_ids,
            artifact_ids=artifact_ids,
            body=validate_customer_wording(body).body,
            created_at=datetime.now(UTC),
            human_review_required=True,
        )
    except ValidationError as error:
        raise CommunicationError("The communication record failed contract validation.") from error


class CommunicationHandler:
    def __init__(self, client: OpenAI, name: str, version: str) -> None:
        if not name.strip() or not version.strip():
            raise ValueError(
                "Communication agent invocation requires an explicit name and version."
            )
        self.client = client
        self.name = name
        self.version = version

    def run(self, claim: Claim, result: HandlerResult) -> CommunicationText:
        prompt = communication_prompt(claim, result)
        metadata = {
            "claim_id": claim.claim_id,
            "assessment_id": result.assessment.assessment_id,
            "agent_name": self.name,
            "agent_version": self.version,
        }
        log_demo_content("communication.request", {"input": prompt}, **metadata)
        response: Any = self.client.responses.create(
            input=prompt,
            extra_body={"agent_reference": {
                "type": "agent_reference",
                "name": self.name,
                "version": self.version,
            }},
        )
        log_demo_content(
            "communication.response",
            response.model_dump(mode="json"),
            response_id=response.id,
            **metadata,
        )
        if response.status != "completed":
            raise CommunicationError("The pinned Communication agent did not complete.")
        try:
            payload = json.loads(response.output_text)
            if not isinstance(payload, dict) or set(payload) != {"body"}:
                raise ValueError("Expected exactly one body field.")
            return validate_customer_wording(payload["body"])
        except (json.JSONDecodeError, TypeError, ValueError) as error:
            raise CommunicationError(
                "The pinned Communication agent returned an invalid output shape."
            ) from error
