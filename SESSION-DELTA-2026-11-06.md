# MYARRA — SESSION DELTA, 2026-11-06

**Current entry point.** Read this first. Supersedes all earlier deltas.

DELTA on top of SESSION-DELTA-2026-11-05-B2.md and earlier. Read those for
architecture and history. Read this for today's work and where we stopped.

---

## 1. WHAT WAS DONE TODAY

### 1.1 Parking-lot items closed
- Demo maintenance event now seeded by populate_demo.py (idempotent,
  highest-production line-4 day, job_id linked to the running job).
  Commit 372c697.
- hourly_runs.sku_id populated at source by generate_demo_history.py.
  The COALESCE workaround in the view remains as belt-and-braces. 372c697.
- Maintenance history block on /job/<number>, below handovers, linked
  to /maintenance/<id>. Commit 3bc8187.
- "assets" -> "lines" rename: already done in Stage 2; item struck.
  Form fields are name="{{ tname }}" via INGEST_ORDER.

### 1.2 Comment pass and policy
Commit 1ece6bc. Docstrings expanded, comments added at fragile points:
views.py (why the file exists, COALESCE scar, drop order), recon.py
(A x P x Q rationale, operator_perf rescale warning), and the maintenance
seed rationale in generate_demo_history.py. Recorded as policy in the B2
delta Section 10.

NEW STANDING INSTRUCTION (agreed with owner 2026-11-06):
  When a design decision is agreed and then coded, add a comment at the
  site: "Agreed YYYY-MM-DD: <one-line decision>, because <one-line
  reason>." Three lines max. If more is needed, it goes in the delta and
  the comment points there by date. Applied to decisions, not mechanics.
  The owner's GPL intent: a purchaser must be able to modify successfully;
  comments and a short ARCHITECTURE.md serve that intent.

