# MYARRA — SESSION DELTA, 2026-11-12 (Herbie Light)

This delta supersedes SESSION-DELTA-2026-11-11-HERBIE.md.
Read alongside PHILOSOPHY.md, HERBIE-ARCHITECTURE.md, and SESSION-DELTA-2026-11-07-REWRITE.md.

**Current entry point.** Read this first. Supersedes all earlier deltas.

**Before anything else, read PHILOSOPHY.md.** It is the governing document, never superseded.

## 0. WHAT THE PRODUCT IS

Myarra is a private, on-premise production tracker running on an NVIDIA Jetson.
It closes the "Check" step of PDCA without a data janitor. Herbie is the AI
Counselor. Herbie Light is the Nano-tier interface. Herbie Counselor (natural
language, conversation, proactive coaching) is the NX-tier upgrade.

## 1. WHAT WAS DONE

- Built **Herbie Light**: a five-card web interface at `/herbie`.
- Five intents, one card each:
    1. Job summary (get_job_summary)
    2. Top downtime jobs (get_jobs_with_downtime_over)
    3. Unaccounted time on a line (get_unaccounted_minutes)
    4. Changeover (get_changeover_summary)
    5. What happened on a line (get_line_summary + get_floor_context)
- AJAX submission. Page does not reload; answer appears at top; auto-scroll to answer.
- Tabs at the top, all five on one horizontal row. Only the selected card inputs are enabled (this fixes the duplicate-name field collision bug).
- Job number inputs use a datalist populated with jobs that actually have production data (not future jobs, which return "no data").
- Active tab persisted in URL hash so a reload does not lose context.
- Each answer has Copy / Download .txt / Print / Ask another buttons.
- Nav link added between Maintenance and Admin.

## 2. WHAT CHANGED (files)

- `myarr_v2/app.py`
    - New `/herbie` route. Detects `X-Requested-With: XMLHttpRequest` and returns JSON for AJAX, full page otherwise.
    - Passes `recent_jobs` (last 30 jobs with production data) and `co_jobs` (last 20 changeover to-jobs) to template.
    - All POST field names are unique per intent (jobs_over_days, unaccounted_days, unaccounted_line_id, changeover_job_number, line_day_line_id) to prevent cross-panel collisions.
- `myarr_v2/herbie.py`
    - Added `narrate(intent, stats, context, question)` — generic narrator.
    - Added `INTENT_NOTES` dict — intent-specific prompt rules.
    - Added `GENERIC_NARRATIVE_PROMPT` — shared prompt template.
    - Added `_fallback_narrative(intent, stats)` — template fallback for LLM failure.
    - Added `_build_changeover_summary(...)` — pre-computed summary string for changeover.
    - `get_jobs_with_downtime_over` — now returns `summary` field; HAVING uses the full aggregate expression, not the SELECT alias (SQLite resolves HAVING column names to underlying table columns, not SELECT aliases — real bug).
    - `get_changeover_summary` — now returns `summary` field with correct sign convention ("28.0 minutes FASTER than standard, a 46.7% improvement").
    - `narrate()` — for `jobs_over` intent, strips the `jobs` array from the payload (replaced with a placeholder string) to prevent the 3B model from enumerating the array.
- `myarr_v2/templates/herbie.html` — NEW. Five tabs, inline AJAX, datalists, active-tab hash, copy/download/print buttons.
- `myarr_v2/templates/base.html` — added Herbie nav link.

## 3. WHAT IS VERIFIED

- All five cards work end to end in the browser.
- Card 1: returns FTQ, P2P, scrap, downtime, hourly breakdown.
- Card 2: returns correct count (29 at 20m / 7d), top three correctly ranked starting WO-2611-153 at 32.8m.
- Card 3: respects day count and shift filter. Earlier bug (always 7 days) fixed.
- Card 4: correctly says "FASTER than standard, 46.7% improvement." Sign convention bug fixed.
- Card 5: returns capacity gap, accounted/unaccounted losses, operator notes verbatim.
- Case-insensitive job lookup via `COLLATE NOCASE`.
- AJAX submission keeps page still; auto-scroll to answer works.
- Tab persistence via URL hash works.

## 4. WHAT IS NOT VERIFIED

- LLM narrative quality is variable on the Nano 3B model. Prompt rules alone are not enough — pre-computed summaries plus stripped payloads are required.
- No conversation memory. Each question is standalone. Follow-ups require re-entering the job number.
- No natural-language input. Each card is a fixed form. This is the Herbie Light vs Herbie Counselor distinction.
- Not tested under concurrent load.
- No PDF export. No CSV export. No conversation history.

## 5. NEXT INSTANCE MUST DO

1. Test Herbie Light end to end after any schema or seed changes.
2. If the Card 2 narrative still drifts, show the `summary` field verbatim (no LLM) as a reliability fallback. Do not keep adding rules to the prompt.
3. Build the PWA to replace Telegram for operator input.
4. Wire the USB backup protocol with a tested restore.
5. Follow up with Kingswood (Hillary Clark) if no reply by Friday 2026-11-14.
6. Revisit the Odoo partner program in Q1 2027. The $4,000 + $4,000 offer is not appropriate for the current stage.

## 6. LESSONS / WORKING METHOD ADDITIONS

**Small-model lesson (the key one):**
On a 3B model you cannot tell the LLM to ignore data that is in the prompt.
It will read the forbidden data anyway. The reliable fix order is:
1. Try a prompt rule.
2. If still failing, pre-compute the summary in Python and instruct the model to paraphrase it.
3. If still failing, strip the offending field from the payload before formatting the prompt.
4. If still failing, skip the LLM entirely for that intent and return the summary verbatim.

**SQLite lesson:**
The `HAVING` clause resolves column names to underlying table columns, not
to SELECT aliases. `HAVING sum_alias > ?` will silently compare the wrong
value. Always use the full aggregate expression in HAVING.

**Working method lesson:**
When patch count on a single file exceeds three in one day, stop and rewrite
the whole file. This session proved the value of that rule. Herbie Light went
through four patches on `herbie.py` before we stopped and did one whole-file
rewrite. Every bug after that rewrite was diagnosable in one step because
the file was coherent.

**Case-insensitive user input:**
Every WHERE clause that takes user-supplied text should use `COLLATE NOCASE`.

END OF DELTA.