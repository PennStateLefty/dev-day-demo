# Initial threat and safety notes

This is a demo boundary statement, not a completed production threat model. Local mode uses unauthenticated synthetic fixtures; deployed Azure mode implements Entra authentication and live SQL/IQ dependencies. Local-development CORS settings are not a security boundary.

## Assets and trust boundaries

- Synthetic claim, policy, and artifact contents are untrusted inputs.
- Policy retrieval, model inference, REST/MCP adapters, and any future identity provider are separate trust boundaries.
- Assessments, citations, customer-response drafts, secrets, and telemetry must be protected from unauthorized access or disclosure.

## Initial risks and planned controls

| Risk | Initial control / future validation |
|---|---|
| Prompt-like instructions embedded in a claim artifact | Treat artifact text as data only; add injection-containment evaluation before agent use. |
| Unsupported approval, denial, settlement, payment, or outbound customer action | Enforce human review in contracts and service behavior; test prohibited requests and adapter capabilities. |
| Unsupported policy conclusion or fabricated citation | Require source-linked policy citations; evaluate citation correctness and behavior when retrieval is unavailable. |
| Sensitive or real customer data entering the demo | Use synthetic-only fixtures, avoid contact/identity fields, review logs, and reject real data. |
| Unauthorized API/MCP use or secret exposure | Azure middleware requires RS256, tenant v2 issuer/audience, an allowed caller and delegated/application permission; test actual grants and gateway behavior before deployment claims. Never commit credentials. |
| Tool/retrieval/model timeout or malformed artifact | Define explicit error handling and deterministic failure tests in the implementation phase. |

The Docker image defaults to local mode when run outside Container Apps. Do not expose that unauthenticated mode on an untrusted network. The Container Apps revision template explicitly selects Azure mode, HTTPS ingress and the runtime identity. Azure middleware protects business routes, MCP, API docs and dependency readiness; liveness, static UI and nonsecret `/auth-config` remain public. Frontend sign-in uses tenant-specific MSAL PKCE, session storage and a separate SPA registration; requests fail visibly rather than retrying anonymously. The identity initializer defaults to planning, rejects ownership/configuration drift, creates no secrets and never grants consent or roles. Live registration/grants, browser authentication, native MCP behavior, gateway bearer/rate-limit policies and end-to-end operational logging still need verification or completion. Resource definitions and unit tests alone do not establish working access controls.

Cloud SQL is restricted to fixed parameterized queries and a bounded append-only review-note procedure; the runtime has no arbitrary-SQL tool or direct claim-update grant. IQ references are validated against the requested policy and indexed evidence, never followed as arbitrary URLs. Cloud errors fail closed rather than loading local fixtures. The in-container smoke runner must distinguish an actual SQL permission denial from credential/network failure, and validates IQ quotes against Blob content; neither proves NSP denied-source behavior.

The operator approved `public-demo` networking after enforced NSP blocked portal presentations. This deliberately removes network-source isolation: public service endpoints and permissive service firewalls are reachable from arbitrary sources. Identity authorization becomes the primary access boundary; Entra-only SQL, disabled Search/Foundry/Storage keys, HTTPS, private Blob containers and scoped managed-identity grants must remain in place. Synthetic data only; do not treat this as production hardening. The template default remains enforced NSP. No private endpoints or jumpbox are introduced.

The temporary resource-group exception tag neither expires automatically nor guarantees that inherited policies cannot change these settings. Verify the selected mode, actual service properties, rejected unauthenticated requests and presenter asset loading after deployment. See [deployment boundaries and gates](azure-deployment.md).
