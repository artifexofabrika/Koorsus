# Myarra appliance state, 2026-11-22

Started 2026-11-19 at the end of the session that completed config
extraction, backup and restore, and the installer. Everything below was
verified on the reference Jetson, not assumed. Git HEAD when this section was
written: 36ed2db.

Where a statement below was true on 19 November and is not true now, it is
corrected in place with the date of the correction rather than left standing.
A state document that keeps a comfortable old sentence is worse than none,
because the next reader has no way to tell which half is current.

## Services running

Seven units on 192.168.100.2. The product is the first four.

    myarr.service            5002  Myarra web app
    myarra-bot.service             Myarra Telegram bot
    koorsus-app.service      5003  Koorsus document assistant
    koorsus-llm.service      8080  llama.cpp, qwen2.5-3b
    arkiv.service            5001  separate product
    koorsus.service          5000  legacy Koorsus, kept for a Telegram bot
    email-agent.service            Koorsus extra, not part of a plant unit

## 2026-11-22, the floor start action

The tablet can start a job. It cannot end one.

    floor_view dispatches on a hidden action field. With no action field it
    falls through to the record path untouched, which is what the record form
    posts today.
    The start action calls bot.jobs.start_job, which writes jobs.status and
    the line_events row in one transaction with rollback, so a crash cannot
    leave one written and not the other.
    check_start now tests the line the job is being started on rather than the
    line the job carries, so a moved work order cannot silently close the
    event of whatever is already running there.

Proven. tools/test_floor_start.py, six cases, 6 of 6, on its own temporary
database. The induced failure is a real BEFORE INSERT trigger on line_events,
so it tests the transaction rather than the except block. Regression after the
change: test_csv_roundtrip 8 of 8, test_pages 26 routes 0 failed, /floor
returns 200 after a restart. Commits df1c99c and 36ed2db.

Not proven. A human on the tablet. Everything above is Flask's test client on
the Jetson, which cannot tell anyone whether a lead in gloves can hit the tile.

## Done and proven

### Config extraction

myarra_settings.py owns DB_PATH, LLM_URL, TELEGRAM_BOT_TOKEN, ODOO_TOKEN
and check_llm(). intent.py, ask.py and herbie.py read from it. ask.py and
herbie.py take DB_PATH from db.py rather than hardcoding it. bot_live_v3.py
no longer imports the Koorsus config, so Myarra no longer depends on
Koorsus to start.

app.py logs LLM reachability at startup and verify.py reports it on
/setup/verify. Proven by overriding LLM_URL to a dead port: all four
readers agreed, check_llm returned False, and the live service logged OK
against the real endpoint.

Before this, LLM_URL existed as four independent copies and DB_PATH as
four, two of which bypassed the environment entirely.

### Backup and restore

deploy/backup/ holds the whole system.

    backup.sh              one archive, Myarra and Koorsus at one vintage
    restore.sh             checksum, decrypt, stop, swap, start, verify
    verify.sh              strict; writes /var/log/appliance-verify.status
    artifacts.txt          both products, 15 artifacts
    artifacts-koorsus.txt  Koorsus only, 10 artifacts

SQLite artifacts are copied with sqlite3 .backup, so a live write cannot
tear them. The archive is encrypted with /etc/koorsus-backup.key, carries
a sha256 beside it, keeps 30, and exits 2 if any artifact is missing.
restore.sh honours APPLIANCE_RESTORE_ROOT, so a scratch test runs the same
code a recovery runs.

appliance-backup.timer runs daily at 03:30 and verifies the archive it has
just written, in the same run.

Proven: scratch restore EXIT=0. In-place restore EXIT=0 with identical
content hashes before and after (a0fd9bd7... and 6e9a416e...), services
back to active, routes serving. verify.sh EXIT=0 reporting 406 jobs,
1659 hours, 13 line events.

### Installer

deploy/install.sh, modes "appliance" and "--koorsus". It refuses on a
failed precondition, never overwrites appliance.env, normalises BOM and
CRLF out of the Koorsus scripts, generates the backup passphrase once,
installs units, and starts certificate-dependent services last.

Run twice in Koorsus mode, EXIT=0 both times, koorsus-app active, 5003
answering 302. Appliance mode run once on 2026-11-20, EXIT=0.

### Deploy templates

myarr.service, myarra-bot.service, koorsus-app.service (flat, supersedes
the old drop-in), koorsus-llm.service, appliance-backup.service and
.timer, appliance.env.example. Customer values come from
/etc/myarra/appliance.env. The legacy koorsus.service for port 5000 is
deleted from the repo.

