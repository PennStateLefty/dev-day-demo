# Baseline decisions and validation gates

This register closes the Phase 1 baseline questions where a reusable default can be selected. It also keeps environment-, rights-holder-, and implementation-dependent checks visible. The register does not authorize importing external assets or deploying Azure resources.

## Implementation checkpoint

The local deterministic baseline is implemented: shared REST/MCP service, React handler UI, synthetic policy/fixtures, Docker packaging and CI. The Azure foundation and real-image application are deployed. Live runtime SQL read/append/denied-update, cited IQ/Blob retrieval and pinned model requests pass using managed identity. Direct/APIM HTTP and MCP pass after the Developer APIM platform upgrade recovered. Public-demo networking is deployed and the demo NSP is removed. Portal policy-blob reads, Search queries and a Foundry playground prompt succeed with Entra; anonymous data-plane requests remain denied. Fresh provisioning and idempotent replay succeed. See [deployment evidence and remaining gates](azure-deployment.md).

Claim Assessor v3, `claims-vision` (`gpt-6-luna` `2026-09-22`), private image
fixtures and the API/UI update are deployed with authorization. Direct API-owned
image inference and authenticated previews work. The Claim Assessor outbound
identity is the Foundry account managed identity. The operator removed
scope/role/caller/audience admission gates in favor of signed, unexpired tokens
from the configured tenant. All four pinned-v3 workflows now return 200 with
actual assessment-tool output and validated recommendations on revision 16.
The operator confirmed the UI works. Earlier token-role diagnosis is historical,
not a remaining demo dependency.
Two initial damage observations missed expected visible details; these are
documented demo limitations, not release blockers. Policy Checker Toolbox v1
and hosted agent v1 are deployed; a bounded direct invocation returned cited
policy evidence. Its separate APIM route now targets Toolbox v3, whose
downstream Claims MCP connection uses the Foundry project's managed identity
(client `8c1a2223-2e82-46ef-9ffb-26fadcb8dcb4`, principal
`a2dd5105-5c19-4da4-a34d-e5f7f14d2fcc`). The project principal has
an existing `Claims.Invoke.Application` assignment, no longer an admission gate. Direct v3
discovery and lookup pass on October 18. Explicitly binding the Studio API to
the named v3 MCP backend and its `mcp` endpoint mapping fixes the empty tool list.
Authenticated APIM initialize/list/call now return cited Section 2.3 evidence;
missing-token requests receive 401. Actual Copilot Studio connector onboarding
remains unverified. Do not weaken the policy or add duplicate grants.
APIM's managed-identity policy authenticates
APIM to Foundry; it does not pass through the Studio caller's identity.
Communication is deployed and its persisted check-then-draft path is verified.
Executable Risk Analyst skill integration, actual Copilot Studio connector
onboarding/supervision, model gateway and complete presenter workflows remain
unverified. No further unrelated access changes or authentication bypasses are
authorized by this status.

New Foundry's model playground disables **Save as agent** in the current Central US project with a regional-support message. This does not establish every agent API's availability; confirm the required versioned-agent features and target region before implementing the specialists.

## Decisions for the baseline

| Area | Baseline decision |
|---|---|
| Demo data | Create new, fully synthetic policies, claims, and evidence for fixtures. Do not select or import an upstream fixture until its exact-file rights and synthetic status are reviewed. |
| External repositories without a license | Record the owner's MIT assumption for the two identified repositories as a planning assumption only. No assets from either repository are included; obtain rights-holder confirmation before copying, adapting, or redistributing their material. |
| Repository license | Do not add a root license in this checkpoint. The repository grants no general reuse permission until its owner selects and adds license terms. This does not block internal presenter review. |
| Foundry agents | Three separate explicit-version specialists: Claim Assessor, Policy Checker and Communication. Risk Analyst is an advisory reusable skill. Copilot Studio owns supervision; the local fixture orchestrator is not a proposed hosted supervisor. |
| Image analysis ownership | Claims API retrieves registered private Blob evidence and calls selected `gpt-6-luna` directly. Claim Assessor remains a prompt agent consuming the enriched tool response, not images. The hosted Policy Checker is a separate specialist and does not receive images. |
| Handler control flow | Existing FastAPI `/workflow` route is ordinary Python in the Claims API Container App, not Foundry Workflows or a new orchestration service. Preview never calls a model. |
| Evidence limitations | Preserve claim 003 without evidence; new claim 004 demonstrates limited visibility. Processing failures retain deterministic findings with explicit unavailable status; no visible damage is not proof of no damage. |
| Agent changes and rollback | Save meaningful prompt changes as immutable versions, evaluate against the same fixed synthetic dataset, and select a previously tested version for the demo rollback. Do not claim a rollback capability until it is exercised in the target Foundry project. |
| Grounding | Keep policy knowledge outside agent prompts. The hosted Policy Checker uses the versioned Toolbox's read-only `lookup_policy` MCP tool, backed by shared Foundry IQ/Azure AI Search, and preserves source citations. |
| MCP boundary | Keep the assessment service as the source of business behavior. The hosted Policy Checker stays on its directly invoked Toolbox v1; do not route its internal MCP calls through APIM. The separate Studio APIM route targets Toolbox v3 through an explicit named backend; direct v3 and authenticated APIM initialize/list/call pass. The Claims MCP route remains intact. |
| Authentication | Demo-only tenant bearer admission at API/APIM: signature, expiry and tenant issuer/`tid`, accepting v1/v2 tokens without audience/client/scope/role gates. Hosted Toolbox v1 uses Agentic Identity; Studio Toolbox v3 uses project managed identity downstream; APIM uses managed identity for Foundry. No per-user OBO or anonymous/key fallback. |
| Copilot Studio scope | Presenter-owned supervisor and optional Claims Data Analyst. Invoke governed specialist and bounded SQL tools; no Fabric dependency, arbitrary SQL generation, autonomous adverse decisions or sending. |
| Deployment layout | `azd` and root `azure.yaml`, subscription-scope Bicep under `infrastructure/`, new Central US demo resource group. New Developer APIM; do not change existing private landing-zone resources. Remote ACR build and real-image application revision deployed. |
| Policy/network boundary | `SecurityControl=Ignore` on the new resource group only; explicit owner/deadline without automatic expiry. Operator-approved `public-demo` networking for portal presentations, retaining Entra/managed identity, disabled keys and scoped data roles. `enforced-perimeter` remains the template default; no jumpbox or Private Link is introduced. |
| Database | SQL Basic synthetic relational backing store with Entra-only authentication. Contained-user migrations and least-privilege grants are required separately from ARM RBAC. |
| Evaluation | Use a fixed synthetic regression set. Measure contract/schema validity, completeness and relationship checks, citation/source correctness, retrieval abstention on missing evidence, and safety invariants (no autonomous decisions or sending). Compare the same data and configuration except for the version or knowledge-source change under test. |
| Runtime and package versions | The foundation provisions chat deployment `claims-chat` for model `gpt-4.1-mini` `2025-04-14`, plus embedding deployment `claims-embedding` for `text-embedding-3-small` `1`, each GlobalStandard capacity 10. Search uses stable `2025-05-01` and the explicitly approved single-unit Basic fallback after serverless provider failure. |

