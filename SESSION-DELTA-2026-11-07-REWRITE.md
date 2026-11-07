# MYARRA — SESSION DELTA, 2026-11-07 (Modular Bot Rewrite)

This delta supersedes the bot architecture described in all prior deltas.
Read this first. It covers the replacement of bot_v2.py with a modular
package, the fixes for shift/maintenance/scrap capture, and the exact
state at handover.

---

## 1. THE REWRITE (Why and What)

`bot_v2.py` had accumulated over 1,400 lines across five instances and
dozens of patches. Every patch was a `sed` command or string replacement
that risked silent failure. Three separate times today, a patch failed
to apply because an anchor changed, leaving the code in a partially
patched state.

Agreed 2026-11-07: **Stop patching. Rewrite the bot as small modules.**
Each module is under 250 lines. Each module can be rewritten in its
entirety without touching the others.

**The new package: `myarr_v2/bot/`**

| Module | Responsibility |
|---|---|
| `db.py` | Connection, Session class, `write_hour` (with scrap), `_parse_scrap`, line events, settings |
| `shift.py` | `start shift` / `end shift`, shift reconciliation math, `shift_reconciliations` table |
| `production.py` | `running job`, `record hour`, plausibility check, scrap capture |
| `changeover.py` | Start/end changeover, per-step timing, BOM diff |
| `maintenance.py` | Open/close maintenance. **DURATION IS OPERATOR-STATED, NOT WALL-CLOCK** |
| `handover.py` | Handover notes, takeover |
| `notes.py` | `note: text`, `note hour N: text`, `relog job WO-X hour N` |
| `support.py` | `status line N`, `status WO-X`, `help`, `sop` |
| `jobs.py` | Start job, end job, variance gate, pause, resume |
| `dispatch.py` | The router. Single entry point. |

**Live bot:** `bot_live_v3.py` now imports `from bot.dispatch import dispatch` and `from bot.db import Session`. It no longer calls `bot_v3.py` or `bot_v2.dispatch()`.

**Rollback:** `bot_live_v3.py.bak_swap` on disk. Copy it back and restart `myarra-bot.service` to revert to the old bot.

---

## 2. THE TEMP BRIDGE (What It Is and How to Remove It)

`bot/jobs.py` imports four functions from the old `bot_v2.py`:
`resolve_job`, `_explain_no_job`, `_fuzzy_note`, `next_job_hour`.

**Why:** Voice-to-text produces mangled job numbers ("w0-2026-006", "WO 2026006"). The fuzzy-matching logic is non-trivial and works. Duplicating it during the rewrite risked re-introducing bugs.

**What to do next session:**
1. Create `bot/resolve.py`.
2. Move those four functions from `bot_v2.py` into it, unmodified.
3. Change `bot/jobs.py` to import them from `.resolve`.
4. `bot_v2.py` can then be renamed to `bot_v2.py.retired`. Nothing imports it.

This is a 15-minute task. Until it is done, `bot_v2.py` must not be deleted.

---

## 3. WHAT IS TESTED AND WHAT IS NOT

**Tested against the live database via Python REPL:**

- `production.h_running_job` with scrap: stored `H4 | 7000 units | 20 scrap` correctly.
- `maintenance` flow: `end maintenance` prompts for minutes, saves operator-stated duration. `STORED: 15.0 min | labeler | E44 error | reseeded the sensor | Randy`.
- `handover` flow: notes saved, takeover reads them.
- `notes.try_relog` + `cont_relog_reason`: original row marked `superseded=1`, new row carries `override_reason`.
- `shift.compute_reconciliation` for Line 1 S1: math checks out (172.66 min production + 307.34 min residual = 480 min usable).
- `jobs.cont_variance_reason`: writes to `completion_variance_reason` and `completion_flagged=1`.

**Tested on live Telegram after the swap:**
- `running job WO-2026-006, hour 4, 7000 parts, 20 scrap` returned the correct receipt and stored `H4|7000|20`.

**NOT tested on live Telegram after the swap (next session must test):**
- Live changeover end-to-end via Telegram.
- Live maintenance end-to-end via Telegram (start → end → minutes prompt → three notes).
- Live `end shift` reconciliation.
- Live variance-reason prompt on `end job`.
- Live `start shift` command.

**Not yet exercised:**
- `shift_reconciliations` table has not been written to via a live `end shift`. The math function works; the interaction path through Telegram has not been run.

---

## 4. DATABASE STATE AND SCHEMA CHANGES

New table: `shift_reconciliations` (id, line_id, shift_date, shift_code, usable_min, actual_units, scrap_units, downtime_min, production_time_min, scrap_time_min, residual_min, explanation, created_at).

`bot_sessions` now includes `override_reason` in the Python list. Was previously in the schema but silently dropped on every save.

`hourly_runs` uses `scrap_units` (total produced minus good = the bad subset). **The convention is:** "600 parts, 20 scrap" means 600 total, 20 bad, 580 good. FTQ = 580/600 = 96.7%. This was agreed explicitly on 2026-11-07 after a long discussion about Herman Miller's takt-time accounting.

---

## 5. THE LOGIC WE AGREED (The Governing Architecture)

**Wall-clock time is used only for ordering events, NEVER for measuring duration.** This was the single most important fix of the day. The old `h_end_maintenance` calculated duration by subtracting timestamps. An operator who logged the end of maintenance two hours late recorded a two-hour repair. The new module asks the operator for the minutes.

**Shift reconciliation is both production-based and event-based.** Production-based answers "how many good parts, how many scrap, how many minutes lost." Event-based answers "how many minutes the line spent in production, changeover, lunch, maintenance, idle." Both are shown. The residual is the number the manager hunts down.

**No threshold for residual.** Even 4 parts in a shift triggers the shift-end prompt. The prompt is once, at shift end, free-text. The Herman Miller benchmark is that 4,792 chairs means 4,792 chairs; anything less needs an explanation.

**Free text, not dropdowns.** The fixed loss category list was rejected. Operators will pick "Other" to get past the screen. The LLM (Koorsus) can categorize free text retroactively when a manager asks.

**Scrap is captured per hour.** The bot previously accepted "600 parts, 20 scrap" and stored `scrap_units=0` because the field was never passed. That is fixed. FTQ is now real.

**TWO DIFFERENT SYSTEMS, two different questions:**
- **Myarra (`/ask`)** — structured SQL over 11 views. "What was unaccounted time on Line 4?"
- **Koorsus (`sop,`)** — narrative RAG over documents and notes. "Why does the labeler keep jamming on Line 4?"

Do not try to make one do the other's job.

---

## 6. WHAT THE NEXT INSTANCE MUST DO

1. **Push the code.** `git push origin main` (personal access token required).
2. **Test the untested paths** (Section 3) on live Telegram. Fix any that fail in the corresponding module, whole.
3. **Extract the temp bridge** (Section 2) to retire `bot_v2.py`.
4. **Write a proper delta for the 2026-11-06 and 2026-11-07 days combined.** The 2026-11-06 delta stops at Stage B2; the work since includes Stage C views, `/ask`, the modular rewrite, the shift reconciliation logic, scrap capture, and the variance gate.

---

## 7. WORKING METHOD (Learned the Hard Way)

- **Whole files, not sed.** The modular rewrite exists because patching failed repeatedly. Write modules whole. Rewrite modules whole when they need changing.
- **One command block at a time.** Do not print five steps when the user only needs the next one.
- **Test before dependency.** `test -f` before referencing, `py_compile` before importing.
- **The residual is the product.** Every design decision should serve the manager finding the unaccounted minutes.

END OF DELTA.
