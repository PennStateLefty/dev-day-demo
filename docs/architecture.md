# Architecture outline

## Implemented local vertical slice

The React/TypeScript handler UI calls a FastAPI REST API. REST and FastMCP tools delegate to one `DemoService`, which loads synthetic fixtures, validates them against the repository's JSON Schemas, retrieves relevant policy sections with source citations, and produces deterministic review flags. A local orchestrator uses that assessment to create a draft response. All outputs remain subject to human review.

The API can serve the built UI from the same origin when the frontend `dist/` directory exists, as in the Docker image. During local development, Vite serves the UI separately and the API allows only the local Vite origins. The container image is multi-stage and includes only the API, runtime dependencies, fixtures, and compiled UI.

The deterministic assessment does not make coverage decisions or assign claimant risk. Checks such as policy dates, listed drivers, missing intake data, estimate threshold, and duplicate artifacts are synthetic demo rules.

## Intended hosted architecture

The approved hosted extension keeps core claims behavior independent of the UI:

The shared data/tool service remains Python/FastAPI. Presenter ownership is:

- Copilot Studio owns the supervisor, not a new Foundry hosted orchestrator.
- A version-pinned Foundry Claim Assessor prompt agent receives a claim ID and evaluates the Claims API's enriched assessment. The API retrieves registered private Blob evidence and owns the direct multimodal damage-analysis call; the specialist does not receive images. Deterministic findings, model observations and the agent's recommendation remain distinct.
- A version-pinned Foundry Policy Checker uses shared Foundry IQ/Azure AI Search grounding and returns source-linked evidence.
- A version-pinned Foundry Communication specialist drafts correspondence and document requests; it cannot decide or send.
- Risk Analyst is an advisory reusable Foundry Skill, packaged into an immutable Toolbox version with only bounded, read-only synthetic-claims MCP tools. Its consumer must use the version-specific Toolbox MCP endpoint; it cannot score, classify or decide.
- An optional Copilot Studio Claims Data Analyst uses bounded SQL-backed tools, not Fabric or unrestricted generated SQL.
- Deterministic validators handle completeness and relationship rules, and deterministic fixtures support contract tests without replacing the hosted-agent demo path.

The application service presents stable assessment and policy-knowledge capabilities. A versioned Foundry Toolbox packages those tools. API Management governs the MCP surface consumed by Copilot Studio. Prefer exposing the Toolbox MCP endpoint as the APIM backend when the target project supports the required protocol and authentication; otherwise, expose a thin MCP facade over the same application service. Copilot Studio adds conversational intake and downstream workflow rather than duplicating Foundry assessment or response logic.

### Image evidence and handler checks

The implemented application path is UI **Run handler checks** -> FastAPI
`/api/claims/{claim_id}/workflow` -> explicitly pinned Claim Assessor -> authenticated
APIM `/assess` tool -> SQL claim/artifact lookup -> private Blob -> API-owned vision
call -> enriched tool result -> agent recommendation -> UI. `/workflow` is ordinary
Python control flow in the existing Container App, **not Foundry Workflows**, an
Azure Function, or a new supervisor. The tool calls `/assess`, never `/workflow`.
Copilot Studio remains the eventual supervisor. A genuinely hosted specialist is
still required for the wider demo; this slice does not implement one.

Claims 001, 002 and 004 reference user-provided AI-generated PNGs via
`artifactIds -> artifactId -> contentRef`. Claim 003 intentionally has no evidence.
The private `evidence` container uses the validated repository-relative `contentRef`
as the Blob key. Preview uses authenticated API byte responses and revocable
browser object URLs; selecting/viewing evidence makes no model calls.

The selected vision model is `gpt-6-luna`, separate from the specialist's
`claims-chat` deployment. The approved `claims-vision` deployment now pins version
`2026-09-22`, and API-owned inference with the supplied images is verified. No
substitute is selected automatically. Local mode remains cloud-free and explicitly reports image analysis
as unavailable. Processing failures retain deterministic findings with an explicit
unavailable limitation; no linked photo produces a distinct `no_evidence` result.
Per-part severity describes visible damage only, not safety, cost or coverage.
No visible damage in an obscured view is not proof of no damage.

