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
- A version-pinned hosted Foundry Policy Checker uses a Foundry Toolbox MCP tool containing only the shared `lookup_policy` capability and returns source-linked evidence.
- A version-pinned Foundry Communication specialist drafts correspondence and document requests; it cannot decide or send.
- Risk Analyst is an advisory reusable Foundry Skill, packaged into an immutable Toolbox version with only bounded, read-only synthetic-claims MCP tools. Its consumer must use the version-specific Toolbox MCP endpoint; it cannot score, classify or decide.
- An optional Copilot Studio Claims Data Analyst uses bounded SQL-backed tools, not Fabric or unrestricted generated SQL.
- Deterministic validators handle completeness and relationship rules, and deterministic fixtures support contract tests without replacing the hosted-agent demo path.

The application service presents stable assessment and policy-knowledge capabilities. A versioned Foundry Toolbox packages the bounded read-only tools. The hosted Policy Checker consumes its pinned Toolbox v1 directly; that Toolbox's downstream `lookup_policy` connection uses the hosted agent's Agentic Identity to reach the existing Entra-protected Claims MCP route through APIM. The separate Copilot Studio MCP route at `/policy-checker-tools/mcp` targets Toolbox v3. APIM validates the caller's tenant JWT, then calls Foundry with APIM's managed identity. Toolbox v3 in turn calls the Claims MCP route through APIM using the Foundry project's managed identity. The APIM Claims MCP route validates and forwards that token to the API; it does not replace it with APIM's identity. No caller identity is forwarded from Studio to Foundry, and there is no per-user OBO path. The operator selected tenant-only demo bearer admission at APIM and the API: verify signature, expiry and tenant issuer/`tid`, without audience, caller, scope or app-role gates. Keep the existing `claims-tools` route intact. Copilot Studio adds conversational intake and downstream workflow rather than duplicating Foundry assessment or response logic.

The live project currently has three RemoteTool project connections for the
same `claims-tools/mcp/` APIM endpoint. Toolbox v1 references
`claims-policy-agent-identity` (`AgenticIdentityToken`) with audience
`api://<Claims API audience>`; v2 references
`claims-policy-studio-project-identity` (`ProjectManagedIdentity`) with the
same audience format; and v3 references
`claims-policy-studio-project-identity-audience` (`ProjectManagedIdentity`)
with the bare Claims API audience GUID. The toolbox default-version pointer
remains v1, while the Studio APIM backend explicitly targets immutable version
3. These are version-specific connections, not three different MCP servers.
Version 2 is not selected by the current hosted-agent or Studio routes and
appears to be an earlier audience-format experiment; it has not been removed.

The explicit Communication draft endpoint runs the pinned Claim Assessor to obtain
verified claim evidence and recommendation, then invokes a separate pinned
Communication prompt agent with no tools. It validates plain customer wording and
stores claim, assessment, citation and artifact IDs separately as record metadata.
The wording guard rejects internal references, unsupported claims that review
already occurred, and promises of follow-up or timing.
After `Run handler checks` succeeds, the UI offers a separate draft action. The
API uses the verified result retained for that completed run, so drafting invokes
only Communication and does not rerun Claim Assessor. The UI exposes review and
mark-sent actions; those actions only persist the handler-entered reviewer and
UTC timestamps. No message transport is configured, and the existing `/workflow`
route remains unchanged.

The next demo increment is intentionally separate from this UI path: create
additional synthetic Foundry IQ knowledge sources (for example, procedural
checklists and planning references) for Copilot Studio to use while planning.
Do not attach these new sources to the existing claims-handler UI, Claim Assessor
workflow, or Communication draft endpoint. A separate reusable
communication-template Skill is intended to be pre-created in Foundry and then
manually added to the Communication agent as a visible Foundry authoring demo;
template selection and Skill invocation are not application-code integrations.

### Image evidence and handler checks

The implemented application path is UI **Run handler checks** -> FastAPI
`/api/claims/{claim_id}/workflow` -> explicitly pinned Claim Assessor -> authenticated
APIM `/assess` tool -> SQL claim/artifact lookup -> private Blob -> API-owned vision
call -> enriched tool result -> agent recommendation -> UI. `/workflow` is ordinary
Python control flow in the existing Container App, **not Foundry Workflows**, an
Azure Function, or a new supervisor. The tool calls `/assess`, never `/workflow`.
Copilot Studio remains the eventual supervisor. The hosted Policy Checker is
the genuinely hosted specialist for the wider demo; Claim Assessor remains a
prompt agent.

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
The observed `openapi_call`/`openapi_call_output` response shape and its nested
`response` JSON envelope are supported; all four pinned-v3 workflows pass live.
See the image-evidence runbook in [Azure deployment](azure-deployment.md).

