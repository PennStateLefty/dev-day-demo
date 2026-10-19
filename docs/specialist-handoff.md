# Specialist session handoff

Status: 2026-10-19. The Communication source implementation, immutable Foundry
version 2, and API/SQL/UI rollout are complete in this worktree. The next
specialist work is the Risk Analyst skill integration. This is a working demo
foundation; actual Copilot Studio connector onboarding/supervision remains
unfinished.

Authentication decision (October 18, supersedes permission requirements below):
the operator explicitly selected tenant-only bearer authentication for this
demo. APIM and the API verify signature, expiry and tenant-bound issuer/`tid`;
they do not require a particular audience, caller client, scope or application
role. Both tenant v1 and v2 issuers are accepted. Any valid token from this
tenant can access the demo, including one intended for another resource.
Keep this demo-only trust boundary explicit; do not reuse it as a production
authorization pattern. APIM still uses its managed identity to call Foundry.
Deployed as API revision 12 and matching policies on Claims REST, Claims MCP
and the Studio Toolbox route. A real same-tenant ARM-audience v1 token reads
claims directly and through APIM (200); anonymous requests remain 401.
Subsequent content-logging diagnosis: Foundry emits `openapi_call` /
`openapi_call_output`, not plain function-call items; the output is a JSON object
whose `response` field contains the actual tool JSON. The handler now accepts
that observed envelope while retaining evidence, citation, claim and artifact
validation. Synthetic prompt/completion/tool content capture is explicitly
enabled in the API; see the query and disable setting in `azure-deployment.md`.
No tokens or authentication headers are recorded.

Revision 16 completes all four real pinned-v3 `/workflow` calls (HTTP 200):
001/002/004 have completed image analysis and human-review recommendations;
003 has no evidence and requests information. Every result preserves
`humanReviewRequired=true`. Full response chunks were reconstructed from
Application Insights, including actual OpenAPI calls and outputs. The
experimental SDK GenAI hook is disabled after its `NonRecordingSpan.attributes`
bug caused a live 500; explicit content traces and request/dependency export
remain enabled. Hosted Policy Checker v1 is unaffected.

## Purpose and next session

Build a compelling synthetic demonstration for developers, project managers and
QA. Keep MCP and Copilot Studio agent policies simple: essential authentication,
bounded tools and human review, not production policy sophistication. Exact
damage recognition is not a release gate. No fine-tuning or further vision prompt
optimization is planned.

The hosted Policy Checker is implemented and working independently. The
Communication agent source, Foundry version 2, and live API/SQL/UI rollout are
complete. Claim Assessor remains a prompt agent. The next session should finish
the Risk Analyst skill integration, then start the RAG/Foundry knowledge-source
enhancements and prepare an independently attachable communication-template
Skill. Copilot Studio remains the intended supervisor; do not add a Foundry
orchestrator or Foundry Workflows.

### Next session: ordered scope

1. **Finish Risk Analyst Skill integration.** Continue the bounded advisory
   skill described below. Keep it read-only, evidence-linked and human-reviewed.
   Do not add risk scores, fraud classifications, coverage decisions, or a
   separate agent.
2. **Prepare a reusable communication-template Skill in Foundry.** The demo
   should show an operator adding this pre-created Skill to the existing
   Communication agent in Foundry. The Skill should provide a small, reviewed
   set of communication-template patterns (the user will choose the useful
   template types in the next session) while preserving the existing wording
   safeguards. Confirm the supported Foundry Skill asset and attachment flow,
   create/publish the asset in Foundry, and verify it is available to add.
   **Do not wire template selection or Skill invocation into the
   claims API, handler UI, or other application code.** The point is to show the
   Foundry authoring workflow of adding a Skill to the agent, not to change the
   deployed UI workflow. Keep Communication v2 selected until an explicitly
   approved Foundry update is ready; adding a Skill in Foundry is a separate
   demo action and must not silently alter the live UI pin.
