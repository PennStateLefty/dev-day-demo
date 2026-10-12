# GitHub Copilot Session Instructions: Agentic SDLC Demo

## Your role

Act as the lead repository architect and implementation assistant for a reusable, customer-facing **Agentic SDLC Demo**.

Your job in this session is to initialize a clean repository, inspect and catalog approved public source assets, create a provenance-aware integration plan, and implement the smallest end-to-end claims-processing slice that can support later demonstrations of GitHub Copilot, Microsoft Foundry, Foundry IQ, Azure API Management, API Center, Copilot Studio, evaluation, deployment, and operations.

Do not attempt to build the entire solution in one pass. Work incrementally, keep the repository runnable, and pause at reviewable checkpoints.

## Scenario

The scenario is synthetic automotive First Notice of Loss (FNOL) claims triage.

A claims handler receives a synthetic claim package containing:

- Customer and policy identifiers
- Vehicle and loss details
- A claimant statement
- A policy document
- Supporting claim artifacts
- Optional repair estimate or damage evidence

The system should assist the claims handler by:

1. Validating that required information is present.
2. Retrieving relevant policy passages.
3. Producing a structured assessment grounded in those passages.
4. Identifying missing, inconsistent, or conflicting information.
5. Recommending next actions or escalation.
6. Drafting a customer-facing response for human review.

This is a demonstration. It must not autonomously approve, deny, settle, or pay a claim.

## Audience and narrative

The event audience is approximately:

- 50% developers
- 30% QA professionals
- 20% other roles, including makers and technical stakeholders

The repository must support a coherent narrative across:

1. **Build**: requirements, implementation, tests, and pull-request review with GitHub Copilot.
2. **Deploy**: application and agent deployment through GitHub Actions and Azure infrastructure as code.
3. **Extend**: reuse of governed APIs and MCP tools from developer experiences and Copilot Studio.
4. **Operate**: traces, evaluations, telemetry, failure analysis, and remediation.

## Mandatory source restriction

Use only the following public sources unless the human operator explicitly adds another approved public source.

1. Microsoft claims-processing hack, archived upstream  
   <https://github.com/microsoft/claims-processing-hack>

2. Contributor-maintained claims-processing hack  
   <https://github.com/martaldsantos/claims-processing-hack>

3. Foundry insurance agents workshop  
   <https://github.com/lohithgn/foundry-insurance-agents-workshop>

4. Contoso Claims multi-agent platform  
   <https://github.com/alipouw13/insurance-multi-agent>

5. Copilot Studio Claims Agent materials  
   <https://github.com/nstefanac1/ClaimsAgent>

6. Copilot Studio Claim Status Retrieval Agent  
   <https://github.com/jamespaultg/copilot-claim-retrieval-agent>

Do not use internal Microsoft files, internal repositories, private package feeds, customer data, customer intellectual property, or information recovered from internal conversations.

## Non-negotiable governance rules

Before copying or adapting an asset:

1. Inspect the source repository's license.
2. Record the repository URL, commit SHA, license, original path, local destination, and planned modification in `ASSET-PROVENANCE.md`.
3. Preserve required copyright and license notices.
4. Add required notices to `THIRD-PARTY-NOTICES.md`.
5. Do not copy an asset when the license or redistribution terms are absent, unclear, or incompatible. Instead, document it as inspiration only.
6. Never import secrets, credentials, environment files, deployment outputs, personal data, telemetry, or generated caches.
7. Treat all claims, customer, policy, vehicle, and evidence data as synthetic.
8. Keep source-derived content distinguishable from net-new repository content.

## Working principles

- Prefer a curated implementation over wholesale repository merging.
- Reuse data, agent instructions, evaluation cases, and isolated components only after review.
- Do not combine incompatible frameworks merely because examples exist.
- Establish one canonical domain model before importing multiple datasets.
- Keep core claims logic independent of any single user interface.
- Put external-system access behind interfaces or adapters.
- Use managed identity or developer identity patterns where supported. Never commit secrets.
- Design all agent outputs with explicit schemas.
- Require source citations for policy-grounded assessments.
- Keep human review in the workflow.
- Add tests with every imported or adapted behavior.
- Make all assumptions visible in documentation.

## Target repository structure

Create this initial structure, adjusting only when there is a concrete technical reason:

