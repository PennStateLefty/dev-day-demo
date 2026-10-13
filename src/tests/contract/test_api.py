from app.main import app
from fastapi.testclient import TestClient


def test_claim_list_and_policy_lookup() -> None:
    with TestClient(app) as client:
        claims = client.get("/api/claims")
        citations = client.get(
            "/api/policies/pol-demo-auto/lookup",
            params={"query": "deer strike"},
        )

    assert claims.status_code == 200
    assert len(claims.json()) == 3
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