### 1.3 Line endings
Commit 9c28d0d. .gitattributes added: "* text=auto eol=lf" plus binary
markers for png/jpg/gif/pdf/gguf/db/sqlite/zip. The renormalize pass
converted CRLF to LF in demo-data/*.csv and docs/demo/setup/download/*.csv.
Verified by full ingest after renormalization: 192 rows loaded, 0 failed.

### 1.4 Passwordless sudo
/etc/sudoers.d/010-jeeves-nopasswd created, validated with visudo -cf
before relying on it, proven with sudo -k && sudo -n true.

### 1.5 LLM unit rename
llama-server.service -> koorsus-llm.service. Binary unchanged
(llama-server, llama.cpp). Dependents koorsus.service and myarra-bot.service
updated (After=/Wants= now reference koorsus-llm.service). Old unit
disabled and removed after the new one was proven active and port 8080
answered. HANDOFF.md updated in 6 places. Commit 0e92054.

---

## 2. STATE OF THE DATABASE (post-reseed, 2026-11-06)

  lines 5 | skus 10 | jobs 30 | users 1 | co_steps_v2 62
  co_event_changes 95 | experiments 5 | hourly_runs 285 (sku_id 285/285)
  maintenance_events 2 (telegram id=1 job_id NULL; demo id=2 job_id=24)
  shift_handovers 0

  views: 9 — v_oee_by_line_day, v_operator_perf_by_line_day,
  v_oee_daily, v_operator_performance, v_production_vs_standard,
  v_changeover_variance, v_unaccounted_by_line_day,
  v_maintenance_by_station, v_pdca_trend

Rebuild from scratch:
  python3 tools/populate_demo.py    # ingests CSVs, generates history
  python3 myarr_v2/views.py          # recreates all 9 views

---

## 3. SERVICES (renamed)

  koorsus-llm.service   — Qwen on port 8080 (formerly llama-server)
  koorsus.service       — RAG on port 5000
  myarr.service         — Flask on port 5002
  myarra-bot.service    — Telegram bot

Check:
  systemctl is-active koorsus-llm koorsus myarr myarra-bot

Note: .bak-rename files remain in /etc/systemd/system/ as safety; systemd
ignores them. Delete in a day or two once stability is proven.

---

## 4. WHERE WE STOPPED

Everything committed and pushed: origin/main = 0e92054. Working tree clean.

Confirmed operational:
  - /reconciliation shows two-measure summary (OEE, Operator)
  - Line 4 demonstrates divergence (~78% OEE vs ~93% Operator) on the
    seeded maintenance day
  - /job/WO-2026-024 shows the maintenance history block
  - all 9 views exist and are rebuildable via views.py
  - LF renormalized CSVs ingest cleanly (192/0)

---

## 5. NEXT — OWNER'S ORDER, CONTINUED

Still open on the parking lot, in rough order:

  1. Timestamp strategy across ALL tables (UTC/local split). The 5 Nov
     delta fixed two inserts; every DEFAULT CURRENT_TIMESTAMP has the
     same fault. Medium risk, needs its own focused slot.
  2. Work-order search and notes view on /job (60 min).
  3. ARCHITECTURE.md for GPL modifiers — module map, read order, fragile
     points. Owner explicitly wants purchasers to be able to modify.
  4. Priority contribution math on /pdca/log.
  5. co_event_changes for other measurement types.
  6. Optional owner/priority columns on jobs.csv.
  7. Small: artifexofabrika.com redirect, Carrd cancellation June 2027,
     Orin NX upgrade (funding), Upwork items.

Stage C views done. Stage D (/ask over views) is the next major phase,
not a parking-lot item.

---

## 6. WORKING METHOD — ADDITIONS FROM 2026-11-06

  - STEP BY STEP. The owner does not want long blocks printed in advance
    with "and then we'll do X, Y, Z." One command block at a time; wait
    for the output; respond. Pre-printing later steps burns tokens for
    no benefit.
  - The comment policy above (Section 1.2).
  - Structural checks over line counts. wc -l is soft; first line, last
    line, and grep count are the real gates.
  - Small paste blocks. Large blocks corrupt on paste.
  - The previous instance is a peer, not an oracle.

END OF DELTA.

---

## 8. ODOO INTEGRATION & MARKETING STRATEGY (Planning for Week of 2026-11-09)

### 8.1 The Model
- **Core App (Myarra):** Stays GPLv3.
- **Odoo Connector Module:** Will be a separate, proprietary module licensed under OPL-1 (Odoo Proprietary License). It will pull work orders from Odoo via API and push them to Myarra.
- **Hardware:** Jetson 8GB appliance sold as a commercial product. GPL compliance requires providing "Installation Information" only for this specific hardware, not every chip on the market.
- **Services:** Setup and consulting billed via Square invoices (direct to client).

### 8.2 App Store Launch Plan
- **Goal:** List the connector on the Odoo Apps Store by next week.
- **Pricing:** "Founding Member" program (first 10 free/discounted) to generate case studies.
- **Integration Path:** Read-only from Odoo. No data written back to the ERP to ensure zero risk for clients.
- **Next Technical Step:** Write the `__manifest__.py` and the XML-RPC client to test against the local Odoo Linux instance.

END OF DELTA.

- VISUAL HOURLY CHART (Requested 2026-11-06): Add a clickable, visual hour-by-hour chart for each line (e.g., bar chart of actual vs expected units per hour). Could resurrect the orphaned /shift/ route or build a dedicated view.

END OF DELTA.

### 8.3 Competitive Deep Dive & Strategic Moats
- **Klyff**: Edge AI/vision platform. $25k-$75k. Software only, requires complex setup.
- **Lyzr.ai**: Enterprise AI. $12M ARR. Appliance starts at $10k. Way too complex/expensive for small plants.
- **OEE Connect (MCA Connect)**: Microsoft Ecosystem. Closest functional competitor, but requires Power Apps and Azure infrastructure.
- **Vorne XL / Raven.ai**: Owned hardware OEE, but no voice AI, no two-measure design.
- **Myarra's Moats**: 
  1. Target market is $1M-$10M revenue plants. Big competitors ignore this segment.
  2. Turnkey $5,500 appliance vs $25k+ enterprise software.
  3. Voice-first, no subscription, data stays local.
  4. Future roadmap: Vision/sensor detection module using Orin Nano edge capabilities.

### 8.4 Branding & Domains
- Consider purchasing artifexofabrica.ai to redirect to the main site for a tech-forward look.

### 8.5 Investor Considerations (Discussion)
- Bootstrapping via consulting/diagnostics revenue vs raising capital.
- VC funding would likely force a SaaS pivot (abandoning the "owned hardware" model) and targeting enterprise clients, sacrificing the small-plant niche.
- Better to stay private, agile, and focused on the $5,500 appliance until a clear scaling path is needed.

END OF DELTA.

### 8.5 Investor Strategy & 90-Day Focus (Critical)
- **VC Avoidance:** Owner has negative prior VC experience (forced SaaS pivot, max revenue over sustainable profit). Decision: DO NOT seek VC funding.
- **Financing Path:** Bootstrap via consulting/diagnostic revenue. Seek Angel investors or Strategic Partners (e.g., local automation distributors) only if hardware inventory capital is needed later.
- **90-Day Constraint:** Cash flow is the priority. Product "nice-to-haves" (Stage D, vision modules, .ai domains) are secondary to landing the first 3 paying clients (Diagnostic + Appliance bundle at $8,000).
- **Action:** Re-prioritize marketing and outreach immediately. Code development pauses if it conflicts with sales effort.

END OF DELTA.

### 8.6 Shift Report & Bot Notes - Fixes Needed
- **Issue 1 (Shift Timestamps):** `generate_demo_history.py` assigns shift label '1' (S1) but the actual timestamps are in the afternoon (14:00-17:00). Fix: Align shift labels with actual timestamps (S1 = 07:00-15:00, S2 = 15:00-23:00, S3 = 23:00-07:00).
- **Issue 2 (Full Skeleton):** The `/line/<id>/report` route needs to render the full 8-hour skeleton (H1-H4, Lunch, H6-H8) regardless of data. Empty hours should show Target but '—' for Actuals.
- **Issue 3 (Bot Notes Fallback):** The `note:` command fails with "No active job" if the session is idle. Fix: Fall back to the most recent `hourly_run` on the user's line if no active job is set.

END OF DELTA.

- FACILITY-LEVEL OEE / TEEP (Raised 2026-11-07): Owner distinguishes line-level OEE (current) from facility-level performance, which should measure actual output against ALL available minutes in the year, including scheduled downtime. This is technically TEEP (Total Effective Equipment Performance), not OEE. Requires: (a) a plant operating calendar (scheduled vs. unscheduled hours), (b) a facility rollup view v_teep_by_period, (c) clear labeling so a manager knows which number they are looking at. Current v_oee_by_line_day is "conditional OEE" (recorded event minutes only). Do not conflate. Add when facility reporting is scoped.

END OF DELTA.

- CALIBRATION & VERIFICATION STEPS (Raised 2026-11-07): Owner noted that many changeovers include a mandatory verification step (e.g., lab weights, color shift proof, alcohol content). The flexible `co_steps_v2` table handles this already, but we should ensure the UI makes these steps prominent (perhaps a `step_type='verification'` flag) so they aren't skipped. Also noted the value of `/ask` to query variance trends by SKU and comment (e.g., "why did we underfill?").

END OF DELTA.
