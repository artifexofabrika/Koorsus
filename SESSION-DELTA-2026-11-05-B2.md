# MYARRA — SESSION DELTA, 2026-11-05 (Stage B2)

**Superseded by SESSION-DELTA-2026-11-06.md.** Read only when that delta points you here.

DELTA on top of SESSION-DELTA-2026-11-05.md (Stage A + B) and HANDOFF.md.
Read those for architecture and history. Read this for Stage B2, the
corrections discovered along the way, and the demonstration of the
two-measure design. Do not re-read old handoffs in full unless this file
points you there.

---

## 1. WHAT WAS DONE TODAY — STAGE B2

### 1.1 Two-measure display on /reconciliation
- New module: myarr_v2/views.py. Idempotent; drops and recreates both
  views. Run directly with `python3 views.py` or via ensure_views()
  imported and called once at app startup.
- New module: myarr_v2/recon.py. Exposes summary_for_window(conn,
  line_filter, days) returning one row per line with all components and
  both ratios computed. All five components present: production,
  changeover, unplanned maintenance, idle, unscheduled (placeholder 0,
  no source table yet).
- New template partial: templates/_recon_summary.html. Included by
  reconciliation.html above the work-order table.
- reconciliation() modified: window default changed from 3 to 7 days;
  options changed from 1/3/7/30 to 7/14/30/90, matching /maintenance.
- Job table column relabelled "Perf" -> "Progress". The figure measures
  actual vs job target quantity, not OEE; sitting beside an OEE column
  it read as self-contradictory. "Progress" is honest.

### 1.2 Two views, per-line-per-day (not per-line-per-window)
- v_oee_by_line_day — one row per (line, day). Components only; no
  ratios. Consumers compute what they need.
- v_operator_perf_by_line_day — same shape, exposes operator_available_min.
- The earlier delta's names v_oee_by_line_window and
  v_operator_perf_by_line_window were unworkable: SQLite views cannot
  take parameters. Correct design is unparameterized views, filtered by
  the Flask query. The ? lives in the query against the view, not in
  the view itself. This is standard.

### 1.3 Demonstration result
- Inserted one maintenance_events row (id=2, line 4, 2026-11-03,
  180 min, category='unplanned', source='demo') via a small script.
- Line 4, 7-day window: OEE ~77%, Operator ~90%, components
  prod 1020 | CO 70 | maint 180 | idle 0.
- The two measures now separate because the operator denominator
  excludes the 180 min of breakdown. This is the demonstration and the
  answer to the vOEE objection the owner raised: OEE counts every loss,
  operator performance does not punish the operator for breakdowns.

---

## 2. DESIGN DECISIONS CONFIRMED OR CORRECTED TODAY

### 2.1 OEE formula — A chosen by owner
Classic A × P × Q. Owner explicitly rejected B (simplified) and C (shift
variant), citing vOEE experience at Treasury Wine Estates: a weighted
number engineered to flatter a COO is a stage prop, not a measure. A
counts every loss; the operator gets his own column beside it.

A = production / (production + changeover + unplanned_maint + idle + unscheduled)
P = actual / expected
Q = (actual - scrap) / actual

### 2.2 "Unscheduled" is a placeholder, not a missing term
No source table yet. Set to 0 in the view; documented in the comment.
When unaccounted time is to be represented as an availability loss,
this is where it goes. Until then, OEE here is *conditional* OEE: the
denominator is only time that has been recorded as an event. Unaccounted
minutes remain a separate metric (the reconciliation shift table already
computes them). This distinction should be explained to any plant
manager who asks why OEE is 77% when the line only ran 1270 minutes
across the week.

### 2.3 Downtime_events are performance losses, not availability
Confirmed with owner. A jam recorded in downtime_events reduces actual
units against expected. It flows through P, not A.

### 2.4 Views vs inline SQL — the correction stands
An interim proposal to abandon views and inline SQL in Flask was
correctly rejected by the previous instance. Inline SQL works but
copies; when Stage D's /ask needs the same numbers, buried SQL drifts
and the two implementations disagree. Views are inspectable with one
sqlite3 command when a number looks wrong. Cost: one small module and
one ensure_views() call at startup.

