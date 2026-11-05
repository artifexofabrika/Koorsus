# MYARRA — SESSION DELTA, 2026-11-05

DELTA on top of SESSION-DELTA-2026-11-03.md and HANDOFF.md (2026-11-03).
Read those for architecture, invariants, and history. Read this for today's
work, the design decisions made, and where we stopped. Do not re-read the
main handoff in full unless this file points you there.

---

## 1. WHAT WAS DONE TODAY

### 1.1 Honest changeover data
Commit f3f91f4.
- Richer BOMs so changeovers show the components that actually change:
  cosmetics 4 (case, formulation, shrink, box), beverage 3 (can, label, pak),
  jewelry 5 (jar, cap, brush, basket, formulation).
- The seed now computes co_event_changes from the BOM diff at seed time via
  write_co_event_changes(). Structural: components list can never drift from
  the BOMs again.
- Standards raised: cosmetics 65, beverage 58, jewelry 45. Placeholder
  numbers, owner should overrule from his own experience.
- Two template fixes: changeover_list.html and changeover.html no longer
  substitute '&mdash;' (which Jinja autoescaped to literal text). Now plain
  'none recorded' and '-'. Entity still appears in the LINE column, correctly,
  because it is raw HTML outside {{ }} and renders as an em dash.

### 1.2 Demo tooling
Commit b85684f.
- tools/make_demo_data.py — exports ten onboarding CSVs from the current DB
  into demo-data/ in template column format. Idempotent.
- tools/generate_demo_history.py — reads master data, produces 30 days of
  hourly runs, line events, changeovers (with computed co_event_changes),
  staggered running shift, five experiments. Refuses if history exists;
  --force wipes first.
- tools/populate_demo.py — one command, wipe + ingest ten CSVs through the
  REAL onboarding path + generate history. Proof that the upload path works.
  Verified: 192 rows loaded, 0 failures.
- demo-data/ holds all ten full CSVs (committed).

### 1.3 Admin ops — export and reset
Commit 46f6652.
- admin_ops.py Flask Blueprint:
  - GET /setup/export — zip of 19 CSVs plus MANIFEST.txt. All tables.
  - POST /setup/reset — soft or hard, typed RESET required.
- SOFT reset wipes: downtime_events, hourly_runs, co_event_steps,
  co_event_changes, co_events, line_events, bot_sessions. Preserves all
  master data, jobs, experiments, users, settings.
- HARD reset wipes everything above PLUS fishbone_causes,
  experiment_actions, experiments, jobs, sku_bom, line_sku_rates,
  co_steps_v2, co_procedures_v2, skus, component_types, lines.
  Preserves ONLY users and settings.
- Neither reset wipes users. Owner was explicit. Also deliberate:
  preserving users means the Telegram bot keeps working after reset.
- Reset messages shown at the top of /setup (success green, refused red).
- Danger zone at the bottom of /setup with two radio buttons and a
  RESET text input.

### 1.4 Outreach kit
Commit 5b55a7c.
- outreach/cv.md, odoo-advisory.md, reperio-note.md, outreach.css,
  md_to_pdf.py.
- PDFs rendered by weasyprint (installed via apt libs + pip). Are NOT in git,
  regenerated with: python3 md_to_pdf.py
- CV restructured from job-seeker to consultant. Leads with results
  ($350k→$8M, 84%→95% FTQ, 86%→2% reject). Includes current firm
  Artifexo Fabrika. The non-linear work history is stated as intentional
  (consultant's CV shape, not employee's).
- Advisory sheet aimed at Odoo partners and mid-implementation
  manufacturers. Deliberately carries no prices — quote each engagement.
- Reperio note applied (reference 246204, NJ snack food, $90–$100 band).

### 1.5 Maintenance as first-class event
Commit 3fff02d.
- New table maintenance_events: line_id, job_id, station, started_at,
  ended_at, aggregate_actual_min, category, symptom, resolution, parts_used,
  technician, called_by, reason_code, notes, source, user_id, raw_text,
  created_at.
