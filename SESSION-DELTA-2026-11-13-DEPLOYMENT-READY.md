# MYARRA — SESSION DELTA, 2026-11-13 (Deployment Readiness)

This delta supersedes SESSION-DELTA-2026-11-12-PWA.md.
Read alongside PHILOSOPHY.md, HERBIE-ARCHITECTURE.md, and SESSION-DELTA-2026-11-07-REWRITE.md.

**Current entry point.** Read this first. Supersedes all earlier deltas.

**Before anything else, read PHILOSOPHY.md.** It is the governing document,
never superseded. If a proposed change contradicts it, the change is wrong.

## 0. WHAT THE PRODUCT IS

Myarra is a private, on-premise production tracker on an NVIDIA Jetson. It
closes the "Check" step of PDCA without a data janitor. It organises the floor
the way the plant organises it, not the way ERP organises it. ERP was written
by finance; its goal is costing, not productivity, and certainly not continuous
improvement.

Three components on one appliance:
- **Myarra** — the structured truth. Hourly runs, OEE, operator performance,
  changeover, downtime, PDCA.
- **Koorsus** — the unstructured truth. Document estate: SOPs, quality records,
  R&D test protocols, maintenance manuals, regulatory documents, training
  material, customer specifications. Answers with cited source. Refuses when
  the answer is not in the documents. Never invents.
- **Herbie** — the bridge. Answers questions that need both the numbers and the
  documents.

Herbie Light (Nano, five fixed questions) is built. Herbie Counselor (NX,
natural language, conversation, proactive coaching) is the upgrade tier.

## 1. WHAT WAS DONE (since the 11-12-PWA delta)

No new code was written in this short session. Two things were captured:

- **The design principle for capture:** paper wins at the moment of capture
  (zero friction, immediate), and loses everything after (aggregation, history,
  survival, feeding a PDCA). Myarra must be as fast as paper for capture and
  do what paper cannot for analysis. This is the value proposition in one
  sentence. Voice via Whisper is the mechanism that makes capture faster than
  paper, which is why it is not a nice-to-have.
- **The marketing frame:** ERP was written by finance guys. Its goal is
  costing. Not productivity. Not continuous improvement. This line is approved
  for marketing use.
- **The RAG marketing gap:** the current website undersells Koorsus. The
  document estate across quality, R&D, maintenance, regulatory, training, and
  commercial departments is larger and more valuable than the transaction data,
  and almost none of it is reachable by search. The differentiator is not that
  Koorsus reads documents; it is that it cites the source, refuses when the
  answer is absent, and runs on hardware the customer owns. A hallucinated
  lockout procedure is a liability, not a nuisance. The refusal is the feature.

## 2. WHAT CHANGED

No code changes. No commits beyond the delta itself.

## 3. WHAT IS VERIFIED (carried forward from 11-12-PWA)

- Herbie Light: five cards tested end to end, correct math, correct narratives,
  pre-computed summaries prevent hallucination.
- PWA: installable at https://192.168.100.2:5002/floor. Chrome shows the
  install prompt. HTTPS via Gunicorn + mkcert. Root CA trusted on Jetson and
  Windows.
- /floor: tile grid, tap-to-expand, POST writes to hourly_runs.
- Seven-line demo factory seeded with realistic unaccounted distribution.

## 4. WHAT IS NOT VERIFIED

- CSV round-trip has never been exercised with real data.
- No systematic functional test pass has been run.
- Whisper is not installed. /floor is text-only.
- Odoo master-data import is not built beyond the existing jobs endpoint.
- Odoo work order notes are not imported.
- No backup or restore procedure.
- No installation procedure document.
- Config paths are hardcoded in source.
- PWA install not yet tested on Android or iOS.
- Service worker caching not tested with the Jetson offline.

## 5. NEXT INSTANCE MUST DO (in order)

1. **CSV round-trip test.** Export demo data via the ten Setup templates
   (`/setup/download/<name>`). Inspect each CSV for column match and data
   integrity. Stand up a second empty database. Import the ten CSVs into it.
   Compare row counts, key totals, spot checks. This validates the onboarding
   path end to end.