### Fixed in passing

/pdca returned 500 because a changeover step with a NULL actual time
reached the trend chart. All four PDCA routes now 200.

myarr_v2/requirements.txt created and pinned from actual imports: Flask
3.1.3, gunicorn 27.0.0, requests 2.34.2, waitress 3.0.2.

## Not done, planned

- The printable installation procedure. Last piece of queue item 3.
- No offsite copy of the appliance archive. export-usb.sh and import-usb.sh
  are hardcoded to /mnt/koorsus-backup.
- Key escrow is not a documented step. The passphrase exists only on the
  machine and in the owner's Downloads.
- No durable document root. Koorsus documents were ingested from /tmp and
  no longer exist, so 64 chunks cite files nobody can open. Neither product
  stores a document.
- Reset the Koorsus collection before any customer install, or the unit
  ships with our test text.
- install.sh should refuse when the env file lacks a variable the units
  interpolate. A stale env file produces empty arguments, not an error.
- install.sh HTTP check should accept 200 and 302 and flag 000 or a 5xx.
- CSV round-trip with real data, then the systematic pass over every page,
  every Herbie card and every bot path. Queue item 4.
  PART DONE 2026-11-20: the CSV round trip, the 26 pages and the 5 Herbie
  cards all run and are re-runnable. The bot write paths are still unwalked,
  and the audit calls them the largest unexamined surface.
- Regenerate the audit from the code. Queue item 5.
  DONE 2026-11-20: deploy/AUDIT.md holds 44 numbered findings, each naming a
  file. The 115 in this line was the count from an earlier audit that was
  never saved, and the two figures should not be reconciled; the saved one
  wins. Regenerated again 2026-11-22 to 47 when A45, A47 and A48 were finally
  written down.
- /floor write path, C27, then Whisper. Queue item 6.
  HALF DONE. The hour was fixed 2026-11-20 and the start action 2026-11-22.
  Still missing: end, and the lunch, maintenance and CIP toggles. A45, the
  variance gate's off-time allowance, gets built before end, in one shared
  function, or it will be built twice and the two will disagree.
- Odoo master-data import and the line-mapping screen. HANDOVER calls this
  install-blocking; the owner's revised list drops it. Unresolved.
- The architecture map. Agreed as worth doing, not yet written.
- Idle versus planned idle, waiting on the owner's PHILOSOPHY amendment.
- Dangling citations when a document is deleted. Parking lot.
- Backup and data share one filesystem. A second disk is needed for the
  archive to survive a disk failure.
- Dropped 2026-11-22 by the owner. No rebase, no force-push, no amending a
  pushed commit: history only grows, and a wrong commit is fixed forward with
  a commit that says what it is fixing. This line proposed rebasing now that
  restore made the tree recoverable, which is the habit it was the seed of.
  It is closed, and closing it here is the point of writing it down.

## Parking lot, hygiene and cleanup

- Five .bak files in the bot package: production.py.bak_override,
  production.py.bak_20261115, jobs.py.bak_bridge, db.py.bak_live,
  shift.py.bak_shiftcode. Two still contain the deleted session gate
  verbatim, which is a trap for the next grep.
- Dead entry points and modules: myarr_v2/bot_live.py, bot_v3.py,
  telegram_bot.py, root telegram_bot.py, and myarr_archive/ at about 830
  lines including its own dashboard.py.
- Client-Demo-backup/ lives inside the repository, holding another copy of
  the code.
- __pycache__ present; check whether .pyc is committed.
- Name collisions: db.py twice, config.py three times, app.py twice,
  telegram_bot.py twice. New rule: a new module gets a name unique across
  the whole repository.
- /mnt/lake is shared by four products: arkiv_index plus five archived
  copies at 6.4MB each, legacy /mnt/lake/index and a stray chroma.sqlite3,
  demo_beverage.db with two backups, metrics.db with one, and two
  myarra.db backups.
- Two identical udev rules, 99-arkiv-usb.rules and 99-koorsus-usb.rules.
- bot_live_v3.py implies a v3 lineage that does not exist; it is the live
  entry point.
- The TEMPORARY BRIDGE comment in bot/jobs.py is false.
- Sudo prompts for a password, so the 2026-11-06 passwordless claim is
  wrong.
- The old Koorsus on 5000 exists only because a Telegram bot posts to it.
- ~/koorsus/systemd/ holds Arkiv-branded units for port 5001 that are not
  what runs.
