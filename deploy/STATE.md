# Myarra appliance state, 2026-11-19

Written at the end of the session that completed config extraction, backup
and restore, and the installer. Everything below was verified on the
reference Jetson, not assumed. Git HEAD at time of writing: 9d6ceab.

## Services running

Seven units on 192.168.100.2. The product is the first four.

    myarr.service            5002  Myarra web app
    myarra-bot.service             Myarra Telegram bot
    koorsus-app.service      5003  Koorsus document assistant
    koorsus-llm.service      8080  llama.cpp, qwen2.5-3b
    arkiv.service            5001  separate product
    koorsus.service          5000  legacy Koorsus, kept for a Telegram bot
    email-agent.service            Koorsus extra, not part of a plant unit

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
- Regenerate the 115-finding audit from the code. Queue item 5.
- /floor write path C27, then Whisper. Queue item 6.
- Odoo master-data import and the line-mapping screen. HANDOVER calls this
  install-blocking; the owner's revised list drops it. Unresolved.
- The architecture map. Agreed as worth doing, not yet written.
- Idle versus planned idle, waiting on the owner's PHILOSOPHY amendment.
- Dangling citations when a document is deleted. Parking lot.
- Backup and data share one filesystem. A second disk is needed for the
  archive to survive a disk failure.
- Rebase onto a fresh branch with fresh eyes, now that restore makes it
  recoverable.

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

grep across myarr_v2, 2026-11-20. Settings keys nothing reads:

  shift_1_start, shift_1_end, shift_2_start, shift_2_end,
  shift_3_start, shift_3_end, lunch_minutes, rate_label

Read and working: unit_label, case_label, job_variance_tolerance.

Four live consequences:

  app.py computes shift_start = 7 + (shift_h - 1) * 8 in three routes. Three
  shifts are configured in settings and ignored. A plant that edits its shift
  times sees no change and gets hours attributed to the wrong shift with no
  error raised.

  lunch_minutes is 30 in settings and read nowhere, so lunch duration is
  fixed in code.

  rate_label is unused, so the rate is described in hardcoded words rather
  than in the plant's own unit.

  bot/db.py UNACC_THRESHOLD = 5.0 is hardcoded, has no settings key, and is a
  different quantity from job_variance_tolerance, which is configured.

Characterisation: the configuration is in the database and specific paths read
the wrong source. Not a redesign.
