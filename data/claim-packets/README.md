# Supervisor escalation packets

These are frozen synthetic handoffs for the Copilot Studio supervisor demo.
The selected integration is a dedicated Foundry IQ knowledge base on the
existing Search service, not direct Studio file upload or SharePoint.

## Foundry IQ connection

**Published on 2026-10-20.** The three packets are indexed and the dedicated base
contains exactly the source below. Search API retrieval returned each complete
packet for its exact claim ID, both with and without an explicit filter. Missing
claim `clm-demo-003` returned no packet. Existing policy definitions and retrieval
remain unchanged. This does not establish native Studio connector compatibility
or access for Lauren's signed-in identity; those still need rehearsal.

- Search endpoint: `https://srch-claims-snlo25badmmpc-basic.search.windows.net`
- Knowledge base: `supervisor-claim-packets`
- Only knowledge source: `claim-escalation-packets-source`
- Dedicated index: `claim-escalation-packets` (one complete document per claim)
- Authentication: **Microsoft Entra ID Integrated**. Local/key authentication
  is disabled on this Search service; the APIM subscription key does not apply.

In the native Foundry IQ tool picker, connect to that Search endpoint and select
`supervisor-claim-packets`. Keep the existing shared risk-history MCP connection.
The source and base configurations in `iq/` deliberately do not reference
`synthetic-policy-source` or modify the existing policy knowledge base.
The packets contain the excerpts returned in their prior assessments, but the
new base does not search the separate policy corpus.

Microsoft currently documents the native connector under **Build > Tools >
Foundry IQ** for agents using the GitHub Copilot harness, with one IQ connection
per agent. Confirm this connector is available in Lauren's agent; this setup
does not convert its harness or create a Power Platform connection for her.
Her signed-in identity must have the necessary Search access. Do not enable
local authentication or create identities solely to work around a failed login.
See [native IQ connection documentation](https://learn.microsoft.com/microsoft-copilot-studio/agents-experience/foundry-iq-connect).

## Packet files and offline fallback

The three Word documents in `upload/` are the readable source artifacts.
The IQ index contains their text, including explicit image observations,
limitations, original recommendations and claim IDs. Original photos are
embedded in the documents, not independently analyzed by IQ.
The indexed document paths are repository references, not browser-accessible
download URLs; the connector does not provide the original photographs.
Direct Studio upload remains an offline fallback only; don't also upload them
when using IQ, since duplicate sources would obscure the native connector demo.

| Packet | Demo role | Important distinction |
|---|---|---|
| `clm-demo-002-escalation-packet.docx` | Recommended primary scenario: collision, USD 7,200 estimate, driver not listed | Estimate is a preliminary summary; USD 5,000 review threshold is demo-only, not a coverage rule |
| `clm-demo-004-escalation-packet.docx` | Limited-image-evidence contrast | No repair estimate supplied; obstructed image does not prove absence of damage; shared policy fixture names another customer |
| `clm-demo-001-escalation-packet.docx` | Optional third case: deer narrative, door/mirror observations | Actual retrieved glass citation is not proof of relevance or coverage |

`source/` preserves the live API responses and capture provenance.
`evidence/` preserves the exact original PNG bytes fetched from the deployed
claims API and embedded in each document. Image hashes match the captured
image-analysis input hashes. The repair estimate for claim 002 exists only as a
synthetic text summary; there is no separate estimate attachment.

All three workflows were run through the existing deployed claims API on
2026-10-20, using `claim-assessor` version `3`. The documents preserve the actual
recommendations, including source limitations; they do not invent a prior agent
decision. All three recommendations say `human_review`, not `escalate`.
The demo treats that human-review handoff as the supervisor escalation.
No communication was created, sent, or marked reviewed during capture.

## Studio instructions to add

> For a supervisor review, obtain the exact claim ID and retrieve only the
> escalation packet with that claim ID. Verify the claim ID in the retrieved
> content before using it. If the packet is absent or retrieval is incomplete,
> report the missing evidence; do not fill gaps from another claim.
>
> The packet is a pre-generated upstream assessment snapshot. Do not say that
> you called Foundry or performed new image analysis. Separate the unverified
> claimant statement, deterministic findings, captured image observations,
> verbatim agent recommendation, and editorial source caveats.
>
> Obtain one explicit UTC review timestamp, then use the existing
> supervisor-claim-history skill and live `get_claim_risk_facts` MCP tool for
> claim frequency, historical claimed amounts, and last prior submission.
> Do not infer history from the current repair estimate or from the packet.
> An unavailable tool is not zero history. Do not use the original loss date
> as the review timestamp.
>
> Present: claim and escalation context; evidence and limitations; prior agent
> recommendation; live history facts and review window; unresolved issues for a
> qualified human supervisor. Cite the packet and identify the tool-derived
> facts separately. Require human review. Do not decide coverage, approve or
> deny claims, assign fraud/risk scores, or recommend pricing or nonrenewal.

Keep the working shared MCP connection and manually uploaded
`agents/risk-analyst/copilot-studio/SKILL.md`. The additional instructions above
complement that skill; no existing Foundry skill or agent needs to change.

## Rehearsal prompts

Use a fixed scenario timestamp consistently across the rehearsal and live demo.
These examples use `2026-10-20T00:00:00Z`; it is a supervisor-review scenario
timestamp, not a claim loss date or the packet capture time.

1. "Review the escalation packet for clm-demo-002 as a supervisor. Use
   2026-10-20T00:00:00Z as the history review timestamp. Explain the prior agent
   recommendation, distinguish the repair estimate from historical claim
   amounts, call the claim-history tool, and identify what a human must verify."
2. "Now review clm-demo-004 at the same review timestamp. What can and cannot
   be established from the photograph? Is a repair estimate supplied? Identify
   any policy/customer mismatch without deciding coverage. Retrieve its own
   claim history rather than reusing clm-demo-002's history."
3. "Review clm-demo-001 at that timestamp. Is the captured glass citation
   relevant evidence for the reported damage? Separate claimant assertions,
   image observations, and unresolved policy questions."

Claims 001 and 002 belong to the same synthetic customer and therefore share
history; they are not two different people. Claim 004 belongs to another customer.
Original claim loss dates and policy periods remain in 2024-2025. Do not
reinterpret a 2026 capture/review timestamp as evidence of current coverage.

IQ knowledge retrieval is relevance-based, not a guaranteed exact-key API.
The index stores one complete packet per document and has a filterable claim ID.
API consumers can constrain the source using `claim_id eq 'clm-demo-002'`;
free-text Studio queries must still verify the returned claim ID and must not
mix different claims or treat unrelated references as the selected packet.
Rehearse that Studio retrieves the correct packet, preserves its limitations,
and actually calls the MCP tool. If it misses a packet or mixes claim IDs,
use the already-discussed fixed-topic/manual-context fallback for the selected
packet rather than starting another integration. Creating the native IQ connection
remains an operator action; Lauren's Studio agent has not been changed by this
deployment.
