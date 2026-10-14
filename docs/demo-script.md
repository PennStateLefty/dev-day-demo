# Demo outline

This planned customer-neutral, 25-minute narrative connects three presenters through one synthetic FNOL scenario. The local claims-handler experience, deterministic review workflow, citations, and response draft are implemented. The hosted Foundry lifecycle and Copilot Studio/APIM integration remain future work; no Azure resources have been deployed. The system never autonomously approves, denies, settles, or pays a claim.

## Presenter handoffs

| Segment | Presenter focus | Demonstration and handoff |
|---|---|---|
| Build and deploy (GitHub Copilot) | Agentic development flow that speeds delivery for developers and QA. | Start from a synthetic requirement. Use Copilot to modify the deterministic validator, add contract/evaluation tests, and run CI. The repository includes Docker packaging and modular platform Bicep; application deployment/authentication and live validation remain incomplete. Do not present the foundation as a deployed demo. |
| Manage and evaluate (Azure / Foundry) | Foundry as the control plane for versioned agents, tools, and knowledge. | Show the Claim Assessor, Policy Checker and Communication specialists only after deployment and explicit-version invocation work. Publish a prompt change and evaluate against a fixed synthetic set; prove selecting a tested version before calling it rollback. Ground policy evidence through IQ and govern shared tools through APIM. Risk Analyst remains advisory. Hand off tested endpoints and contracts to Studio. |
| Extend (Copilot Studio) | Studio owns supervision and capability extension. | Build the supervisor that gathers missing information, invokes governed capabilities and presents results for human review. An optional Claims Data Analyst uses bounded SQL tools, not Fabric or arbitrary generated SQL. Prove cross-tenant Entra connectivity; any authentication fallback requires a compatibility result and explicit decision. |

## Shared architecture for the demo

- Copilot Studio supervises three explicit-version Foundry specialists: Claim Assessor, Policy Checker and Communication. The local deterministic orchestrator is not the hosted supervisor.
- Deterministic checks enforce completeness and support contract tests.
- Foundry IQ/Azure AI Search is a shared knowledge source; agents consume it through a stable connection rather than having the knowledge embedded in each prompt.
- A versioned Foundry Toolbox/APIM MCP surface exposes the assessment workflow to Copilot Studio; the exact backend/authentication path must be proven in the target tenant.
- Studio collects information and coordinates specialist calls without reimplementing their assessment, interpretation or drafting logic.
- A newly authored advisory Risk Analyst skill may inspect synthetic consistency/history through bounded tools. Production fraud scoring, risk classification and approve/deny outcomes remain excluded; no upstream code or prompts are imported.

## Evaluation and operational follow-up

Use one controlled synthetic regression, such as a missing citation or retrieval failure. Show evaluation against a pinned, published generation, the failure evidence, a bounded GitHub Copilot repair, and the passing regression evaluation before selecting a known-good version. No production incident or real claim data is used. Version comparison and rollback are demo goals, not verified capabilities of this repository checkpoint.

## Controlled failure scenario

The local baseline evaluation runner is executable with `uv run pytest -q`. No hosted telemetry, live agent evaluation, or deployed service is available.

For a later controlled demo, select one bounded failure (for example, policy retrieval failure, malformed synthetic artifact, MCP timeout, assessment-schema violation, or evaluation-detected prompt regression). Document how to introduce it, what detects it, the issue and repair workflow, and the regression test. Use synthetic inputs only; do not simulate a production incident or autonomously act on a claim.