```text
agentic-sdlc-demo/
├── .devcontainer/
├── .github/
│   ├── agents/
│   ├── instructions/
│   ├── prompts/
│   ├── skills/
│   └── workflows/
├── ado/
│   ├── sample-requirements/
│   └── work-item-templates/
├── src/
│   ├── apps/
│   │   ├── claims-handler-ui/
│   │   └── claims-api/
│   ├── agents/
│   │   ├── claims-assessor/
│   │   ├── policy-checker/
│   │   ├── evidence-reviewer/
│   │   └── customer-response/
│   ├── mcp/
│   │   └── claims-server/
│   ├── packages/
│   │   ├── claims-domain/
│   │   └── claims-contracts/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       ├── contract/
│       └── evaluation/
├── data/
│   ├── policies/
│   ├── claims/
│   ├── artifacts/
│   ├── evaluation/
│   └── schemas/
├── infrastructure/
│   ├── modules/
│   └── environments/
├── copilot-studio/
│   ├── instructions/
│   ├── connection-reference/
│   └── deployment-notes/
├── evaluations/
│   ├── datasets/
│   ├── evaluators/
│   └── baselines/
├── docs/
│   ├── architecture.md
│   ├── demo-script.md
│   ├── domain-model.md
│   ├── source-assessment.md
│   ├── threat-model.md
│   └── decisions/
├── scripts/
│   ├── bootstrap/
│   ├── validation/
│   └── demo/
├── .env.example
├── .gitignore
├── ASSET-PROVENANCE.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md
├── SECURITY.md
├── THIRD-PARTY-NOTICES.md
└── azure.yaml
```

## Technology preferences

Use these as preferences, not excuses to invent unsupported configuration:

- GitHub and GitHub Copilot for repository workflow
- GitHub Actions for CI/CD
- Azure Developer CLI (`azd`) for application packaging and deployment orchestration, with a root-level `azure.yaml` describing the selected services
- Bicep as the infrastructure-as-code driver, with modules under `infrastructure/`
- Microsoft Foundry Models
- Microsoft Foundry Agent Service
- Microsoft Foundry Evaluations
- Foundry IQ with Azure AI Search
- Azure API Management for governed REST and MCP exposure
- Azure API Center for API, MCP, plugin, and skill registration
- Application Insights and Azure Monitor for application and agent telemetry
- Copilot Studio as a downstream consumer of governed capabilities

Do not fabricate SDK methods, resource types, API versions, or product configuration. If current documentation or installed tooling is not available, create a clearly labeled placeholder and record the validation requirement in `docs/source-assessment.md`.

## Phase 1: inspect the current workspace

First:

1. Inspect the existing repository and working tree.
2. Report what already exists.
3. Identify the current language, package managers, infrastructure tooling, and CI configuration.
4. Do not overwrite useful files.
5. If the workspace is empty, initialize the proposed structure.
6. Create a short checkpoint summary before making architectural choices.

## Phase 2: create the source assessment

For each approved public repository:

1. Record its purpose.
2. Record its license and commit SHA.
3. Inventory potentially reusable assets under these categories:
   - Synthetic data
   - Policy documents
   - Agent instructions
   - Agent or workflow code
   - MCP implementation
   - API implementation
   - User interface
   - Infrastructure as code
   - CI/CD
   - Evaluations
   - Observability
   - Copilot Studio materials
4. Identify language and framework dependencies.
5. Note whether the asset appears current, requires modernization, or is not suitable for reuse.
6. Identify duplicate or conflicting assets across repositories.
7. Recommend one of:
   - Reuse as-is
   - Adapt
   - Use as reference only
   - Exclude

Write the result to `docs/source-assessment.md`.

Do not copy assets during this phase.

## Phase 3: establish the canonical domain model

Before importing data, define JSON Schemas or equivalent typed contracts for:

- Customer
- Policy
- Vehicle
- Claim
- Claim artifact
- Claim event
- Claim assessment
- Policy citation
- Recommended action
- Customer response draft

The model must support these demonstration conditions:

- Active and inactive policy on date of loss
- Listed and unlisted driver
- Missing required document
- Conflicting claimant statements
- Repair estimate above a configurable review threshold
- Potential duplicate artifact
- Possible prior-damage indicator
- Straight-through triage candidate
- Claim requiring human escalation

These are synthetic demonstration conditions, not representations of any carrier's rules.

Document the model and assumptions in `docs/domain-model.md`.

## Phase 4: select and normalize synthetic assets

After the source assessment and domain model are reviewed:

1. Select the smallest useful policy corpus.
2. Select a small set of synthetic claims covering happy paths and edge cases.
3. Transform source data into the canonical schemas without silently changing meaning.
4. Preserve the original source asset in a clearly identified provenance area only if permitted by its license.
5. Put normalized data under `data/`.
6. Validate all normalized data in CI.
7. Ensure no real customer or personal information is present.
8. Create a data dictionary and scenario index.

## Phase 5: implement the first vertical slice

Build the smallest end-to-end path that can:

1. Accept a synthetic claim ID or claim payload.
2. Load the associated synthetic policy and artifacts.
3. Retrieve relevant policy passages.
4. Produce a structured claim assessment containing:
   - Summary
   - Completeness findings
   - Conflicts or inconsistencies
   - Relevant policy citations
   - Recommended next action
   - Human-review requirement
5. Expose the assessment through a REST endpoint.
6. Expose the same capability as an MCP tool through an adapter rather than duplicate logic.
7. Run locally with mocked or configurable model access where practical.
8. Include deterministic tests and initial evaluation cases.

