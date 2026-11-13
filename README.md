# Myarra / Koorsus

Production-to-standard tracking and continuous improvement, on-premise.
No cloud. No subscription. Data stays in the building.

Owner: Randy Wolf, Artifexo Fabrika, Columbus, Ohio.
Licensed GPL v3. Modification encouraged.

## Read this first

`PHILOSOPHY.md` is the governing document. Read it before anything else.
It is never superseded. If a proposed change contradicts it, the change is
wrong, not the document.

After that, the newest session delta supersedes everything else. Read in
this order:

1. `PHILOSOPHY.md` — philosophy and inviolable commitments
2. `SESSION-DELTA-2026-11-13-DEPLOYMENT-READY.md` — Odoo Apps Store publication,
   Apify lead scraping, Odoo CRM setup, current state and next steps
3. `HANDOFF.md` — architecture, hardware, network, history
4. Older `SESSION-DELTA-*.md` — only when the newest delta points you there

Do not read the older handoffs in full. They are long, and the newest
delta names what still matters.

## Repositories

Two repositories, with distinct purposes. Do not confuse them.

- `~/Client-Demo` — the Koorsus monorepo: application, bot, tools, outreach,
  documentation, and all session deltas. This is the handover record.
- `~/myarra-connector-repo` — the Odoo connector, published on the Odoo Apps
  Store. Branch `20.0` is the default and the series branch. Public at
  github.com/artifexofabrika/myarra-connector.

The connector lives in both places. `~/myarra-connector-repo` is the source
of truth for the published module; `~/odoo_connector` is a build directory
kept in step by copying from it, never the reverse.

## What is here

- `myarr_v2/` — the Flask application (port 5002) and the Telegram bot
- `myarr_v2/views.py` — the shared measure layer: eleven SQL views
- `myarr_v2/recon.py` — OEE and operator performance, the two-measure design
- `myarr_v2/parsers.py` — freeform capture parsing; jidoka in software
- `myarr_v2/bot/` — modular Telegram bot, ten modules
- `odoo_connector/` — build directory for the published Odoo 20 module
- `tools/` — demo data generation and population
- `outreach/` — consulting collateral, CV, advisory sheets, pricing, listings,
  one-pager, Reddit copy, jigsaw mailer concept, hardware sourcing
- `docs/` — static documentation, marketing site, demo downloads

## Commercial pipeline

- Odoo Apps Store: Myarra Connector, v20.0.1.0.2, 99 EUR, OPL-1, published.
- Odoo CRM: pipeline stages New, Contacted, Proposition, Won. Leads are
  tagged `Tier 1 - *` for packagers, bottlers, cosmetics, food, partners,
  manufacturing, and mobile canning, and `Tier 2 - *` for breweries,
  distilleries, wineries.
- Lead generation via Apify (Compass Google Maps Scraper), exported to CSV
  and imported through Odoo list view.
- Pricing ladder in `outreach/pricing_tiers.md`: free self-hosted, $1,200
  hardware, $1,500 bundle, $3,500 turnkey Orin Nano, $5,500 turnkey Orin NX,
  $99 connector, $100/hour spot consulting.
- Odoo partnerships contacts: Andrew Boeing (AE) escalated to Cameron and
  Collin on the partnerships team, 2026-11-09.

## Working method

Section 6 of the newest delta. In short: talk before coding; one change at
a time with a verification gate; verify with SQL before patching Flask;
small paste blocks; and at the site of any agreed decision, a comment of
the form `Agreed YYYY-MM-DD: <decision>, because <reason>`.

Code changes are whole-file replacements. No `sed`, no string substitution,
no blind patches. No heredocs for writing files; use `python3 -c` or `scp`.