# MYARRA AUDIT, 2026-11-20

Rebuilt from the code and from tests that were run. Not from memory, and not
from a delta.

The audit of 2026-11-13 was handed to an instance and never saved to disk. It
is not recoverable, and this is not a reproduction of it. It is a replacement,
and where the two disagree this one wins, because every finding here names a
file and an observation that can be repeated.

Method. Every finding below rests on one of three things: a test that was run,
a grep whose output is quoted, or code that was read. Items marked FIXED were
repaired and verified on 2026-11-20. They stay in the list because a future
instance needs to know the defect existed, not merely that it was patched.

Severity.

  S1  Silently produces a wrong number, or lets two subsystems diverge.
  S2  Records the wrong attribution, or blocks or bypasses capture.
  S3  Misleads a reader, hides a failure, or loses recoverability.
  S4  Cosmetic, naming, dead weight.

Numbering. Findings run A01 to A44 without a gap. A45 and A47 appear here for
the first time: both numbers were already cited, A45 in the owner's session
notes and A47 in bot/jobs.py's start_job docstring, before any entry existed,
so they are filled rather than renumbered. A46 was never written down and is
cited by nothing on either machine; the slot is left empty rather than filled
with a guess. Numbering resumes at A48.

## S1

A01 OPEN  bot/db.py ideal_rate() returns 600.0 when no rate row exists, and
          app.py repeats "or 600.0" in five routes, not four: 197 dashboard,
          319 line_report, 417 job_detail, 810 shift_detail, 903 board. A
          plant with an unloaded rate gets confident arithmetic: expected
          units, gap minutes, FTY and unaccounted minutes are all wrong and
          nothing says so. This is the most dangerous constant in the product.

A02 OPEN  Herbie computed a figure instead of quoting one. The changeover card
          for WO-2611-398 read "32.0 minutes faster than the standard of 60.0
          minutes, resulting in a 46.7% improvement". A 32 minute saving on a
          60 minute standard is 53.3%. The model divided. It did not recur on
          a second run, so the violation is intermittent and a green test run
          is not evidence of correctness.

A03 OPEN  Herbie misstates losses_accounted on the line_day card. It wrote
          "the losses accounted for are 12 scrap units plus 0 lost capacity,
          totaling 12 units" in a paragraph that also reported 12 units of lost
          capacity and 2248 unexplained. Accounted loss is 24. Reproduced on
          consecutive runs.

A04 OPEN  Two competing schema strategies in one appliance. db.py applies
          tools/schema.sql and refuses a stale database loudly. bot/db.py
          ensure_schema silently ALTERs in missing columns. The bot can patch
          a database the web app would have refused, leaving a partial schema
          that then passes the column check.

A05 FIXED Onboarding decoded uploads with errors='replace', so a Windows-1252
          CSV exported from Excel imported as mojibake with no error and no
          warning. The operator's own words are the data of record. Now UTF-8,
          then cp1252, then a refusal that names the problem.

A45 OPEN  The variance gate compares units produced against target_quantity
          with no allowance for time the line was not scheduled to run, so
          off-time trips it by itself. Thirty minutes of lunch on a ten hour
          shift is five percent, which is the entire default tolerance: the
          gate refuses to close a job that was never behind, and the reason it
          then demands is the reason the PDCA reads. bot/jobs.py:156 computes
          (actual - target) / target and nothing subtracts lunch, maintenance
          or CIP. Build the allowance once, in one shared function, before the
          end action exists, or it will be built twice and the two will
          disagree.

A48 OPEN  The bot conversational path commits the job status and the line
          event as two transactions. cont_start_minutes commits the status at
          jobs.py:120 and then calls the committing transition_line at :123;
          cont_end_minutes, h_pause_job, h_resume_job and changeover.py:286 do
          the same. A crash between the two commits leaves one written and not
          the other. This is A47 seen from the other end. The floor path does
          not use it: /floor calls start_job, which writes both in one
          transaction. Recorded as a numbered finding rather than left as the
          paragraph in the A06 build plan, because a paragraph does not
          survive a grep and reads as commentary.

## S2