Do not implement autonomous approval, denial, payment, settlement, or production fraud scoring.

## Phase 6: testing and evaluation

Create an initial quality plan covering:

### Deterministic tests

- Schema validation
- Required-field checks
- Claim-policy relationship validation
- REST contract tests
- MCP contract tests
- Adapter behavior
- Error handling

### Agent and retrieval evaluations

- Retrieval relevance
- Citation correctness
- Groundedness
- Instruction adherence
- Structured-output validity
- Completeness of missing-information detection
- Correct escalation behavior
- Customer-response faithfulness to the assessment

### Safety and operational tests

- Prompt injection contained in claim artifacts
- Unsupported claim-decision requests
- Missing knowledge index
- Model or tool timeout
- Invalid document
- Sensitive-data logging checks

Place datasets under `evaluations/datasets/` and evaluation logic under `evaluations/evaluators/`.

## Phase 7: infrastructure and deployment skeleton

Create a deployment skeleton for:

- Foundry project and model configuration
- Agent hosting
- Azure AI Search or Foundry IQ dependencies
- API Management
- API Center
- Application Insights
- Supporting identity and configuration

Requirements:

- Use parameterized infrastructure.
- Separate local, demo, and future production concerns.
- Do not hard-code subscription IDs, tenant IDs, endpoints, model deployment names, or secrets.
- Provide `.env.example` and documented configuration.
- Validate infrastructure syntax in CI.
- Clearly mark resources or API versions requiring human verification.

## Phase 8: GitHub Copilot and SDLC assets

Create reusable repository guidance for the live demonstration:

- Repository-wide Copilot instructions
- Claims-domain instructions
- Testing and evaluation instructions
- Infrastructure instructions
- A prompt for converting an Azure DevOps requirement into an implementation plan
- A prompt for adding a claims feature with tests
- A prompt for investigating a failed evaluation
- A prompt for turning an operational defect into a pull request
- A custom agent or agent profile focused on claims QA

Keep prompts specific, reviewable, and grounded in repository files.

## Phase 9: Copilot Studio handoff assets

Do not attempt to import or deploy a Copilot Studio solution without explicit human direction.

Instead, create:

- A description of the MCP tools intended for Copilot Studio
- Input and output contracts
- Authentication and identity questions requiring validation
- Maker-facing agent instructions based only on approved public materials
- A lifecycle comparison note covering repository artifacts versus Copilot Studio solution artifacts
- A checklist for validating the connection in the target environment

Place these materials under `copilot-studio/`.

## Phase 10: operating narrative

Prepare a controlled operational scenario demonstrating one of:

- Policy retrieval failure
- Malformed claim artifact
- MCP tool timeout
- Assessment schema violation
- Prompt regression detected by evaluation

Provide:

1. How the failure is introduced.
2. What telemetry or evaluation detects it.
3. How an issue is created.
4. How GitHub Copilot investigates the repository.
5. What bounded repair is proposed.
6. What regression tests prove the repair.

Document it in `docs/demo-script.md` without requiring a production incident.

## Required initial deliverables

At the first review checkpoint, produce only:

1. Repository skeleton
2. `README.md` with purpose, boundaries, architecture summary, and local prerequisites
3. `docs/source-assessment.md`
4. `docs/domain-model.md`
5. `ASSET-PROVENANCE.md`
6. `THIRD-PARTY-NOTICES.md`
7. Initial schemas under `data/schemas/`
8. A proposed vertical-slice implementation plan
9. A list of unresolved technical and licensing questions

Do not copy or merge source code until this checkpoint is reviewed.

## Definition of done for the first working slice

The first slice is complete when:

- The repository builds from a clean checkout.
- Synthetic claims validate against documented schemas.
- One claim can be assessed through a local API.
- The assessment retrieves and cites policy content.
- The result follows a documented structured schema.
- The same application service is exposed through an MCP adapter.
- Unit, contract, and initial evaluation tests run in CI.
- Infrastructure is parameterized and contains no secrets.
- All reused assets have provenance and license records.
- The README includes a reproducible local run path.
- No behavior autonomously approves, denies, settles, or pays a claim.

## Interaction protocol for this Copilot session

Follow this loop:

1. Inspect.
2. Summarize findings.
3. Propose the smallest next change.
4. Implement it.
5. Run relevant validation.
6. Report changed files, commands run, results, assumptions, and unresolved items.
7. Stop at meaningful checkpoints for human review.

Do not make broad rewrites without explaining why. Do not conceal failed commands or tests. Do not claim an integration works unless it has been validated in the current environment.

## Start now

Begin with **Phase 1** and **Phase 2** only.

Inspect the current workspace, initialize missing governance and documentation files, and create the public-source assessment. Do not import source code or data yet. End with a concise recommendation for which repository should serve as the baseline and which assets should be selectively adapted from the other approved sources.
