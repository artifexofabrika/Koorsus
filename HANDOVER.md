# MYARRA AND KOORSUS — HANDOVER

Written 2026-11-19. This is the state of the union and it
supersedes HANDOFF.md (2026-11-03), which describes a project that
no longer exists. The session deltas remain the detailed history.

CORRECTED 2026-11-24. Five sessions have happened since this was written, and
several statements below were true on 19 November and are not true now. They are
corrected in place with their dates, in the manner deploy/STATE.md uses: a state
document that keeps a comfortable old sentence is worse than none, because the
next reader cannot tell which half is current. Where this file and
deploy/STATE.md disagree, STATE.md wins. deploy/AUDIT.md is the catalogue of
defects, not section 6 below.

## 1. Read these, in this order

1. PHILOSOPHY.md. Governing, never superseded. If a change
   contradicts it, the change is wrong.
2. deploy/STATE.md. The current state, corrected in place, with what is
   proven and what is merely believed.
3. deploy/AUDIT.md. 52 findings, 20 fixed, 32 open, each naming a file and
   an observation that can be repeated.
4. SESSION-DELTA-2026-11-24.md, the most recent session, and the deltas
   before it as far back as the question needs. 11-24 is the one that says
   where the previous instance stopped and what to do first.
5. HERBIE-ARCHITECTURE.md, the three-layer design.
6. Do not read HANDOFF.md as current. It describes bot_v2.py,
   Waitress and five lines.

## 2. What the product is

Myarra is a private production tracker on a Jetson, sold to plants
doing $3M to $15M a year. It closes the Check step of PDCA without a
data janitor. Three parts on one appliance:

- Myarra, the structured truth: hourly runs, two measures,
  changeover, downtime, PDCA.
- Koorsus, the unstructured truth: documents, cited answers, refuse
  when the answer is absent.
- Herbie, the bridge: pulls numbers from Myarra, context from notes,
  and asks the local LLM to narrate. The LLM never computes.

Nano tier runs Herbie Light, five fixed questions, plus the PWA. NX
tier runs Herbie Counselor, natural language and coaching. On
premise, no subscription, GPL v3, the customer owns the hardware.

## 3. Where the code is

- ~/Client-Demo is the Myarra working copy. Its git remote is
  github.com/artifexofabrika/Koorsus. That one repo holds the
  Myarra application, the Koorsus RAG application, AND the website
  under docs/. Do not expect a separate Myarra repository.
- ~/koorsus-site is a second clone of the same repo, used only for
  the website.
- ~/arkiv is Arkiv, a different product, separate repo, with its own
  START-HERE.md. Not this project.
- ~/koorsus is NOT a spare clone. It is the live Koorsus on port 5003,
  started by koorsus-app.service. This line used to say it was a local
  clone of ~/arkiv and to ignore it, which was wrong and cost a session
  (A41).

## 4. State as of 2026-11-19

Believed built and working. Verify, do not assume.

- Onboarding: ten CSV templates, download, upload with natural-key
  resolution, /setup/verify, and a partial-replacement guard on
  co_steps.
- Maintenance as a first-class event with operator-stated duration.
  Shift handovers. Relog with an audit trail.
- Data lake views plus /ask, text-to-SQL over those views, refusing
  on ambiguity rather than guessing.
- Modular bot package under bot/. Per-run rate math, per-job hours,
  spine as authority, record-flow state machine, lunch and CIP,
  fuzzy job resolution restored from git history.
- PWA at /floor. Installs on a trusted certificate, tile grid,
  writes hourly_runs. Text only, no voice.
- Herbie Light: five cards, pre-computed summaries, the LLM
  narrates and nothing else.
- Odoo connector published on the Apps Store, MO to jobs proven end
  to end.
- tools/schema.sql: 25 tables, 7 indexes, idempotent. db.py applies
  it and refuses a pre-2026-11-13 partial schema rather than
  migrating silently.

## 5. The ideas that keep getting lost

- Two measures, never one. OEE counts every loss. Operator
  performance excludes what the operator did not cause. recon.py
  carries the math and a comment. Do not collapse them.
- Capture never blocks. No gate on logging an hour. bot_sessions is
  a convenience pointer, never an authority. line_events is the
  authority for what is running; jobs.status decides whether a job
  can take production.
- Wall clock orders events. It never measures duration. Maintenance
  duration is what the operator states.
- Scrap convention: "600 parts, 20 scrap" means 600 total, 20 bad,
  580 good. FTQ is 580/600.
- Free text, not dropdowns. "unknown" and "skip" are valid answers
  to every reason prompt.
- The refusal is the feature, in Koorsus and in Herbie.
- Small model rule: a 3B model reads data you told it to ignore.
  Pre-compute in Python, tell it to paraphrase, strip the field, and
  if that fails skip the LLM for that intent.
- Whole files, not patches. Three patches on one file in a day
  means rewrite the file.

## 6. Open, in priority order

Written 2026-11-19 and mostly consumed since. Four of these were closed by work
that deserves to stay visible rather than be quietly deleted, so they are marked
with their dates. The live list is deploy/AUDIT.md.