- line_events gains maintenance_event_id column (mirrors co_event_id).
- Bot flow: 'maintenance <station> <symptom>' opens event and state; station
  is parsed if it matches a known station name (from co_steps_v2.station
  UNION downtime_events.station). 'end maintenance' closes the event, computes
  wall-clock minutes, resumes prior state, and enters a THREE-step notes
  prompt: resolution → parts_used → technician. Each accepts 'skip'.
  'me' on technician fills the caller's name. 'cancel' aborts the prompts.
- Web: /maintenance list with line + station + window filters (7/14/30/90);
  /maintenance/<id> detail with editable symptom, resolution, parts_used,
  technician, called_by, reason_code, notes, category.
- category is unplanned/breakdown/planned/PM, default unplanned.

### 1.6 Stage B — shift handovers history
Committed and pushed (see git log for hash; end of session).
- New table shift_handovers: job_id, line_id, from_user_id, to_user_id,
  notes, open_issues, created_at, taken_at.
- Backfilled from jobs.handover_notes as single-entry histories
  (from_user_id null, unknown). Demo had none, so backfill was 0 rows.
- Bot: cont_handover_notes now inserts a shift_handovers row in addition to
  updating jobs.handover_notes (kept for backward compatibility). h_takeover
  closes the most recent open handover (fills to_user_id + taken_at) and
  prints that handover's notes.
- Web: /job/<number> gains a Handover history block below the hourly table,
  chronological, most recent bold.

---

## 2. DESIGN DECISIONS MADE TODAY — CAREFUL, THESE ARE LOAD-BEARING

### 2.1 OEE vs operator performance — two different measures
Same data, two views. This is the core of the two-measure design and must
not be collapsed into one number.

OEE (administrative measure): counts everything.
  - Unscheduled maintenance and breakdowns are availability losses.
  - Changeover is an availability loss.
  - Scrap counts against quality.
  - Lunch and CIP do NOT count (scheduled stops).
  - Answers: "of the time we scheduled, how much produced at rate and to
    spec?"

Operator shift performance (what the floor sees): excludes what the operator
did not cause.
  - Breakdowns and unscheduled maintenance removed from the denominator.
  - Scrap does NOT count (quality is a process measure, not a shift measure).
  - Changeover and idle DO count (the operator carries those).
  - Answers: "during the time the line was actually available, did the
    operator run it well?"

Rationale: holding breakdowns against the operator teaches him to under-report
and corrupts every number downstream. Holding scrap against him does the
same. But OEE must count both, or the OEE number is a fiction no plant
manager will trust.

Display format on /reconciliation: "Line 1: OEE 71%, operator performance
94%." That one sentence tells a manager more than either number alone.

### 2.2 Odoo direction — pull only, never push
Myarra reads from Odoo's API. Myarra never writes into Odoo. Pushing into
Odoo would make Myarra an accounting/inventory actor, which is out of scope
by definition. The dependency is one-way: Myarra depends on the ERP, not
the reverse.

When ERP API (item 8 on the future list) is built: expose Myarra's data via
GET /api/v1/... for Odoo or anything else to read. Separately, a small Odoo
client pulls job orders and SKU lists so a consultant does not type them
twice. Both directions are reads.

### 2.3 Maintenance time — accounted, not expected
A line in maintenance is not producing. Those minutes are accounted time in
reconciliation but are NOT expected-production time. Otherwise every job
with a breakdown looks like it underperformed against standard.

### 2.4 Recommended OEE formula (pending owner approval at B2)
Classic OEE: A × P × Q.
  A = production_time / (production + changeover + unplanned_maint + idle
      + unscheduled)
  P = actual / (ideal_rate × production_time / 60)
  Q = (units − scrap) / units
Operator performance = actual / (ideal_rate × (production + changeover +
idle + unscheduled) / 60). Same denominator as A, minus unplanned maint.

Owner has not yet chosen among A (classic), B (simplified), C (shift) for
the OEE number itself. Recommendation was A. ASK HIM FIRST THING AT B2.

