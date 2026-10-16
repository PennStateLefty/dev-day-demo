import pytest
from app.service import DemoService, ResourceNotFound


def test_policy_lookup_returns_source_linked_evidence() -> None:
    service = DemoService()

    citations = service.lookup_policy("pol-demo-auto", "deer strike vehicle damage")

    assert citations
    assert citations[0].section.startswith("Section 2.3")
    assert citations[0].source_document == "data/policies/demo-auto-policy.md"
    assert "animal strikes" in citations[0].quoted_text


def test_assessment_flags_driver_and_estimate_without_deciding_coverage() -> None:
    assessment = DemoService().assess_claim("clm-demo-002")

    finding_codes = {finding.finding_code for finding in assessment.completeness_findings}
    assert finding_codes == {
        "driver_not_listed",
        "possible_policy_exclusion",
        "repair_estimate_above_review_threshold",
    }
    assert assessment.policy_citations
    exclusion = next(
        finding
        for finding in assessment.completeness_findings
        if finding.finding_code == "possible_policy_exclusion"
    )
    cited_text = {
        citation.citation_id: citation.quoted_text for citation in assessment.policy_citations
    }
    assert exclusion.supporting_citation_ids
    assert "commercial ride-share or delivery" in cited_text[exclusion.supporting_citation_ids[0]]
    assert any(
        action.action_type == "route_to_human_adjuster"
        and exclusion.supporting_citation_ids[0] in action.supporting_citation_ids
        for action in assessment.recommended_actions
    )
    assert assessment.human_review_required is True
    assert "not a coverage decision" in assessment.summary


@pytest.mark.parametrize(
    ("statement", "exclusion_number"),
    [
        ("The vehicle was used on a delivery trip.", 1),
        ("The driver was racing on a speed contest course.", 2),
        ("An insured intentionally damaged the vehicle.", 3),
        ("The engine had a mechanical breakdown.", 4),
        ("An excluded driver without a valid license was driving.", 5),
        ("The damaged custom equipment was installed last year.", 6),
    ],
)
def test_each_section_three_exclusion_match_has_exact_source_citation(
    statement: str, exclusion_number: int
) -> None:
    service = DemoService()
    claim = service.get_claim("clm-demo-001")
    service.claims[claim.claim_id] = claim.model_copy(update={"claimant_statement": statement})

    assessment = service.assess_claim(claim.claim_id)
    exclusion = next(
        finding
        for finding in assessment.completeness_findings
        if finding.finding_code == "possible_policy_exclusion"
    )
    citations = {
        citation.citation_id: citation for citation in assessment.policy_citations
    }
    citation = citations[exclusion.supporting_citation_ids[0]]

    assert citation.section.startswith("Section 3")
    assert citation.quoted_text.startswith(f"{exclusion_number}. ")
    assert citation.quoted_text in service.policy_text[claim.policy_id]
    assert assessment.human_review_required is True


def test_no_exclusion_phrase_does_not_raise_a_policy_exclusion_finding() -> None:
    assessment = DemoService().assess_claim("clm-demo-001")

    assert "possible_policy_exclusion" not in {
        finding.finding_code for finding in assessment.completeness_findings
    }


def test_incomplete_claim_requests_information() -> None:
    assessment = DemoService().assess_claim("clm-demo-003")

    assert assessment.triage_recommendation == "request_information"
    assert {finding.finding_code for finding in assessment.completeness_findings} == {
        "required_information_missing",
        "required_document_missing",
    }
    assert assessment.policy_basis == "grounded"
    assert assessment.policy_citations
    assert assessment.human_review_required is True


def test_unknown_claim_is_an_explicit_not_found_error() -> None:
    try:
        DemoService().get_claim("clm-does-not-exist")
    except ResourceNotFound as error:
        assert "was not found" in str(error)
    else:
        raise AssertionError("Expected a missing claim to raise ResourceNotFound.")
