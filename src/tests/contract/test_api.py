from app import main
from app.main import app
from app.service import PolicyEvidenceUnavailable
from fastapi.testclient import TestClient


def test_claim_list_and_policy_lookup() -> None:
    with TestClient(app) as client:
        claims = client.get("/api/claims")
        citations = client.get(
            "/api/policies/pol-demo-auto/lookup",
            params={"query": "deer strike"},
        )

    assert claims.status_code == 200
    assert len(claims.json()) == 4
    assert citations.status_code == 200
    assert citations.json()[0]["section"].startswith("Section 2.3")


def test_workflow_returns_human_review_assessment_and_draft() -> None:
    with TestClient(app) as client:
        response = client.post("/api/claims/clm-demo-001/workflow")

    assert response.status_code == 200
    result = response.json()
    assert result["assessment"]["humanReviewRequired"] is True
    assert result["responseDraft"]["humanReviewRequired"] is True
    assert "not a coverage decision" in result["assessment"]["summary"]


def test_assessment_surfaces_delivery_exclusion_with_exact_policy_wording() -> None:
    with TestClient(app) as client:
        response = client.post("/api/claims/clm-demo-002/assess")

    assert response.status_code == 200
    assessment = response.json()
    finding = next(
        item
        for item in assessment["completenessFindings"]
        if item["findingCode"] == "possible_policy_exclusion"
    )
    citation = next(
        item
        for item in assessment["policyCitations"]
        if item["citationId"] in finding["supportingCitationIds"]
    )
    assert citation["section"].startswith("Section 3")
    assert "commercial ride-share or delivery" in citation["quotedText"]
    assert any(
        action["actionType"] == "route_to_human_adjuster"
        for action in assessment["recommendedActions"]
    )


def test_missing_section_three_evidence_returns_explicit_service_error(monkeypatch) -> None:
    def unavailable(claim_id: str):
        raise PolicyEvidenceUnavailable("Exact Section 3 evidence is unavailable.")

    monkeypatch.setattr(main.service, "assess_claim", unavailable)
    with TestClient(app) as client:
        response = client.post("/api/claims/clm-demo-002/assess")

    assert response.status_code == 503
    assert response.json()["detail"] == "Exact Section 3 evidence is unavailable."


def test_unknown_claim_returns_404() -> None:
    with TestClient(app) as client:
        response = client.post("/api/claims/clm-unknown/assess")

    assert response.status_code == 404


def test_empty_lookup_query_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/policies/pol-demo-auto/lookup",
            params={"query": " "},
        )

    assert response.status_code == 422