### 2.5 The plant lifecycle maintenance memory
Owner's framing: a $3M/year plant does not have a standard procedure for
most of what goes wrong. It has memory — last time the labeler threw E44,
Ray reseated the sensor and it took twenty minutes. Capturing that
organically, as it happens, is worth more than any ERP module.

Three design points:
- A symptom, a resolution, and a way to find it again (reason_code).
- Do NOT build a rigid taxonomy. Station names and reason codes emerge
  from use (derived from history, like component filters on /changeover).
- Koorsus is the answer to "what did we do last time" — index the
  maintenance notes into Koorsus and the question becomes a RAG query over
  the plant's own maintenance history. No new AI work needed.

---

## 3. KNOWN BUG — TIMESTAMP DRIFT (fix scripted, applied? CONFIRM)

created_at uses SQLite DEFAULT CURRENT_TIMESTAMP (UTC). taken_at and
started_at/ended_at use Python datetime.now().isoformat() (local).

Observed: created_at 13:56:26 vs taken_at 08:56:35 on the same row — five
hours apart. Eastern time vs UTC.

Fix was written but its application to bot_v2.py needs confirmation. If not
applied:
  - In bot_v2.cont_handover_notes, the shift_handovers insert must pass
    created_at explicitly: (job_id, line_id, from_user_id, notes, created_at)
    VALUES (?,?,?,?,?) with datetime.now().isoformat() as the fifth value.
  - In bot_v2.h_start_maintenance, the maintenance_events insert must pass
    created_at explicitly.
  Either way, a reseed clears existing rows.

---

## 4. STATE OF THE DATABASE

After last reseed (end of Stage B, before B2):
  lines                5
  skus                10
  jobs                30
  users                1
  co_steps_v2         62
  co_event_changes    95
  experiments          5
  hourly_runs        285
  maintenance_events   0 (cleared by reseed — fine)
  shift_handovers      0 (cleared by reseed — fine)

To restore fully populated demo state from any condition:
  curl -s -X POST -d "confirm=RESET&reset_mode=hard" \
    http://127.0.0.1:5002/setup/reset
  cd ~/Client-Demo && python3 tools/populate_demo.py

---

## 5. WHERE WE STOPPED — STAGE B2 IS NEXT

Stage B2: add OEE and operator performance to /reconciliation.

NEXT INSTANCE MUST DO, IN ORDER:

1. Confirm the timestamp fix applied to bot_v2.py (Section 3). If not, apply
   it with the same guarded method (count-checked anchors, py_compile after
   write).
2. ASK THE OWNER: which OEE formula — A (classic A×P×Q, recommended),
   B (simplified actual/expected), or C (shift performance variant)?
   Recommend A. Explain the choice briefly.
3. Wait for these three fragments (do not write blind):
     grep -n "def reconciliation" ~/Client-Demo/myarr_v2/app.py
     sed -n "$(grep -n 'def reconciliation' ~/Client-Demo/myarr_v2/app.py \
       | cut -d: -f1),+50p" ~/Client-Demo/myarr_v2/app.py
     cat ~/Client-Demo/myarr_v2/templates/reconciliation.html
4. Design B2 with two views (built in Step 1 of B2, useful immediately):
     v_oee_by_line_window
     v_operator_perf_by_line_window
   Both views take line and window (days). Return the components, not just
   the ratio, so the numbers can be inspected.
5. /reconciliation gains two columns per line: OEE, Operator. Beneath the
   table: "OEE counts all losses, including unscheduled maintenance.
   Operator performance excludes time the operator did not cause —
   breakdowns and unplanned maintenance. Both are correct; they answer
   different questions."
6. Verify: known demo numbers should be plausible (OEE in 60s–80s,
   operator in 90s). If OEE is under 30% or above 110%, a denominator is
   wrong. Diagnose before committing.

---

## 6. FUTURE STATE — reordered per owner, 2026-11-03

  1. Maintenance as third billable event — DONE today
  2. Shift handovers history — DONE today
  3. Relog with audit trail
  4. Multi-line leads
  5. Query-level reporting (Stage C: views, then Stage D: /ask)
  6. Recommendations on top of queries
  7. PWA with PIN pairing
  8. ERP API

