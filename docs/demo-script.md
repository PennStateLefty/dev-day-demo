# Demo outline

This planned customer-neutral, 25-minute narrative connects three presenters through one synthetic FNOL scenario. GitHub Copilot changes and deploys the application/agent assets; Azure demonstrates Foundry's governed asset lifecycle; Copilot Studio consumes the capabilities through an APIM MCP endpoint. The system never autonomously approves, denies, settles, or pays a claim.

## Presenter handoffs

| Segment | Presenter focus | Demonstration and handoff |
|---|---|---|
| Build and deploy (GitHub Copilot) | Agentic development flow that speeds delivery for developers and QA. | Start from a synthetic requirement. Use Copilot to modify the hosted orchestrator or deterministic validator, update a prompt-specialist configuration, add contract/evaluation tests, and deploy through Azure Developer CLI with Bicep. Hand off the deployed project and versioned assets to Azure. |
| Manage and evaluate (Azure / Foundry) | Foundry as the control plane for versioned agents, tools, and knowledge. | Show the hosted orchestrator and its explicitly versioned prompt specialists, publish a prompt change, run evaluations against a fixed synthetic set, and compare results. Select a previously tested version as the rollback only after proving the version-selection path in the target project. Add a synthetic policy/knowledge source to Foundry IQ and rerun evaluation without rewiring agent prompts. Package stable tools—including an assessment operation and an IQ-backed policy-knowledge query—in a versioned Foundry Toolbox and govern its MCP endpoint through API Management. Hand off the governed endpoint to Copilot Studio. |
| Extend (Copilot Studio) | Copilot Studio as a workflow and capability-extension platform, not a duplicate Foundry agent. | Build a conversational intake/handler flow that gathers missing claim information and invokes the governed MCP capabilities through APIM. Demonstrate both the IQ-backed knowledge query and assessment operation; present the assessment and response draft for human review. Prefer Entra authentication where supported; demonstrate the scoped APIM subscription-key path for a cross-tenant connection only after validating it in the target tenant, without exposing the key. |

## Shared architecture for the demo

- A Foundry hosted orchestrator coordinates explicitly versioned prompt-based policy and response specialists through the Agent Framework Foundry integration.
- Deterministic checks enforce completeness and support contract tests.
- Foundry IQ/Azure AI Search is a shared knowledge source; agents consume it through a stable connection rather than having the knowledge embedded in each prompt.
- A versioned Foundry Toolbox/APIM MCP surface exposes the assessment workflow to Copilot Studio; the exact backend/authentication path must be proven in the target tenant.
- The Copilot Studio flow collects information and presents results; it does not reimplement claim assessment, policy interpretation, or response drafting.
- The source repository's risk analyst, claimant-history analysis, fraud scoring, and approve/deny outcomes are excluded.

## Evaluation and operational follow-up

Use one controlled synthetic regression, such as a missing citation or retrieval failure. Show evaluation against a pinned, published generation, the failure evidence, a bounded GitHub Copilot repair, and the passing regression evaluation before selecting a known-good version. No production incident or real claim data is used. Version comparison and rollback are demo goals, not verified capabilities of this repository checkpoint.

## Controlled failure scenario

No operational scenario is executable at the current checkpoint: there is no application, telemetry, evaluation runner, or deployed service.

For a later controlled demo, select one bounded failure (for example, policy retrieval failure, malformed synthetic artifact, MCP timeout, assessment-schema violation, or evaluation-detected prompt regression). Document how to introduce it, what detects it, the issue and repair workflow, and the regression test. Use synthetic inputs only; do not simulate a production incident or autonomously act on a claim.
