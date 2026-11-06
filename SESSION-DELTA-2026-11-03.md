# MYARRA — SESSION DELTA, 2026-11-03 (evening)

**Superseded by later deltas.** Read only when pointed to.

This is a DELTA on top of HANDOFF.md (2026-11-03 afternoon) and the
2026-11-01 and 2026-10-31 handoffs. Read those for architecture,
invariants, and history. Read this for what changed today and what is
next. Do not re-read the old handoffs in full unless something here
points you there.

---

## 1. WHAT WAS DONE TODAY

### 1.1 Onboarding Stage 1 — DONE, VERIFIED
Files written:
  onboarding.py            (new) ten template definitions + generate_csv()
  app.py                   (whole-file rewrite) adds /setup/download/<name>
  templates/setup.html     (whole-file rewrite) shows ten download links

Verification passed:
  All eleven routes return 200 (the /setup page plus ten downloads).
  Three CSV bodies spot-checked (lines, co_steps, sku_bom) — headers
  and two example rows correct.

### 1.2 Onboarding Stage 2a/2b — DEPLOYED, VERIFIED
Upload handlers for all ten templates with natural-key resolution and
per-row error reporting. Reset button with typed confirmation.

Verified by uploading all ten templates back into the demo database:
  uploaded=2 succeeded=2 failed=0 on every template.
  UPSERT proven idempotent: uploading lines.csv twice leaves count at 5.

---

## 2. THE RISK STAGE 2 REVEALED — FIX BEFORE CLIENT

co_steps_v2 uses DELETE-then-INSERT per procedure on upload. Uploading a
PARTIAL co_steps.csv therefore silently deletes the full procedure and
replaces it with the rows in the CSV.

Observed live: procedure line 1 COS-CMP-RS -> COS-CMP-SD went from 6
steps to 2 because the template contained only two example rows.

This is dangerous at a client site. The guard, when built:
  - Refuse the delete for a procedure unless the CSV contains all steps
    for it, OR
  - Add an explicit "full replace" checkbox per procedure upload.

This is a small item. It is NOT in Stage 2c. It should be done before
any client upload of co_steps.csv.

---

## 3. DESIGN DECISIONS CONFIRMED TODAY

1. Path A for v1. Natural keys in CSVs; uploader resolves to internal
   IDs. Header names must match; column order is free (csv.DictReader).

2. Stage 2c (mapping form: "which of your columns is the job number?")
   DEFERRED. Build only after a real customer brings a real sheet and
   we can see what actually needs mapping.

3. Jobs table is the eventual integration point for both CSV upload and
   an Odoo API. Same rows, different door.

4. Unknown columns in a customer CSV are silently ignored. The customer
   can hand us their full Smartsheet export; we take what we can use.

5. Optional jobs.csv columns noted for a later pass: owner (free text),
   priority (LOW/MED/HIGH). Matches the customer's Smartsheet vocabulary.
   Both nullable. Not built.

6. Smartsheet-vs-Odoo question settled: the customer's weekly schedule
   lives in a visual planning canvas (Smartsheet/Excel), not an Odoo
   scheduling engine. Our jobs.csv is the right shape for the extract.
   The gap Myarra fills is visible in the Smartsheet itself: Planned
   Output / Actual Output / Variance are all manual there. Myarra
   automates them.

---

## 4. THE REPRIORITIZED LIST (from the 2026-11-03 Addendum)

Near-term, before any customer engagement:
  1. Onboarding templates              (Stage 1 + 2a/2b DONE; Stage 3 next)
  2. Query-level reporting (text-to-SQL over data lake)
  3. Recommendations on top of queries
  4. PWA with PIN pairing
  5. Maintenance as third billable event
  6. Shift handovers history table
  7. Multi-line leads
  8. Relog with audit trail
  9. ERP API                            (end of the pre-customer list)

Genuinely after first customer:
  - Orin NX upgrade (funding-dependent)
  - Recommendations refinement based on real usage
  - Whatever a client asks for that we have not anticipated

Nothing above item 9 is gated on a customer engagement. It is work we do
because we have time.

Also newly on the list, small:
  - co_steps delete-then-insert guard (see Section 2)
  - Rename the upload form field "assets" to "lines" for consistency
    with the filename lines.csv. Cosmetic but confusing.

---

## 5. STATE OF THE DATABASE