## Validation gates before implementation or presentation claims

1. **Specialist invocation:** In the target project, prove all three specialists.
   The hosted Policy Checker v1 has returned cited evidence directly, while its
   separate Studio-facing v3 APIM route now passes protocol acceptance. Claim Assessor v3 is pinned
   and the runtime consumer endpoint honors versions. Actual tool-result extraction
   and all four Claim Assessor recommendations pass. Communication's live
   check-then-draft persistence also passes; executable skill integration
   remains an acceptance gate. Do not substitute another
   model or bypass permission checks to make the demo appear successful.
   Exact damage recognition is not a demo gate. Keep policies simple for the
   developer/PM/QA audience: essential authentication and human-review boundaries,
   not production-hardening or fine-tuning work.
2. **Grounding:** Confirm the chosen Foundry IQ/Azure AI Search configuration exposes the intended synthetic policy source and that the assessment preserves valid source references. Test retrieval failure and citation behavior.
3. **Toolbox, APIM, and Copilot Studio:** The hosted agent's direct Toolbox v1 path and the separate authenticated APIM-to-Toolbox-v3 path return cited evidence. Verify the actual Copilot Studio Streamable HTTP connector next; protocol acceptance alone does not prove connector onboarding. Do not route hosted-agent Toolbox traffic through APIM or require model traffic through APIM.
4. **Deployment topology:** ARM validation, exception deadline, remote packaging, SQL/IQ initialization and application bearer middleware are established. Portal asset loading and fresh public-demo reprovisioning pass without losing data or enabling anonymous/key/password access. Full presenter orchestration and SPA sign-in still need proof. Do not expose the unauthenticated local-mode container publicly. No separate cost-approval flag is required; material tier or architecture changes need an explicit decision.
5. **Evaluation and rollback demo:** Choose concrete quality thresholds and the controlled regression only after the evaluation dataset and target Foundry features are available. Prove the full compare, repair or rollback, and passing-regression sequence without real claims or production telemetry.
6. **Rights and release:** Before external publication or reuse, resolve the root license, the archived Microsoft repository's attribution discrepancy, and file-level rights/synthetic status for every candidate asset. Until then, keep source projects as references and author fixtures independently.

## Current Microsoft guidance reviewed

- [Connect Agent Framework applications to Foundry prompt and hosted agents](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/agent-services/foundry) documents connecting to a named prompt-agent version and a hosted-agent endpoint.
- [Use a toolbox with a hosted agent](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/use-toolbox-hosted-agent) documents the Toolbox consumer endpoint, version-specific test endpoint, and Entra authentication from a hosted agent.
- [Agent development lifecycle](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/development-lifecycle) documents immutable agent versions, comparisons, evaluation, publishing, and monitoring.
- [Secure access to MCP servers in API Management](https://learn.microsoft.com/en-us/azure/api-management/secure-mcp-servers) documents inbound subscription-key or Entra token validation and outbound backend authentication for existing or APIM-managed MCP servers.
- [Connect Copilot Studio to an existing MCP server](https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-add-existing-server-to-agent) documents the MCP onboarding wizard, authentication choices, and supported Streamable HTTP transport.
- [Azure Developer CLI templates](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/azd-templates) documents `azure.yaml`, deployable services, and Bicep/Terraform infrastructure conventions.
