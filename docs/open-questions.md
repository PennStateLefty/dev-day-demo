# Baseline decisions and validation gates

This register closes the Phase 1 baseline questions where a reusable default can be selected. It also keeps environment-, rights-holder-, and implementation-dependent checks visible. The register does not authorize importing external assets or deploying Azure resources.

## Implementation checkpoint

The local deterministic baseline is now implemented: shared REST/MCP service, React handler UI, adapted synthetic policy and independently authored claim/evaluation fixtures, Docker packaging, and CI for Python, frontend, container-build, and Bicep checks. `azure.yaml` points to the Bicep template, which currently creates only a Container Apps managed environment with Azure Monitor logging. No cloud resources are deployed, and the app has no authentication; the container is for local synthetic demonstrations only.

The Foundry hooks are configuration-gated and have not been exercised against a live project. Hosted Foundry agents, Foundry IQ/Search, Toolbox/APIM, Copilot Studio, production authentication, and a complete hosted deployment remain unimplemented and must pass the validation gates below before being presented as working integrations.

## Decisions for the baseline

| Area | Baseline decision |
|---|---|
| Demo data | Create new, fully synthetic policies, claims, and evidence for fixtures. Do not select or import an upstream fixture until its exact-file rights and synthetic status are reviewed. |
| External repositories without a license | Record the owner's MIT assumption for the two identified repositories as a planning assumption only. No assets from either repository are included; obtain rights-holder confirmation before copying, adapting, or redistributing their material. |
| Repository license | Do not add a root license in this checkpoint. The repository grants no general reuse permission until its owner selects and adds license terms. This does not block internal presenter review. |
| Foundry agents | Keep a code-based hosted orchestrator and separate prompt-based policy and response specialists. The orchestrator will invoke each specialist through the Foundry Agent Framework integration, pinning an explicit prompt-agent name and version rather than resolving `latest` at runtime. |
| Agent changes and rollback | Save meaningful prompt changes as immutable versions, evaluate against the same fixed synthetic dataset, and select a previously tested version for the demo rollback. Do not claim a rollback capability until it is exercised in the target Foundry project. |
| Grounding | Keep policy knowledge outside agent prompts. Use a shared Foundry IQ/Azure AI Search knowledge source and preserve source references in assessment outputs. |
| MCP boundary | Keep the assessment service as the source of business behavior. The intended public tool surface is a versioned Foundry Toolbox MCP endpoint governed through APIM. APIM can expose an existing MCP backend or expose APIs as MCP; prove the selected Toolbox-to-APIM path before relying on it. If that path is incompatible, use a thin MCP facade over the same application service rather than duplicating claims logic. |
| Authentication | Prefer Entra authentication where the participating tenants and connector support it. For the cross-tenant demo fallback, use an APIM subscription key scoped to the Copilot Studio consumer, stored in a protected connection/configuration, and revocable/rotatable. Never commit the key or place it in prompts, logs, or demo material. |
| Copilot Studio scope | Build one intake/handler flow that asks for missing information and invokes the governed assessment and policy-knowledge capabilities. Studio does not implement policy interpretation or assessment logic itself. All assessments and customer-response drafts remain subject to human review. |
| Deployment layout | Use `azd` with a root `azure.yaml`; keep Bicep under `infrastructure/` as required by the repository layout. Add service declarations, parameters, and Bicep module boundaries only after the selected runtime and resource topology are verified. |
| Evaluation | Use a fixed synthetic regression set. Measure contract/schema validity, completeness and relationship checks, citation/source correctness, retrieval abstention on missing evidence, and safety invariants (no autonomous decisions or sending). Compare the same data and configuration except for the version or knowledge-source change under test. |
| Runtime and package versions | Select model deployment, Python/runtime, SDKs, API versions, and service tiers in the implementation spike against the target region, quota, and current supported samples. Pin the tested versions in manifests and deployment configuration; do not guess them in this documentation-only baseline. |

## Validation gates before implementation or presentation claims

1. **Specialist invocation:** In the target Foundry project, create two prompt-agent versions and prove the hosted orchestrator can call each by explicit version through the supported Python Agent Framework integration. Capture a repeatable evaluation and demonstrate selecting a known-good version.
2. **Grounding:** Confirm the chosen Foundry IQ/Azure AI Search configuration exposes the intended synthetic policy source and that the assessment preserves valid source references. Test retrieval failure and citation behavior.
3. **Toolbox, APIM, and Copilot Studio:** Verify the chosen versioned Toolbox endpoint can be exposed or governed as an APIM MCP server and that Copilot Studio's MCP client can connect using the supported Streamable HTTP transport. Exercise inbound authentication in the actual target tenant; verify the scoped API-key fallback only if Entra is unsuitable.
4. **Deployment topology:** Select the deployable services and hosting targets, then validate the `azure.yaml` service paths, Bicep provider path under `infrastructure/`, parameters, identities, and required permissions against current `azd` and service guidance. Do not expose the unauthenticated demo container to a public network.
5. **Evaluation and rollback demo:** Choose concrete quality thresholds and the controlled regression only after the evaluation dataset and target Foundry features are available. Prove the full compare, repair or rollback, and passing-regression sequence without real claims or production telemetry.
6. **Rights and release:** Before external publication or reuse, resolve the root license, the archived Microsoft repository's attribution discrepancy, and file-level rights/synthetic status for every candidate asset. Until then, keep source projects as references and author fixtures independently.

## Current Microsoft guidance reviewed

- [Connect Agent Framework applications to Foundry prompt and hosted agents](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/agent-services/foundry) documents connecting to a named prompt-agent version and a hosted-agent endpoint.
- [Use a toolbox with a hosted agent](https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/use-toolbox-hosted-agent) documents the Toolbox consumer endpoint, version-specific test endpoint, and Entra authentication from a hosted agent.
- [Agent development lifecycle](https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/development-lifecycle) documents immutable agent versions, comparisons, evaluation, publishing, and monitoring.
- [Secure access to MCP servers in API Management](https://learn.microsoft.com/en-us/azure/api-management/secure-mcp-servers) documents inbound subscription-key or Entra token validation and outbound backend authentication for existing or APIM-managed MCP servers.
- [Connect Copilot Studio to an existing MCP server](https://learn.microsoft.com/en-us/microsoft-copilot-studio/mcp-add-existing-server-to-agent) documents the MCP onboarding wizard, authentication choices, and supported Streamable HTTP transport.
- [Azure Developer CLI templates](https://learn.microsoft.com/en-us/azure/developer/azure-developer-cli/azd-templates) documents `azure.yaml`, deployable services, and Bicep/Terraform infrastructure conventions.
