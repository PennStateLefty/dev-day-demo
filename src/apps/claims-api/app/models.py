from __future__ import annotations

import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


def to_camel(value: str) -> str:
    first, *rest = value.split("_")
    return first + "".join(part.capitalize() for part in rest)


class DemoModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        extra="forbid",
    )


class RepairEstimate(DemoModel):
    amount: float = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class Claim(DemoModel):
    claim_id: str = Field(pattern=r"^clm-[a-z0-9-]+$")
    customer_id: str | None = Field(default=None, pattern=r"^cust-[a-z0-9-]+$")
    policy_id: str | None = Field(default=None, pattern=r"^pol-[a-z0-9-]+$")
    vehicle_id: str | None = Field(default=None, pattern=r"^veh-[a-z0-9-]+$")
    loss_date: date | None = None
    reported_driver_id: str | None = Field(default=None, pattern=r"^drv-[a-z0-9-]+$")
    claimant_statement: str | None = Field(default=None, min_length=1, max_length=10000)
    artifact_ids: list[str] = Field(default_factory=list)
    repair_estimate: RepairEstimate | None = None


class Coverage(DemoModel):
    coverage_id: str
    description: str = Field(min_length=1, max_length=2000)


class Policy(DemoModel):
    policy_id: str = Field(pattern=r"^pol-[a-z0-9-]+$")
    insured_customer_id: str = Field(pattern=r"^cust-[a-z0-9-]+$")
    status: Literal["active", "inactive"]
    effective_date: date
    expiration_date: date
    covered_vehicle_ids: list[str]
    listed_driver_ids: list[str]
    coverages: list[Coverage] = Field(min_length=1)
    exclusions: list[str] = Field(default_factory=list)
    source_document_refs: list[str] = Field(default_factory=list)


class Artifact(DemoModel):
    artifact_id: str = Field(pattern=r"^art-[a-z0-9-]+$")
    claim_id: str = Field(pattern=r"^clm-[a-z0-9-]+$")
    artifact_type: Literal[
        "claimant_statement",
        "policy_document",
        "repair_estimate",
        "damage_photo",
        "police_report",
        "other",
    ]
    received_at: datetime
    content_ref: str | None = None
    duplicate_of_artifact_id: str | None = None
    description: str | None = Field(default=None, max_length=1000)
    provenance: Literal["user_provided_ai_generated"] | None = None


class Finding(DemoModel):
    finding_code: Literal[
        "required_information_missing",
        "required_document_missing",
        "policy_inactive_on_loss_date",
        "driver_not_listed",
        "repair_estimate_above_review_threshold",
        "possible_duplicate_artifact",
        "possible_prior_damage",
        "straight_through_candidate",
        "human_escalation",
        "other",
    ]
    status: Literal["clear", "missing", "inconsistent", "needs_review", "unknown"]
    description: str = Field(min_length=1, max_length=2000)
    related_artifact_ids: list[str] = Field(default_factory=list)


class Citation(DemoModel):
    citation_id: str = Field(pattern=r"^cit-[a-z0-9-]+$")
    policy_id: str = Field(pattern=r"^pol-[a-z0-9-]+$")
    source_document: str = Field(min_length=1)
    section: str = Field(min_length=1, max_length=300)
    quoted_text: str = Field(min_length=1, max_length=4000)


class RecommendedAction(DemoModel):
    action_id: str = Field(pattern=r"^act-[a-z0-9-]+$")
    action_type: Literal[
        "request_missing_information",
        "verify_policy_status",
        "verify_driver_listing",
        "review_conflicting_information",
        "review_repair_estimate",
        "review_possible_prior_damage",
        "investigate_possible_duplicate_artifact",
        "route_to_human_adjuster",
        "prepare_customer_update",
    ]
    priority: Literal["low", "normal", "high"] = "normal"
    rationale: str = Field(min_length=1, max_length=2000)
    supporting_citation_ids: list[str] = Field(default_factory=list)
    human_review_required: Literal[True] = True


class Assessment(DemoModel):
    assessment_id: str = Field(pattern=r"^asm-[a-z0-9-]+$")
    claim_id: str = Field(pattern=r"^clm-[a-z0-9-]+$")
    generated_at: datetime
    summary: str = Field(min_length=1, max_length=4000)
    completeness_findings: list[Finding]
    conflicts: list[dict[str, object]]
    policy_basis: Literal["grounded", "unavailable", "not_assessed"]
    policy_citations: list[Citation]
    recommended_actions: list[RecommendedAction]
    triage_recommendation: Literal[
        "request_information",
        "human_review",
        "escalate",
        "straight_through_candidate",
    ]
    human_review_required: Literal[True] = True


class ResponseDraft(DemoModel):
    draft_id: str = Field(pattern=r"^drf-[a-z0-9-]+$")
    claim_id: str = Field(pattern=r"^clm-[a-z0-9-]+$")
    assessment_id: str = Field(pattern=r"^asm-[a-z0-9-]+$")
    body: str = Field(min_length=1, max_length=10000)
    human_review_required: Literal[True] = True


