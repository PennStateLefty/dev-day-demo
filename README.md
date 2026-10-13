# Agentic SDLC Demo

A reusable demonstration of an AI-assisted First Notice of Loss (FNOL) workflow using **synthetic automotive claims**. The local vertical slice gives a claims handler deterministic completeness and consistency checks, policy citations, and a customer-response draft for review.

## Safety boundaries

- This is a demonstration, not an insurance decision system.
- Every assessment requires human review. The system does not approve, deny, settle, pay, or send customer communications.
- Use only synthetic claims, policies, vehicles, and artifacts. Do not add customer data, credentials, or production telemetry.
- The review checks are deterministic demonstration rules, not underwriting or risk scoring.
- The adapted policy is fictional training content and must not be used to make real coverage decisions.

## Local quickstart

Prerequisites: Python 3.12, [uv](https://docs.astral.sh/uv/), Node.js 22+, and npm.

Start the API and MCP server:

```bash
uv sync --locked
uv run uvicorn app.main:app --app-dir src/apps/claims-api --reload
```

In another terminal, start the handler UI:

```bash
npm ci --prefix src/apps/claims-handler-ui
npm run dev --prefix src/apps/claims-handler-ui
```

Open the Vite URL printed in the terminal (normally `http://localhost:5173`). The API listens at `http://localhost:8000`; its OpenAPI document is at `/docs`, and the MCP endpoint is mounted at `/mcp`.

The local workflow is deterministic and uses checked-in synthetic fixtures. The optional Foundry integration is isolated behind configuration and has not been exercised against a live Foundry project.

## Validation

```bash
uv run ruff check src/apps/claims-api src/tests
uv run pytest -q
npm run test --prefix src/apps/claims-handler-ui
npm run build --prefix src/apps/claims-handler-ui
```

GitHub Actions runs the Python checks, UI typecheck/build, container image build, and Bicep compilation on pushes and pull requests. No Azure login, resource deployment, or live model invocation is part of CI.

## Packaging and infrastructure

`Dockerfile` builds the React UI and serves its static assets with the FastAPI app. Build locally with `docker build -t synthetic-claims-demo .`, then run with `docker run --rm -p 8000:8000 synthetic-claims-demo`.

`azure.yaml` points `azd` at the Bicep under `infrastructure/`. The current template defines only an Azure Container Apps managed environment; it does not deploy the application, create a public ingress, configure identity/authentication, or provision Foundry, Search, APIM, or Copilot Studio resources. No Azure resources have been provisioned. Validate the target topology, access controls, region, and cost before extending or deploying it.

## Repository map

- `src/apps/claims-api/` — shared deterministic service, REST API, MCP tools, and local orchestrator.
- `src/apps/claims-handler-ui/` — React/TypeScript handler experience.
- `data/` — synthetic claim/artifact fixtures, adapted fictional policy, and JSON Schemas.
- `evaluations/datasets/` — independently authored baseline cases.
- `src/tests/` — unit, REST/MCP contract, and evaluation checks.
- `infrastructure/`, `azure.yaml`, and `Dockerfile` — validation-ready packaging and minimal IaC foundation.
- `ASSET-PROVENANCE.md`, `THIRD-PARTY-NOTICES.md` — source and license records.
- `docs/` — phase specification, architecture, threat model, decisions, and demo outline.

The repository currently has no root license. Refer to the provenance and third-party notices before reusing any adapted asset.