The next three after B2:
  - Stage C (data lake views): v_oee_daily, v_operator_performance,
    v_unaccounted_by_line_day, v_maintenance_by_station,
    v_production_vs_standard, v_changeover_variance, v_pdca_trend.
    Useful without any LLM. /reconciliation can rebuild on top of them.
  - Stage D (/ask): text-to-SQL choosing among the views, refusing when
    the question does not match. Then index maintenance notes into
    Koorsus for the "what did we do last time" corpus.
  - Then items 3 and 4 on the future list.

The owner's stated example for Stage C/D:
  "How many minutes of unaccounted time did we have last week across all
   five lines by line?" → "Line 1 missing 62 minutes, Line 2 missing 15."
v_unaccounted_by_line_day is the view that answers it.

---

## 7. PARKING LOT — unchanged from 2026-11-03 plus two

From 2026-11-03 (still open):
  - artifexofabrica.com (no k) redirect
  - rename llama-server.service → koorsus-llm.service
  - passwordless sudo before client install
  - .gitattributes line-ending pass
  - cert.pem in git history (low risk)
  - Telegram token rotation (at end, per owner)
  - co_event_changes for other measurement types
  - priority contribution math on /pdca/log
  - work-order search and notes view
  - optional owner / priority columns on jobs.csv
  - Carrd cancellation June 2027
  - Orin NX upgrade (funding)
  - Upwork video intro
  - Upwork rate reconciliation ($60/hr advisory vs $1,385 day rate)
  - Project Catalog: replace the $600 entry with Diagnostic and Install
    entries

New today:
  - Reconcile timestamp strategy across ALL tables (Section 3). Every table
    using DEFAULT CURRENT_TIMESTAMP has the same UTC/local split.
  - Maintenance event should appear on /job/<number> alongside handovers
    (deferred from Stage A — add when B2 or C touches job_detail.html).

---

## 8. WORKING METHOD — UNCHANGED, RESTATED

  - Talk before coding. Plan, approval, then code.
  - Whole files, not patches. Guarded replacements are acceptable for small
    edits IF every anchor is count-checked (== 1) and py_compile runs after
    the write. Stage B today failed that discipline once: 'cp = job[
    "case_pack"] or 1' appeared in dashboard() with deeper indent, the
    replace hit the wrong one, IndentationError. Multi-line anchors when
    a single line cannot be guaranteed unique.
  - One change at a time, verification gate between each.
  - Verify with SQL before patching Flask.
  - Push back on bad architecture.
  - No em dashes in customer-facing prose. Em dashes in internal docs are
    fine and match house style.
  - Voice-to-text is lossy; read for intent; ask when uncertain.
  - When token budget is tight: write a delta like this one at each
    verified milestone rather than re-pasting old handoffs. The point of
    this file is that the next instance reads ~200 lines, not 60,000
    tokens.

---

## 9. HOW TO RESUME

SSH from Windows PowerShell:
  ssh jeeves@192.168.100.2

Check estate:
  systemctl is-active llama-server koorsus myarr myarra-bot
  for u in / /reconciliation /changeover /maintenance /pdca /setup \
           /setup/verify; do printf "%-20s " "$u"; \
    curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:5002$u"; done

Check DB:
  sqlite3 /mnt/lake/myarra.db "SELECT
    (SELECT COUNT(*) FROM lines),
    (SELECT COUNT(*) FROM jobs),
    (SELECT COUNT(*) FROM co_event_changes),
    (SELECT COUNT(*) FROM hourly_runs),
    (SELECT COUNT(*) FROM maintenance_events),
    (SELECT COUNT(*) FROM shift_handovers);"
  # expect: 5|30|95|285|0|0

Check git:
  cd ~/Client-Demo && git log --oneline -10

Repository: github.com/artifexofabrika/Koorsus (public, GPL v3).
Push requires username artifexofabrika + personal access token.

---

END OF DELTA.
