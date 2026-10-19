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

The local workflow is deterministic and uses checked-in synthetic fixtures. The
deployed Azure demo and Foundry integrations are documented below and in the
deployment guide; the local quickstart does not require Azure resources.

## Validation

```bash
uv run ruff check src/apps/claims-api src/tests scripts
uv run pytest -q
uv run python -m unittest discover -s scripts/validation -p 'test_*.py'
npm run test --prefix src/apps/claims-handler-ui
npm run build --prefix src/apps/claims-handler-ui
```

GitHub Actions runs the Python checks, UI typecheck/build, container image build, Bicep compilation, and compiled infrastructure invariants on pushes and pull requests. No Azure login, resource deployment, or live model invocation is part of CI.

## Packaging and infrastructure

`Dockerfile` builds the React UI and serves its static assets with the FastAPI app. Build locally with `docker build -t synthetic-claims-demo .`, then run with `docker run --rm -p 8000:8000 synthetic-claims-demo`.

`azure.yaml` points `azd` at subscription-scope Bicep under `infrastructure/`. The platform foundation defines an isolated resource group, Container Apps environment and runtime identity, ACR, monitoring, Entra-only SQL, private Blob containers, Foundry account/project and pinned models, Basic Search, Developer APIM, Free API Center and scoped RBAC. Networking defaults to `enforced-perimeter`; the operator selected explicit `public-demo` mode for portal-driven presentations, retaining identity-only authentication.

`azure.yaml` also declares a remote-built Container Apps service. Its separate Bicep revision template requires the real published image, attaches the runtime managed identity and explicitly enables Azure mode. postprovision hooks apply relational SQL migrations, synthetic seeds and object-level contained-user grants, then initialize Blob policies and extractive IQ knowledge. Azure mode requires signed bearer tokens from the configured tenant for REST/MCP (tenant-only demo admission, not production authorization), reads SQL and retrieves live IQ citations without fixture fallback; local mode remains unchanged.

The hosted UI implements tenant-specific MSAL PKCE sign-in with a separate SPA registration. A plan-first identity initializer can create isolated secretless API/SPA registrations, but never grants consent or caller roles. REST/native MCP gateway routes and bearer policies are declared with the application revision; ARM and runtime validation remain required.

**The Azure foundation and claims application are deployed.** Claim Assessor v3,
Policy Checker v1, and Communication v2 have been published and exercised;
check-then-draft persisted a Communication record for a synthetic claim. Drafts
remain subject to human review and are never sent. Actual Copilot Studio
connector onboarding/supervision, Risk Analyst skill integration, and
interactive browser sign-in remain unfinished. Do not expose the unauthenticated
**local-mode** container. See [Azure deployment and bill of materials](docs/azure-deployment.md)
for evidence and remaining work.

## Repository map

- `src/apps/claims-api/` — shared deterministic service, REST API, MCP tools, and local orchestrator.
- `src/apps/claims-handler-ui/` — React/TypeScript handler experience.
- `src/apps/policy-checker/` — hosted Policy Checker service.
- `agents/` and `scripts/agents/` — versioned Foundry agent/skill sources and publishers.
- `data/` — synthetic claim/artifact fixtures, adapted fictional policy, and JSON Schemas.
- `evaluations/datasets/` — independently authored baseline cases.
- `src/tests/` — unit, REST/MCP contract, and evaluation checks.
- `infrastructure/`, `azure.yaml`, and `Dockerfile` — modular Azure infrastructure and application packaging.
- `ASSET-PROVENANCE.md`, `THIRD-PARTY-NOTICES.md` — source and license records.
- `docs/` — current architecture, deployment runbook, handoff, threat model, and demo outline.

The initial scaffold's empty `src/agents/`, `src/packages/`, `src/mcp/`,
`infrastructure/environments/`, `scripts/bootstrap/`, `scripts/demo/`,
`copilot-studio/`, and `ado/` paths have been removed. Agent sources live at the
repository root under `agents/`; the API owns shared contracts and MCP tools.
Empty scaffold directories are not kept in Git; create a directory when its
first real implementation or asset exists.

The repository currently has no root license. Refer to the provenance and third-party notices before reusing any adapted asset.
