# Azure deployment and bill of materials

## Current status

The foundation and real-image application have been deployed in Central US using
azd. Foundry/project/models, SQL, Blob, Developer APIM, ACR, telemetry and the
Container Apps environment exist. ARM validation passed. Application health,
gateway bearer enforcement and runtime managed-identity Blob access have been
exercised successfully. Authenticated readiness, SQL history and append-only
notes, cited IQ retrieval and MCP initialize/list/call pass directly and through
APIM. Both pinned model deployments accept real managed-identity requests.
Whole-stack `azd provision --no-prompt` completed successfully after recovery.

Serverless Search creation repeatedly failed with an internal provider error.
The operator approved a separate Basic service with one replica and one partition
in Central US, retaining identity-only authentication and enforced NSP. The failed
serverless service and its association were deleted with explicit approval.
Exactly one Search service remains.

The operator subsequently approved **public-demo networking** because enforced
NSP blocked presenter portal data-plane workflows. This changes network admission,
not authentication. The desired and deployed mode is `AZURE_NETWORK_MODE=public-demo`.
All four associations and the empty demo perimeter are removed; exactly one Basic
Search service remains, and no stored data was removed.

Live public-mode verification on 2026-10-14:

- Azure Portal loads the private policy blob's contents using Microsoft Entra.
- Search explorer loads `synthetic-policies` and returns all six indexed passages.
- Foundry loads the `claims` project and both model assets; its chat playground
  answers a synthetic prompt with `PORTAL_NETWORK_OK` using Entra, with keys disabled.
- A subsequent Agents-page check initially returned an NSP rejection, then
  succeeded on retry without configuration changes. Both authenticated agent-list
  APIs return 200 with empty lists, and the portal shows no error. This is
  consistent with delayed backend propagation or stale session state; the exact
  cause is not established.
- Claim Assessor v2 was published to this project using deployment `claims-chat`
  (`gpt-4.1-mini` is the model name, not the deployment name). Its explicit-version
  Responses call reached `getClaim` through APIM, which returned 401 because the
  Foundry client ID was not in the deployed Claims API caller allowlist and did
  not have the required application role. Both changes were subsequently
  authorized and applied on 2026-10-16; see the evidence rollout below.
  Version 1 was an initial immutable version using the model name as a deployment
  identifier; do not invoke it.
- External authenticated Blob reads and Search queries succeed. Anonymous Search
  and model requests return 401; Blob returns 409 `PublicAccessNotPermitted`.
  These are authentication/private-container denials, not remaining NSP blocks.
- Direct/APIM HTTP and native MCP smoke, runtime SQL read/append/denied UPDATE,
  and cited IQ/Blob retrieval pass after the networking change.
- A fresh `azd provision --no-state --no-prompt` succeeds, including the
  postprovision hook, in 1 minute 16 seconds. An ordinary repeat detects no changes.
  The hook uses the authoritative resource GET, not lagging ARM collection listings,
  to confirm deletion; replay does not recreate NSP.

The live audit confirms public service settings, Entra-only SQL, restored SQL
administrator, disabled keys and anonymous Blob access. No jumpbox, Bastion or
landing-zone change was introduced.

The subscription-scope entry point creates only a new, deterministically named
demo resource group. Existing landing-zone resources are not referenced or changed.
Deployment must use the external tenant and subscription selected by the operator;
their actual IDs belong in ignored azd settings, not committed configuration.

### Confirmed deployment blockers

The initial read-only diagnosis found no azd environment. The local `claims-demo`
environment now stores the approved tenant/subscription, Central US location,
2026-10-23 exception deadline, approved admin details, current operator public
`/32` and newly created API/SPA registration IDs in ignored settings.
Live preprovision configuration/context/provider/model/Search metadata checks pass.
The user approved exception-tag removal on 2026-10-23, after the
environment's required lifetime through EOD 2026-10-22. No automated tag removal
is implemented. The user also clarified authority to provision in this account:
the implementation-added cost flag has been removed. It was not an Azure or
established organizational approval requirement.

Azure CLI authentication matches the approved enabled tenant/subscription, and
the current principal has a subscription Owner assignment. Insufficient
subscription RBAC is not the currently demonstrated blocker.

Inherited management-group assignments include `MCAPSGovDenyPolicies` and
`Block Azure RM Resource Creation` with Default enforcement. Reading the latter
assignment directly failed `Microsoft.Authorization/policyAssignments/read` at
management-group scope. Its exact matching effect and treatment of
`SecurityControl=Ignore` are therefore unknown, **not a confirmed policy denial**.
Actual subscription ARM validation succeeded and the foundation was created.
No matching policy deny has been demonstrated. Subscription Owner does not imply
access to parent management-group policy.

