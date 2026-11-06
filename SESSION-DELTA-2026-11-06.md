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