3. **Add Foundry IQ knowledge sources for Copilot Studio planning.** The
   intended example content includes synthetic policy references and procedural
   checklists. Existing policy IQ retrieval is already part of the handler's
   current assessment path; do not silently redirect or alter it. Add or expose
   the additional planning sources for Copilot Studio to retrieve while planning
   a response/workflow. These new sources are **not inputs to the existing
   claims-handler UI flow or its Claim Assessor/Communication sequence**.
   Preserve that boundary in source, configuration, tests and the architecture
   diagram. First inspect the existing Foundry IQ/Search assets and decide the
   simplest reuse path; avoid creating duplicate infrastructure or overbuilding
   a retrieval layer. Verify source grounding and missing/ambiguous retrieval
   behavior with synthetic content.

Keep these as distinct demo capabilities: the Communication Skill is manually
added to the Communication agent in Foundry, while the IQ sources are intended
for Copilot Studio planning. Neither change should be represented as already
integrated into the current handler UI. Coordinate Foundry version/default
changes and shared Azure deployments; do not provision a new foundation or
create another Foundry project by default. Ask the user before adding
significant complexity or expanding beyond the stated demo scope.

### Communication agent: implemented and deployed

The source adds a no-tools, draft-only prompt agent, strict response/record
schemas, explicit API routes, SQL persistence procedures, and a UI workflow
separate from `/workflow`. Claim, assessment, citation, and artifact links remain
record metadata; the body omits internal references. Human review and mark-sent
actions store reviewer/timestamps only and never transmit a message. Customer
wording validation rejects internal references, claims that handler review
already occurred, and promises of follow-up or timing.

The handler UI now reveals a separate draft action only after `Run handler checks`
returns successfully. It submits that assessment ID; the API reuses the verified
per-process result and calls only the Communication agent. Drafting does not
repeat Claim Assessor. The check result is transient; after an API restart, rerun
handler checks before drafting.

Foundry agent `communication` version **2** is published with source digest
`ed867c13f62a64e6096bb454c7ab5b84d637614ae15938c41326c8399f7d54fd`, using
`claims-chat`. Direct version-pinned invocations for normal, missing-evidence,
unavailable-image and conflicting-information scenarios completed; each output
passed the strict JSON schema and API customer-wording validator. The Foundry
MCP identity still receives 403 for `agents/read`; the repository publisher and
invocation used local `DefaultAzureCredential` successfully. Do not grant roles
automatically.

The approved application-only rollout is complete: the idempotent SQL
initializer applied one migration and inserted no records; the existing
`claims-demo` environment pins `CLAIM_COMMUNICATION_AGENT_VERSION=2`; and
`azd deploy claims-api --no-prompt` deployed only the claims API/UI revision.
No foundation provisioning or role changes were made. Existing runtime ACR Pull
and Foundry Agent Consumer assignments were confirmed.

Live `/health`, authenticated `/ready`, unauthenticated REST/MCP denial, and
authenticated MCP smoke checks passed. A live handler-check followed by a
Communication v2 draft for synthetic claim `clm-demo-001` persisted claim,
assessment, citation and artifact metadata; the customer-text guard passed.
The draft was left unreviewed and unsent, and no message was transmitted; a
mark-sent attempt before review returned 409 and left the record unchanged. The
UI bundle and its handler-check/draft actions were verified. Application
Insights recorded the successful draft request and Communication traces;
interactive browser sign-in remains unverified.

### Risk Analyst implementation details

Start from current `main`; develop the existing advisory skill rather than a
fourth standalone agent. Its source name is **Risk Analyst**:
`agents/risk-analyst/SKILL.md`, publisher `scripts/agents/risk_analyst.py`, schema
`data/schemas/risk-review.schema.json`. Skill v1 is already published; inspect
the current remote asset before creating another version. Its MCP Toolbox/
connection and consuming-agent integration are not yet verified.

Wire only the bounded claim, assessment and customer-history tools required by
the skill. Avoid repeating image inference merely to obtain deterministic flags:
inspect the existing `assess_synthetic_claim` behavior and decide how to reuse
verified evidence. Review at most the selected customer's bounded history;
distinguish present-claim facts from prior-claim context and cite concrete
claim IDs/fields. No fraud labels, claimant classifications, risk scores,
coverage decisions or communications; every finding requires human review.
Prove skill attachment/execution in its chosen consuming agent, schema-valid
results and limited/missing-history behavior. Coordinate with the Communications
session before changing shared contracts, API tools, model settings or pins.

