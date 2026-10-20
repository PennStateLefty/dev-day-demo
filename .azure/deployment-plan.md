# Claims risk data test deployment

Status: Deployed

Current change (2026-10-20): Publish captured synthetic escalation packets as a
new Foundry IQ knowledge source, and create a separate knowledge base containing
only that source. Reuse existing demo resources; preserve existing policy
knowledge and the working claim-history MCP connection. Published and verified
against the existing service; native Studio connection remains operator-owned.

## Claim-packet IQ plan (2026-10-20)

- Recipe: Azure CLI / existing Azure AI Search data-plane REST, API 2026-04-01.
- Target: approved existing subscription 987a5b92-2573-4981-a76c-bbd7756592c8,
  rg-claims-claims-demo-snlo25, centralus;
  https://srch-claims-snlo25badmmpc-basic.search.windows.net.
- Create index `claim-escalation-packets`, knowledge source
  `claim-escalation-packets-source`, knowledge base `supervisor-claim-packets`.
  The new base must contain exactly that one source. Preserve the existing
  synthetic-policy index/source/base byte-for-byte in relevant definitions.
- Publish the three captured synthetic packets for claims 001, 002 and 004,
  including statements, evidence observations and limitations, actual agent
  recommendations, source caveats and provenance. Keep live history separate.
- Reuse the existing extractive search-index knowledge-source pattern. No new
  compute, model, identity, API service, or authentication configuration.
- Search currently has local/key authentication disabled. Lauren should use
  Microsoft Entra ID Integrated in the native IQ connector; no API key creation
  or enabling local authentication is in scope. No new access grants without
  a separately identified and approved target principal.
- Validate schema, data completeness, source isolation, exact-claim retrieval,
  reference contents and existing policy knowledge unchanged. Verify retrieval
  using existing data-plane identity before handing off.
- Native connector documentation currently describes the GitHub Copilot harness
  and only one IQ connection per agent. Lauren's Studio connection/UI capability
  remains a prerequisite outside this deployment; do not substitute an MCP wrapper.

Operator approved this isolated IQ setup and the existing target on 2026-10-20.
Preparation complete: three live snapshots captured, original photos hash-checked
against vision inputs, Word packets generated, isolated IQ definitions prepared,
create-only initializer and source checks added. Reuse the existing `claims-chat`
model binding for natural-language retrieval; no model deployment or role change.

IQ validation checklist:
- [x] All validation checks pass (IQ data-plane rollout).
  - [x] Core CLI/auth/schema/plan/preflight checks; no ARM resource writes.
  - [x] Packet generation and OOXML validation; Docker not applicable.
  - [x] Azure Policy review: existing service only, no ARM, networking,
    authentication, role assignment, region or SKU changes.
- [x] CLI authentication and existing Search data-plane access.
- [x] Definition inspection and local create-only plan (three new named objects).
- [x] Packet text/provenance, original-image hashes, focused tests and lint.
- [x] Read-only target/schema preflight and existing-policy snapshot.
- [x] Applicable policy and identity review.
- ARM build/validate/what-if and Docker build: not applicable. This rollout only
  writes Search data-plane objects and documents, not ARM resources or containers.

IQ deployment proof (2026-10-20):

- `initialize_claim_packets.py --apply` succeeded; subsequent `--verify` passed:
  exactly three indexed documents, full content/provenance equality, exact
  index/source/base definitions, and only one source in the new base.
- Six successful HTTP 200 retrievals: each of 001, 002, 004 with and without
  a claim-ID filter. References contain only the requested ID; full response
  content matches the source packet (7368, 8000, 7130 characters respectively).
- Missing claim 003 returned no references in filtered and unfiltered requests.
- Retrieval activity used only claim-escalation-packets-source. Existing policy
  definitions equal the pre-deployment snapshot; policy retrieval still succeeds.
- Full retrieval responses retained in session files/iq-retrieval-results.json.
- No new grants, resources, model deployments, or changes to Search local auth.
- Studio connection, GitHub Copilot harness availability, and Lauren's access
  remain unverified. Photos are not indexed binaries or hosted download links.

Current change: Studio subscription-key ingress (2026-10-19). Prior deployment
evidence below remains historical.

## 1. Scope and approval

MODIFY the existing synthetic claims demo. Operator approved this plan and target
on 2026-10-19. Deploy only the new native DAB MCP service and APIM proxy; preserve
the existing claims app, Foundry agents, networking, and authentication settings.

## 2. Target

