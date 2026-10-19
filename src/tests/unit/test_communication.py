from __future__ import annotations

import json
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.communication import (
    CommunicationError,
    CommunicationHandler,
    communication_prompt,
    create_communication_record,
    validate_customer_wording,
)
from app.models import (
    AgentRecommendation,
    EnrichedAssessment,
    HandlerResult,
)
from app.service import DemoService


def verified_result() -> tuple[object, HandlerResult]:
    service = DemoService()
    claim = service.get_claim("clm-demo-003")
    assessment = service.assess_claim(claim.claim_id)
    enriched = EnrichedAssessment.model_validate(
        assessment.model_dump()
        | {
            "image_analysis": {
                "status": "no_evidence",
                "artifact_ids": [],
                "limitation": "No linked image evidence was supplied.",
                "human_review_required": True,
            }
        }
    )
    recommendation = AgentRecommendation(
        claim_id=claim.claim_id,
        summary="Request supporting information for handler review.",
        triage_recommendation="request_information",
        recommended_actions=["Request supporting information"],
        supporting_artifact_ids=[],
        supporting_citation_ids=[item.citation_id for item in enriched.policy_citations],
        human_review_required=True,
    )
    return claim, HandlerResult(
        assessment=enriched,
        recommendation=recommendation,
        agent_name="claim-assessor",
        agent_version="3",
        response_id="resp-synthetic",
    )


@pytest.mark.parametrize(
    "body",
    [
        "Thank you for sharing this information. A handler will review it.",
        "Please provide a copy of the repair estimate so the handler can review the file.",
    ],
)
def test_customer_wording_accepts_plain_language(body: str) -> None:
    assert validate_customer_wording(body).body == body


@pytest.mark.parametrize(
    "body",
    [
        "The agent found a policy section for this claim.",
        "Please see citation cit-demo-001.",
        "See https://example.test/policy for details.",
        "Your artifact art-demo-photo-001 was processed.",
        "A handler will contact you soon with next steps.",
        "We have reviewed your images.",
        "   ",
    ],
)
def test_customer_wording_rejects_internal_references_and_unsupported_promises(body: str) -> None:
    with pytest.raises(CommunicationError):
        validate_customer_wording(body)


def test_prompt_uses_verified_evidence_and_checks_relationships() -> None:
    claim, result = verified_result()
    prompt = communication_prompt(claim, result)
    payload = json.loads(prompt.split("\n\n", 1)[1])
    assert payload["claim"]["claimId"] == claim.claim_id
    assert payload["assessment"]["assessmentId"] == result.assessment.assessment_id
    assert payload["recommendation"]["claimId"] == claim.claim_id
    invalid = result.model_copy(update={
        "recommendation": result.recommendation.model_copy(
            update={"supporting_artifact_ids": ["art-not-linked"]}
        )
    })
    with pytest.raises(CommunicationError, match="unrelated"):
        communication_prompt(claim, invalid)


def test_record_keeps_claim_evidence_links_outside_customer_wording() -> None:
    claim, result = verified_result()
    record = create_communication_record(
        claim,
        result.assessment,
        "Thank you for contacting us. A handler will review the information.",
    )
    assert record.claim_id == claim.claim_id
    assert record.assessment_id == result.assessment.assessment_id
    assert record.citation_ids == [
        item.citation_id for item in result.assessment.policy_citations
    ]
    assert record.artifact_ids == claim.artifact_ids
    assert record.created_at.tzinfo == UTC
    assert record.human_review_required is True
    assert record.reviewed_by is None
    assert record.reviewed_at is None
    assert record.sent_at is None


def test_handler_passes_a_pinned_agent_reference_and_validates_response() -> None:
    claim, result = verified_result()
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        status="completed",
        output_text=json.dumps({
            "body": "Thank you for contacting us. A handler will review the information."
        }),
        id="response-1",
        model_dump=lambda **_: {"output_text": "synthetic"},
    )
    handler = CommunicationHandler(client, "communication", "1")
    draft = handler.run(claim, result)
    assert draft.body.startswith("Thank you")
    kwargs = client.responses.create.call_args.kwargs
    assert kwargs["extra_body"]["agent_reference"] == {
        "type": "agent_reference",
        "name": "communication",
        "version": "1",
    }
    assert claim.claim_id in kwargs["input"]

    client.responses.create.return_value.output_text = json.dumps(
        {"body": "See citation cit-demo-001."}
    )
    with pytest.raises(CommunicationError, match="evidence-link"):
        handler.run(claim, result)


def test_record_requires_review_before_sent_metadata() -> None:
    claim, result = verified_result()
    record = create_communication_record(
            claim,
            result.assessment,
            "Thank you for contacting us. A handler will review the information.",
        )
    with pytest.raises(ValueError, match="before human review"):
        type(record).model_validate(record.model_dump() | {"sent_at": datetime.now(UTC)})
