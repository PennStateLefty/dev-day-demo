# Contributing

This repository is an incremental demonstration. Keep changes small and reviewable, update relevant documentation and tests with each behavior, and preserve the human-review boundary for all claim assessments and customer drafts. Put application, agent, MCP, package, and test code under `src/`; keep documentation, schemas/data, and infrastructure at the repository root.

Before copying or adapting any external asset:

1. Confirm the source is in the allowlist in `docs/phase-1-spec.md`.
2. Review the exact source license, file-level rights, and synthetic-data status.
3. Record the immutable commit, original path, destination, and planned modification in `ASSET-PROVENANCE.md`.
4. Preserve required notices and update `THIRD-PARTY-NOTICES.md`.

Never add real customer, policyholder, vehicle, claim, or evidence data, secrets, credentials, deployment outputs, or generated caches. Do not introduce an autonomous claim approval, denial, settlement, or payment path.
