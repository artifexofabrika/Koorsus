# MYARRA AND KOORSUS — HANDOVER

Written 2026-11-19. This is the state of the union and it
supersedes HANDOFF.md (2026-11-03), which describes a project that
no longer exists. The session deltas remain the detailed history.

## 1. Read these, in this order

1. PHILOSOPHY.md. Governing, never superseded. If a change
   contradicts it, the change is wrong.
2. This file.
3. SESSION-DELTA-2026-11-13-SPINE-AUTHORITY.md and
   SESSION-DELTA-2026-11-13-AFTERNOON.md, the most recent technical
   record.
4. HERBIE-ARCHITECTURE.md, the three-layer design.
5. Do not read HANDOFF.md as current. It describes bot_v2.py,
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
- ~/koorsus is a local clone of ~/arkiv. Ignore it.

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

Blocking a customer install:

1. Backup and restore. None exists. Required before any install.
2. Installation procedure document. None exists.
3. Config extraction. DB_PATH is an environment variable; cert
   paths and LLM_URL are still in source.
4. Odoo master-data import and the line-mapping screen. Only work
   orders are imported today.

Blocking correctness:

5. /floor write path (C27). It writes no line_events, no source and
   no user_id, and hardcodes shift='1' and duration_min=60. Must be
   fixed before Whisper lands in the same POST.
6. CSV round-trip with real data. Never run. This is the exact path
   a customer walks during onboarding.
7. Systematic test pass: every page, every Herbie card, every bot
   path. Never run.
8. Timestamp strategy across all tables. DEFAULT CURRENT_TIMESTAMP
   is UTC, Python writes local. Both are in use.
9. Regenerate the audit. The 115-finding audit from 2026-11-13 was
   never saved to disk. Only eight priorities survived, and two are
   now closed (rate averaging, /ask view list). Rebuild it from the
   code rather than searching for the original.

Next features:

10. Whisper and /api/transcribe, then a microphone button on /floor
    that parses units and scrap from the transcript.
11. Odoo work order notes into jobs.handover_notes, HTML stripped.
12. Idle versus planned idle (O1). Deferred until the owner writes
    the PHILOSOPHY amendment in his own hand.

## 7. Parking lot

Repo hygiene, none of it functional: delete bot/db.py.bak_live and
bot/shift.py.bak_shiftcode; archive bot_live.py, telegram_bot.py and
bot_v3.py; fix the false TEMPORARY BRIDGE comment in bot/jobs.py;
note that bot_live_v3.py is the live entry point despite its name.

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
- The audit is missing, as above. Without it, this priority order
  is inferred from deltas rather than from a catalogue.

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
