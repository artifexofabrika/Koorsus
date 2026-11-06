# Myarra / Koorsus

Production-to-standard tracking and continuous improvement, on-premise.
No cloud. No subscription. Data stays in the building.

Owner: Randy Wolf, Artifexo Fabrika, Columbus, Ohio.
Licensed GPL v3. Modification encouraged.

## Read this first

The newest session delta supersedes everything else. Read in this order:

1. `SESSION-DELTA-2026-11-06.md` — current state, next steps, working method
2. `HANDOFF.md` — architecture, hardware, network, history
3. Older `SESSION-DELTA-*.md` — only when the newest delta points you there

Do not read the older handoffs in full. They are long, and the newest
delta names what still matters.

## What is here

- `myarr_v2/` — the Flask application (port 5002) and the Telegram bot
- `myarr_v2/views.py` — the shared measure layer: nine SQL views
- `myarr_v2/recon.py` — OEE and operator performance, the two-measure design
- `tools/` — demo data generation and population
- `outreach/` — consulting collateral, CV, advisory sheets
- `docs/` — static documentation and demo downloads

## Working method

Section 6 of the newest delta. In short: talk before coding; one change at
a time with a verification gate; verify with SQL before patching Flask;
small paste blocks; and at the site of any agreed decision, a comment of
the form `Agreed YYYY-MM-DD: <decision>, because <reason>`.