- HANDOVER says of ~/koorsus, "ignore it". That is wrong, it is the live
  Koorsus.
- HANDOVER says backup and restore does not exist. It does now, and the
  record is a day stale.
- Agentic Herbie, agreed 2026-11-23 and gated on hardware. Give the model
  read-only tools behind a fixed vocabulary of named verbs: get jobs, get
  hourly records, get downtime by cause, get changeover steps, get maintenance
  history. Then the manager asks why Line 4 lost capacity this week and the
  model walks those five itself and assembles an A3. Two rules keep it
  contained. Read authority and act authority stay separate, so text the agent
  fetched can inform an answer but cannot trigger a tool on its own. And the
  tool surface is an allowlist of named verbs that each do one known thing,
  never a shell and never a general HTTP client. Number-crunching stays in
  Python where it already is: the agent plans and gathers, the arithmetic
  remains ours, read-only so nothing can be damaged.
  Not feasible on the current board. This needs an Orin NX or an AGX. A 3B
  model cannot hold a tool schema and a five-step plan at the same time, and
  the failure mode of pretending otherwise is confident nonsense in front of
  a plant manager.
- Repository cleanup before a stranger sees it, agreed 2026-11-23. A28 to A33
  in one commit: the five .bak files in the bot package, bot_v2.py.retired, the
  dead entry points, the backup copies of the tree, __pycache__, and the
  duplicate module names. Every one is already named in the audit, so it is
  deletion rather than detective work, and it stops "too messy" being an
  available description of a working product.
- A one-page walking route for a visitor. Which screen to open first, what to
  point at, and what to say about the two rate gaps being deliberate. Written
  for an engineer who has never seen the appliance, and short enough to read
  standing up. Showing a visitor the repository invites him to count .bak
  files; walking him through the appliance invites better questions.
- When the owner walks the demo looking for weaknesses, every finding gets one
  of three labels before anyone touches it: blocks the demo, blocks a pilot, or
  a note. Without that discipline a two-day walk becomes a two-week one,
  because every finding is urgent while it is in front of you.

## Competitor watch

### JUUSTE, assessed 2026-11-20

Flemish, small, early. Their footer places them in Voka Bryo and Start it X
2026 Fall programmes, with VLAIO logos. Pre-Series A, not an incumbent.

Positioning: "JUUSTE works on the input side, the checks, the settings, the
handovers." They frame scrap, downtime and OEE as "every other tool watches
here, these only move after the shift is over." Sharper sentence than ours
and aimed at the same buyer.

Stronger than Myarra today: twelve modules (centerlines, CIL, one-point
lessons, near misses, 5 Why, skills matrix, tasks, safety observations), and
a live scrollable demo on a chocolate line with a named operator and per
machine uptime. Our demo is seeded beverage data.

Where they are not: capture is form driven in their own demo, "Type: no
selection", "Classification: minor defects", "Priority: choose one". Their
data quality depends on the taxonomy being right, which is the 101st
category wall. Their OEE is textbook Availability, Performance, Quality per
machine, which is one instrument charging every loss to one number. And
there is no refusal anywhere.

The real risk is not losing a bake-off on the Check step. It is that they get
installed first, become the operator's screen, and Myarra becomes a second
system. That breaks "one place, no data janitor" outright.

Watch item. Do not mention in marketing. The counter is the two measures and
capture that cannot be blocked: their form makes the operator choose a
category, ours records what he said.

## Findings from the systematic pass, 2026-11-20

First output of the audit rebuild, in the order found. Each was found by
running something rather than by reading.

FIXED  /pdca returned 500. A changeover step with a NULL actual_min reached
       the trend chart and the template divided it. Points with no
       measurement are now dropped in _compute_trend.

FIXED  /favicon.ico returned 404 on every page. The route served from
       app.root_path and the file lives in myarr_v2/static. One wrong
       directory.

FIXED  Onboarding decoded uploads with errors='replace', so a Latin-1 CSV
       from Excel imported as mojibake with no error and no warning. Now
       UTF-8, then Windows-1252, then a refusal that names the problem.

FIXED  Onboarding resolved part numbers and component types case
       sensitively, so a CSV spelling a part number differently from the
       stored one failed with "unknown SKU". Exact match first, then
       case-insensitive fallback.

OPEN   maintenance_events holds zero rows. The maintenance list page renders
       an empty table, and neither the maintenance detail page nor the bot
       maintenance handler has ever produced a surviving row. HANDOVER calls
       maintenance a first-class event with an operator-stated duration.
       Either the demo never exercised it or the data was cleared. Untested
       rather than broken, which is worse.

