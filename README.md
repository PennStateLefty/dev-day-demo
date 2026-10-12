# Agentic SDLC Demo

A staged, customer-facing demonstration of an AI-assisted First Notice of Loss (FNOL) workflow for **synthetic automotive claims**. The system is intended to help a human claims handler check completeness, retrieve relevant policy language, identify inconsistencies, recommend next steps, and prepare a customer-response draft for review.

## Boundaries

- This is a demonstration, not an insurance decision system.
- No agent or application may autonomously approve, deny, settle, or pay a claim.
- Claims, policyholders, vehicles, policies, and artifacts must be synthetic. Do not add customer data or intellectual property, secrets, credentials, telemetry, or deployment outputs.
- Policy-grounded assessments must cite their sources; all claim decisions and customer communications stay subject to human review.
- External assets are limited to the public repositories in `docs/phase-1-spec.md`. No source code or data from those repositories has been copied into this checkpoint.

## Proposed architecture

The initial vertical slice is planned, not implemented: a claims-handler UI calls a REST API; both the API and an MCP adapter delegate to one claims application service. Application code, agents, MCP adapters, packages, and tests will live under `src/`; schemas and synthetic data remain under `data/`. The service uses the canonical contracts in `data/schemas/`, a policy-retrieval interface, and configurable model access. Deterministic validation and evaluation surround the service.

The first-slice direction is Python/FastAPI with a Foundry hosted orchestrator, prompt-based policy and response specialists, and deterministic validators. Foundry IQ/Azure AI Search provides shared policy grounding; deterministic fixtures support contract tests. Azure packaging will use Azure Developer CLI (`azd`) with a root-level `azure.yaml`; Bicep under `infrastructure/` will define Azure resources. The `azure.yaml` service entries and Bicep modules will be added after the deployment topology is validated.

Identity will use developer credentials locally and managed identity for Azure service-to-service calls. Prefer Entra-authenticated API Management consumers; validate a scoped APIM subscription-key fallback only if the target Copilot Studio tenant requires it. Keys must be managed outside the repository; do not assume tenant sharing.

## Repository status

This repository is at its presenter-review baseline checkpoint. It contains the Phase 1–2 workspace/source assessment, proposed domain contracts, governance records, a staged repository skeleton, and a decision register with implementation validation gates. No runnable claims application, agent, API, MCP server, infrastructure deployment, or Copilot Studio solution is included yet.

## Local prerequisites

For this documentation and schema checkpoint:

- Git
- Python 3 (used only for lightweight local JSON checks; no Python application is implemented)

No package installation, Azure subscription, credentials, or model endpoint is required for the current checkpoint. Application runtime prerequisites will be selected and documented before implementation. Azure deployment packaging is planned with `azd` and Bicep; no deployment configuration or cloud resource is implemented yet.

## Checkpoint artifacts

- `docs/phase-1-spec.md` — project requirements and staged operating protocol.
- `docs/source-assessment.md` — assessment of the six approved public sources.
- `docs/domain-model.md` and `data/schemas/` — initial synthetic claims domain and JSON Schema contracts.
- `docs/architecture.md`, `docs/threat-model.md`, and `docs/demo-script.md` — checkpoint-level architecture, safety, and demo placeholders for the planned phases.
- `docs/vertical-slice-plan.md` — proposed, bounded first implementation slice.
- `docs/open-questions.md` — baseline decisions, implementation validation gates, and current Microsoft guidance.
- `ASSET-PROVENANCE.md` and `THIRD-PARTY-NOTICES.md` — current reuse ledger and notices.

## Next checkpoint

Review this baseline with the presenters before implementation begins. The next technical checkpoint is to prove version-pinned specialist invocation, shared knowledge grounding, and the Toolbox/APIM/Copilot Studio MCP path in the target environment. Keep fixtures synthetic and author them independently; resolve asset rights and the root license before external reuse or publication.