A06 OPEN  /floor can now start a job and still cannot end one. Two halves
          closed: on 2026-11-20 the hour itself, with shift derived from the
          clock via _current_shift, duration_min from the form, source='floor',
          user_id from a picker and zero accepted as a valid hour; on
          2026-11-22 the start action, which writes jobs.status and the
          line_events row in one transaction through bot.jobs.start_job. Still
          open: end, and the lunch, maintenance and CIP toggles, so the tablet
          cannot close a job. Known as C27. Must precede Whisper, which lands
          in the same POST.

A07 FIXED app.py computed shift_start = 7 + (shift_h - 1) * 8 in three routes
          while three shifts sat configured in settings. A plant that edited
          its shift times saw no change and had hours attributed to the wrong
          shift, with no error raised. Now reads shift_N_start.

A08 FIXED bot/db.py held UNACC_THRESHOLD = 5.0 with no settings key at all,
          and it is a different quantity from job_variance_tolerance, which is
          configured. Now unacc_threshold(conn), settings first.

A09 FIXED Onboarding resolved part numbers and component types with an exact
          case-sensitive match while the rest of the product is case
          insensitive. A CSV spelling a part number differently from the stored
          one failed with "unknown SKU". Now exact first, then COLLATE NOCASE.

A10 OPEN  Herbie's changeover narrative lists per-station savings beside an
          overall variance: "Filler saved 5.0, Capper saved 8.0, Labeler saved
          10.0". Those minutes can be concurrent, and a manager reading the
          list will add them. Per-station detail belongs to a PDCA question on
          a larger model, not on the card.

A11 OPEN  parsers.py holds KNOWN_STATIONS as a literal. It is philosophy
          compliant, because it only guides attribution and falls back to
          station='unspecified' with the words intact, but a wine corker or a
          bag sealer is never attributed. It should be built from the plant's
          own co_steps_v2.station values.

A12 FIXED herbie.narrate's no-data guard fired for any intent with zero units
          and a line_id, and the job summary carries no date, so Herbie said
          "Line 7 on None: no production recorded" about every job that had not
          started. Now intent-specific, and a job gets a true sentence.

A13 FIXED /pdca returned 500. A changeover step with a NULL actual_min reached
          the trend chart and the template divided it. Points with no
          measurement are now dropped in _compute_trend.

A47 OPEN  A line transition closes the current event and inserts the next one
          as two statements. A crash between them leaves the line with no open
          event at all, and every reader treats that as idle: shift
          reconciliation attributes the rest of the shift to nothing and the
          hour by hour chart shows a line that stopped existing. Both
          statements share a transaction in start_job, so the floor start path
          cannot do this. Still open in db.transition_line and in every caller
          that follows it with a separate status commit (A48). Cited by the
          start_job docstring since commit 2178509, which is why this entry
          now exists rather than the citation being removed.

## S3

A14 OPEN  /etc/koorsus-backup.key encrypts every archive and is outside every
          archive. Lose it and the archives become unreadable noise,
          permanently, with no recovery path. Escrow is not a documented step
          anywhere.

A15 OPEN  /mnt/appliance-backup is on the same filesystem as the data. The
          archive protects against deletion and corruption, not against the
          disk dying.

A16 OPEN  export-usb.sh and import-usb.sh in /usr/local/sbin/koorsus are
          hardcoded to /mnt/koorsus-backup and do not carry the appliance
          archive. So Myarra has no offsite backup path at all, only Koorsus
          does.

A17 OPEN  No document root. Koorsus stores extracted text and metadata and
          never the original file, so the document estate lives wherever the
          customer keeps it. The live collection holds 64 chunks from two
          files in /tmp that no longer exist, so its citations point at
          documents nobody can open, and nothing in the system notices.

A18 OPEN  No export path for master data. Onboarding is import only, and
          generate_csv emits the template examples rather than live rows. A
          customer cannot get their SKUs, lines, rates or jobs back out of the
          appliance they own.

A19 OPEN  install.sh does not verify that appliance.env defines every variable
          the units interpolate. With a stale env file, systemd resolves an
          undefined ${VAR} to an empty string and the service fails with a bad
          argument rather than a missing variable. A fresh install is safe
          because the file is created complete; an upgrade is not.

