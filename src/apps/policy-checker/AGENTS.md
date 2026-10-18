# Policy Checker

This project was built with the microsoft-foundry skill. Before working on or answering questions about foundry agents, read the microsoft-foundry skill first.

This is the hosted, read-only synthetic policy evidence specialist. It consumes
the exact-version Foundry Toolbox endpoint directly; do not route its own
Toolbox calls through APIM. Keep the Toolbox restricted to `lookup_policy`,
preserve source citations, and never return coverage, eligibility, approval,
denial, payment, or liability decisions.
