# Demo outline

This customer-neutral, 25-minute narrative connects three presenters through one synthetic FNOL scenario. The claims-handler experience, deterministic review workflow, citations, draft-only Communication path, Azure foundation, private image evidence and API-owned vision analysis are deployed. Claim Assessor v3 and Policy Checker v1 have passed their pinned invocation paths; the Studio-facing APIM route to Toolbox v3 passes authenticated MCP initialize/list/call. Communication v2 has passed live check-then-draft persistence. Risk Analyst Skill v1 has no configured MCP Toolbox, and actual Copilot Studio connector onboarding/supervision remains unverified. The system never autonomously approves, denies, settles, pays, or sends a claim communication.

## Presenter handoffs

| Segment | Presenter focus | Demonstration and handoff |
|---|---|---|
| Build and deploy (GitHub Copilot) | Agentic development flow that speeds delivery for developers and QA. | Start from a synthetic requirement. Use Copilot to modify the deterministic validator, add contract/evaluation tests, and run CI. The platform and authenticated application API are already deployed; use the source-controlled definitions and focused update path for specialist changes. Do not imply that the specialist lifecycle is complete before its version-pinned invocation and tool tests pass. |
| Manage and evaluate (Azure / Foundry) | Foundry as the control plane for versioned agents, tools, and knowledge. | Show the Claim Assessor, Policy Checker and Communication specialists only after deployment and explicit-version invocation work. Publish a prompt change and evaluate against a fixed synthetic set; prove selecting a tested version before calling it rollback. Ground policy evidence through IQ and govern shared tools through APIM. Risk Analyst remains advisory. Hand off tested endpoints and contracts to Studio. |
| Extend (Copilot Studio) | Studio owns supervision and capability extension. | Build the supervisor that gathers missing information, invokes governed capabilities and presents results for human review. An optional Claims Data Analyst uses bounded SQL tools, not Fabric or arbitrary generated SQL. Prove cross-tenant Entra connectivity; any authentication fallback requires a compatibility result and explicit decision. |

## Build and deploy script (GitHub Copilot)

### Product Owner - drafts user story from business requirement

Using **New Chat** in the GitHub Copilot App in **Plan** mode, with `PennStateLefty/dev-day-demo` as context:

1. Draft the first user story. Prompt:

   > Draft a user story with acceptance criteria for Requirement 1: Enhance claims review with claim cards and image viewer. Claim fixture cards replace the raw claim selector with a drop-down list that includes the claim ID, loss date and review status. An evidence image viewer shows evidence images as thumbnails and lets the handler click on an image to zoom in.
   >
2. Create the first GitHub issue. Prompt:
   >
   > Create the GitHub issue from the user story you just drafted, with a clear title, user-focused description, and acceptance criteria, in: https://github.com/PennStateLefty/dev-day-demo

3. Draft the second user story. Prompt:

   > Draft a user story with acceptance criteria for Requirement 2: Automated exclusion screening. The system automatically screens each claim statement against the policy exclusions in Section 3. It surfaces a possible exclusion with the quoted policy wording and routes the claim to a human adjuster.
   >
   > Do not use any emojis.

4. Create the second GitHub issue. Prompt:

   > Create the GitHub issue from the user story you just drafted, with a clear title, user-focused description, and acceptance criteria, in: https://github.com/PennStateLefty/dev-day-demo

### Developer: implement the user story

1. Select the new issue in the Copilot App and ask the developer agent to plan the implementation using Plan mode:

   > Plan how to implement this issue.

2. Review the plan. If unit tests are not explicitly included, prompt to include them.
3. Prompt to start implementation, then downgrade to **Auto -> Efficiency**:

   > Implement this feature completely.

4. Run the application for verification.
5. Create a PR to the `main` branch summarizing the changes made, and include verification screenshots as part of the acceptance criteria.
6. Add `@copilot` as a Reviewer.

### Handoff

This concludes the requirement, plan, implementation, test and code review flow. Transition to the Foundry hosted agent demo.

## Shared architecture for the demo

- Copilot Studio supervises three explicit-version Foundry specialists: Claim Assessor, Policy Checker and Communication. The local deterministic orchestrator is not the hosted supervisor.
- The new image-evidence source shows supplied synthetic PNGs for claims 001, 002 and 004; 003 stays without evidence. Preview is not inference. **Run handler checks** is an ordinary API application handler, not Foundry Workflows. Claim Assessor gets a claim ID; its API tool owns private Blob retrieval and the `gpt-6-luna` image call. Show deterministic checks, model observations and agent recommendations separately. No visible damage in the obstructed fourth image is not proof of no damage.
- The claims dropdown shows each claim ID, loss date and session-local handler-check progress. “Checks complete” still requires human review and is not an approval or a completed human review. Browse evidence with the thumbnail strip, then open a photo to zoom and close the viewer to return to that photo. Image browsing does not run handler checks or model inference.
- The vision model, private images and revised Claim Assessor v3 are deployed; live handler checks use verified tool output. Missed damage details are disclosed model limitations, not demo blockers; no fine-tuning or further vision optimization is planned. Local unavailable/fixture results are not live specialist evidence.
- Deterministic checks enforce completeness and support contract tests.
- Foundry IQ/Azure AI Search is a shared knowledge source; agents consume it through a stable connection rather than having the knowledge embedded in each prompt.
- The hosted Policy Checker consumes Toolbox v1 directly. The separate APIM MCP route for Copilot Studio targets Toolbox v3; APIM authenticates to Foundry with its managed identity, and Toolbox v3 calls Claims MCP through APIM with the Foundry project's managed identity. Actual connector onboarding remains to be verified.
- Studio collects information and coordinates specialist calls without reimplementing their assessment, interpretation or drafting logic.
- The published Risk Analyst Skill is advisory only. It may inspect synthetic consistency/history after its bounded Toolbox is configured and verified. Production fraud scoring, risk classification and approve/deny outcomes remain excluded; no upstream code or prompts are imported.

## Evaluation and operational follow-up

Use one controlled synthetic regression, such as a missing citation or retrieval failure. Show evaluation against a pinned, published generation, the failure evidence, a bounded GitHub Copilot repair, and the passing regression evaluation before selecting a known-good version. No production incident or real claim data is used. Version comparison and rollback are demo goals, not verified capabilities of this repository checkpoint.

## Controlled failure scenario

The local baseline evaluation runner is executable with `uv run pytest -q`. The foundation and claims API are deployed; hosted-agent telemetry, live agent evaluation, and the final Studio integration are not yet established.

For a later controlled demo, select one bounded failure (for example, policy retrieval failure, malformed synthetic artifact, MCP timeout, assessment-schema violation, or evaluation-detected prompt regression). Document how to introduce it, what detects it, the issue and repair workflow, and the regression test. Use synthetic inputs only; do not simulate a production incident or autonomously act on a claim.