The Claim Assessor definition and advisory Risk Analyst Skill/Toolbox publisher are
source-controlled. Claim Assessor v3 and Risk Analyst Skill v1 are published, but
tool access and the Risk Analyst Toolbox are not verified. Policy Checker and
Communication definitions, browser sign-in and model gateway connection/policies
remain end-to-end demo work, not platform provisioning blockers.
The serverless provider failure does not prove its root cause was capacity or NSP
compatibility. Before the approved public-mode change, runtime managed identity
could list the protected Blob containers, but operator Blob and SQL requests
were denied by NSP despite the synchronized /32 rule.
Actual perimeter logs identify rotating Azure-bound proxy source addresses, distinct
from the IP-check address. No broad allowlist was added. Diagnostics reach protected
Blob, and cloud managed-identity initialization succeeded under the original NSP.

The New Foundry model playground currently disables **Save as agent** with
"Saving as agent isn't supported in this region." This is an observed Central US
feature limitation, not a network denial or proof that every agent API is unsupported.
Resolve target agent-version/region compatibility before claiming specialist readiness.

### Image evidence setup and handler-check runbook

**Deployed on 2026-10-16; agent-driven acceptance remains blocked.** The three
images are uploaded and byte-verified in private Blob, the five reviewed SQL
changes are applied, and initializer replay leaves no fixture drift.
`claims-vision` runs `gpt-6-luna` version `2026-09-22`, GlobalStandard capacity
10, with `NoAutoUpgrade`. Claim Assessor v3 is published and pinned; the API/UI
revision uses the existing `claims` project. Foundry Workflows is not used.

Authenticated private previews match the supplied file hashes through both
direct API and APIM; anonymous requests are denied. Actual API-owned inference
completed for claims 001, 002 and 004; claim 003 returned `no_evidence` without
model metadata. Image accuracy is a documented demo limitation, not a release
gate: the first live
001 result described scratches and a missing mirror cover but missed the expected
dent; 002 described bumper scrapes but missed the expected hood misalignment and
broken cover. The limited-view 004 result correctly abstained from identifying
damage. Keep these misses visible against the evaluation fixture; do not inject
the expected answers into model inputs or claim exhaustive damage recognition.

The confirmed outbound caller is the **project managed identity**, not the
agent instance identity. Its allowed client ID and `Claims.Invoke.Application`
assignment are deployed. Foundry is still reusing a token issued before that
grant (2026-10-16 14:57:43 UTC), expiring **2026-10-17 15:02:43 UTC**. Its APIM
tool calls therefore still return 403 for the missing role claim. Token refresh
must be observed, not assumed from the Graph assignment. No token bypass or key
fallback was added. Temporary identity-only denial diagnostics were removed.
`Run handler checks` returns an explicit 503 while this persists; matching actual
tool-result extraction and all four agent recommendations remain unverified.

The supplied assets are already in this worktree:

| Claim | Repository path / Blob key inside private `evidence` |
|---|---|
| `clm-demo-001` | `data/artifacts/images/clm-demo-001/passenger-door.png` |
| `clm-demo-002` | `data/artifacts/images/clm-demo-002/collision.png` |
| `clm-demo-004` | `data/artifacts/images/clm-demo-004/limited-view.png` |

`data/claims/demo-claims.json` supplies `artifactIds`.
`data/artifacts/demo-artifacts.json` associates each artifact with its claim and
`contentRef`; the full `contentRef` is the Blob key, not a public URL or SAS.
Claim 002 retains its estimate and gains a photo. New claim 004 uses a distinct
synthetic customer; claim 003 keeps no evidence. No further manual JSON work is
required for these assets. Generator/prompt provenance is unspecified and must
not be fabricated. User evaluation expectations live only in
`evaluations/datasets/image-analysis.json`, never in inference prompts.

Local setup uses `uv sync --locked` and the existing UI scripts. Preview endpoints
read these registered local files; handler checks remain a labeled fixture flow
and never call a model in local mode. In Azure, preview reads only the private
Blob container using runtime managed identity. PNG/JPEG evidence is limited to
5 MiB, 16 million decoded pixels, and one linked photo per assessment.

After selecting/exporting the existing ignored environment configuration, first
create a **local upload manifest without cloud reads or writes**:

```sh
uv run --locked python scripts/initialize_evidence.py \
  --output /tmp/claims-evidence-images.json
```