- Subscription: 987a5b92-2573-4981-a76c-bbd7756592c8
- Resource group: rg-claims-claims-demo-snlo25
- Location: centralus
- Existing environment: cae-snlo25badmmpc
- Existing registry: acrclaimssnlo25badmmpc
- Existing SQL: sql-claims-snlo25badmmpc.database.windows.net / claims
- Existing APIM: apim-claims-snlo25badmmpc
- New app: ca-claims-risk-snlo25badmmpc

## 3. Recipe

recipe.type: bicep

Use the existing incremental resource-group template
`infrastructure/claims-risk-data.bicep`, not a whole-stack azd provision.
Build the pinned nonroot DAB image in existing ACR; no local Docker is required.

## 4. Architecture and security

Dedicated user-assigned identity: ACR pull plus procedure-only SQL permissions.
Fixed stored procedure returns synthetic claim frequency, amounts and last prior
submission. No arbitrary SQL, generic DML, REST or GraphQL. Entra bearer auth at
DAB and existing tenant validation at APIM. Select the existing API audience and
actual issuer from the existing configuration before validation.

## 5. Execution

1. Validate Bicep, tests, live prerequisites and ARM what-if.
2. Build DAB in ACR and pin its resulting digest.
3. Provision only identity and ACR pull permission; verify role propagation.
4. Apply reviewed migration and procedure grants using existing Entra SQL admin.
5. Deploy application and APIM proxy.
6. Exercise SQL acceptance and native MCP direct/APIM calls, including denials.
7. Record endpoints and live evidence in the deployment runbook.

## 6. Validation checklist

- [x] All validation checks pass
  - [x] Bicep compilation and ARM validation/what-if
  - [x] Focused Python tests and DAB versioned configuration validation
  - [x] Required resource providers, existing resources and deployment permissions
  - [x] Object-scoped SQL grants and ACR role reviewed
  - [x] Image build succeeds

## 7. Validation Proof

Claim-packet IQ update, 2026-10-20:

- Create-only local initializer plan: one new index, source and base, 3 documents.
- Search data-plane GET confirms all three names absent (404); existing policy
  definitions captured in session files/iq-policy-before.json with SHA-256
  b63eb1c562f134164193358b217533bbb768ab1970641f5e9f71a57c7887c89a.
- Index schema deserializes with the installed Azure Search SDK.
- Focused packet and existing initialization tests: 15 passed; Ruff passes.
- All three DOCX files pass OOXML schema validation; packet content checks verify
  actual claim IDs, statements, agent output and response IDs, and original image
  hashes both in the source snapshots and embedded DOCX images.
- Search local auth remains disabled, system identity unchanged. Existing
  Cognitive Services OpenAI User role on aif-claims-snlo25badmmpc permits the
  reused claims-chat deployment. No new grants are generated.
- Policy review: data-plane schema/content only; no resource-manager changes.
- No ARM deployment/template, container build, SQL migration, APIM update, or
  Foundry agent deployment applies to this rollout.

Studio ingress update, 2026-10-19:

- azure-validate workflow: core script OVERALL PASS for claims-risk-apim.bicep
  with .azure/risk-apim.parameters.json, resource group and subscription above.
- Resource-level what-if: 3 creates (product, API association, subscription),
  2 modifies (risk MCP API and policy), backend unchanged, 0 resource deletes.
  The helper's larger counts include nested property diffs, not resource deletes.
- Full claims-risk-data.bicep compilation also passes with shared APIM module.
- Ruff passes; focused claim-history/initializer tests: 18 passed.
- Applicable inherited Azure Policy assignments retrieved via Azure MCP;
  ARM validation passes without policy denial. No new region, SKU, identity,
  database, network, or compute resources in the APIM-only rollout.
- Static identity review: APIM existing system identity requests the existing
  custom API token, whose service principal does not require app-role assignment.
  DAB authenticated execution and SQL grants remain unchanged; no new RBAC.
- Predeploy context: operator approved existing subscription, resource group,
  centralus, product/subscription creation and managed-identity exchange.

2026-10-19:

- Shared validate-deployment.sh against claims-risk-data.bicep and the ignored
  risk-data.parameters.json: OVERALL PASS; what-if Create 7, Modify 0, Delete 0.
- Focused pytest: 27 passed. Ruff and pinned v2.1.5 JSON schema: passed.
- Existing environment/registry Succeeded; all four resource providers Registered.
- Operator is existing Entra SQL administrator and has subscription Owner.
- No applicable policy assignments returned for the selected resource-group scope.
- Dedicated identity only gets AcrPull on the registry; SQL grants are EXECUTE
  and VIEW DEFINITION on claims.GetClaimRiskFacts only.
