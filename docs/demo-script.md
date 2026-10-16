# Demo outline

This planned customer-neutral, 25-minute narrative connects three presenters through one synthetic FNOL scenario. The local claims-handler experience, deterministic review workflow, citations, response draft, Azure foundation, private image evidence and API-owned vision analysis are deployed. Claim Assessor v3 and Risk Analyst Skill v1 are published, but their complete specialist paths are not ready: Foundry still uses a cached pre-grant API token, image semantic checks have misses, and the Risk Analyst Toolbox has no configured MCP project connection. Do not present either specialist as ready until explicit-version invocation, tool access, and synthetic regression pass. The system never autonomously approves, denies, settles, or pays a claim.

## Presenter handoffs

| Segment | Presenter focus | Demonstration and handoff |
|---|---|---|
| Build and deploy (GitHub Copilot) | Agentic development flow that speeds delivery for developers and QA. | Start from a synthetic requirement. Use Copilot to modify the deterministic validator, add contract/evaluation tests, and run CI. The platform and authenticated application API are already deployed; use the source-controlled definitions and focused update path for specialist changes. Do not imply that the specialist lifecycle is complete before its version-pinned invocation and tool tests pass. |
| Manage and evaluate (Azure / Foundry) | Foundry as the control plane for versioned agents, tools, and knowledge. | Show the Claim Assessor, Policy Checker and Communication specialists only after deployment and explicit-version invocation work. Publish a prompt change and evaluate against a fixed synthetic set; prove selecting a tested version before calling it rollback. Ground policy evidence through IQ and govern shared tools through APIM. Risk Analyst remains advisory. Hand off tested endpoints and contracts to Studio. |
| Extend (Copilot Studio) | Studio owns supervision and capability extension. | Build the supervisor that gathers missing information, invokes governed capabilities and presents results for human review. An optional Claims Data Analyst uses bounded SQL tools, not Fabric or arbitrary generated SQL. Prove cross-tenant Entra connectivity; any authentication fallback requires a compatibility result and explicit decision. |

## Shared architecture for the demo

- Copilot Studio supervises three explicit-version Foundry specialists: Claim Assessor, Policy Checker and Communication. The local deterministic orchestrator is not the hosted supervisor.
- The new image-evidence source shows supplied synthetic PNGs for claims 001, 002 and 004; 003 stays without evidence. Preview is not inference. **Run handler checks** is an ordinary API application handler, not Foundry Workflows. Claim Assessor gets a claim ID; its API tool owns private Blob retrieval and the `gpt-6-luna` image call. Show deterministic checks, model observations and agent recommendations separately. No visible damage in the obstructed fourth image is not proof of no damage.
- The vision model, private images and revised agent v3 are deployed, but this is not a completed cloud demo: successful outbound authorization and actual tool-result extraction must pass. Missed damage details are disclosed model limitations, not demo blockers; no fine-tuning or further vision optimization is planned. Local unavailable/fixture results are not live specialist evidence. The observed token expires 2026-10-17 15:02:43 UTC; refresh and successful authorization must be observed before using the handler button as a demo.
- Deterministic checks enforce completeness and support contract tests.
- Foundry IQ/Azure AI Search is a shared knowledge source; agents consume it through a stable connection rather than having the knowledge embedded in each prompt.
- A versioned Foundry Toolbox/APIM MCP surface exposes the assessment workflow to Copilot Studio; the exact backend/authentication path must be proven in the target tenant.
- Studio collects information and coordinates specialist calls without reimplementing their assessment, interpretation or drafting logic.
- The published Risk Analyst Skill is advisory only. It may inspect synthetic consistency/history after its bounded Toolbox is configured and verified. Production fraud scoring, risk classification and approve/deny outcomes remain excluded; no upstream code or prompts are imported.

## Evaluation and operational follow-up

Use one controlled synthetic regression, such as a missing citation or retrieval failure. Show evaluation against a pinned, published generation, the failure evidence, a bounded GitHub Copilot repair, and the passing regression evaluation before selecting a known-good version. No production incident or real claim data is used. Version comparison and rollback are demo goals, not verified capabilities of this repository checkpoint.

## Controlled failure scenario

The local baseline evaluation runner is executable with `uv run pytest -q`. The foundation and claims API are deployed; hosted-agent telemetry, live agent evaluation, and the final Studio integration are not yet established.

For a later controlled demo, select one bounded failure (for example, policy retrieval failure, malformed synthetic artifact, MCP timeout, assessment-schema violation, or evaluation-detected prompt regression). Document how to introduce it, what detects it, the issue and repair workflow, and the regression test. Use synthetic inputs only; do not simulate a production incident or autonomously act on a claim.