`AZURE_STORAGE_ACCOUNT_NAME` must name the existing account. Inspect the three
Blob keys, byte counts, content types and SHA-256 digests. To include an exact
expected-before SQL diff, sign in as the existing authorized SQL administrator,
set `AZURE_SQL_SERVER` and `AZURE_SQL_DATABASE`, and run:

```sh
uv run --locked python scripts/initialize_evidence.py --include-sql \
  --output /tmp/claims-evidence-reviewed.json
```

This is read-only. Existing insert-only `initialize_sql.py` deliberately rejects
seed drift; do not weaken it or give the API runtime SQL UPDATE access.
On macOS, if the SQL driver's OpenSSL loader fails despite Homebrew OpenSSL being
installed, prefix the command with
`DYLD_LIBRARY_PATH="$(brew --prefix openssl@3)/lib"`; do not disable TLS.
Review the manifest before explicitly approving/applying the changes:

```sh
uv run --locked python scripts/initialize_evidence.py \
  --apply /tmp/claims-evidence-reviewed.json
```

Apply uploads/compares image bytes before updating references. Existing Blob
content is never overwritten; differing content fails. SQL uses a transaction,
fixed parameterized statements, and reviewed before-state checks; concurrent
drift fails and rolls back. An already-applied matching manifest is replayable.
SQL failure can leave harmless unreferenced images; it never commits partial SQL
updates. This operator-local tool uses Azure CLI credentials, not runtime grants.

Cloud inference is opt-in through these application Bicep settings, mirrored
to environment variables. Empty values keep the feature unconfigured:

| Setting | Meaning |
|---|---|
| `CLAIMS_VISION_ENDPOINT` | Approved HTTPS Azure `/openai/v1` endpoint |
| `CLAIMS_VISION_DEPLOYMENT` | Actual deployment of **gpt-6-luna**, not merely the model name |
| `CLAIMS_VISION_MODEL_VERSION` | Verified pinned model version `2026-09-22` |
| `FOUNDRY_PROJECT_ENDPOINT` | Existing project endpoint |
| `CLAIM_ASSESSOR_AGENT_VERSION` | Explicit version published from the updated claim-ID-only definition |

Set the first three together and the final two together. The API uses its runtime
managed identity for Blob, model and Foundry calls; there are no API keys or
automatic fallback models. Azure returned the deployment alias `claims-vision`
in the live Responses `model` field, not the model/version name. The client
accepts only the configured alias or exact family/version identifier. Verify the
alias's actual family, version and `NoAutoUpgrade` through ARM on deployment;
an alias alone is not per-response proof of the underlying model. Structured
image responses are verified. The specialist still uses `claims-chat`, not the
vision deployment.
If a gateway is used, verify its identity/audience and model routing separately;
an SDK call alone is not evidence that model traffic traverses APIM.

Repeatable focused infrastructure updates, after selecting the existing
subscription and resource group:

```sh
az deployment group create --resource-group "$AZURE_RESOURCE_GROUP" \
  --template-file infrastructure/claims-vision.bicep \
  --parameters foundryAccountName="$AZURE_AI_ACCOUNT_NAME"
az deployment group create --resource-group "$AZURE_RESOURCE_GROUP" \
  --template-file infrastructure/claims-agent-access.bicep \
  --parameters foundryAccountName="$AZURE_AI_ACCOUNT_NAME" \
    runtimePrincipalId="$AZURE_RUNTIME_PRINCIPAL_ID"
```

The second template grants **Foundry Agent Consumer at project scope** to the
API runtime. Runtime and operator invocation use the SDK's consumer endpoint
(`allow_preview=True`, `get_openai_client(agent_name="claim-assessor")`) and
still send an explicit `agent_reference.version`. A nonexistent version returned
404, proving this route does not silently select latest. The generic project
developer Responses endpoint returned 403 for the runtime identity; broader
authoring rights were not retained. Trial role assignments/custom role were
removed after this distinction was established.

The project managed identity separately needs the API application's
`Claims.Invoke.Application` app-role assignment in Entra and the existing
caller allowlist entry. Inspect `appRoleAssignments` for the project service
principal before creating an assignment, resolving the API service principal
and role by their configured application ID and role value. Reuse a matching
assignment rather than creating duplicates. The live assignment exists; cached
tokens do not retroactively acquire the role. Do not weaken audience, issuer,
caller or permission validation while waiting for refresh.

Publish the revised prompt agent using `scripts/agents/claim_assessor.py publish`
with the existing project endpoint, `--model claims-chat`,
`--claims-gateway-url "$CLAIMS_GATEWAY_REST_URL"` and
`--api-audience "api://$CLAIMS_API_AUDIENCE"`. Pin the returned immutable version
in the ignored environment, then deploy only the intended application update
after approvals. Reusing an identical source hash reuses its existing version.
For a direct operator invocation after authentication is configured:

```sh
uv run --locked python scripts/agents/claim_assessor.py invoke \
  --project-endpoint "$FOUNDRY_PROJECT_ENDPOINT" \
  --agent-version "$CLAIM_ASSESSOR_AGENT_VERSION" \
  --claims-gateway-url "$CLAIMS_GATEWAY_REST_URL" \
  --api-audience "api://$CLAIMS_API_AUDIENCE" \
  --claim-id clm-demo-001
```

The operator requires their own authorized API access. The CLI fetches the claim
from the API and invokes the same shared handler client, with no image input.
Actual matching tool evidence must be present in the Foundry response. A missing
or unsupported tool-output shape fails closed; it does not rerun assessment.
Re-run this invocation after the cached token has refreshed, then exercise
claims 001 through 004. Do not call the specialist ready until extraction and
demo contract and safety checks pass. Exact damage recognition is not required.

If azd's remote build fails while checking an ACR log Blob that does not yet
exist, inspect the actual ACR run before retrying. The observed run succeeded
despite azd's log-polling 404. A verified recovery is `az acr build --no-logs`
with the same Dockerfile/context, followed by
`azd deploy claims-api --from-package <verified-registry-image@sha256:digest>`.
This still uses the source-controlled application Bicep and environment settings;
it is not a portal-only configuration change.

In the UI, selecting a claim fetches its authenticated image without inference.
**Run handler checks** invokes the API application handler, the pinned agent and
its enriched `/assess` tool. Local fixture runs are distinct from cloud success.
Results separate deterministic checks, advisory per-part model observations,
limitations, and the agent's recommendation. `no_evidence` makes no model call;
`unavailable` retains checks and requires human review. A limited view must not
be described as an undamaged vehicle. Re-running incurs fresh inference work;
automatic model retries are disabled, and exactly-once execution across service
failures is not promised.

For live acceptance, record asset hashes, model/deployment and prompt versions,
agent version, actual tool result and final recommendation for all four claims.
Compare semantic observations with the evaluation dataset, not exact wording.
Assert no automatic coverage decision, invented citation, hidden-damage diagnosis
or claimant classification. The full path is not verified until real private
Blob access, image inference, APIM tool authentication and response extraction
all succeed.

### Local specialist publisher

The current Claim Assessor definition is published as agent version 3. Its APIM
tool access remains blocked on a cached pre-grant token despite the authorized
caller allowlist and API role updates. Risk Analyst Skill v1 was
published from `agents/risk-analyst/SKILL.md` and read back successfully; the
downloaded source and digest match the checked-in file. The project currently has
no connections, so the authenticated APIM MCP project connection required by
the Risk Analyst Toolbox is not configured and no Toolbox was published.

The current source changes the specialist to **claim-ID-only input** and requires
an enriched assessment tool result. Do not pin version 2 for the new handler path;
its old direct-image invocation is no longer the intended flow. Agent v3 appearing
in Foundry is not evidence that the full handler path has passed.

Publish or verify the standalone Skill without changing project access:

```sh
uv run --locked python scripts/agents/risk_analyst.py publish-skill \
  --project-endpoint "$AZURE_AI_PROJECT_ENDPOINT"
```

After the authenticated APIM MCP project connection has been explicitly
configured, publish the immutable Toolbox version with that connection:

```sh
uv run --locked python scripts/agents/risk_analyst.py publish \
  --project-endpoint "$AZURE_AI_PROJECT_ENDPOINT" \
  --claims-mcp-url "$CLAIMS_GATEWAY_MCP_URL" \
  --project-connection-id "$CLAIMS_MCP_PROJECT_CONNECTION_ID"
```

The returned Toolbox version is invoked through its exact Foundry endpoint:
`{AZURE_AI_PROJECT_ENDPOINT}/toolboxes/risk-analyst-toolbox/versions/{version}/mcp?api-version=v1`.
The consumer rejects the default/latest endpoint, verifies the exact version exists,
loads the Skill through `FoundryToolbox.as_skills_provider()`, and validates the
review against `data/schemas/risk-review.schema.json`. Invocation still requires
target-project validation and synthetic regression evidence.

## Selected bill of materials

All resources default to Central US. A region change requires a new compatibility
check, not a silent fallback.