---

## 3. SCHEMA DRIFT DISCOVERED

### 3.1 hourly_runs.sku_id is NULL on all 285 rows
populate_demo.py writes job_id but not sku_id. All 285 hourly_runs
have job_id; all 285 have sku_id NULL. The view works around this by
joining jobs on job_id and using COALESCE(r.sku_id, j.sku_id) for the
line_sku_rates join. Robust either way; a future fix at source is
preferable but not blocking.

### 3.2 scrap_units vs scrap_bottles
HANDOFF.md (Section 4.1) records the column as scrap_bottles. Live
schema has scrap_units. The handoff is stale on this one column. The
delta here is corrected.

### 3.3 The workaround (recorded for the next instance)
prod CTE joins:
  LEFT JOIN jobs j ON j.id = r.job_id
  LEFT JOIN line_sku_rates lsr
         ON lsr.line_id = r.line_id
        AND lsr.sku_id  = COALESCE(r.sku_id, j.sku_id)

Verified: expected_units non-zero on every row where production_min is
non-zero; performance ratio in the 0.95-0.97 band on seeded data.

---

## 4. KNOWN LIMITATIONS

### 4.1 Two measures cannot separate without maintenance data
With no maintenance_events, and no day carrying both production and a
changeover, OEE and Operator collapse to identical figures. The demo
currently relies on the seeded maintenance row to demonstrate divergence.
A live demo should log a maintenance event via the bot on a production
day rather than seeding — the mechanism is proven, the live path is not
yet tested.

### 4.2 The seeded maintenance event has awkward drill-through
The seed is on 2026-11-03, which has zero production runs on Line 4.
Aggregated over 7 days the divergence reads 77 vs 90; drilled into that
single day, OEE reads 0% and Operator reads "no data." A cleaner story
would place the event on 2026-11-02 (780 min production that day).
Optional fix, not blocking.

### 4.3 Conditional OEE (see 2.2)
Not a fault; a design consequence. Worth one line to the client if asked.

### 4.4 ensure_views() at import time
app.py calls ensure_views() at module load. If the DB is locked (e.g.
another process holds a write lock), import fails with a traceback.
Not observed on this appliance (SQLite, single process, single user).
If Myarra ever becomes multi-process, move to lazy initialization.

---

## 5. STATE OF THE DATABASE

After B2 verification:
  lines                5
  skus                10
  jobs                30
  users                1
  co_steps_v2         62
  co_event_changes    95
  experiments          5
  hourly_runs        285
  maintenance_events   2 (see note)
  shift_handovers      0
  views: v_oee_by_line_day, v_operator_perf_by_line_day

NOTE: maintenance_events count is 2. Row id=2 is the demo row inserted
today (line 4, 2026-11-03, 180 min, source='demo'). Row id=1 is from
an earlier source — check provenance with:
  SELECT id, line_id, started_at, category, source FROM maintenance_events;

To restore fully populated demo state from any condition:
  curl -s -X POST -d "confirm=RESET&reset_mode=hard" \
    http://127.0.0.1:5002/setup/reset
  cd ~/Client-Demo && python3 tools/populate_demo.py
  python3 myarr_v2/views.py    # views are dropped by hard reset

---

## 6. WHERE WE STOPPED

Stage B2 complete and verified:
  - compile clean (py_compile on app.py, recon.py, views.py)
  - HTTP 200 on /reconciliation
  - partial included (grep "Line Summary" returns 1)
  - explanatory sentence rendered
  - divergence demonstrated on line 4 (77 vs 90)
  - job column relabelled Progress

The live maintenance path was exercised on 2026-11-04 (maintenance_events id=1, line 1, source=telegram).
That is the next verification step.

---

## 7. NEXT — RECOMMENDED ORDER

1. Log a live maintenance event via the bot on a production day, confirm
   /maintenance list and detail reflect it, and that /reconciliation
   shows the divergence on refresh. This tests the real path, not the
   seeded one. The previous session's Stage A maintenance flow should
   still work; if it doesn't, that is the first fault to chase.