Architecture clarification for this work: the hosted Policy Checker calls its
version-pinned Foundry Toolbox directly. A separate APIM MCP route exposes a
Toolbox version to Copilot Studio and leaves the existing Claims MCP route
intact. The hosted path remains pinned to Toolbox v1, whose upstream connection
uses the hosted agent's Agentic Identity. The Studio route targets Toolbox v3,
whose upstream Claims MCP connection uses the Foundry project's managed
identity; APIM separately uses its managed identity to call Foundry. There is
no per-user OBO flow, and the Studio-facing route does not change the hosted
agent's direct path.

Read `docs/architecture.md`, `docs/azure-deployment.md`, `docs/open-questions.md`,
schemas, tool contracts, `agents/`, and `scripts/agents/`. Agent sources live
under repository-root `agents/`; `src/apps/claims-api/app/agents.py` is the
older two-specialist adapter.
Risk Analyst Skill v1 is published but has no configured MCP Toolbox/connection.
Communication is deployed and draft-only; human review and sent status remain
metadata actions and never transmit a message.

## Reuse existing Azure resources

| Item | Target |
|---|---|
| Subscription | `987a5b92-2573-4981-a76c-bbd7756592c8` |
| Resource group | `rg-claims-claims-demo-snlo25` |
| Foundry project | `aif-claims-snlo25badmmpc/claims`, Central US |
| Project endpoint | `https://aif-claims-snlo25badmmpc.services.ai.azure.com/api/projects/claims` |
| API/UI | `https://ca-claims-snlo25badmmpc.livelyfield-abf14243.centralus.azurecontainerapps.io` |
| APIM REST | `https://apim-claims-snlo25badmmpc.azure-api.net/claims` |
| APIM MCP | `https://apim-claims-snlo25badmmpc.azure-api.net/claims-tools/mcp/` |
| azd environment | `claims-demo` |

Do not reprovision the foundation, change region or create a new project by
default. Public-demo networking is intentional; retain Entra, managed identities,
disabled keys and private blobs. Keep Claim Assessor through APIM for now.
API Center registration and actual Copilot Studio connector onboarding remain
separate work. The operator has confirmed that the deployed browser UI works.

`.azure/claims-demo/` configuration is Git-ignored and will not automatically
follow into a new worktree. A durable copy of the current `.env` and `config.json`
is retained at `/Users/jeremiahgutherie/Development/pennstatelefty-org/dev-day-demo/.azure/claims-demo/`
in the primary checkout. Copy those existing ignored files into each fresh
worktree without committing them; do not copy transient `.env.lock` files.
Deployment instructions and focused templates are in `docs/azure-deployment.md`.
No secrets belong in Git. Coordinate shared Azure changes and Foundry
default/version updates rather than deploying concurrently.
Leave Claim Assessor v3 and hosted Policy Checker v1 selected until a replacement
has passed acceptance. This checkpoint requires no foundation deployment.

## Deployed and working

- Claim Assessor **v3**: claim-ID-only prompt agent, `claims-chat` deployment.
  Definition SHA: `84677a0667f2eb264b4fcf9c7f6eefeee0058812d27306a9423c8c97f0bc6ae2`.
- API-owned vision: `claims-vision`, `gpt-6-luna` `2026-09-22`,
  GlobalStandard capacity 10, NoAutoUpgrade. Existing chat/embedding preserved.
- Three private evidence images uploaded and byte-verified; five reviewed SQL
  fixture changes applied and idempotent replay verified. Claim 003 has no photo.
  Linkage: claim artifact IDs -> artifact -> repository-relative contentRef,
  also the Blob key in private `evidence`.
- Authenticated image previews and actual API-owned image inference work.
  Preview alone never invokes a model. Failures retain deterministic findings
  and report explicit `unavailable`; no fixture fallback.
- API/UI revision `ca-claims-snlo25badmmpc--0000016`; all four real pinned-v3
  workflows return 200. The operator confirmed UI behavior after this rollout.
- Single-call production vision prompt remains unchanged. Multi-pass, detail
  crops and example labels were experiments only; they did not justify rollout.
  Missed dent/hood/bumper details are disclosed limitations, not blockers.

