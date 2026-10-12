# Architecture outline

This is a proposed architecture only; no application or cloud resource has been implemented.

The first vertical slice should keep core claims logic independent of the UI. Application, agent, MCP, package, and test code will live under `src/`; documentation, contracts/data, and Bicep infrastructure remain at the repository root. A future claims-handler UI will call a REST adapter, while an MCP adapter will expose the same application service. The shared service will validate canonical contracts, load synthetic claims/policy/artifacts through interfaces, perform deterministic checks, retrieve policy passages through a replaceable retrieval interface, and return a structured assessment with citations and mandatory human review.

The first-slice direction is Python/FastAPI with a trimmed multi-agent workflow:

- A Foundry hosted orchestrator coordinates assessment and response drafting using the Python Agent Framework integration.
- A version-pinned prompt-based policy specialist uses shared Foundry IQ/Azure AI Search grounding and returns source-linked evidence.
- A version-pinned prompt-based response specialist drafts a customer response from the structured assessment; it cannot decide or send.
- Deterministic validators handle completeness and relationship rules, and deterministic fixtures support contract tests without replacing the hosted-agent demo path.

The application service presents stable assessment and policy-knowledge capabilities. A versioned Foundry Toolbox packages those tools. API Management governs the MCP surface consumed by Copilot Studio. Prefer exposing the Toolbox MCP endpoint as the APIM backend when the target project supports the required protocol and authentication; otherwise, expose a thin MCP facade over the same application service. Copilot Studio adds conversational intake and downstream workflow rather than duplicating Foundry assessment or response logic.

Azure deployment packaging is planned with Azure Developer CLI (`azd`) and a root-level `azure.yaml`; Bicep under `infrastructure/` is the IaC driver. Service declarations, hosting targets, and module boundaries are intentionally deferred until the resource topology is verified. Use developer identity locally and managed identity for Azure service-to-service calls. Prefer Entra authentication for API Management consumers where supported. A potentially cross-tenant Copilot Studio consumer can use a scoped APIM subscription key as a fallback, subject to a target-tenant connection test. Keep keys outside source control and validate the target environment's supported authentication options.

Current Microsoft guidance supports connecting the hosted application to named prompt-agent versions through the Agent Framework Foundry integration, connecting hosted agents to versioned Foundry Toolboxes, and publishing MCP servers through APIM. The specific Foundry Toolbox-to-APIM-to-Copilot Studio path, cross-tenant authentication, model/deployment selection, runtime/package versions, and Bicep module boundaries still require target-environment validation before implementation or demo claims. See `docs/open-questions.md` for the decision register and gates. Any selected external asset requires prior provenance and license review.