| Component | Selected configuration | Implemented provisioning scope |
|---|---|---|
| Foundry | AIServices S0 account, project, system-assigned identities | Yes |
| Specialist chat model | Deployment `claims-chat`: `gpt-4.1-mini`, `2025-04-14`, GlobalStandard, capacity 10 | Deployed; retained for Claim Assessor |
| API-owned image model | Selected `gpt-6-luna`; catalog lists `2026-09-22` | Not deployed; endpoint, image inference and access require verification/approval |
| Embedding model | Deployment `claims-embedding`: `text-embedding-3-small`, version `1`, GlobalStandard, capacity 10 | Yes |
| Foundry IQ / Search | Basic, one replica and partition; identity authentication | Seeded semantic index and extractive knowledge source/base; live citations resolve to protected Blob |
| API Management | New classic Developer, one unit, managed identity | REST/native MCP readiness, initialize/list/call and missing-token denial pass; model gateway unfinished |
| Relational data | SQL Basic, 5 DTU, 2 GB; Entra-only administrator | Migrations, six synthetic records and contained runtime user initialized; live reads and append-only writes pass |
| Synthetic documents | StorageV2 Standard LRS Hot; private `policies` and `evidence` containers | Synthetic policies uploaded; live managed-identity reads and NSP diagnostic delivery verified |
| Application hosting | Container Apps environment, user-assigned runtime identity | Real-image azd revision deployed with HTTPS ingress, Entra API middleware and working public liveness |
| Container registry | ACR Basic; admin authentication disabled | Yes |
| Telemetry | Log Analytics, 30-day retention and 1 GB/day cap; Application Insights | Yes; no application instrumentation yet |
| Network boundary | Explicit `public-demo` mode for presentations; `enforced-perimeter` remains the template default | Public endpoints/firewalls permit Entra-authenticated access; the demo NSP and its four associations are retired by the provision hook |
| API catalog | API Center Free | Empty service; no contract registration |
| Copilot Studio | Supervisor and optional SQL-backed data analyst | Separate presenter-owned work; not deployed here |

The three intended Foundry specialists are Claim Assessor, Policy Checker and
Communication. Risk Analyst is an advisory reusable skill, not an autonomous
decision-maker. The existing fixture-based local orchestrator is not the intended
Copilot Studio supervisor.

### Cost evidence and boundaries

Central US USD public retail meter discovery returned the following rates.
Re-query before approval; these are not MCA negotiated prices or a complete quote.

| Meter | Observed rate | Illustrative continuous usage |
|---|---|---|
| APIM Developer Unit | $0.0658/hour | $48.03 at 730 hours |
| APIM Basic Unit | $0.2016/hour | $147.17 at 730 hours |
| APIM Basic v2 Unit | $0.20548/hour | $150.00 at 730 hours |
| SQL Database Single Basic, B DTU | $0.161/day | $4.83 at 30 days |
| ACR Basic Registry Unit | $0.1666/day | $5.00 at 30 days |

Developer is selected for the nonproduction gateway because it supports the
required native MCP and AI gateway capabilities. Consumption does not support
native MCP. Developer has no production SLA. Reusing the discovered private
gateway was rejected because it would require landing-zone/jump-box access.

These examples exclude model tokens, Basic Search fixed capacity,
Container Apps usage, Blob operations/storage, Log Analytics ingestion, network
egress, build tasks, applicable NSP charges and taxes. Neither model capacity
units nor the Log Analytics daily cap represent a total budget cap. Complete the
usage-based estimate for operational visibility. The user has authorized
provisioning the agreed demo resources in this account; there is no separate
cost-approval flag. Material tier or architecture changes still require a decision.

The native MCP preview endpoint has a demonstrated schema discrepancy:
`2025-09-01-preview` documentation describes an endpoint array, but the live API
rejects arrays and requires a dictionary. The runtime also requires `backendId`,
which is absent from the published Bicep schema. The narrowly scoped dynamic
properties object preserves the proven payload rather than suppressing all
validation. The backend URL is the application root and its MCP endpoint is
`/mcp/`. The exact gateway endpoint ends in `/claims-tools/mcp/`; preserving the
trailing slash is essential. Live initialize/list/call passes with all five tools.

## Network and identity contract

Networking has two explicit modes:

- `enforced-perimeter` is the template default. SQL, Search, Storage and Foundry
  join enforced NSP associations; one operator IPv4 `/32` and same-subscription
  managed identities are permitted. NSP is **not Private Link**. APIM and
  Container Apps cannot join it; scoped data permissions remain independent.
- `public-demo` is the operator-approved presentation mode. SQL, Search and
  Storage enable public endpoints; Storage and Foundry use Allow network defaults.
  SQL permits the IPv4 range only in this mode, while always requiring Entra.
  Blob containers remain private, not anonymous. Search/Foundry keys and Storage
  shared keys remain disabled. Public connectivity is deliberately reachable
  from arbitrary sources; there is no claim of network-source isolation.

