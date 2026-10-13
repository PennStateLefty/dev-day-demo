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
        "repair_estimate_above_review_threshold",
    }
    assert assessment.policy_citations
    assert assessment.human_review_required is True
    assert "not a coverage decision" in assessment.summary


def test_incomplete_claim_requests_information() -> None:
    assessment = DemoService().assess_claim("clm-demo-003")

    assert assessment.triage_recommendation == "request_information"
    assert {finding.finding_code for finding in assessment.completeness_findings} == {
        "required_information_missing",
        "required_document_missing",
    }
    assert assessment.policy_citations == []
    assert assessment.human_review_required is True


def test_unknown_claim_is_an_explicit_not_found_error() -> None:
    try:
        DemoService().get_claim("clm-does-not-exist")
    except ResourceNotFound as error:
        assert "was not found" in str(error)
    else:
        raise AssertionError("Expected a missing claim to raise ResourceNotFound.")
