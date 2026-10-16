# Specialist session handoff

Status: 2026-10-16. Start the next session from current `main` after this
specialist/vision slice is merged. This is a working demo foundation, not a
completed end-to-end specialist experience.

## Purpose and next feature

Build a compelling synthetic demonstration for developers, project managers and
QA. Keep MCP and Copilot Studio agent policies simple: essential authentication,
bounded tools and human review, not production policy sophistication. Exact
damage recognition is not a release gate. No fine-tuning or further vision prompt
optimization is planned.

Recommended next feature: a genuinely **hosted Policy Checker** using MCP to
retrieve shared policy evidence and return citations, not an autonomous coverage
decision. Claim Assessor is deliberately a prompt agent. At least one genuinely
hosted specialist remains required. Copilot Studio remains the supervisor; do not
add a Foundry orchestrator or Foundry Workflows.

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
SPA sign-in and API Center registration are separate work.

`.azure/claims-demo/` configuration is Git-ignored and will not automatically
follow into a new worktree. Arrange access to the existing ignored configuration
from the previous worktree without committing it. Deployment instructions and
focused templates are in `docs/azure-deployment.md`. No secrets belong in Git.

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
- API/UI revision `ca-claims-snlo25badmmpc--0000007`, image digest
  `sha256:74b003358b610e2c6f03f5b836d6e74ed6d4dc0407a50a6bac5f584b71f1d95a`.
- Single-call production vision prompt remains unchanged. Multi-pass, detail
  crops and example labels were experiments only; they did not justify rollout.
  Missed dent/hood/bumper details are disclosed limitations, not blockers.

Latest checks: 156 Python tests, 25 validation tests, 12 UI tests, UI build,
Ruff and compiled application authorization invariants passed.

## Remaining Claim Assessor blocker and retest

The outbound caller was confirmed as the **project managed identity**:
client `92b3eda7-884d-4465-8c96-0bead00b7bfb`, principal
`4122278b-ddcc-42c0-925a-16d1f601b161`. It is allowlisted and has the API app role
`Claims.Invoke.Application`; Graph assignment was verified. The agent-instance
identity is not the caller, and no additional grant to it is needed.

Foundry was reusing a token issued before the grant:
issued **2026-10-16 14:57:43 UTC**, expires **2026-10-17 15:02:43 UTC**
(11:02 a.m. Eastern). APIM returns 403 for the absent role. The API handler
returns explicit 503. There is no established customer-controlled forced refresh;
a new Copilot session does not clear it. Expiry is a retest point, not proof of
resolution. Do not weaken authorization, recycle identities or duplicate grants.
Temporary denial diagnostics and trial broader roles were removed.

Runtime -> Foundry invocation is fixed: use `AIProjectClient(allow_preview=True)`
and `get_openai_client(agent_name="claim-assessor")`, retaining explicit
`agent_reference.version="3"`. The generic developer Responses endpoint returned
403 for the runtime. The consumer endpoint works with project-scoped **Foundry
Agent Consumer**; nonexistent version 999999 returned 404, proving pinning.

After a fresh token is observed:

1. Invoke explicit v3 on no-photo claim 003 first via
   `scripts/agents/claim_assessor.py invoke` (see runbook for flags).
2. Capture the **actual** Responses output. `app/handler.py` currently expects
   matching `function_call`/`function_call_output` items; that live shape remains
   unproven. Fix extraction against observed output, not speculative schemas.
3. Preserve the real assessment tool output; do not reconstruct it from final
   prose, substitute fixtures, or rerun vision as a workaround.
4. Exercise all four claims through `/workflow`: verified tool evidence and
   recommendation, correct claim/artifact/citation linkage, human review,
   explicit missing evidence/failure handling. Exact damage recall is not a gate.

The next MCP specialist may hit the same cache if using the same project identity
and audience, but implementation and local testing can proceed independently.

## Deployment recovery notes

ACR build succeeded even when azd reported a premature log-Blob 404. Inspect the
actual ACR run before rebuilding. Proven recovery: `az acr build --no-logs`, then
`azd deploy claims-api --from-package` with the verified image digest; this still
uses application Bicep. Follow the Foundry skill's inline azd user-agent guidance.
Do not redeploy the full foundation to ship application changes.

Live trial JSON and reviewed manifests were kept in the previous Copilot session
folder, not committed. They are diagnostic artifacts, not required runtime inputs.
Source fixtures, images, definitions, repeatable initialization and tests are in Git.