- Existing API token successfully acquired with its /.default scope. Claims match
  configured audience and v2 issuer; no auth changes or consent required.
- ACR remote image build cjj: Succeeded for claims-risk-data:20261019-1.
- Application runtime and SQL acceptance are postdeployment checks; no live
  database mutation has yet occurred.

## 8. Deployment evidence

Studio ingress update, 2026-10-19:

- Incremental deployment claims-risk-studio-key-20261019: Succeeded.
- Product copilot-studio-risk-tools is published, requires subscriptions, and
  contains only claims-risk-tools (verified with 2025-09-01-preview; older API
  lists omit native MCP entries).
- Standalone subscription copilot-studio-risk-tools is active, scoped to that
  product, tracing disabled; APIM-generated keys retained only in APIM.
- Live MCP acceptance direct and gateway passed all six argument rejection
  scenarios, discovery and expected facts including empty detail windows.
- Missing key, invalid key and bearer-only gateway requests denied.
- Valid subscription key alone succeeds through APIM's system-assigned identity;
  a separate valid-key/invalid-bearer call succeeds, proving caller replacement.
- Container App remains on ready revision 0000001, Running; AcrPull unchanged.
- No new app registration, app-role assignment, SQL grants, or identity created.
- Studio connection/manual skill upload remain operator-owned.

2026-10-19: staged identity deployment, migration 003 and dedicated SQL grants
succeeded. Initial runtime acceptance identified a protected /health probe and
null empty-window detail; root probes and append-only migration 004 corrected
these. ARM revalidation and deployment succeeded.

- Container App revision 0000001: Healthy.
- Native MCP direct and APIM: accepted exact required parameter schemas and
  expected frequency/amount/last timestamp. Empty windows correctly return [].
- Six invalid argument cases per endpoint rejected. Anonymous execution denied;
  invalid and unrelated-audience tokens denied.
- SQL acceptance 10 passed, disposable mutation case skipped.
- Dedicated SQL effective permissions: no SELECT on Claim or ClaimHistory;
  EXECUTE on GetClaimRiskFacts allowed. ACR pull assignment verified.
- All 13 synthetic history rows present, 12 under USD 2,000 and max USD 32,000.
- Image digest cec46e75b273ad569fa43b59c055caf082c7ed32efe6571310e5f95bbbd236b8.
- MCP URL: https://apim-claims-snlo25badmmpc.azure-api.net/claims-risk-tools/mcp
- Studio manual skill upload and OAuth onboarding remain pending.
- Final backend regression: 197 passed, 11 opt-in SQL cases skipped without
  a selected target; live SQL acceptance was separately run with 10 passed.
# Studio subscription-key ingress update

Status: Deployed

Operator approved the scoped plan and existing target on 2026-10-19.

Scope: Change only claims-risk-tools to required APIM subscription-key ingress,
create a dedicated Studio risk-tools product and subscription, and authenticate
APIM to DAB using its existing managed identity. Preserve SQL permissions and all
other routes. Keys must not appear in source, logs, or chat.

Target: Existing approved subscription ME-MngEnvMCAP438243-jgutherie-1,
resource group rg-claims-claims-demo-snlo25, centralus.

Validation: Compile infrastructure, run targeted tests, preview incremental
deployment, and exercise MCP with valid, missing, and invalid keys.

Execution:
1. Add a route-specific policy that strips inbound credentials and uses APIM's
   existing system-assigned identity for the existing DAB API resource.
2. Require subscriptions, create published product copilot-studio-risk-tools,
   associate only claims-risk-tools, and create its active Studio subscription.
   Let APIM generate primary/secondary keys; never output them.
3. Preserve DAB issuer/audience validation and procedure-only SQL identity.
   No other API or Foundry route changes, database changes, or image rebuild.
4. Update source checks, smoke runner, and Studio connection instructions.
5. Validate and preview the incremental Bicep deployment before applying it;
   verify missing/invalid keys denied and valid key succeeds without a caller
   bearer token. Retrieve the generated key from the portal for Studio.

APIM-only rollout: reuse `infrastructure/claims-risk-apim.bicep` directly with
`.azure/risk-apim.parameters.json`; the full app template calls the same module.
This avoids updating the already-healthy Container App or its identity/grants.
Validation steps: core CLI/auth/build/ARM validate/what-if; focused tests and
lint; applicable Azure Policy review; static identity/role review.