Select the approved mode in the existing environment, then provision:

```bash
azd env set AZURE_NETWORK_MODE public-demo
azd provision --no-prompt
```

ARM incremental deployments do not remove omitted resources. The postprovision
hook validates matching requested/deployed mode, subscription, owned resource
group and public service settings, then removes only the four recognized demo
associations and their empty perimeter. It never deletes SQL, Search, Foundry,
Storage or stored data. Replaying public mode with no perimeter is a no-op.
Deletion verification retries the authoritative resource GET for up to five minutes;
only a confirmed NotFound is absence, and authorization/other lookup failures abort.
To restore enforcement, set `AZURE_NETWORK_MODE=enforced-perimeter`, supply the
operator `/32` and provision again. Bicep recreates enforced associations and deny
defaults. The public SQL rule is ineffective under SecuredByPerimeter, but review
and remove that named rule if permanently retiring public-demo capability.

Search and Storage disable key authentication; SQL uses Entra-only authentication;
Foundry disables local authentication. The application revision template attaches
the runtime identity and the platform grants scoped roles. SQL ARM roles do not create SQL users:
an administrator must apply contained-user migrations and minimum database grants
before runtime SQL access can work. The explicit SQL initializer implements this:
the contained service-principal SID comes from the runtime **client/application
ID**, encoded as little-endian UUID bytes; driver authentication also uses its
client ID. ARM RBAC uses its object/principal ID instead. Object-specific SELECT
and procedure EXECUTE grants replace
generic `db_datareader`/`db_datawriter` helpers to preserve the approved narrower
boundary. There are no runtime DDL or direct claim-update grants.

In enforced mode, NSP access diagnostics target the same Blob account that joins the perimeter,
after its association is created. Log Analytics remains outside the perimeter
for platform logging; it is not the NSP diagnostic destination. Historical diagnostic delivery was verified using actual denied-source records.
Removing the perimeter does not delete the Blob account or historical logs.

The same-subscription rule and model roles do not prevent every direct model
call. No claim is made that model traffic is forced through APIM: configure the
Foundry APIM connection, inbound issuer/audience/client validation, outbound
gateway identity and routing, then observe real calls before making that claim.

`SecurityControl=Ignore` and exception owner/deadline tags apply only to the new
resource group. Individual resources receive ordinary application/environment
tags, not the policy-exception tag. Effective inherited policy and tag exemption
behavior must be checked through ARM validation/what-if.

**The expiry tag does not expire the exception or remove resources.** An explicit
owner must remove the tag or delete the demo group by the approved deadline.
There is no automatic teardown implementation or assumed approval to delete.

## Operator inputs and local checks

Prerequisites are Azure CLI, Bicep, azd, uv and the project's Python 3.12 runtime.
Use an identity authorized for the selected tenant/subscription, resource-group
creation and scoped role assignments. Do not switch to another subscription to
work around an authorization or capacity failure.

Create an azd environment and populate the keys listed in `.env.example` using
`azd env set KEY VALUE`. Do not source that example as if it were real
configuration. It intentionally leaves identity, contact, IP and expiry
values blank. The Entra administrator name/type must describe the
tenant-local object identified by `AZURE_OPERATOR_PRINCIPAL_ID`.

`azure.yaml` runs the read-only preprovision hook with azd's environment variables.
It rejects missing inputs, a missing/expired exception deadline,
broad/private operator CIDRs, context mismatch and unavailable advertised
capabilities. The operator `/32` is required only in enforced mode. It neither
registers providers nor changes Azure context.

Local checks that need no Azure login:

```bash
uv run ruff check src/apps/claims-api src/tests scripts
uv run python -m unittest discover -s scripts/validation -p 'test_*.py'
uv run pytest -q
set -o pipefail
az bicep build --file infrastructure/main.bicep --stdout |
  uv run python scripts/validation/check_infrastructure.py
az bicep build --file infrastructure/claims-api.bicep --stdout |
  uv run python scripts/validation/check_infrastructure.py --application
```

The compiled-template check covers required resource presence and selected
authentication, SKU, exception-input and explicit network-mode invariants. It is not
an ARM expression evaluator or a replacement for Azure validation.

Basic Search uses the stable `2025-05-01` management API. Its extractive knowledge
resources use the `2026-04-01` data-plane API during explicit initialization.

The native MCP schema discrepancy above was resolved against actual ARM
responses and protocol calls, not compilation alone.

Pinned AVM dependencies are restored by Bicep from `br/public:avm`: workspace
`0.16.0`, Application Insights `0.8.0`, ACR `0.13.0` and API Center `0.1.0`.
Module telemetry is disabled. Do not vendor unrelated source or persist generated
ARM output, azd secrets, tokens or SQL connection passwords in the repository.

