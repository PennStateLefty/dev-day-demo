from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastmcp import FastMCP

from .agents import LocalDemoOrchestrator
from .models import Assessment, Claim, Policy, WorkflowResult
from .service import DemoService, ResourceNotFound

service = DemoService()
mcp = FastMCP("Synthetic Claims Demo")


@mcp.tool
def list_synthetic_claims() -> list[dict[str, object]]:
    """List the synthetic claim fixtures available to the demo."""
    return [claim.model_dump(mode="json", by_alias=True) for claim in service.list_claims()]


@mcp.tool
def lookup_policy(policy_id: str, query: str) -> list[dict[str, object]]:
    """Find policy sections relevant to a query; citations are evidence, not decisions."""
    try:
        return [
            citation.model_dump(mode="json", by_alias=True)
            for citation in service.lookup_policy(policy_id, query)
        ]
    except ResourceNotFound as error:
        raise ValueError(str(error)) from error


@mcp.tool
def assess_synthetic_claim(claim_id: str) -> dict[str, object]:
    """Run deterministic review checks and return an assessment requiring human review."""
    try:
        return service.assess_claim(claim_id).model_dump(mode="json", by_alias=True)
    except ResourceNotFound as error:
        raise ValueError(str(error)) from error


mcp_app = mcp.http_app(path="/")

app = FastAPI(
    title="Synthetic Claims Demo API",
    version="0.1.0",
    description=(
        "Synthetic policy lookup and handler-review assistance; not a coverage decision system."
    ),
    lifespan=mcp_app.lifespan,
)
app.mount("/mcp", mcp_app)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/claims", response_model=list[Claim])
def list_claims() -> list[Claim]:
    return service.list_claims()


@app.get("/api/claims/{claim_id}", response_model=Claim)
def get_claim(claim_id: str) -> Claim:
    try:
        return service.get_claim(claim_id)
    except ResourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


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


@app.post("/api/claims/{claim_id}/assess", response_model=Assessment)
def assess_claim(claim_id: str) -> Assessment:
    try:
        return service.assess_claim(claim_id)
    except ResourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@app.post("/api/claims/{claim_id}/workflow", response_model=WorkflowResult)
def run_workflow(claim_id: str) -> WorkflowResult:
    try:
        return LocalDemoOrchestrator(service).run(claim_id)
    except ResourceNotFound as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


ui_dist = Path(__file__).resolve().parents[4] / "src/apps/claims-handler-ui/dist"
if ui_dist.is_dir():
    app.mount("/", StaticFiles(directory=ui_dist, html=True), name="claims-handler-ui")