A20 OPEN  install.sh treats any HTTP status as neutral. It should accept 200
          and 302 and flag 000 or a 5xx, otherwise a dead service reads as a
          slow one.

A21 OPEN  Import-time side effects. app.py runs ensure_views at import and
          ask.py runs _get_schemas() at import, so a wrong MYARRA_DB fails with
          an error that does not name the path.

A22 OPEN  maintenance_events holds zero rows. The list page renders an empty
          table, and neither the detail page nor the bot's maintenance handler
          has ever produced a surviving row. HANDOVER calls maintenance a
          first-class event. Untested rather than broken, which is worse.

A23 OPEN  rate_label is in settings and read nowhere. The rate is described by
          a hardcoded "/hr" in board.html, line_report.html, job_detail.html,
          bot/production.py:154 and herbie.py:264.

A24 OPEN  lunch_minutes is in settings, read nowhere, and should be deleted
          rather than wired. bot/shift.py measures actual lunch from
          line_events, which is more truthful than any configured duration.

A25 OPEN  onboarding._int_or_none uses int(float(v)), so 12.7 silently becomes
          12 for case_pack, target_quantity and the rest. Truncation with no
          warning.

A26 OPEN  onboarding._float_or_none does not handle a decimal comma. A
          European CSV fails with "missing ideal_rate" rather than a message
          saying comma decimals are not supported.

A27 FIXED /favicon.ico returned 404 on every page. The route served from
          app.root_path and the file lives in myarr_v2/static.

## S4

A28 OPEN  Five .bak files in the bot package: production.py.bak_override,
          production.py.bak_20261115, jobs.py.bak_bridge, db.py.bak_live,
          shift.py.bak_shiftcode. Two still contain the deleted session gate
          verbatim and will mislead the next grep.

A29 OPEN  Dead entry points and modules: myarr_v2/bot_live.py, bot_v3.py,
          telegram_bot.py, root telegram_bot.py, and myarr_archive/ at about
          830 lines including its own dashboard.py.

A30 OPEN  intent.py is dead. It is imported only by bot_v3.py and
          test_intent.py, both dead. It carries a can-line station list and
          "bottles" wording that describe nothing that runs, which is how a
          future instance concludes the live parser is hardcoded when it is
          not.

A31 OPEN  Client-Demo-backup/ inside the repository holds another complete
          copy of the code, including its own config.py.

A32 OPEN  __pycache__ present in the tree. Whether .pyc files are committed is
          unverified.

A33 OPEN  Name collisions: db.py twice, config.py three times, app.py twice,
          telegram_bot.py twice. New rule adopted: a new module gets a name
          unique across the whole repository.

A34 OPEN  Two identical udev rules now exist, 99-arkiv-usb.rules and
          99-koorsus-usb.rules.

A35 OPEN  The TEMPORARY BRIDGE comment in bot/jobs.py is false.

A36 OPEN  bot_live_v3.py implies a v3 lineage that does not exist. It is the
          live entry point.

A37 OPEN  FISHBONE_CATEGORIES is the six M's, hardcoded in app.py. Arguably
          universal, recorded so nobody wonders.

A38 OPEN  _priority_total weights 10/30/30/30/50 are hardcoded in app.py.

A39 OPEN  /mnt/lake is shared by four products: arkiv_index plus five archived
          copies at 6.4MB each, the legacy /mnt/lake/index, a stray
          chroma.sqlite3, demo_beverage.db with two backups, metrics.db with
          one, and two myarra.db backups.

A40 OPEN  Sudo prompts for a password. The 2026-11-06 delta claims passwordless
          sudo was configured and proven.

A41 OPEN  HANDOVER says of ~/koorsus, "a local clone of ~/arkiv. Ignore it."
          It is the live Koorsus on 5003.

A42 OPEN  HANDOVER says backup and restore does not exist. It does, and has
          since 2026-11-17 for Koorsus and 2026-11-20 for the appliance.

