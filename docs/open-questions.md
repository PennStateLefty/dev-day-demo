# Baseline decisions and validation gates

This register closes the Phase 1 baseline questions where a reusable default can be selected. It also keeps environment-, rights-holder-, and implementation-dependent checks visible. The register does not authorize importing external assets or deploying Azure resources.

## Implementation checkpoint

The local deterministic baseline is implemented: shared REST/MCP service, React handler UI, synthetic policy/fixtures, Docker packaging and CI. The Azure foundation and real-image application are deployed. Live runtime SQL read/append/denied-update, cited IQ/Blob retrieval and pinned model requests pass using managed identity. Direct/APIM HTTP and MCP pass after the Developer APIM platform upgrade recovered. Public-demo networking is deployed and the demo NSP is removed. Portal policy-blob reads, Search queries and a Foundry playground prompt succeed with Entra; anonymous data-plane requests remain denied. Fresh provisioning and idempotent replay succeed. See [deployment evidence and remaining gates](azure-deployment.md).

Specialist definitions and the model gateway remain unimplemented. Browser sign-in and complete presenter workflows remain unverified. Service resource definitions alone are not evidence of working integrations.

New Foundry's model playground disables **Save as agent** in the current Central US project with a regional-support message. This does not establish every agent API's availability; confirm the required versioned-agent features and target region before implementing the specialists.

## Decisions for the baseline

| Area | Baseline decision |
|---|---|
| Demo data | Create new, fully synthetic policies, claims, and evidence for fixtures. Do not select or import an upstream fixture until its exact-file rights and synthetic status are reviewed. |
| External repositories without a license | Record the owner's MIT assumption for the two identified repositories as a planning assumption only. No assets from either repository are included; obtain rights-holder confirmation before copying, adapting, or redistributing their material. |
| Repository license | Do not add a root license in this checkpoint. The repository grants no general reuse permission until its owner selects and adds license terms. This does not block internal presenter review. |
| Foundry agents | Three separate explicit-version specialists: Claim Assessor, Policy Checker and Communication. Risk Analyst is an advisory reusable skill. Copilot Studio owns supervision; the local fixture orchestrator is not a proposed hosted supervisor. |
| Agent changes and rollback | Save meaningful prompt changes as immutable versions, evaluate against the same fixed synthetic dataset, and select a previously tested version for the demo rollback. Do not claim a rollback capability until it is exercised in the target Foundry project. |
| Grounding | Keep policy knowledge outside agent prompts. Use a shared Foundry IQ/Azure AI Search knowledge source and preserve source references in assessment outputs. |
| MCP boundary | Keep the assessment service as the source of business behavior. The intended public tool surface is a versioned Foundry Toolbox MCP endpoint governed through APIM. APIM can expose an existing MCP backend or expose APIs as MCP; prove the selected Toolbox-to-APIM path before relying on it. If that path is incompatible, use a thin MCP facade over the same application service rather than duplicating claims logic. |
| Authentication | Public website, authenticated APIs; Entra and managed identity for service calls. Do not assume cross-tenant connector support. Any key fallback needs a verified compatibility issue and an explicit decision; never silently weaken authentication. |
| Copilot Studio scope | Presenter-owned supervisor and optional Claims Data Analyst. Invoke governed specialist and bounded SQL tools; no Fabric dependency, arbitrary SQL generation, autonomous adverse decisions or sending. |
| Deployment layout | `azd` and root `azure.yaml`, subscription-scope Bicep under `infrastructure/`, new Central US demo resource group. New Developer APIM; do not change existing private landing-zone resources. Remote ACR build and real-image application revision deployed. |
| Policy/network boundary | `SecurityControl=Ignore` on the new resource group only; explicit owner/deadline without automatic expiry. Operator-approved `public-demo` networking for portal presentations, retaining Entra/managed identity, disabled keys and scoped data roles. `enforced-perimeter` remains the template default; no jumpbox or Private Link is introduced. |
| Database | SQL Basic synthetic relational backing store with Entra-only authentication. Contained-user migrations and least-privilege grants are required separately from ARM RBAC. |
| Evaluation | Use a fixed synthetic regression set. Measure contract/schema validity, completeness and relationship checks, citation/source correctness, retrieval abstention on missing evidence, and safety invariants (no autonomous decisions or sending). Compare the same data and configuration except for the version or knowledge-source change under test. |
| Runtime and package versions | The foundation pins `gpt-4.1-mini` `2025-04-14` and `text-embedding-3-small` `1`, each GlobalStandard capacity 10; both are provisioned. Search uses stable `2025-05-01` and the explicitly approved single-unit Basic fallback after serverless provider failure. |

## Validation gates before implementation or presentation claims

1. **Specialist invocation:** In the target project, create three explicit-version specialists and prove invocation by the intended client. Exercise synthetic photo analysis, a repeatable evaluation and selection of a known-good version.
2. **Grounding:** Confirm the chosen Foundry IQ/Azure AI Search configuration exposes the intended synthetic policy source and that the assessment preserves valid source references. Test retrieval failure and citation behavior.
3. **Toolbox, APIM, and Copilot Studio:** Verify the chosen versioned Toolbox endpoint can be governed as an APIM MCP server and Studio can connect using supported transport/authentication. Exercise actual inbound Entra validation and observe model traffic through the Foundry APIM connection. An alternative authentication mechanism requires a separate decision.
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
