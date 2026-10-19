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


def test_unknown_claim_returns_404() -> None:
    with TestClient(app) as client:
        response = client.post("/api/claims/clm-unknown/assess")

    assert response.status_code == 404


def test_communication_draft_persists_links_and_human_lifecycle_only() -> None:
    with TestClient(app) as client:
        premature = client.post(
            "/api/claims/clm-demo-003/communications/draft",
            json={"assessmentId": "asm-demo-003"},
        )
        checks = client.post("/api/claims/clm-demo-003/workflow")
        assessment_id = checks.json()["assessment"]["assessmentId"]
        stale = client.post(
            "/api/claims/clm-demo-003/communications/draft",
            json={"assessmentId": "asm-demo-stale"},
        )
        created = client.post(
            "/api/claims/clm-demo-003/communications/draft",
            json={"assessmentId": assessment_id},
        )
        communication = created.json()["communication"]
        listed = client.get("/api/claims/clm-demo-003/communications")
        sent_too_early = client.post(
            f"/api/communications/{communication['communicationId']}/mark-sent"
        )
        reviewed = client.post(
            f"/api/communications/{communication['communicationId']}/review",
            json={"reviewer": "  Demo Handler  "},
        )
        marked_sent = client.post(
            f"/api/communications/{communication['communicationId']}/mark-sent"
        )
        reviewed_again = client.post(
            f"/api/communications/{communication['communicationId']}/review",
            json={"reviewer": "Another Handler"},
        )

    assert premature.status_code == 409
    assert checks.status_code == 200
    assert stale.status_code == 409
    assert created.status_code == 200
    assert created.json()["assessment"]["assessmentId"] == assessment_id
    assert communication["claimId"] == "clm-demo-003"
    assert communication["assessmentId"] == created.json()["assessment"]["assessmentId"]
    assert communication["humanReviewRequired"] is True
    assert communication["reviewedBy"] is None
    assert communication["reviewedAt"] is None
    assert communication["sentAt"] is None
    assert communication["citationIds"] == [
        item["citationId"] for item in created.json()["assessment"]["policyCitations"]
    ]
    assert listed.status_code == 200
    assert any(
        item["communicationId"] == communication["communicationId"]
        for item in listed.json()
    )
    assert sent_too_early.status_code == 409
    assert reviewed.status_code == 200
    assert reviewed.json()["reviewedBy"] == "Demo Handler"
    assert reviewed.json()["reviewedAt"].endswith(("Z", "+00:00"))
    assert marked_sent.status_code == 200
    assert marked_sent.json()["sentAt"].endswith(("Z", "+00:00"))
    assert reviewed_again.status_code == 409


def test_communication_review_requires_non_whitespace_reviewer() -> None:
    with TestClient(app) as client:
        checks = client.post("/api/claims/clm-demo-003/workflow")
        created = client.post(
            "/api/claims/clm-demo-003/communications/draft",
            json={"assessmentId": checks.json()["assessment"]["assessmentId"]},
        )
        communication_id = created.json()["communication"]["communicationId"]
        response = client.post(
            f"/api/communications/{communication_id}/review", json={"reviewer": "  "}
        )

    assert response.status_code == 422


def test_empty_lookup_query_is_rejected() -> None:
    with TestClient(app) as client:
        response = client.get(
            "/api/policies/pol-demo-auto/lookup",
            params={"query": " "},
        )

    assert response.status_code == 422
