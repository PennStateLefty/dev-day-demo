from __future__ import annotations

import io
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app.database import payload
from app.evidence import (
    MAX_IMAGE_BYTES,
    BlobEvidenceReader,
    EvidenceAssessment,
    LocalEvidenceReader,
    VisionClient,
    evidence_key,
    validate_image,
)
from app.handler import ClaimHandler, HandlerError, handler_result
from app.models import ImageAnalysis, VisionObservations
from app.service import DemoService, ResourceNotFound
from app.settings import Settings
from initialize_evidence import apply_rows, desired_rows, image_manifest, upload_verified
from PIL import Image


def observations() -> VisionObservations:
    return VisionObservations(
        visibility="limited", parts=[], statement_comparison="Damage is not visible.",
        limitations=["Foreground obstruction prevents confirming or excluding damage."],
    )


def vision() -> Mock:
    client = Mock(spec=VisionClient)
    client.deployment = "approved-vision"
    client.model_version = "2026-09-22"
    client.analyze.return_value = observations()
    return client


def test_supplied_images_are_linked_validated_and_not_in_history_fixture() -> None:
    service = DemoService()
    images = image_manifest(service)
    assert {item["claimId"] for item in images} == {
        "clm-demo-001", "clm-demo-002", "clm-demo-004",
    }
    assert all(item["contentType"] == "image/png" for item in images)
    assert all(0 < item["bytes"] <= MAX_IMAGE_BYTES for item in images)
    assert service.get_claim("clm-demo-003").artifact_ids == []
    assert service.get_claim("clm-demo-004").customer_id != "cust-demo-one"
    assert "provenance" not in json.loads(payload(service.artifacts["art-demo-estimate-002"]))


@pytest.mark.parametrize("path", [
    "/etc/file.png", "https://example.com/a.png", "data/artifacts/images/../outside.png",
    "data/artifacts/images/clm-demo-002/collision.png",
    "data/artifacts/images/clm-demo-001//photo.png",
    "data/artifacts/images/clm-demo-001/photo.svg",
])
def test_image_reference_cannot_escape_registered_claim(path) -> None:
    artifact = DemoService().artifacts["art-demo-photo-001"].model_copy(
        update={"content_ref": path},
    )
    with pytest.raises(ValueError):
        evidence_key(artifact)


def test_foreign_artifact_and_symlink_are_rejected(tmp_path) -> None:
    service = DemoService()
    with pytest.raises(ResourceNotFound):
        service.get_artifact("clm-demo-001", "art-demo-photo-002")
    service.artifacts["art-demo-photo-001"] = service.artifacts[
        "art-demo-photo-001"
    ].model_copy(update={"claim_id": "clm-demo-002"})
    with pytest.raises(ResourceNotFound):
        service.get_artifact("clm-demo-001", "art-demo-photo-001")
    root = tmp_path / "root"
    directory = root / "data/artifacts/images/clm-demo-001"
    directory.mkdir(parents=True)
    outside = tmp_path / "secret.png"
    outside.write_bytes(b"not an image")
    (directory / "passenger-door.png").symlink_to(outside)
    with pytest.raises(ValueError):
        LocalEvidenceReader(root).read(DemoService().artifacts["art-demo-photo-001"])


@pytest.mark.parametrize("content", [b"", b"not a png", b"x" * (MAX_IMAGE_BYTES + 1)])
def test_image_bytes_must_be_bounded_and_decodable(content) -> None:
    with pytest.raises((ValueError, OSError)):
        validate_image(content)


def test_image_pixel_limit() -> None:
    output = io.BytesIO()
    Image.new("RGB", (4001, 4001)).save(output, format="PNG")
    with pytest.raises(ValueError, match="16 million"):
        validate_image(output.getvalue())


def test_no_photo_never_calls_reader_or_model() -> None:
    reader, model = Mock(), vision()
    assessment = EvidenceAssessment(reader, model).assess(DemoService(), "clm-demo-003")
    assert assessment.image_analysis.status == "no_evidence"
    reader.read.assert_not_called()
    model.analyze.assert_not_called()


def test_enrichment_retains_deterministic_checks_and_provenance() -> None:
    model = vision()
    service = DemoService()
    enriched = EvidenceAssessment(LocalEvidenceReader(), model).assess(service, "clm-demo-002")
    assert enriched.completeness_findings == service.assess_claim(
        "clm-demo-002",
    ).completeness_findings
    assert enriched.image_analysis.status == "completed"
    assert enriched.image_analysis.model == "gpt-6-luna"
    assert len(enriched.image_analysis.input_sha256) == 64
    assert enriched.image_analysis.artifact_ids == ["art-demo-photo-002"]
    assert model.analyze.call_count == 1