## Application deployment and initialization

The `claims-api` azd service uses the root Dockerfile, Linux AMD64 and ACR remote
build; a local Docker daemon is not required for that build path. Build/task usage
should be included in cost estimates. The non-root runtime starts its installed
Uvicorn binary directly rather than restoring dependencies at container startup.
Ignored azd/Foundry state is excluded from the remote build context.

The platform creates no hello-world or fixture-mode application. Once azd publishes
the real image, its controlled revision deployment uses
`infrastructure/claims-api.bicep` and matching parameters. This template attaches
the user-assigned identity for image pulls and data access, explicitly sets
`CLAIMS_MODE=azure`, and configures public HTTPS ingress. It scales between zero
and one replica; cold starts and MCP reconnection still need live testing.
Reprovisioning the platform does not reset a deployed image.

Before provisioning, supply an Entra API application client GUID as
`CLAIMS_API_AUDIENCE` and explicit comma-separated caller **client IDs** as
`CLAIMS_API_CLIENT_IDS`. Also supply a separate SPA client GUID as
`CLAIMS_UI_CLIENT_ID` and include it in that caller allowlist.
The API registration must issue v2 access tokens and expose
delegated `claims.invoke` and/or application `Claims.Invoke.Application`, with explicit caller
grants. A valid token also needs the configured tenant issuer/audience and allowed
`azp`.

`scripts/initialize_identity.py` plans isolated, secretless API/SPA registrations
without cloud calls by default. Run it with the selected tenant, subscription and
environment variables in the process environment:

```bash
uv run python scripts/initialize_identity.py
```

Only `--apply` creates registrations and service principals; it requires explicit
exception owner/expiry, matching subscription context and operator
Graph permissions. It never grants consent, assigns caller roles, invites guests,
creates secrets or adopts an unrelated application by display name. Ownership
markers and declared configuration must match on replay; drift fails explicitly.
It prints nonsecret IDs for manual storage in the selected ignored azd environment.
The isolated API/SPA registrations and service principals have been created with
the approved admin identity, and replay returned the same IDs without duplicates.
The postdeployment SPA redirect is configured, and the selected CLI caller has
delegated API consent for smoke testing. SPA browser consent/sign-in is unverified.
The application role is deliberately distinct from the delegated scope even under
case-insensitive comparison: Entra rejected the original case-only distinction
with `DuplicateValue`.

To avoid a hostname bootstrap dependency, the first apply may omit `--redirect-uri`.
The resulting empty SPA redirect list intentionally cannot complete browser login.
After deployment supplies `SERVICE_CLAIMS_API_URI`, rerun the same plan/apply with
`--redirect-uri https://<exact-container-app-host>/`. This permits only the initial
empty-to-explicit redirect transition, not replacement of an existing redirect.
An administrator must separately grant the SPA delegated
`api://<API-client-GUID>/claims.invoke` consent. Other callers need their own
explicit grants; app creation alone grants no access.

The hosted UI implements tenant-specific MSAL authorization-code/PKCE sign-in,
session-storage caching and same-origin authenticated API requests. Public
`/auth-config` exposes only mode, tenant/client IDs and the delegated scope, never
credentials. Claims are not fetched until sign-in; configuration/token failures
are visible and never retry anonymously. The updated Azure UI uses the application `/workflow` handler to invoke one pinned
specialist, not Foundry Workflows or the local fixture orchestrator. It does not
fabricate specialist communication. This source change is deployed, but full
handler acceptance remains blocked as described above.
The browser flow has not been exercised against real Entra registrations.

Provisioning no longer implicitly runs local data-plane initialization: an
operator's Azure-bound proxy address may differ from the configured `/32`.
Run `initialize_sql.py` followed by `initialize_knowledge.py` explicitly from an
authorized network. SQL tracks migration hashes
and seeds fixed relational records; replay detects drift instead of overwriting.
Knowledge initialization uploads synthetic policy markdown, checks semantic index
definitions/documents, and creates extractive IQ resources with API `2026-04-01`.
This mode does not claim LLM query planning, synthesis or embeddings. Failed
initialization fails explicitly; operator permissions and the selected network mode must work.