Closed since: backup and restore (2026-11-20, and as of 2026-11-24 with a USB
export carrying both products, a nightly Koorsus index timer, and a tested escrow
procedure); the installation procedure (deploy/INSTALL.md); config extraction
(2026-11-19, myarra_settings.py owns DB_PATH, LLM_URL and the tokens); the /floor
write path C27 (2026-11-22, start, end and the three switches, verified 15 of 15);
the CSV round-trip (2026-11-20, 8 checks); the systematic test pass (2026-11-20,
and 27 routes as of 2026-11-24); and the audit itself (deploy/AUDIT.md, rebuilt
twice, now 52 findings).

Still open:

1. Odoo master-data import and the line-mapping screen. Only work
   orders are imported today.
2. Timestamp strategy across all tables. DEFAULT CURRENT_TIMESTAMP
   is UTC, Python writes local. Both are in use. Never filed as a
   numbered finding, which is its own problem.
3. Whisper and /api/transcribe, then a microphone button on /floor
   that parses units and scrap from the transcript.
4. Odoo work order notes into jobs.handover_notes, HTML stripped.
5. Idle versus planned idle (O1). Deferred until the owner writes
   the PHILOSOPHY amendment in his own hand.

## 7. Parking lot

Repo hygiene, done 2026-11-24 except one item. The .bak files are gone (41 of
them across the tree, not the two named here), bot_live.py, telegram_bot.py,
bot_v3.py and intent.py are deleted along with both spare copies of the tree and
every __pycache__, and telegram-bot.service went with the script it started.
Still outstanding: the false TEMPORARY BRIDGE comment in bot/jobs.py, which is
A35. bot_live_v3.py is still the live entry point despite its name, which is A36
and needs the unit edited rather than the file renamed.

Product: MCP server for strategy-layer interop, read-only tools
first; TEEP and facility OEE, distinct from conditional OEE;
mid-shift residual wording so an open shift is not read as a bad
one; step_type='verification' for calibration steps; visual hourly
chart per line; tablets locked to a single line; plant manager relog
across line leads; co_event_changes for the other measurement types;
priority contribution math on /pdca/log.

Business: the Myarra one-pager predates current pricing; pricing
appears in three places (site, one-pager, outreach/pricing_tiers.md)
and must agree; 57 CRM records lack an email; the Kingswood
follow-up with Hillary Clark was due 2026-11-14 and its status is
unknown; the Odoo partner program is deferred to Q1 2027;
artifexofabrica.com without the k should redirect; Carrd cancels at
renewal; the NX 16GB module is needed for the Counselor tier and is
funding-dependent.

## 8. Contradictions and gaps in the record

- The 2026-11-06 delta says passwordless sudo was configured and
  proven. On 2026-11-18 and 19 every sudo command prompted for a
  password. One of those is wrong.
- Several items appear once and never again: the Live Board
  defaulting to blank when there is no data today, the shift label
  alignment in generate_demo_history.py, the full eight-hour
  skeleton on /line/<id>/report, and the bare-confirm phone test. A
  later delta not mentioning something is not evidence it was done.
- The audit is no longer missing, corrected 2026-11-24. deploy/AUDIT.md holds 52
  findings, each naming a file and an observation that can be repeated, and the
  priority order in section 6 is now derived from it rather than from deltas.

## 9. How to resume

  ssh jeeves@192.168.100.2
  systemctl is-active koorsus-llm koorsus myarr myarra-bot

  for u in / /reconciliation /changeover /pdca /setup /herbie \\
           /floor; do printf "%-18s " "$u"; \\
    curl -sk -o /dev/null -w "%{http_code}\\n" \\
    "https://127.0.0.1:5002$u"; done

  sqlite3 /mnt/lake/myarra.db "SELECT
    (SELECT COUNT(*) FROM lines),
    (SELECT COUNT(*) FROM jobs),
    (SELECT COUNT(*) FROM hourly_runs),
    (SELECT COUNT(*) FROM maintenance_events);"

  cd ~/Client-Demo && git log --oneline -5 && git status --short

Ports and units: koorsus-llm on 8080, koorsus on 5000, myarr on
5002, myarra-bot polling as @KoorsusTheBot. Arkiv is 5001 and is a
separate product. The machine is 192.168.100.2 over Ethernet. The
onboard Wi-Fi card is defective and is disabled; do not re-enable
it hoping it behaves.

## 10. How the owner works

- He dictates. Expect garbles and reconstruct rather than asking him
  to retype.
- One command at a time, and name the window, PowerShell or Jetson.
  Never number a command; the number gets pasted with it.
- Whole files over patches. Short heredocs can truncate and fail
  silently, so verify every write with wc -l and a grep before
  trusting it. Verify the write, not the success message.
- Commit and push after each verified fix.
- Push back when he is wrong, plainly, and stop pushing once he has
  answered.
- No em dashes in customer-facing prose.
- If it was only said in chat, it is not in the repository and it
  does not exist.