Azure Developer CLI (`azd`) uses modular, subscription-scope Bicep under `infrastructure/`. It defines a new isolated Central US platform: Container Apps environment and runtime identity, ACR/monitoring, Entra-only SQL, Blob, Foundry/project/models, Basic Search, Developer APIM, Free API Center and scoped RBAC. The operator selected `public-demo` networking for portal presentations; `enforced-perimeter` remains the template default. The temporary policy-exception tag applies only to its new resource group, with a required owner and explicit deadline; the tag does not remove itself. The foundation and application are deployed. Basic Search is the explicitly approved fallback after serverless creation failed.

The azd service builds remotely in ACR and deploys a real-image Container Apps revision through `infrastructure/claims-api.bicep`, separately from the platform. Its public HTTPS website shares an origin with tenant-authenticated REST/MCP routes. Tokens intended for other resources in the same tenant are intentionally accepted for this demo; this is not production authorization guidance. Existing audience/client settings remain as browser/deployment configuration, not request-admission gates. The attached user-assigned identity accesses SQL and Search. Local mode remains unauthenticated and fixture-based; the Container App cannot implicitly select it.

SQL initialization creates relational claim/policy/artifact tables and bounded history queries, plus an append-only human-review note procedure. A contained runtime user receives object-level SELECT and procedure EXECUTE only. Blob initialization uploads synthetic policies and creates a semantic index, search-index knowledge source and extractive IQ knowledge base. Retrieved references must resolve to matching policy/index documents; dependency failures do not substitute local fixtures.

The UI implements tenant-specific MSAL PKCE sign-in using a separate SPA client and delegated API scope. Public `/auth-config` contains only nonsecret authentication metadata. Azure requests require sign-in and never fall back to anonymous calls or local fixtures. A plan-first registration initializer supports secretless API/SPA bootstrap but leaves consent and caller grants to an administrator.

Claim Assessor v3, private image fixtures, vision model and API/UI revision 16
are deployed. All four real workflows return verified tool evidence and advisory
recommendations; the operator confirmed the UI works. The runtime uses Foundry's
consumer endpoint with an explicit version and project-scoped Agent Consumer
permission. Policy Checker is independent of this UI button flow.
Vision accuracy remains a disclosed demo limitation.
Risk Analyst Skill v1 is published but its consuming-agent/tool integration is
not verified. Policy Checker Toolbox v1 and hosted agent v1 return cited evidence
directly; the separate APIM-to-Toolbox-v3 route passes initialize/list/call.
Communication agent v2 is published and its four direct draft scenarios pass
output/wording validation. The API/SQL/UI rollout is deployed to the existing
claims demo, and live check-then-draft verified a persisted, unreviewed,
unsent record with separate evidence metadata. No customer message was sent.
Application Insights recorded the draft request and Communication traces.
Interactive browser sign-in remains unverified. Actual Copilot Studio
connector/supervision also remains next work.
API prompt, completion and tool content is explicitly logged for this synthetic
demo, without credentials/headers. Browser ingestion and the hosted agent's
exporter update remain unverified; its new versions failed remote build.
Missing tokens are denied.
SQL runtime stays read-only apart from its bounded append-note procedure.
Temporary bootstrap access was removed and the selected SQL administrator
restored. No connector authentication fallback is pre-authorized.

NSP is a public data-plane boundary, not a private endpoint. In enforced mode, SQL, Foundry, Search and Storage join enforced associations with an operator IPv4 `/32` and same-subscription managed-identity access; APIM and Container Apps cannot join. This worked for runtime identities but blocked presenter portal workflows. The explicit public-demo mode enables service public endpoints/firewalls and retires the demo perimeter, retaining Entra-only SQL, disabled service keys, private Blob containers and scoped RBAC. It intentionally provides no network-source isolation. Historical NSP logs remain in Blob. A mode change must be deployed through azd, not just changed in the portal.

Current Microsoft guidance supports named prompt-agent versions, Foundry Toolboxes and publishing MCP through APIM. Runtime extractive IQ retrieval, the hosted agent's direct v1 path and authenticated Studio APIM `lookup_policy` are verified. The hosted agent must not route its Toolbox calls through APIM. Actual Studio onboarding remains separate from protocol acceptance. CI compiles Bicep and checks selected compiled invariants, but does not authenticate or deploy. See [deployment/BOM](azure-deployment.md), [decision gates](open-questions.md) and [fresh-session handoff](specialist-handoff.md). Any selected external asset requires prior provenance and license review.