Pristine as of this session, after reseed and cleanup:
  lines                5
  skus                10
  jobs                30
  users                1   (Randy Wolf only; Alice Smith deleted)
  co_steps_v2         62
  co_procedures_v2    10

Backup taken before reseed:
  /mnt/lake/myarra.db.bak.YYYYMMDD-HHMMSS

If the database needs to be restored to demo state again:
  /home/jeeves/jeeves-env/bin/python3 /tmp/seed_5lines.py
  sqlite3 /mnt/lake/myarra.db "DELETE FROM bot_sessions;"

NOTE: seed_5lines.py does NOT clear the users table. Delete any
non-Randy user rows after reseeding if the demo must be exactly one user.
The seed script lives in /tmp and may vanish; Section 11.2 of the main
handoff has the recipe to recreate it.

---

## 6. HOW TO RESUME

The estate is unchanged from the 2026-11-03 handoff Section 10. Four
services, all active. The routes and invariants are unchanged. Do not
re-derive them; read HANDOFF.md Section 1 and Section 14.

Check the estate:
  systemctl is-active llama-server koorsus myarr myarra-bot
  for u in / /setup /reconciliation /changeover /pdca /pdca/log; do
    printf "%-24s " "$u"
    curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:5002$u"
  done

Verify database is pristine:
  sqlite3 /mnt/lake/myarra.db "SELECT
    (SELECT COUNT(*) FROM lines), (SELECT COUNT(*) FROM skus),
    (SELECT COUNT(*) FROM jobs),  (SELECT COUNT(*) FROM users),
    (SELECT COUNT(*) FROM co_steps_v2);"
  # expect: 5|10|30|1|62

---

## 7. WHAT IS NEXT

Stage 3 of onboarding: /setup/verify page. Read-only. For each of the
ten tables: total row count, three most recent rows as a preview, and
sanity warnings for common mistakes:
  - SKU with no line rate
  - Procedure with no steps
  - Job referencing an unknown SKU
  - Line with no SKUs
Plus a checklist at the top: "Lines: 5 / 5 expected" with green or amber
marks.

After Stage 3, the co_steps guard, then item 2 from the reprioritized
list (query-level reporting).

Nothing else in flight. The day closed at a clean rest-stop.

---

## 8. WORKING METHOD — UNCHANGED, RESTATED FOR SAFETY

  - Talk before coding. Plan, approval, then code.
  - Whole files, not patches.
  - One change at a time, verification gate between each.
  - Verify with SQL before patching Flask.
  - Push back on bad architecture.
  - No em dashes in customer-facing prose.
  - Voice-to-text is lossy; read for intent; ask when uncertain.
  - When token budget is a concern: write a delta like this one at each
    verified milestone, rather than re-pasting old handoffs. The point
    of this file is that the next instance reads 150 lines instead of
    60,000 tokens.


## 9. EVENING ADDENDUM — ONBOARDING COMPLETE

As of commit d0dd67f, onboarding is complete. Supersedes Section 7.

Done since this delta was first written:
  - Stage 3: /setup/verify. New verify.py (Flask Blueprint) and
    templates/setup_verify.html. Checklist with per-table counts, sanity
    warnings (SKU without rate or BOM, procedure without steps, job
    referencing unknown SKU, line without SKUs), three-row previews.
    Verified: warning fired on a deliberately deleted rate row; counts
    match the pristine database.
  - co_steps guard: _ingest_co_steps now takes full_replace=False.
    Default (checkbox unchecked): delete only the (procedure_id, seq)
    rows present in the CSV, then insert. Steps not mentioned are kept.
    Checked: delete ALL steps for each procedure in the CSV, then insert.
    Both paths tested live: 6 steps -> 6 unchecked, 6 -> 2 checked.
    Database reseeded to pristine (62|10|6) after the test.
  - The "assets" field-name item in Section 4 is resolved: setup.html
    names file inputs by template name via INGEST_ORDER. No action.

Commits pushed: 4ba2174 (Stage 3), d0dd67f (co_steps guard).

Remaining before first client: nothing in onboarding. The reprioritized
list stands; the next item is query-level reporting (text-to-SQL over the
data lake).

Operational note: git push from the Jetson prompts for username
artifexofabrika plus a personal access token each time. Expect the prompt.

END OF DELTA.
