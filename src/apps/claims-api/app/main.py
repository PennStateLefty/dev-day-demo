from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

import httpx
from azure.core.exceptions import AzureError
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastmcp import FastMCP
from mssql_python import Error as SqlError
from openai import APIError
from PIL import Image, UnidentifiedImageError
from pydantic import Field, ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .agents import LocalDemoOrchestrator
from .auth import EntraAuthMiddleware
from .evidence import validate_image
from .handler import HandlerError
from .models import Artifact, Claim, EnrichedAssessment, HandlerResult, Policy, WorkflowResult
from .runtime import Runtime
from .search_rest import KnowledgeError
from .service import PolicyEvidenceUnavailable, ResourceNotFound
from .settings import Settings

logger = logging.getLogger(__name__)
settings = Settings.from_environment()
runtime = Runtime(settings)
service = runtime.service
mcp = FastMCP("Synthetic Claims Demo", mask_error_details=True)


@mcp.tool
def list_synthetic_claims() -> list[dict[str, object]]:
    """List the synthetic claim fixtures available to the demo."""
    return [claim.model_dump(mode="json", by_alias=True) for claim in service.list_claims()]


@mcp.tool
def lookup_policy(
    policy_id: Annotated[str, Field(pattern=r"^pol-[a-z0-9-]+$", max_length=100)],
    query: Annotated[str, Field(min_length=1, max_length=1000, pattern=r".*\S.*")],
) -> list[dict[str, object]]:
    """Find policy sections relevant to a query; citations are evidence, not decisions."""
    try:
        return [
            citation.model_dump(mode="json", by_alias=True)
            for citation in service.lookup_policy(policy_id, query)
        ]
    except ResourceNotFound as error:
        raise ValueError(str(error)) from error


@mcp.tool
def assess_synthetic_claim(
    claim_id: Annotated[str, Field(pattern=r"^clm-[a-z0-9-]+$", max_length=100)],
) -> dict[str, object]:
    """Return deterministic checks and separate API-owned image observations for human review."""
    try:
        return runtime.evidence.assess(service, claim_id).model_dump(mode="json", by_alias=True)
    except ResourceNotFound as error:
        raise ValueError(str(error)) from error


@mcp.tool
def get_synthetic_claim(
    claim_id: Annotated[str, Field(pattern=r"^clm-[a-z0-9-]+$", max_length=100)],
) -> dict[str, object]:
    """Read one synthetic claim to ground bounded review and history lookups."""
    try:
        return service.get_claim(claim_id).model_dump(mode="json", by_alias=True)
    except ResourceNotFound as error:
        raise ValueError(str(error)) from error


@mcp.tool
def synthetic_customer_history(
    customer_id: Annotated[str, Field(pattern=r"^cust-[a-z0-9-]+$")],
) -> dict[str, object]:
    """Read up to 20 synthetic claims for advisory consistency review, never fraud scoring."""
    if runtime.store is None:
        claims = [claim for claim in service.list_claims() if claim.customer_id == customer_id][:20]
    else:
        claims = runtime.store.customer_history(customer_id)
    return {
        "claims": [claim.model_dump(mode="json", by_alias=True) for claim in claims],
        "humanReviewRequired": True,
        "purpose": "Synthetic consistency review only; not a risk or coverage decision.",
    }


@mcp.tool
def add_synthetic_review_note(
    claim_id: Annotated[str, Field(pattern=r"^clm-[a-z0-9-]+$")],
    note: Annotated[str, Field(min_length=1, max_length=2000)],
) -> dict[str, object]:
    """Append a synthetic handler-review note; cannot change claims, decisions or send messages."""
    if runtime.store is None:
        raise ValueError(
            "Persistent review notes require the explicitly configured Azure SQL mode."
        )
    service.get_claim(claim_id)
    return {
        "noteId": runtime.store.add_review_note(claim_id, note),
        "claimId": claim_id,
        "humanReviewRequired": True,
    }


mcp_app = mcp.http_app(path="/")


@asynccontextmanager
async def lifespan(application: FastAPI):
    try:
        async with mcp_app.lifespan(application):
            yield
    finally:
        runtime.close()


app = FastAPI(
    title="Synthetic Claims Demo API",
    version="0.1.0",
    description=(
        "Synthetic policy lookup and handler-review assistance; not a coverage decision system."
    ),
    lifespan=lifespan,
)
app.mount("/mcp", mcp_app)
if settings.mode == "azure":
    app.add_middleware(EntraAuthMiddleware, settings=settings)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.exception_handler(AzureError)