OPEN   The case-insensitive fallback for component types is implemented but
       not exercised, because the round-trip test uses an exact-case
       component name. Reasoned, not proven.

COVERAGE  tools/test_csv_roundtrip.py   8 checks, all passing
COVERAGE  tools/test_pages.py           26 routes, all 200
COVERAGE  tools/test_floor_start.py     15 cases, all passing, added 2026-11-22
COVERAGE  tools/test_rates.py           5 checks, all passing, added 2026-11-23

Which of these need a restart. test_pages and test_herbie_cards make requests to
the running service on 5002, so after any change to app.py or to a template they
only tell the truth once myarr has been restarted. The other three build their
own database and import the modules themselves, so they test what is on disk and
need nothing restarted. Learned on 2026-11-23 the hard way: a template change
installed without a restart failed four pages with a Jinja compile error, "No
filter named num", because the running process still held the previous app.py in
memory. New templates, old process, no filters. A green test_rates beside a red
test_pages is that signature exactly.

## Herbie Light: the guarantee does not hold

Ran tools/test_herbie_cards.py against live data, 2026-11-20. Five cards, all
reachable, all narrating. Two defects observed that matter far more than
reachability.

OBSERVED  The changeover card computed a number. Asked about WO-2611-398 it
          wrote "32.0 minutes faster than the standard of 60.0 minutes,
          resulting in a 46.7% improvement". A 32 minute saving on a 60
          minute standard is 53.3%, not 46.7. The model divided instead of
          quoting variance_pct, which the HARD NUMBERS rule forbids and the
          intent notes already prohibit. A later run of the same card did not
          repeat it. The violation is intermittent, so one green run proves
          nothing.

OBSERVED  The line_day card misstates losses_accounted. It wrote "the losses
          accounted for are 12 scrap units plus 0 lost capacity, totaling 12
          units", while the same paragraph reported 12 units of lost capacity
          and 2248 unexplained. The accounted loss is 24. Reproduced on
          consecutive runs.

NOTE      Numeric tracing catches a computed figure. It does not catch a
          field reported with the wrong value, which is the line_day defect.
          Reading is still required. A passing test is not a clean bill.

NEXT      Both are prompt and payload problems, not code problems. The
          changeover summary is already pre-computed and the intent notes
          already call it authoritative, and the model overrode it anyway.
          Options: strengthen the prompt, or route changeover and line_day to
          the template fallback on the Nano and let the model narrate only
          where it is reliable. Not started. Needs the operator workflow
          description first.

COVERAGE  tools/test_herbie_cards.py   5 cards, all reachable

## Config exists, code ignores it

grep across myarr_v2, 2026-11-20. On that date these settings keys were read
by nothing:

  shift_1_start, shift_1_end, shift_2_start, shift_2_end,
  shift_3_start, shift_3_end, lunch_minutes, rate_label

By 2026-11-22 the six shift keys are read and working, through
_shift_start_hour and _shift_hours. Still unread: lunch_minutes, which should
be deleted rather than wired, and rate_label, which should be wired.

Read and working: unit_label, case_label, job_variance_tolerance,
unacc_threshold, shift_N_start, shift_N_end.

Four live consequences as at 2026-11-20, each marked with its status on
2026-11-22:

  app.py computed shift_start = 7 + (shift_h - 1) * 8 in three routes. Three
  shifts were configured in settings and ignored. A plant that edited its
  shift times saw no change and got hours attributed to the wrong shift with
  no error raised.
  FIXED 2026-11-20 as A07. _shift_start_hour reads shift_N_start and the hour
  ceiling comes from _shift_hours, so ten and twelve hour shifts work.

  lunch_minutes is 30 in settings and read nowhere, so lunch duration is
  fixed in code.
  STILL TRUE, and the answer is deletion, not wiring (A24). bot/shift.py
  measures actual lunch from line_events, which is more truthful than any
  configured duration.

  rate_label is unused, so the rate is described in hardcoded words rather
  than in the plant's own unit.
  STILL TRUE as A23.

  bot/db.py UNACC_THRESHOLD = 5.0 is hardcoded, has no settings key, and is a
  different quantity from job_variance_tolerance, which is configured.
  FIXED 2026-11-20 as A08. unacc_threshold(conn), settings first.

Characterisation: the configuration is in the database and specific paths read
the wrong source. Not a redesign.
