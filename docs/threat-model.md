# Initial threat and safety notes

This is a checkpoint-level boundary statement, not a completed production threat model. A detailed threat model is required before deployment or connection to an external system.

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
| Unauthorized API/MCP use or secret exposure | Select and validate identity/access controls before deployment; never commit credentials. |
| Tool/retrieval/model timeout or malformed artifact | Define explicit error handling and deterministic failure tests in the implementation phase. |

No deployed endpoint, model, storage account, or credential exists at this checkpoint.