A43 OPEN  ~/koorsus/systemd/ holds arkiv-branded units for port 5001 that are
          not what runs. The live unit is koorsus-app.service on 5003.

A44 OPEN  koorsus.service on 5000 is the legacy Koorsus, kept only because a
          Telegram bot posts to it. Nothing records that.

## What this audit does not cover

Read in full: intent.py (dead), ask.py, herbie.py, onboarding.py, verify.py,
db.py, bot/db.py, bot_live_v3.py, parsers.py, app.py, and the deploy set.

Not read in full: bot/dispatch.py beyond one function, bot/production.py
through greps only, bot/changeover.py, bot/jobs.py, bot/shift.py,
bot/notes.py, bot/maintenance.py, bot/handover.py, bot/support.py,
bot/resolve.py, views.py, recon.py, admin_ops.py, and every template.

The bot write paths are therefore the largest unexamined surface, and A06 is
the only finding there whose shape is known. Expect more.

## Counts

47 findings. 7 fixed and verified on 2026-11-20: A05, A07, A08, A09, A12,
A13, A27. 40 open. A45, A47 and A48 were written down on 2026-11-22; A46 is
still unaccounted for.

Tools that produced them, all in the repository and all re-runnable:
tools/test_csv_roundtrip.py, tools/test_pages.py, tools/test_herbie_cards.py.

## A06 build plan, 2026-11-20

Done. Zero hours accepted, `source='floor'`, `user_id` from a picker,
`shift` derived from the clock via `_current_shift`, `duration_min` from the
form, hour ceiling from `_shift_hours`. Verified: a POST of zero units wrote
`1660|H8|0|1|60|floor|1` and the test row was deleted.

Start. Done 2026-11-22. floor_view dispatches on the hidden action field, and
a post with no action field falls through to the record path untouched. The
start action calls bot.jobs.start_job, which writes jobs.status and the line
event in one transaction, and check_start now tests the line the job is being
started on rather than the line the job carries, so a moved work order can no
longer close the running job's event without a refusal. Six cases in
tools/test_floor_start.py, 6 of 6, including an induced BEFORE INSERT trigger
on line_events that proves jobs.status is unchanged when the event insert
aborts.

Still open. No end action, so the tablet cannot close a job, and no lunch,
maintenance or CIP toggles.

Shape of the remainder. Rewrite floor_view's POST as an action dispatcher on a
hidden `action` field: record, start, end, toggle.

  start   Built. Dropdown of the line's open jobs, plus a typed job number for
          the moved case, an optional reason for the move and an optional
          operator picker. The three checks are check_start's own: not
          completed, not paused, and the line is not already running a
          different job. Status and event are written by start_job inside one
          transaction, not by a separate transition_line call as this bullet
          first said; that shape is now A48.

  end     Require the current line event to be production. Apply the variance
          gate exactly as bot/jobs.py does: if no completion_variance_reason
          and |actual-target|/target exceeds job_variance_tolerance, demand a
          reason before closing. Then status='completed' with actual_end, and
          transition_line to idle.

  toggle  Lunch, maintenance and CIP as three on/off switches. Throwing a
          switch closes the production event and opens one of those states,
          carrying the job id on the event. Throwing it back reads the job id
          off the event and returns to production. No new storage.

Two things to fix on the way. bot/jobs.py writes the job status and the line
event in two separate commits, in cont_start_minutes, cont_end_minutes,
h_pause_job, h_resume_job and changeover.py:286, so a crash between them leaves
one written and not the other. That is now A48. The new floor path does write
both inside one transaction. And the variance gate must not be skippable from
the tablet, or a lead can close a badly missed job with no reason, which is the
record the PDCA needs.

Note, not a finding, 2026-11-22. h_start_job commits status='running' at
jobs.py:91 and writes no line event until cont_start_minutes at :123. If the
operator never answers the minutes prompt, the job is running and the line
shows idle indefinitely. It is recorded because it is what the record cannot
see, not because a fix is owed. Noticing that a line is not running is the
floor's job, and capture stays flexible so that whatever can be recorded is
recorded. The floor path has no such window, because start_job writes both at
once.