Final checkpoint checks: 197 Python/validation tests, 15 UI tests and the
TypeScript/Vite production build pass.

Policy Checker Toolbox v1 and hosted agent v1 are active. A bounded remote
invocation returned cited Section 2.3 evidence while preserving human review.
The hosted agent remains pinned to v1 and its direct path is unchanged.

The separate APIM route at
`https://apim-claims-snlo25badmmpc.azure-api.net/policy-checker-tools/mcp`
now targets Toolbox v3. Toolbox v3 uses the Foundry project service principal
(client `8c1a2223-2e82-46ef-9ffb-26fadcb8dcb4`, object
`a2dd5105-5c19-4da4-a34d-e5f7f14d2fcc`) for its downstream Claims MCP
connection. Existing app-role assignments remain in Entra, but the demo API and
APIM now use tenant-only admission; no new role grants or allowlists are needed.

Direct v3 discovery and lookup succeed unchanged on October 18. The Studio APIM
route initially initialized as Azure API Management with an empty tool list.
Binding the API explicitly to its named MCP backend, updating that backend from
Toolbox v1 to v3, and using the `mcp` endpoint mapping fixed routing. Initialize
now reports Foundry Toolbox MCP; discovery exposes only
`claims-policy___lookup_policy`; a real call returns cited Section 2.3 evidence.
Missing-token requests still return 401. This proves the authenticated APIM
protocol path, not onboarding in the actual Copilot Studio connector.
Do not weaken authorization or change the hosted agent's direct v1 connection.
No foundation provisioning is needed.
Evaluation generation stays deferred until policy data is ready for
collaborative Q&A authoring.

API/browser telemetry code is deployed in revision 16. API requests/dependencies
are ingested in the existing Application Insights resource; matching APIM/API
operation IDs prove backend correlation. Browser ingestion and hosted GenAI
export remain unverified. Monitoring child settings are deployed. Earlier
permission-denial traces were useful during diagnosis; those policy gates and
their traces were removed by the tenant-only simplification.
The hosted exporter updates failed in immutable versions 2 and 3; v1 is active.
Build triage found the same reported transitive dependencies in successful v1,
so neither truncated dependency hint establishes the cause. Keep Microsoft
controlled package feeds; do not bypass the managed-device proxy. Full remote
build logs are not exposed by the supported diagnostics tried.

## Resolved Claim Assessor blockers and remaining work

The October 18 UI failure combined an overly restrictive application-role gate
and a handler that assumed function-call output rather than Foundry's actual
OpenAPI output. The operator explicitly approved tenant-only demo admission;
the gate was removed at APIM and the API. Result extraction now unwraps real
tool output and all four workflows pass. No fixture/prose fallback or extra
vision call was added.

Runtime -> Foundry invocation is fixed: use `AIProjectClient(allow_preview=True)`
and `get_openai_client(agent_name="claim-assessor")`, retaining explicit
`agent_reference.version="3"`. The generic developer Responses endpoint returned
403 for the runtime. The consumer endpoint works with project-scoped **Foundry
Agent Consumer**; nonexistent version 999999 returned 404, proving pinning.

Diagnostic Claim Assessor v4 used the equivalent API resource application ID to
test token acquisition. It is not the selected UI version; leave consumers on
verified v3. Hosted Policy Checker v2/v3 failed builds are also not selected.

Remaining integration work: actual Copilot Studio connector onboarding and
supervision; executable Risk Analyst skill integration; browser telemetry
ingestion proof and hosted exporter recovery. Evaluation data generation remains
deferred for collaborative Q&A authoring.

## Deployment recovery notes

ACR build succeeded even when azd reported a premature log-Blob 404. Inspect the
actual ACR run before rebuilding. Proven recovery: `az acr build --no-logs`, then
`azd deploy claims-api --from-package` with the verified image digest; this still
uses application Bicep. Follow the Foundry skill's inline azd user-agent guidance.
Do not redeploy the full foundation to ship application changes.

Live trial JSON and reviewed manifests were kept in the previous Copilot session
folder, not committed. They are diagnostic artifacts, not required runtime inputs.
Source fixtures, images, definitions, repeatable initialization and tests are in Git.
