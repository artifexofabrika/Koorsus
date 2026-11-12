# MYARRA — SESSION DELTA, 2026-11-11 (Herbie & Unaccounted Minutes)

**Superseded by SESSION-DELTA-2026-11-12-HERBIE-LIGHT.md.** Read only when that delta points you here.
This delta supersedes SESSION-DELTA-2026-11-10-DEMO-FACTORY.md.
Read alongside PHILOSOPHY.md, HERBIE-ARCHITECTURE.md, and SESSION-DELTA-2026-11-07-REWRITE.md.

**Current entry point.** Read this first. Supersedes all earlier deltas.

**Before anything else, read PHILOSOPHY.md.** It is the governing document, never superseded.

## 0. WHAT THE PRODUCT IS
Myarra is a private, on-premise production tracker running on an NVIDIA Jetson. It is a working appliance, not a concept. The core philosophy is TPS (Toyota Production System) and closing the "Check" step of the PDCA cycle without requiring a data janitor. 

Herbie is the AI Counselor. Named after Herbie in The Goal: the constraint that limits the system. Herbie is a router and a coach, not a summarizer. He pulls hard math from Myarra, context from the operator notes, and asks the local LLM to write a narrative. The LLM never computes.

## 1. WHAT WAS DONE
- **Herbie Module:** Built `myarr_v2/herbie.py` with four functions: `get_line_summary`, `get_floor_context`, `ask_herbie`, `narrate_capacity_gap`.
- **Unaccounted Minutes View:** Created `v_unaccounted_minutes_by_run`. It calculates the gap between expected output and recorded downtime, flooring at zero. This is the metric that catches the operator who did not log a reason.
- **Architecture Document:** Wrote `HERBIE-ARCHITECTURE.md`, defining the Nano/NX hardware split, the five query types (Job Lookup, Attribution, Reconciliation, Aggregation by Threshold, Aggregation by Time Window), and the three-layer architecture (Classifier, Function Library, Narrator).
- **Prompt Engineering:** Refined the LLM prompt with strict rules: quote numbers exactly, never derive, never blame the operator, never call the standard wrong, tell the manager to "talk to the line lead" when the loss is unexplained.
- **Tested on Nano:** Ran Herbie against Line 7 for 2026-11-10. It correctly identified 652 units of accounted loss (scrap + downtime) and 4,015 units of unexplained loss, and told the manager to revisit with the line lead.
- **Website Lightbox:** Added click-to-zoom on gallery screenshots (docs/index.html).
- **Reddit Post Published:** The "Check is where PDCA dies" post went live in r/LeanManufacturing. Got 8 responses.
- **Odoo Partner Reply Sent:** Colin replied with the offer terms ($3,950/yr, 1 qualified lead/month, dedicated AM). Scheduled call Thursday 10:30 EST with Colin and Cameron Remington.
- **Kingswood Email Sent:** Contacted Hillary Clark with a two-week free pilot offer. Awaiting reply.

## 2. WHAT CHANGED (Files & Schema)
- `myarr_v2/herbie.py`: NEW. Four functions. LLM is only used for narration.
- `myarr_v2/views.py`: Added `v_unaccounted_minutes_by_run` to the view definitions and the drop list.
- `HERBIE-ARCHITECTURE.md`: NEW. The full architecture.
- `docs/index.html`: Added lightbox CSS/JS for gallery image zoom.

## 3. WHAT IS VERIFIED
- `herbie.py` runs end to end on the Nano (Qwen 2.5 3B). Response time ~10 seconds for a standard narrative.
- The math is bulletproof. All numbers in the narrative come from the Python-computed stats dict.
- `v_unaccounted_minutes_by_run` returns correct data: 13.1 minutes accounted, 17.5 minutes unaccounted on Line 7 for 2026-11-10.
- The narrative correctly diagnoses the standard-vs-data distinction: "revisit with the line lead," not "the standard is wrong."
- Lightbox zoom works on the website.

## 4. WHAT IS NOT VERIFIED
- Herbie is not yet wired to a web route or the Telegram bot. It runs only from the command line.
- Herbie has no conversation state. Follow-up questions require repeating the job number.
- Herbie cannot yet answer the four other query types (Attribution, Reconciliation, Aggregation by Threshold, Aggregation by Time Window). Those need the Function Library to be built out.
- The Nano cannot run the proactive coaching loop (end-of-shift summary). That is the NX upsell.
- Kingswood has not replied. The pilot offer is pending.
- Reddit responses have not been fully processed. One commenter accused the OP of being AI. The OP defended credibly.

## 5. NEXT INSTANCE MUST DO
1. Wire Herbie to the `/herbie` web route and the "Herbie" keyword in the Telegram bot.
2. Build out the Function Library: `get_job_summary`, `get_downtime_attribution`, `get_jobs_with_downtime_over`, `get_unaccounted_minutes`.
3. Add conversation state for follow-up questions.
4. Take the Thursday 10:30 call with Colin and Cameron (Odoo Partnership).
5. Follow up with Kingswood if no reply by Friday.
6. Post a second Reddit thread if the first one stalls, or reply to the skeptics.

## 6. LESSONS / WORKING METHOD ADDITIONS
- **The LLM will invent characterizations if you let it.** The prompt must say "quote operator notes verbatim, do not summarize." This is the same problem as inventing numbers, one layer up.
- **The unaccounted minutes metric is the product.** It is the only number that forces the operator to account for every minute. Herbie's coaching depends on it.
- **Nano vs. NX.** The Nano proves the concept. The NX delivers the full experience. Do not try to force multi-turn coaching onto the Nano. Sell it as the hardware upgrade.
- **Never let the user paste SQL into bash.** Always wrap SQL execution in `python3 -c` with explicit sqlite3.connect.

END OF DELTA.