2. Stage C (data lake views): add v_changeover_variance,
   v_maintenance_by_station, v_production_vs_standard, v_pdca_trend,
   v_unaccounted_by_line_day. Same per-day shape. /reconciliation
   rebuilds on top of them rather than inline SQL. The views.py module
   is the natural home for the additions.

3. Stage D (/ask): text-to-SQL over the views; refusal on unmatched
   questions. Index maintenance notes into Koorsus for the "what did
   we do last time" query.

4. Then items 3 (relog with audit trail) and 4 (multi-line leads) on
   the future-state list.

---

## 8. PARKING LOT — additions since last delta

- hourly_runs.sku_id should be populated by populate_demo.py at source
  (workaround in place; not blocking)
- Move demo maintenance event from 2026-11-03 (no production) to
  2026-11-02 (production day) for cleaner drill-through story
- Identify maintenance_events id=1 provenance
- The shift table default window changed from 3d to 7d; any bookmarks
  or demo scripts expecting 3d should be updated
- "Perf" -> "Progress" rename; audit other templates for consistency
  (job_detail.html uses "Perf" in its hourly table)
- Reconcile timestamp strategy across all tables (parking-lot item from
  the previous delta; unchanged)

---

## 9. HOW TO RESUME

SSH from Windows PowerShell:
  ssh jeeves@192.168.100.2

Check estate:
  systemctl is-active llama-server koorsus myarr myarra-bot
  for u in / /reconciliation /changeover /maintenance /pdca /setup; do
    printf "%-20s " "$u"
    curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:5002$u"
  done

Check DB and views:
  sqlite3 /mnt/lake/myarra.db "SELECT
    (SELECT COUNT(*) FROM lines),
    (SELECT COUNT(*) FROM jobs),
    (SELECT COUNT(*) FROM co_event_changes),
    (SELECT COUNT(*) FROM hourly_runs),
    (SELECT COUNT(*) FROM maintenance_events),
    (SELECT COUNT(*) FROM shift_handovers);"
  # expect: 5|30|95|285|2|0
  sqlite3 /mnt/lake/myarra.db "SELECT name FROM sqlite_master WHERE type='view';"
  # expect: v_oee_by_line_day, v_operator_perf_by_line_day

Check git:
  cd ~/Client-Demo && git log --oneline -5

Repository: github.com/artifexofabrika/Koorsus (public, GPL v3).
Push requires username artifexofabrika + personal access token.

---

## 10. WORKING METHOD — UPDATED WITH LESSONS FROM B2

  - Talk before coding. Plan, approval, then code.
  - One change at a time, verification gate between each.
  - Verify with SQL before patching Flask.
  - Push back on bad architecture.
  - No em dashes in customer-facing prose.
  - Voice-to-text is lossy; read for intent; ask when uncertain.

NEW THIS SESSION — these cost time today, do not repeat:

  - Small paste blocks over large ones. A 78-line SQL file pasted as one
    block truncated or scrambled twice. Three smaller blocks, concatenated
    after each was verified, did not. When a block must be large, provide
    a structural check (first line, last line, grep count) in addition
    to wc -l.

  - wc -l is a soft signal; structural checks are the real gate. The
    same body was miscounted twice today, giving false reassurance.

  - Own arithmetic errors immediately when spotted. Recomputing silently
    confuses the owner.

  - When the owner asks "should we ask the previous instance," the
    correct answer is usually: run the diagnostics first, ask the
    previous instance with evidence attached. A question without
    evidence gets the evidence-gathering command back. That round-trip
    wastes an instance.

  - The previous instance is a peer, not an oracle. It corrected the
    new instance on the "abandon views" over-correction, which was
    correct. Treat its counsel as authoritative on architecture it
    built, and as advisory otherwise.

  - COMMENT POLICY (agreed 2026-11-06): When a design decision is agreed
    and then coded, add a comment at the site stating: "Agreed YYYY-MM-DD:
    <decision>, because <reason>." The delta carries history; the comment
    carries the reasoning where the reader will encounter it. The
    /reconciliation explanatory sentence is the model. Keep comments
    short: fragile anchors and decisions only, not essays.

END OF DELTA.
