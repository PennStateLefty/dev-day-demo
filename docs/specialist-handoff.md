# Specialist session handoff

Status: 2026-10-18. Start the next session from current `main` after this
specialist/vision slice is merged. This is a working demo foundation, not a
completed end-to-end specialist experience.

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

## Purpose and next feature

Build a compelling synthetic demonstration for developers, project managers and
QA. Keep MCP and Copilot Studio agent policies simple: essential authentication,
bounded tools and human review, not production policy sophistication. Exact
damage recognition is not a release gate. No fine-tuning or further vision prompt
optimization is planned.

The hosted Policy Checker is implemented and working independently. Next work
should use two fresh sessions: the Communications agent and the Risk Assessor
skill (currently named `risk-analyst` in source). Claim Assessor remains a prompt
agent. Copilot Studio remains the supervisor; do not add a Foundry orchestrator
or Foundry Workflows.

### Fresh session: Communications agent

Start from current `main` and this handoff. Review `data/schemas/` for the response
draft contract, existing communication behavior in `app/agents.py`, and
`docs/architecture.md` before implementing a separate versioned Foundry agent.
The current UI `/workflow` invokes only Claim Assessor; Policy Checker and
Communications are not implicitly part of that path.

The agent should consume verified assessment/recommendation and policy evidence,
draft a clear handler-reviewable communication, and preserve claim/citation/
artifact linkage. It must never send messages, decide coverage, approve/deny a
claim, invent evidence or infer intent. Exercise normal, missing-evidence,
unavailable-image and conflicting-information cases. Keep the current UI working;
make any workflow integration explicit. Reuse the existing project/model and
tenant-only demo authentication. Publish and pin an immutable version, prove
actual invocation/output validation, and retain useful synthetic content traces.

### Fresh session: Risk Assessor skill

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
schemas, tool contracts, `agents/`, and `scripts/agents/`. Original `src/agents/`
folders are placeholders; `app/agents.py` is the older two-specialist adapter.
Risk Analyst Skill v1 is published but has no configured MCP Toolbox/connection.
Communication is still future work and must draft, never send.

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
Deployment instructions and
focused templates are in `docs/azure-deployment.md`. No secrets belong in Git.
Use separate branches/worktrees for the two fresh sessions. Coordinate any
shared Azure changes and deploy/pin updates rather than deploying concurrently.
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
supervision; Communications agent; executable Risk Analyst skill integration;
browser telemetry ingestion proof and hosted exporter recovery. Evaluation data
generation remains deferred for collaborative Q&A authoring.

## Deployment recovery notes

ACR build succeeded even when azd reported a premature log-Blob 404. Inspect the
actual ACR run before rebuilding. Proven recovery: `az acr build --no-logs`, then
`azd deploy claims-api --from-package` with the verified image digest; this still
uses application Bicep. Follow the Foundry skill's inline azd user-agent guidance.
Do not redeploy the full foundation to ship application changes.

Live trial JSON and reviewed manifests were kept in the previous Copilot session
folder, not committed. They are diagnostic artifacts, not required runtime inputs.
Source fixtures, images, definitions, repeatable initialization and tests are in Git.
