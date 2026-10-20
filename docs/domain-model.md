# Initial synthetic claims domain model

This is an initial contract for the demonstration, not an insurance standard or a representation of any carrier's rules. All content and identifiers used with these schemas must be synthetic. Do not put real customer names, contact details, policy records, vehicle identifiers, claim records, or evidence in this repository.

## Entities and relationships

- **Customer** is referenced by a claim and by a policyholder identifier. The initial contract contains no address, date of birth, or contact details; `displayName` is only a fictional label.
- **Policy** belongs to a customer, applies over a date range, lists covered vehicles and drivers, and carries simplified coverage/exclusion text used only to demonstrate grounded retrieval.
- **Vehicle** is a synthetic vehicle record identified by a demo ID, not a VIN.
- **Claim** references its customer, policy, vehicle, loss date, claimant statement, reporting driver, and any repair estimate. At intake only `claimId` is mandatory; optional claim details allow the application to represent incomplete submissions and report missing information instead of rejecting them before assessment. A policy's effective/expiration dates and listed-driver IDs support date-of-loss and driver checks.
- **Claim artifact** describes one synthetic document or evidence item. A duplicate may point to an earlier artifact; a content reference is a repository-relative path, never a remote URL.
- **Claim event** records a synthetic workflow event.
- **Policy citation** identifies the source document and location plus the supporting excerpt used by an assessment.
- **Recommended action** is a bounded next step such as requesting information or routing for human review; it is not a coverage decision.
- **Claim assessment** contains summary, completeness findings, conflicts, citation state and citations, next actions, and a human-review requirement. A grounded assessment must have at least one policy citation; an unavailable or unassessed policy source must not support a policy conclusion.
- **Customer response draft** references the assessment and is explicitly a draft requiring human review.
- **Claim history** is a separate relational synthetic submission ledger under
  `claims.ClaimHistory`, linked to current claims by `customer_id`. Each row has a
  unique historical claim ID, UTC submission timestamp, nonnegative USD claimed
  amount and an enforced synthetic-data marker. Amounts are not payments or
  repair estimates. Current intake claims are not copied into this ledger.
  `claims.GetClaimRiskFacts` resolves the customer from one current claim, then
  returns 12/24-month counts, 24-month amount aggregates, up to 20 recent detail
  records, and the latest prior timestamp across all supplied history. Windows
  exclude their lower bound and include the explicit UTC review timestamp.
  Missing customer identity is an error, not a zero-history customer.

## Demonstration conditions

The schemas allow test fixtures and assessments to represent:

- An active or inactive policy on the loss date.
- A listed or unlisted reporting driver.
- Missing required information or documents.
- Conflicting statements or evidence.
- A repair estimate exceeding a configurable review threshold.
- A possible duplicate artifact.
- A possible prior-damage indicator.
- A straight-through triage *candidate*.
- A claim requiring escalation.

The configurable repair review threshold belongs to runtime configuration, not an insurance policy rule. Findings are indicators for review, not evidence of fraud or coverage outcomes.

## Safety invariants

- `humanReviewRequired` is always `true` in a claim assessment and customer response draft.
- “Straight-through candidate” describes a triage candidate only; it never authorizes approval, denial, settlement, payment, or an unreviewed customer communication.
- Assessments cite policy sources for policy-grounded statements. A citation is a reference, not a claim that the cited text decides coverage.
- Claim, document, model, and tool inputs are untrusted. Prompt-like content in an artifact is data to inspect, never an instruction to follow.
- The schemas describe structure; deterministic validation, authorization, retrieval quality, and human review must be implemented and tested separately.

## Contracts

The JSON Schema contracts are under `data/schemas/`, using JSON Schema Draft 2020-12. Cross-entity relationships are represented by identifiers and relative schema references. Date and timestamp strings use the standard `date` and `date-time` formats; a validator must enable format checking where required.

The initial contracts deliberately keep business rules out of the schema where they require comparing records or configurable thresholds. Examples include checking whether a policy covers the loss date, matching a driver against the policy's listed-driver IDs, and comparing an estimate to the configured review threshold.