@pytest.mark.parametrize("failure", [OSError("blob unavailable"), ValueError("invalid JSON")])
def test_image_failure_is_explicit_and_retains_deterministic_findings(failure, caplog) -> None:
    model = vision()
    model.analyze.side_effect = failure
    service = DemoService()
    result = EvidenceAssessment(LocalEvidenceReader(), model).assess(service, "clm-demo-002")
    assert result.image_analysis.status == "unavailable"
    assert result.image_analysis.observations is None
    assert result.completeness_findings
    assert "unavailable" in caplog.text
    with pytest.raises(ResourceNotFound):
        EvidenceAssessment(LocalEvidenceReader(), model).assess(service, "clm-unknown")


def test_unconfigured_local_mode_cannot_claim_live_vision() -> None:
    result = EvidenceAssessment(LocalEvidenceReader()).assess(DemoService(), "clm-demo-001")
    assert result.image_analysis.status == "unavailable"
    assert "not configured" in result.image_analysis.limitation
    with pytest.raises(ValueError):
        ImageAnalysis(status="completed")


def test_runtime_uses_consumer_endpoint_without_agent_authoring_permissions(monkeypatch) -> None:
    from app import runtime

    clients = {}
    for name in (
        "ManagedIdentityCredential", "SqlClaimsStore", "connector", "connection_string",
        "SearchClient", "SearchRestClient", "AIProjectClient",
    ):
        clients[name] = Mock()
        monkeypatch.setattr(runtime, name, clients[name])
    endpoint = "https://example.services.ai.azure.com/api/projects/claims"
    instance = runtime.Runtime(Settings(
        mode="azure", foundry_endpoint=endpoint, assessor_version="3",
    ))
    clients["AIProjectClient"].assert_called_once_with(
        endpoint=endpoint,
        credential=clients["ManagedIdentityCredential"].return_value,
        allow_preview=True,
    )
    clients["AIProjectClient"].return_value.get_openai_client.assert_called_once_with(
        agent_name="claim-assessor", timeout=180, max_retries=0,
    )
    assert instance.handler.version == "3"
    instance.close()


def test_blob_read_is_private_bounded_and_no_url_comes_from_model() -> None:
    fixtures = DemoService()
    artifact = fixtures.artifacts["art-demo-photo-001"]
    content = LocalEvidenceReader().read(artifact)
    blobs = Mock()
    blobs.get_blob_client.return_value.download_blob.return_value.readall.return_value = content
    assert BlobEvidenceReader(blobs).read(artifact) == content
    blobs.get_blob_client.assert_called_once_with("evidence", artifact.content_ref)
    assert blobs.get_blob_client.return_value.download_blob.call_args.kwargs["length"] == (
        MAX_IMAGE_BYTES + 1
    )


def test_vision_payload_contains_image_and_statement_not_evaluation_answers() -> None:
    client = Mock()
    client.responses.create.return_value = SimpleNamespace(
        status="completed", output_text=observations().model_dump_json(by_alias=True),
        model="gpt-6-luna-2026-09-22",
    )
    service = DemoService()
    VisionClient(client, "approved-vision", "2026-09-22").analyze(
        service.get_claim("clm-demo-004"), b"image-bytes", "image/png",
    )
    call = client.responses.create.call_args.kwargs
    assert call["model"] == "approved-vision"
    assert call["input"][0]["content"][1]["image_url"].startswith("data:image/png;base64,")
    assert "out of focus plant" not in json.dumps(call)
    assert call["store"] is False
    client.responses.create.return_value.model = "approved-vision"
    VisionClient(client, "approved-vision", "2026-09-22").analyze(
        service.get_claim("clm-demo-004"), b"image-bytes", "image/png",
    )
    client.responses.create.return_value.model = "gpt-4.1-mini-2025-04-14"
    with pytest.raises(ValueError, match="approved model/version"):
        VisionClient(client, "approved-vision", "2026-09-22").analyze(
            service.get_claim("clm-demo-004"), b"image-bytes", "image/png",
        )
    client.responses.create.return_value.model = "gpt-6-luna-2026-09-22"
    client.responses.create.return_value.output_text = "{}"
    with pytest.raises(ValueError):
        VisionClient(client, "approved-vision", "2026-09-22").analyze(
            service.get_claim("clm-demo-004"), b"image-bytes", "image/png",
        )