The handler accepts only an actual matching assessment-tool output from the
Foundry response and validates its relationship to the selected claim, then
validates the separate agent recommendation. It fails closed if tool evidence is
missing or the service returns an unrecognized result shape; it never reconstructs
authoritative evidence from the agent's final prose or repeats the vision call.
The live response shape still needs target-project proof after authorization.
See the image-evidence runbook in [Azure deployment](azure-deployment.md).

Azure Developer CLI (`azd`) uses modular, subscription-scope Bicep under `infrastructure/`. It defines a new isolated Central US platform: Container Apps environment and runtime identity, ACR/monitoring, Entra-only SQL, Blob, Foundry/project/models, Basic Search, Developer APIM, Free API Center and scoped RBAC. The operator selected `public-demo` networking for portal presentations; `enforced-perimeter` remains the template default. The temporary policy-exception tag applies only to its new resource group, with a required owner and explicit deadline; the tag does not remove itself. The foundation and application are deployed. Basic Search is the explicitly approved fallback after serverless creation failed.

The azd service builds remotely in ACR and deploys a real-image Container Apps revision through `infrastructure/claims-api.bicep`, separately from the platform. Its public HTTPS website shares an origin with Entra-protected REST/MCP routes. Azure mode requires an explicit tenant, GUID audience, allowed caller clients and delegated/application permission, and uses the attached user-assigned identity for SQL and Search. Local mode remains unauthenticated and fixture-based; the Container App cannot implicitly select it.

SQL initialization creates relational claim/policy/artifact tables and bounded history queries, plus an append-only human-review note procedure. A contained runtime user receives object-level SELECT and procedure EXECUTE only. Blob initialization uploads synthetic policies and creates a semantic index, search-index knowledge source and extractive IQ knowledge base. Retrieved references must resolve to matching policy/index documents; dependency failures do not substitute local fixtures.

The UI implements tenant-specific MSAL PKCE sign-in using a separate SPA client and delegated API scope. Public `/auth-config` contains only nonsecret authentication metadata. Azure requests require sign-in and never fall back to anonymous calls or local fixtures. A plan-first registration initializer supports secretless API/SPA bootstrap but leaves consent and caller grants to an administrator.

This is not a fully verified hosted demo. Claim Assessor v3, the private image
fixtures, vision model and updated API/UI are deployed. The runtime uses Foundry's
consumer endpoint with an explicit version and project-scoped Agent Consumer
permission. The confirmed project managed identity is allowed through APIM and
has its API application role, but Foundry still reuses a pre-grant token expiring
2026-10-17 15:02:43 UTC; tool calls return 403 and the handler fails explicitly.
Actual tool-output extraction and full recommendations remain unverified.
Initial vision outputs also missed expected details in two damage fixtures.
Risk Analyst Skill v1 is published, but its MCP Toolbox, Policy Checker,
Communication, the required genuinely hosted specialist, SPA browser sign-in,
model gateway configuration and Studio integration remain unfinished or
unverified. Direct/APIM readiness and native MCP pass; missing tokens are denied.
SQL runtime stays read-only apart from its bounded append-note procedure.
Temporary bootstrap access was removed and the selected SQL administrator
restored. No connector authentication fallback is pre-authorized.

NSP is a public data-plane boundary, not a private endpoint. In enforced mode, SQL, Foundry, Search and Storage join enforced associations with an operator IPv4 `/32` and same-subscription managed-identity access; APIM and Container Apps cannot join. This worked for runtime identities but blocked presenter portal workflows. The explicit public-demo mode enables service public endpoints/firewalls and retires the demo perimeter, retaining Entra-only SQL, disabled service keys, private Blob containers and scoped RBAC. It intentionally provides no network-source isolation. Historical NSP logs remain in Blob. A mode change must be deployed through azd, not just changed in the portal.

Current Microsoft guidance supports named prompt-agent versions, Foundry Toolboxes and publishing MCP through APIM. Runtime extractive IQ retrieval is verified. The precise Toolbox-to-APIM-to-Copilot Studio path, cross-tenant authentication, specialist grounding and Foundry model routing through the AI gateway still require target-environment proof. New Foundry's playground currently reports Save as agent unsupported in Central US; confirm the required versioned-agent features before claiming specialist readiness. CI compiles Bicep and checks selected compiled security invariants, but does not authenticate or deploy. See [deployment/BOM](azure-deployment.md) and [decision gates](open-questions.md). Any selected external asset requires prior provenance and license review.
