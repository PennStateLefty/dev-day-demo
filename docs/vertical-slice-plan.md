# Proposed first vertical slice

## Goal

Deliver one local, deterministic-first path that assesses a synthetic claim against its linked policy and artifacts, returns a structured result with policy citations, and exposes the same application service through REST and MCP adapters. Keep claim decisions and customer communication under human review.

## Proposed flow

1. Accept a synthetic `claimId` or validated claim payload.
2. Load the claim, linked customer/policy/vehicle, and referenced claim artifacts through a repository interface.
3. Run deterministic completeness and relationship checks, including required intake fields, policy status on date of loss, listed driver, duplicate references, and a configurable synthetic estimate threshold. These deterministic paths also support contract tests.
4. Retrieve policy passages through shared Foundry IQ/Azure AI Search and preserve source references, independently of agent prompts.
5. Use a Foundry hosted orchestrator with the Python Agent Framework integration to call explicitly versioned prompt-based policy and response specialists. The policy specialist returns cited evidence; the response specialist drafts only from the structured assessment.
6. Emit `claim-assessment.schema.json` with completeness findings, conflicts, citations, recommended actions, and mandatory human review.
7. Expose the workflow through FastAPI and a versioned Foundry Toolbox/APIM MCP endpoint as one governed capability. Verify that APIM can expose the Toolbox endpoint for the target Copilot Studio MCP client; if not, use a thin MCP facade over the same application service. Keep the Copilot Studio experience as a downstream consumer with conversational intake, not a duplicate assessment implementation.
8. Test schema, domain, deterministic contract paths, REST/MCP contracts, retrieval/citation behavior, agent outputs, versioned evaluations, error paths, and rollback behavior.

## Boundaries and decisions deferred

- Place application, agent, MCP, package, and test code under `src/`; keep docs and schemas/data at the repository root and Bicep under `infrastructure/`.
- Use Azure Developer CLI (`azd`) with a root `azure.yaml` for packaging/orchestration, and Bicep for infrastructure. Define services and modules only after runtime/topology selection and current documentation validation.
- Use Python/FastAPI for the service/API; use a Foundry hosted orchestrator with prompt-based policy and response specialists; use Foundry IQ/Azure AI Search as a shared knowledge source.
- Expose stable capabilities through a versioned Foundry Toolbox and API Management MCP endpoint. Copilot Studio consumes this governed surface and may add intake/interaction flow, but does not replicate assessment or response-generation logic.
- Use deterministic fixtures/contract paths alongside the Foundry agent path so contracts can be tested without live model calls.
- Use developer identity locally, managed identity for Azure service-to-service calls, and prefer Entra for API Management consumers. Support a scoped APIM subscription-key path only if required for cross-tenant Copilot Studio connectivity and validated in the target tenant. Keep keys outside source control.
- Configure demo-only completeness checks for policy reference, loss date, vehicle, reporting driver, claimant statement, and at least one supporting artifact. Customer ID may be resolved through the policy. Default the configurable repair-estimate review threshold to USD 5,000. These are synthetic demonstration settings, not carrier rules.
- Do not approve, deny, settle, or pay a claim; do not send customer communications.
- Do not implement fraud scoring, claimant-history analytics, or risk classification. A possible prior-damage or inconsistency finding only requests review.
- Pin current Foundry, Agent Framework, FastMCP, Azure AI Search/Foundry IQ, and API Management SDK/API versions after a target-environment implementation spike. Do not invent version-specific service declarations or cloud resources.
- Keep model and retrieval access behind interfaces; allow deterministic fixtures/mocks for local runs.
- Select one small, approved synthetic policy/claim set only after the source assessment and licensing/data review checkpoint.
- Infrastructure, Copilot Studio deployment, and production security controls are future phases.
