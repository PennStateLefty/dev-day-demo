from dataclasses import replace
from unittest.mock import Mock

from app import main
from app.evidence import EvidenceAssessment, LocalEvidenceReader
from app.handler import HandlerError
from fastapi.testclient import TestClient
from fastmcp import Client


def test_preview_is_claim_scoped_private_and_makes_no_model_call(monkeypatch) -> None:
    vision = Mock()
    evidence = EvidenceAssessment(LocalEvidenceReader(), vision)
    monkeypatch.setattr(main.runtime, "evidence", evidence)
    with TestClient(main.app) as client:
        metadata = client.get("/api/claims/clm-demo-001/artifacts")
        assert metadata.json()[0]["artifactId"] == "art-demo-photo-001"
        image = client.get("/api/claims/clm-demo-001/artifacts/art-demo-photo-001/content")
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        assert image.headers["cache-control"] == "private, no-store"
        assert image.content.startswith(b"\x89PNG")
        assert client.get(
            "/api/claims/clm-demo-001/artifacts/art-demo-photo-002/content",
        ).status_code == 404
    vision.analyze.assert_not_called()


async def test_rest_and_mcp_share_enrichment_and_no_evidence_status() -> None:
    with TestClient(main.app) as client:
        rest = client.post("/api/claims/clm-demo-003/assess").json()
        local_run = client.post("/api/claims/clm-demo-001/workflow").json()
    async with Client(main.mcp) as client:
        mcp = await client.call_tool("assess_synthetic_claim", {"claim_id": "clm-demo-003"})
    assert rest["imageAnalysis"]["status"] == "no_evidence"
    assert mcp.data["imageAnalysis"] == rest["imageAnalysis"]
    assert local_run["assessment"]["imageAnalysis"]["status"] == "unavailable"


def test_cloud_handler_is_not_fixture_success_when_agent_fails(monkeypatch) -> None:
    monkeypatch.setattr(main, "settings", replace(main.settings, mode="azure"))
    handler = Mock()
    handler.run.side_effect = HandlerError("untrusted generated result")
    monkeypatch.setattr(main.runtime, "handler", handler)
    with TestClient(main.app) as client:
        response = client.post("/api/claims/clm-demo-001/workflow")
    assert response.status_code == 503
    assert "no fixture fallback" in response.json()["detail"]