2. **Full testing pass.** Every page, every Herbie card, /floor submission,
   Odoo connector. Produce a punch list. Fix in one pass.
3. **Website and one-pager rewrite.** Lead with the RAG estate. Lead with the
   three-part architecture. Use the finance-frame line. Add real Herbie
   screenshots and the Herbie Light vs Herbie Counselor tier distinction.
4. **Whisper install and /api/transcribe.** Then add a mic button to /floor
   that records, uploads, transcribes locally, and fills the notes field. Parse
   units and scrap from the transcript using the existing bot parsers.
5. **Odoo master-data import.** Extend the Odoo connector to read SKUs
   (product.product), work centers (mrp.workcenter), rates and stations
   (mrp.routing.workcenter), jobs (mrp.production), users (res.users). Add a
   setup screen where the customer groups work centers into Myarra lines.
   Changeover procedures remain the one CSV the customer supplies.
6. **Odoo work order notes** into jobs.handover_notes (strip HTML).
7. **Backup and restore.** USB backup on cron, tested restore procedure,
   retention policy. Required before any customer install.
8. **Installation procedure document.** Required before any customer install.
9. **Config extraction.** DB_PATH, cert paths, LLM_URL out of source.
10. **Kingswood follow-up** with Hillary Clark if no reply.

## 6. LESSONS / WORKING METHOD ADDITIONS

### The capture principle
Paper wins at capture. Software wins at analysis. Myarra must be faster than
paper at capture and do what paper cannot for analysis. Any feature that adds
friction to capture is a regression, however elegant.

### The organisational principle
Odoo has no concept of a "line." It has work centers. Myarra groups work
centers into lines because that is how the plant manager thinks. Competitors
inherit the work-center frame from ERP. This is a genuine differentiator, not
a limitation. Keep it.

### The refusal principle
Koorsus refuses to answer when the document does not contain the answer. A
confident wrong answer about lockout/tagout is a liability. The refusal is
the feature that makes the answers it does give trustworthy. Same principle
applies to Herbie: it must not speculate about a standard being wrong when
the data is incomplete. The correct diagnosis for a large unexplained gap
is "revisit with the line lead," not "the standard may need reevaluation."

### Small-model lesson (carried forward)
On a 3B model, you cannot tell the LLM to ignore data that is in the prompt.
It will read the forbidden data anyway. Escalation ladder:
  1. Prompt rule.
  2. Pre-compute the summary in Python; instruct the model to paraphrase.
  3. Strip the offending field from the payload before formatting.
  4. Skip the LLM entirely for that intent; return the summary verbatim.

### Patch discipline (proven twice)
When patches on a single file exceed three in one day, stop and rewrite the
whole file. Herbie Light went through four patches on herbie.py before we
stopped and rewrote it; every bug after the rewrite was diagnosable in one
step. Apply this rule earlier next time.

### SQLite HAVING clause
HAVING resolves column names to underlying table columns, not SELECT aliases.
HAVING alias_name > ? silently compares the wrong value. Always use the full
aggregate expression in HAVING.

### PWA prerequisites
A PWA requires a secure context. HTTP LAN addresses will not register a
service worker, install the app, or access the microphone. mkcert plus a
trusted root CA is the local-only path. Tailscale (subscription) and
Headscale (coordination server) are the remote-access paths and both
contradict the "no monthly fees" promise unless handled explicitly. For
in-building use, mkcert is the correct choice.

### Waitress and TLS
Waitress does not support TLS natively. Passing ssl_context raises
"Unknown adjustment." Use Gunicorn with --certfile and --keyfile.

### The Reddit lesson
The r/LeanManufacturing thread reached 5,500 views and produced substantive
engagement. One DM to a substantive commenter is safe if it opens with the
substance and includes no link. Public replies with links are self-promotion
and will be removed. The 9:1 ratio of helpful comments to product mentions
is the community norm. Do not cross-post to r/manufacturing; its rules
prohibit self-promotion outright.

END OF DELTA.