For this environment, the approved alternative was a temporary managed-identity
Container Apps job inside the existing environment. After `azd provision` and
`azd deploy claims-api`, inspect `uv run --locked python scripts/bootstrap_azure.py`.
Only run `--apply` with explicit authorization for the complete lifecycle:
create a dedicated identity/job and four resource-scoped roles, temporarily select
it as SQL administrator, initialize, restore and verify the selected administrator,
then remove the job/roles/identity. This is not a permanent runtime privilege or an
automatic provision hook. Both initialization and the approved legacy SID repair
completed successfully; the selected administrator is restored and no bootstrap
job or identity remains. Normal replay never drops a user. The optional
`--repair-legacy-principal-sid` requires separate authorization and matches only
the exact old object-ID SID before recreating that user's limited grants.

Public `/health` and Container Apps probes establish process liveness only.
Entra-protected `/ready` checks seeded SQL and nonempty Search, **not** the IQ
knowledge-base retrieval path. `runtime_smoke.py`, executed inside the deployed
container with its configured identity, checks SQL reads/history, an allowed
append note, denied direct UPDATE, Blob access and IQ citations. Each successful
write check appends one synthetic note; it does not delete or modify claims.

`http_smoke.py --base-url <explicit-HTTPS-base>` checks denied unauthenticated
REST/MCP, authenticated Azure readiness, and real MCP initialize/list/call. Run it
separately for the direct API and configured APIM base path. It acquires the
operator CLI's API token; that caller needs explicit authorization, not an implicit
test bypass. For APIM's separate REST and native MCP routes, supply both exact
outputs (the endpoints must share a host):

```bash
uv run python scripts/validation/http_smoke.py \
  --base-url "$CLAIMS_GATEWAY_REST_URL" \
  --mcp-url "$CLAIMS_GATEWAY_MCP_URL"
```

Without `--mcp-url`, the runner uses `<base-url>/mcp/`, matching the direct API.
Both scripts emit JSON and fail nonzero. HTTP smoke passes against the direct
application and APIM, including real grounded MCP assessment. Runtime SQL/Blob/IQ
checks execute inside the deployed container using its managed identity.
The SQL driver omits native error numbers; the denied-update check requires its
specific programming-error category and exact UPDATE-denied message for
`claims.Claim`, not a generic error or a numeric substring.
Neither script proves specialist behavior or APIM model routing. NSP diagnostic
delivery and denied operator-source requests were verified separately.

## Gates before declaring the phase complete

Do not run `azd up` as though this foundation deploys a working demo. Live application
registration/caller grants and browser sign-in verification, three versioned
specialists, advisory skill, model
gateway configuration and API Center registration remain unfinished.
Application packaging, Entra middleware, SQL migration/seed tools and IQ
initialization and direct/gateway protocol smoke are verified in Azure; browser
and agent orchestration still need their own end-to-end proof.

Provisioning additionally requires the approved exception deadline/owner,
operator IP and administrator metadata, APIM publisher metadata,
effective-policy review, and ARM validation/what-if. Complete
azure-validate before azure-deploy. Do not widen access or upgrade a tier silently.

The final machine-readable live smoke evidence must cover:

- Entra-authenticated MCP initialize/list/call through APIM; unauthorized calls denied.
- Runtime managed-identity SQL reads and allowed writes; disallowed writes denied.
- Blob access and IQ retrieval with citations resolving to the seeded synthetic policy.
- Explicit-version calls to each Foundry specialist and a synthetic photo test.
- Model calls observed through APIM, with no unauthenticated backend access.
- In enforced mode: authenticated allowed/denied network sources and perimeter
  diagnostic delivery. In public-demo mode: presenter portal data-plane access,
  rejected unauthenticated requests and unchanged managed-identity permissions.
- Correlation telemetry and a repeat deployment with no destructive replacement.

Health checks and successful control-plane deployment alone do not satisfy these
requirements. Keep deterministic local fixtures available for local regression
tests, but never silently substitute them for a failed cloud dependency.

## Sources

- [Serverless Search costs](https://learn.microsoft.com/azure/search/serverless-cost-optimization)
- [APIM feature comparison](https://learn.microsoft.com/azure/api-management/api-management-features)
- [Foundry AI gateway](https://learn.microsoft.com/azure/foundry/agents/how-to/ai-gateway)
- [NSP diagnostics and destination requirements](https://learn.microsoft.com/azure/private-link/network-security-perimeter-diagnostic-logs)
- [Azure Retail Prices API](https://learn.microsoft.com/rest/api/cost-management/retail-prices/azure-retail-prices)
- [azd service and Docker configuration](https://learn.microsoft.com/azure/developer/azure-developer-cli/azd-schema)
- [SQL Python Entra authentication](https://learn.microsoft.com/sql/connect/python/mssql-python/entra-authentication)
- [IQ extractive retrieval](https://learn.microsoft.com/azure/search/agentic-retrieval-how-to-retrieve)