def response_fixture(claim_id="clm-demo-001"):
    service = DemoService()
    assessment = EvidenceAssessment(LocalEvidenceReader(), vision()).assess(service, claim_id)
    recommendation = {
        "claimId": claim_id, "summary": "Human verification is required.",
        "triageRecommendation": "human_review", "recommendedActions": ["Verify the evidence."],
        "supportingArtifactIds": assessment.image_analysis.artifact_ids,
        "supportingCitationIds": [], "humanReviewRequired": True,
    }
    items = [
        {"type": "function_call", "call_id": "tool-1", "name": "claims_api_getClaimAssessment",
         "arguments": json.dumps({"claim_id": claim_id})},
        {"type": "function_call_output", "call_id": "tool-1",
         "output": assessment.model_dump_json(by_alias=True)},
    ]
    response = SimpleNamespace(
        status="completed", id="response-1", output_text=json.dumps(recommendation),
        output=[SimpleNamespace(model_dump=lambda item=item: item) for item in items],
    )
    return response, items


def test_pinned_handler_uses_actual_tool_evidence_and_claim_id_only() -> None:
    response, _ = response_fixture()
    client = Mock()
    client.responses.create.return_value = response
    result = ClaimHandler(client, "claim-assessor", "3").run(
        DemoService().get_claim("clm-demo-001"),
    )
    assert result.assessment.image_analysis.status == "completed"
    assert result.agent_version == "3"
    call = client.responses.create.call_args.kwargs
    assert call["extra_body"]["agent_reference"]["version"] == "3"
    assert isinstance(call["input"], str)
    assert "input_image" not in json.dumps(call)
    assert client.responses.create.call_count == 1


@pytest.mark.parametrize("mutation", ["no_tool", "wrong_claim", "wrong_artifact", "fake_citation"])
def test_handler_cannot_substitute_generated_text_for_tool_evidence(mutation) -> None:
    response, _ = response_fixture()
    final = json.loads(response.output_text)
    if mutation == "no_tool":
        response.output = []
    elif mutation == "wrong_claim":
        final["claimId"] = "clm-demo-002"
    elif mutation == "wrong_artifact":
        final["supportingArtifactIds"] = ["art-demo-photo-002"]
    else:
        final["supportingCitationIds"] = ["cit-invented"]
    response.output_text = json.dumps(final)
    with pytest.raises(HandlerError):
        handler_result(response, DemoService().get_claim("clm-demo-001"), "claim-assessor", "3")


def test_sql_update_requires_reviewed_before_state_and_never_changes_grants() -> None:
    service = DemoService()
    row = desired_rows(service)[0]
    cursor = Mock()
    cursor.fetchall.return_value = [(json.dumps({"changed": True}),)]
    with pytest.raises(ValueError, match="changed since review"):
        apply_rows(cursor, [{**row, "before": {"old": True}}], service)
    assert all(call.args[0].startswith("SELECT") for call in cursor.execute.call_args_list)
    cursor.reset_mock()
    cursor.fetchall.return_value = [(json.dumps(row["after"]),)]
    apply_rows(cursor, [{**row, "before": {"old": True}}], service)
    assert cursor.execute.call_count == 1  # Replay of an already-applied row is read-only.


def test_sql_insert_and_blob_replay_are_bounded_to_reviewed_fixtures() -> None:
    service = DemoService()
    row = desired_rows(service)[0]
    cursor = Mock()
    cursor.fetchall.return_value = []
    apply_rows(cursor, [{**row, "before": None}], service)
    assert cursor.execute.call_args.args[0].startswith("INSERT claims.Claim")
    blobs = Mock()
    manifest = image_manifest(service)
    first = manifest[0]
    content = LocalEvidenceReader().read(service.artifacts[first["artifactId"]])
    blob = blobs.get_blob_client.return_value
    blob.download_blob.return_value.readall.return_value = content
    upload_verified(blobs, [first], service)
    blob.download_blob.assert_called_once_with(offset=0, length=len(content) + 1)
    blob.upload_blob.assert_not_called()
    blob.download_blob.return_value.readall.return_value = b"different"
    with pytest.raises(ValueError, match="differs"):
        upload_verified(blobs, [first], service)
    blob.upload_blob.assert_not_called()