class CommunicationText(DemoModel):
    body: str = Field(min_length=1, max_length=10000)


class CommunicationRecord(DemoModel):
    communication_id: str = Field(pattern=r"^com-[a-f0-9-]{36}$")
    claim_id: str = Field(pattern=r"^clm-[a-z0-9-]+$")
    assessment_id: str = Field(pattern=r"^asm-[a-z0-9-]+$")
    citation_ids: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    body: str = Field(min_length=1, max_length=10000)
    created_at: datetime
    reviewed_by: str | None = Field(
        default=None, min_length=1, max_length=200, pattern=r".*\S.*"
    )
    reviewed_at: datetime | None = None
    sent_at: datetime | None = None
    human_review_required: Literal[True] = True

    @model_validator(mode="after")
    def validate_lifecycle(self) -> CommunicationRecord:
        if self.created_at.tzinfo is None:
            raise ValueError("Communication creation time must include a timezone.")
        if (self.reviewed_by is None) != (self.reviewed_at is None):
            raise ValueError("Reviewer identity and review time must be recorded together.")
        if self.reviewed_at is not None and self.reviewed_at.tzinfo is None:
            raise ValueError("Communication review time must include a timezone.")
        if self.sent_at is not None and self.reviewed_at is None:
            raise ValueError("A communication cannot be marked sent before human review.")
        if self.sent_at is not None and self.sent_at.tzinfo is None:
            raise ValueError("Communication sent time must include a timezone.")
        if any(not re.fullmatch(r"cit-[a-z0-9-]+", item) for item in self.citation_ids):
            raise ValueError("Communication citation IDs must be valid.")
        if any(not re.fullmatch(r"art-[a-z0-9-]+", item) for item in self.artifact_ids):
            raise ValueError("Communication artifact IDs must be valid.")
        if len(self.citation_ids) != len(set(self.citation_ids)):
            raise ValueError("Communication citation IDs must be unique.")
        if len(self.artifact_ids) != len(set(self.artifact_ids)):
            raise ValueError("Communication artifact IDs must be unique.")
        return self


class CommunicationReviewRequest(DemoModel):
    reviewer: str = Field(min_length=1, max_length=200, pattern=r".*\S.*")

    @model_validator(mode="after")
    def normalize_reviewer(self) -> CommunicationReviewRequest:
        self.reviewer = self.reviewer.strip()
        return self


class CommunicationDraftRequest(DemoModel):
    assessment_id: str = Field(pattern=r"^asm-[a-z0-9-]+$")


class PartObservation(DemoModel):
    part: str = Field(min_length=1, max_length=100)
    damage: str = Field(min_length=1, max_length=1000)
    severity: Literal["minor", "moderate", "severe", "unknown"]


class VisionObservations(DemoModel):
    visibility: Literal["clear", "limited", "unusable"]
    parts: list[PartObservation] = Field(max_length=20)
    statement_comparison: str = Field(min_length=1, max_length=2000)
    limitations: list[str] = Field(min_length=1, max_length=10)


class ImageAnalysis(DemoModel):
    status: Literal["completed", "no_evidence", "unavailable"]
    artifact_ids: list[str] = Field(default_factory=list)
    input_sha256: str | None = None
    model: str | None = None
    model_version: str | None = None
    deployment: str | None = None
    prompt_version: str = "damage-observations-v1"
    observations: VisionObservations | None = None
    limitation: str | None = None
    human_review_required: Literal[True] = True

    @model_validator(mode="after")
    def consistent_status(self) -> ImageAnalysis:
        if self.status == "completed":
            if (
                len(self.artifact_ids) != 1 or self.observations is None
                or not self.input_sha256 or not self.model or not self.model_version
                or not self.deployment or self.limitation is not None
            ):
                raise ValueError("Completed analysis requires source, model and observations.")
        elif self.observations is not None or not self.limitation:
            raise ValueError("Unsuccessful analysis requires a limitation and no observations.")
        if self.status == "no_evidence" and self.artifact_ids:
            raise ValueError("No-evidence analysis cannot refer to a photo.")
        return self


class EnrichedAssessment(Assessment):
    image_analysis: ImageAnalysis


class AgentRecommendation(DemoModel):
    claim_id: str = Field(pattern=r"^clm-[a-z0-9-]+$")
    summary: str = Field(min_length=1, max_length=4000)
    triage_recommendation: Literal["request_information", "human_review", "escalate"]
    recommended_actions: list[str] = Field(min_length=1, max_length=10)
    supporting_artifact_ids: list[str]
    supporting_citation_ids: list[str]
    human_review_required: Literal[True]


class HandlerResult(DemoModel):
    assessment: EnrichedAssessment
    recommendation: AgentRecommendation
    agent_name: str
    agent_version: str
    response_id: str


class WorkflowResult(DemoModel):
    assessment: EnrichedAssessment | Assessment
    response_draft: ResponseDraft


class CommunicationRunResult(DemoModel):
    assessment: EnrichedAssessment | Assessment
    recommendation: AgentRecommendation | None = None
    communication: CommunicationRecord
    agent_name: str | None = None
    agent_version: str | None = None