@app.exception_handler(SqlError)
@app.exception_handler(httpx.HTTPError)
@app.exception_handler(KnowledgeError)
async def cloud_dependency_error(request: Request, error: Exception) -> JSONResponse:
    logger.error("Cloud dependency failed: %s", type(error).__name__)
    return JSONResponse(
        {"detail": "A required cloud dependency is unavailable; no fixture fallback was used."},
        status_code=503,
    )


@app.exception_handler(PolicyEvidenceUnavailable)
async def policy_evidence_unavailable(
    request: Request, error: PolicyEvidenceUnavailable
) -> JSONResponse:
    return JSONResponse({"detail": str(error)}, status_code=503)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/auth-config")
def auth_config() -> JSONResponse:
    configuration = {"mode": settings.mode}
    if settings.mode == "azure":
        configuration.update(
            {
                "tenantId": settings.tenant_id,
                "clientId": settings.ui_client_id,
                "scope": f"api://{settings.audience}/claims.invoke",
            }
        )
    return JSONResponse(configuration, headers={"Cache-Control": "no-store"})


@app.get("/ready")
def ready() -> dict[str, str]:
    try:
        runtime.probe()
    except RuntimeError as error:
        logger.error("Cloud readiness probe failed: %s", type(error).__name__)
        raise HTTPException(
            status_code=503, detail="Required data has not been initialized."
        ) from error
    return {"status": "ready", "mode": settings.mode}


@app.get("/api/claims", response_model=list[Claim])
def list_claims() -> list[Claim]:
    return service.list_claims()


@app.get("/api/claims/{claim_id}", response_model=Claim)
def get_claim(claim_id: str) -> Claim:
    try:
        return service.get_claim(claim_id)
    except ResourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/claims/{claim_id}/artifacts", response_model=list[Artifact])
def list_artifacts(claim_id: str) -> list[Artifact]:
    try:
        return service.list_artifacts(claim_id)
    except ResourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/claims/{claim_id}/artifacts/{artifact_id}/content")
def artifact_content(claim_id: str, artifact_id: str) -> Response:
    try:
        artifact = service.get_artifact(claim_id, artifact_id)
        if artifact.artifact_type != "damage_photo":
            raise ResourceNotFound("Artifact is not an image.")
        reader = runtime.evidence.reader
        if reader is None:
            raise HTTPException(status_code=503, detail="Evidence storage is not configured.")
        content = reader.read(artifact)
        return Response(content, media_type=validate_image(content), headers={
            "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        })
    except ResourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (
        OSError, ValueError, UnidentifiedImageError,
        Image.DecompressionBombError, Image.DecompressionBombWarning,
    ) as error:
        logger.warning("Evidence preview unavailable (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail="Evidence image is unavailable.") from error


@app.get("/api/policies/{policy_id}", response_model=Policy)
def get_policy(policy_id: str) -> Policy:
    try:
        return service.get_policy(policy_id)
    except ResourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.get("/api/policies/{policy_id}/lookup")
def lookup_policy_endpoint(
    policy_id: str,
    query: str = Query(min_length=1, max_length=1000, pattern=r".*\S.*"),
) -> list[dict[str, object]]:
    try:
        return [
            citation.model_dump(mode="json", by_alias=True)
            for citation in service.lookup_policy(policy_id, query)
        ]
    except ResourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/claims/{claim_id}/assess", response_model=EnrichedAssessment)
def assess_claim(claim_id: str) -> EnrichedAssessment:
    try:
        return runtime.evidence.assess(service, claim_id)
    except ResourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/claims/{claim_id}/workflow", response_model=WorkflowResult | HandlerResult)
def run_workflow(claim_id: str) -> WorkflowResult | HandlerResult:
    try:
        claim = service.get_claim(claim_id)
        if settings.mode == "local":
            result = LocalDemoOrchestrator(service).run(claim_id)
            return WorkflowResult(
                assessment=runtime.evidence.assess(service, claim_id),
                response_draft=result.response_draft,
            )
        if runtime.handler is None:
            raise HTTPException(status_code=409, detail=(
                "Pinned Claim Assessor is not configured; no fixture fallback was used."
            ))
        return runtime.handler.run(claim)
    except ResourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (HandlerError, APIError, ValidationError, ValueError) as error:
        logger.error("Agent handler failed (%s)", type(error).__name__)
        raise HTTPException(status_code=503, detail=(
            "Pinned agent result could not be verified; no fixture fallback was used."
        )) from error


ui_dist = Path(__file__).resolve().parents[4] / "src/apps/claims-handler-ui/dist"
if ui_dist.is_dir():
    app.mount("/", StaticFiles(directory=ui_dist, html=True), name="claims-handler-ui")
