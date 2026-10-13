# Architecture outline

## Implemented local vertical slice

The React/TypeScript handler UI calls a FastAPI REST API. REST and FastMCP tools delegate to one `DemoService`, which loads synthetic fixtures, validates them against the repository's JSON Schemas, retrieves relevant policy sections with source citations, and produces deterministic review flags. A local orchestrator uses that assessment to create a draft response. All outputs remain subject to human review.

The API can serve the built UI from the same origin when the frontend `dist/` directory exists, as in the Docker image. During local development, Vite serves the UI separately and the API allows only the local Vite origins. The container image is multi-stage and includes only the API, runtime dependencies, fixtures, and compiled UI.

The deterministic assessment does not make coverage decisions or assign claimant risk. Checks such as policy dates, listed drivers, missing intake data, estimate threshold, and duplicate artifacts are synthetic demo rules.

## Intended hosted architecture

The planned hosted extension keeps core claims behavior independent of the UI:

The first-slice direction is Python/FastAPI with a trimmed multi-agent workflow:

- A Foundry hosted orchestrator coordinates assessment and response drafting using the Python Agent Framework integration.
- A version-pinned prompt-based policy specialist uses shared Foundry IQ/Azure AI Search grounding and returns source-linked evidence.
- A version-pinned prompt-based response specialist drafts a customer response from the structured assessment; it cannot decide or send.
- Deterministic validators handle completeness and relationship rules, and deterministic fixtures support contract tests without replacing the hosted-agent demo path.

The application service presents stable assessment and policy-knowledge capabilities. A versioned Foundry Toolbox packages those tools. API Management governs the MCP surface consumed by Copilot Studio. Prefer exposing the Toolbox MCP endpoint as the APIM backend when the target project supports the required protocol and authentication; otherwise, expose a thin MCP facade over the same application service. Copilot Studio adds conversational intake and downstream workflow rather than duplicating Foundry assessment or response logic.

Azure Developer CLI (`azd`) is configured to use Bicep under `infrastructure/`. The current Bicep template creates only a Container Apps managed environment with Azure Monitor logging; it does not create an app, public ingress, or identity configuration. This deliberately limited template is not a deployable hosted demo yet. Service declarations, hosting targets, and module boundaries remain gated on topology and security validation. Use developer identity locally and managed identity for Azure service-to-service calls. Prefer Entra authentication for API Management consumers where supported. A potentially cross-tenant Copilot Studio consumer can use a scoped APIM subscription key as a fallback, subject to a target-tenant connection test. Keep keys outside source control and validate the target environment's supported authentication options.

Current Microsoft guidance supports connecting the hosted application to named prompt-agent versions through the Agent Framework Foundry integration, connecting hosted agents to versioned Foundry Toolboxes, and publishing MCP servers through APIM. The specific Foundry Toolbox-to-APIM-to-Copilot Studio path, cross-tenant authentication, model/deployment selection, runtime/package versions, and Bicep module boundaries still require target-environment validation before implementation or demo claims. The CI workflow compiles Bicep but does not authenticate or deploy. See `docs/open-questions.md` for the decision register and gates. Any selected external asset requires prior provenance and license review.
