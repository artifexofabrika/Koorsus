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

A01 FIXED Both halves closed: the web half 2026-11-23, the Telegram half
          2026-11-24. The web half: app.py no longer substitutes 600.0 at any of
          its five sites (dashboard, line_report, job_detail, shift_detail,
          board). A missing rate renders as an em dash through two Jinja
          filters, a total with no rate behind it renders as a dash rather than
          a confident zero, and FTQ still reports because FTQ needs no rate.
          tools/test_rates.py, 5 checks, renders all four pages against a
          database with one line deliberately missing its rate, because the
          reference appliance has a rate for every open job and test_pages would
          never have executed that path. Also added the same day: a job-level
          check on /setup/verify that names open jobs whose line and SKU have no
          rate row, which is the grain the arithmetic actually uses.
          The Telegram half: bot/db.py ideal_rate() returns None, and treats a
          row holding NULL or zero as absent because a zero cannot divide
          anything. The five call sites were four in production.py and one in
          shift.py, not six: the sixth occurrence was a second ideal_rate in
          bot/resolve.py with the same 600.0 fallback and no caller, deleted
          with this change. production.py skips the plausibility challenge and
          leaves the gap unmeasured when there is no expectation to check a
          number against, names the SKU and the line in the reply, keeps FTQ,
          and write_hour takes an unknown gap without flagging the hour.
          shift.py had two substitutions of its own beyond the one it inherited:
          a falsy rate became 600.0 in the per-run loop and the weighted rate
          defaulted to 600.0 again. An unrated run now leaves production time,
          scrap time and the residual None for the whole window, because scoring
          the rated runs and calling the difference a residual charges the
          unrated hours to nothing and reports it as fact. The report dashes
          those figures and names the SKU and the line, and end shift closes
          without asking the operator to explain a number that does not exist.
          tools/test_bot_rates.py, 19 checks, builds its own database with one
          rated pair and one unrated pair and drives the bot's own functions at
          both, so a fix that deleted the arithmetic outright fails there too.
          Run against the deployed code it failed at 600.0, at 0.0 from the zero
          row, on the surviving resolve.py copy, and crashed the record reply on
          the no-rate gap; after the change it is 19 of 19. Regressions:
          test_rates 5 of 5, test_floor_start 15 of 15, test_csv_roundtrip 8 of
          8, test_pages 27 routes 0 failed.
          Unproven, deliberately: myarra-bot has not been restarted, because
          sudo asks for a password on this appliance (A40). The unit is still
          running the previous modules in memory, so it will keep answering
          600.0 until it is restarted. The file on disk is the fix; the service
          is not yet the file.
          This gap will keep occurring rather than being an edge case. A rate
          belongs to a SKU on a line, and a SKU that has never run on that line
          has no rate until the first run measures it (FLOOR-MODEL, Nothing
          stops the line). The floor is unaffected either way: it asks nothing
          about rates.

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
          Observed correct once, 2026-11-22: the same card read "12 scrap units
          and 12 units of lost capacity, totaling 24 losses accounted". One run
          of an intermittent behaviour is not a fix and is not recorded as one.
          The same run's tracer flagged 24.0 as an untraced number, because 24
          is a derived sum rather than a quoted field. That is the limit
          STATE.md already states: tracing catches a computed figure, not a
          field reported with the wrong value.
          Second instance, 2026-11-23, on the line_day card. Given a payload
          note reading "32 minutes running this hour" for a partial hour, the
          model wrote "32 minutes running each hour". The number traced
          perfectly and the sentence around it was false, which is this defect
          exactly: the field was right and the scope was invented. Addressed the
          same day by marking partial hours in the payload and giving line_day
          rules of its own, and the generalisation did not recur in four runs.
          The job card has since shown the same family from the other direction,
          mixing minutes and units in one clause and calling FTQ a rate. It is
          the next card running without rules of its own.

A04 OPEN  Two competing schema strategies in one appliance. db.py applies
          tools/schema.sql and refuses a stale database loudly. bot/db.py
          ensure_schema silently ALTERs in missing columns. The bot can patch
          a database the web app would have refused, leaving a partial schema
          that then passes the column check.

A05 FIXED Onboarding decoded uploads with errors='replace', so a Windows-1252
          CSV exported from Excel imported as mojibake with no error and no
          warning. The operator's own words are the data of record. Now UTF-8,
          then cp1252, then a refusal that names the problem.

A45 FIXED Built 2026-11-22, verified 9 of 9 in tools/test_floor_start.py. The
          gate compared units produced against target_quantity with no
          allowance for time the line was not scheduled to run, so thirty
          minutes of lunch on a ten hour shift, five percent, tripped the
          default tolerance by itself and demanded a reason for a job that was
          never behind. scheduled_window reads the weekly schedule feed, which
          both Odoo and the jobs.csv upload write, and variance_allowance
          subtracts measured lunch, maintenance and CIP minutes clipped to that
          window: a 600 minute window at 1000 target, minus 30 off-time
          minutes, allows 950. The eighteen line copy in h_ending_job is gone,
          so the floor end action will call the same gate rather than a second
          one.
          A job with no window still gates against the raw target and says so
          in the sentence; a job with no target does not gate, because that is
          a master-data defect. Capacity is measured on parts produced, not
          good parts: a scrap-heavy hour at full rate has lost no capacity.

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

A49 FIXED 2026-11-22. The service worker served /floor cache-first, so once a
          device had seen the page it served itself that page forever and never
          revalidated; CACHE_NAME never changed, so activation never purged it.
          The floor forms carry job_number and period in hidden fields, so a
          frozen page posts the job and the hour that were true when it was
          cached: an hour written against a job that ended days ago, no error
          and no trace anywhere. Fixed in static/sw.js. /floor is network-first
          with the cached copy as the offline fallback only, /static stays
          cache-first, POST and /api are never touched, and the cache name is
          myarra-shell-v2 so every device purges v1 on its next visit. Found by
          reading, not by a device; no one has yet watched a phone pick up v2.

A50 FIXED Found 2026-11-24 while proving A01, fixed the same day. Same family as
          A01 and the opposite sign. The line_day payload computed lost capacity
          with COALESCE(lsr.ideal_rate, 0) at herbie.py:226, so a line whose SKU
          had no rate reported zero lost capacity, and the view behind
          unaccounted minutes, v_unaccounted_minutes_by_run, ended with "AND
          lsr.ideal_rate > 0", so unrated hours were absent from that view
          altogether and SUM over it returned 0. The card therefore stated "no
          downtime, and no lost capacity. Scrap accounted for all losses, with
          no unexplained losses. The standard rate was 0" about hours it could
          not score, and then in the next breath reported a capacity gap.
          Observed on Line 2 for 2026-11-23 in a card run.
          A zero stood where a figure was unknown, and zero lost capacity is a
          stronger claim than admitting the figure does not exist: it says the
          line lost nothing. It was the dash contract one layer below the
          templates, in the payload rather than in the wording.
          The model quoted what it was handed, so no prompt change reaches this.
          Fixed 2026-11-24. The view keeps the row and NULLs the three
          rate-derived columns (gap_units, gap_min, unaccounted_min), so a
          missing rate no longer deletes an hour and its recorded downtime with
          it; unrated_min carries the duration that could not be scored, so the
          job card and the unaccounted card stop presenting a partial sum as a
          whole. The line card leaves lost capacity, losses accounted, losses
          unexplained and theoretical capacity null, keeps the capacity gap
          because it compares production with the target, and says in a sentence
          carried in the payload which figures were not computed and for which
          SKU on which line. The template fallback learned to render an unknown
          as an em dash, which item 2's veto now depends on.
          tools/test_line_card_rate_gap.py, 15 checks: red at rows=1 before the
          change, 15 of 15 after, with the rated line asserted to its old
          arithmetic so a fix that flattened both lines into dashes fails.
          Label: blocks the demo. The demo carries two unrated SKU-line pairs on
          purpose and one of them has a live running job, so a walk that opens
          the line_day card meets the contradiction directly. It blocks a pilot
          for the same reason whether or not anyone opens the card.

A52 FIXED Found 2026-11-24 while implementing A50, fixed the same day.
          gross_production was computed as actual_units + scrap_units, and the
          2026-11-07 convention, stated in FLOOR-MODEL and in herbie's own
          glossary, is that units_filled already contains scrap: 600 produced
          with 20 scrap is 600 total and 580 good. Adding scrap again counted it
          twice, so theoretical_capacity and capacity_gap were inflated by
          exactly scrap_units on every line card that had scrap. The card of
          2026-11-23 read gross production 12,212 for 11,987 produced with 225
          scrap, and reported a capacity gap of 550 against a target of 11,662
          where produced against target is 325.
          That mattered beyond arithmetic: the diagnostic rule tells a reader to
          compare losses_unexplained with losses_accounted, so "when
          losses_unexplained is larger than losses_accounted the data is
          incomplete" was advice computed from an inflated gap.
          Fixed: gross_production is actual_units, so theoretical_capacity,
          capacity_gap and losses_unexplained all lose the extra scrap. The
          glossary now says gross production is the parts produced and that scrap
          is a subset of it rather than a second helping, and the fallback
          narrative no longer calls actual_units "good output" when it is the
          total including scrap.
          Capacity gap figures change as a result. The card that read 550 against
          a target of 11,662 now reads 325, which is 11,987 produced against
          11,662 due. tools/test_line_card_rate_gap.py holds it at 16 checks:
          three were red against the previous arithmetic — the unrated gap, the
          rated arithmetic, and gross against actual — and all are green after,
          with the rated line still carrying its downtime uplift.
          Label: blocks the demo. A plant manager who totals the parts himself
          finds a gross figure larger than the number of parts made.

## S2

A06 FIXED Closed 2026-11-22, in three pieces rather than one. On 2026-11-20 the
          hour itself: shift derived from the clock via _current_shift,
          duration_min from the form, source='floor', user_id from a picker and
          zero accepted as a valid hour. On 2026-11-22 the start action, which
          writes jobs.status and the line_events row in one transaction through
          bot.jobs.start_job. Then end and the three switches, where a lead can
          start, log, close, and throw lunch, maintenance or CIP and throw it
          back, with the job id carried on the event. Verified 15 of 15 in
          tools/test_floor_start.py. Known as C27. Whisper still lands in the
          same POST when it comes.

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

A14 OPEN  Half done 2026-11-24. /etc/koorsus-backup.key encrypts every archive
          and is outside every archive. Lose it and the archives become
          unreadable noise, permanently, with no recovery path. Escrow was not a
          documented step anywhere, in the installer or in the install notes.
          Built: deploy/ESCROW.md, which states the model (two holders in the
          plant's password manager, one printed copy sealed and held off site,
          kept apart from the USB archives because a key in the same bag as the
          ciphertext is one loss rather than two), the sealing procedure, and
          what must never happen. deploy/backup/escrow-check.sh proves a
          passphrase read off paper opens an archive on a machine that is not the
          appliance, and it separates the two failures that need different
          actions: it verifies the archive's own .sha256 before decrypting, so a
          damaged file is reported as damaged rather than as mis-keyed.
          A second key file, /etc/arkiv-backup.key, is not a second passphrase to
          escrow but a way to open the wrong one during a restore; it is recorded
          as A53.
          15 checks in test-escrow-check.sh, no root and no appliance needed.
          Not closed, deliberately: recoverability exists when a copy is off site
          and has been used, not when a procedure is written down. The sealed copy
          is the owner's act. Until it is sealed, stored apart from the archives,
          and run once against the oldest archive still held, this stays open.
          An instance cannot escrow anything on the owner's behalf, and an
          instance that marks this fixed because the document exists has confused
          a procedure with a copy.

A15 OPEN  /mnt/appliance-backup is on the same filesystem as the data. The
          archive protects against deletion and corruption, not against the
          disk dying.

A16 OPEN  Half done 2026-11-24. export-usb.sh and import-usb.sh in
          /usr/local/sbin/koorsus are hardcoded to /mnt/koorsus-backup and do not
          carry the appliance archive, so Myarra had no offsite path at all.
          Built: deploy/backup/export-usb.sh and import-usb.sh carry both
          products' newest archives with a manifest the import reads instead of
          guessing which archive belongs to which product. Every checksum is
          verified after the copy to the device and again after staging, a damaged
          copy is reported as damaged rather than as a wrong passphrase, and a
          device that already holds a passphrase file is refused outright, because
          the key must not travel with the ciphertext (A14).
          Import stages and stops. It prints the archives now available and how to
          restore any of them, so a plant that discovers three days later it was
          running the wrong thing can go back to an older archive without the
          appliance restoring itself because somebody inserted a stick. It also
          refuses a manifest naming a destination this appliance does not own: a
          device does not get to choose where files land.
          20 checks in test-usb-roundtrip.sh, no root and no stick: newest not
          oldest, manifest names both products, no key on the device, staleness
          warning, foreign destination refused, damaged archive refused, and the
          import restoring nothing.
          Also built: deploy/koorsus-backup.service and .timer, because nothing
          scheduled the Koorsus index backup and the newest archive on the
          reference appliance was a week old, which the export would have carried
          and called an offsite copy. 03:15 sits between Arkiv's 03:00 and the
          appliance's 03:30 so the three nightly jobs do not contend for the disk.
          Installed and run 2026-11-24T12:19. The timer is enabled, next elapse
          03:18 on 2026-11-25, and the first run wrote
          koorsus-20261124-121924.tar.gz.enc: 261,696 bytes against 94,096 for the
          week-old archive, because the index now holds 80 documents.
          ExecStartPost verified the result rather than trusting the exit code:
          sqlite integrity ok, and the document count inside the archive matched
          live at 80 of 80, which is the only check that distinguishes a backup
          from a file that merely got written.
          Not closed: the old Koorsus-only scripts in /usr/local/sbin/koorsus
          still sit there with the old behaviour. An operator who reaches for
          those gets a Koorsus-only export that restores on insert, which is the
          same shape as A53 and belongs to the Koorsus tree rather than this
          repository.

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

A22 OPEN  maintenance_events held zero rows. The list page rendered an empty
          table, and neither the detail page nor the bot's maintenance handler
          had ever produced a surviving row. HANDOVER calls maintenance a
          first-class event. Untested rather than broken, which is worse.
          Since 2026-11-23 the table holds three rows, written by
          tools/seed_improvement_layer.py and attached to real jobs on the
          lines that carried the most recorded downtime, so the list and detail
          pages are exercised for the first time and the default thirty-day
          view is no longer empty. That is not the same as the handler working:
          nothing has still produced a maintenance row through the bot, and no
          line has ever entered the maintenance state in line_events, so the
          maintenance switch and the bot path both remain unproven.

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

A51 OPEN  Found 2026-11-24. bot/shift.py writes shift_reconciliations (usable
          minutes, actual, scrap, downtime, production time, scrap time,
          residual, explanation) and nothing reads it. A grep across app.py,
          views.py, recon.py and every template finds no reference outside the
          writer. So when end shift asks the operator what happened and he
          answers, the answer is stored where no screen, no card and no export
          ever shows it. The bot asks a question whose answer the product does
          not display, which is the shape PHILOSOPHY's "unknown is a valid
          answer" exists to prevent: an operator who never sees his answer used
          learns not to give one.
          Not fixed. The shift page computes its own figures from hourly_runs,
          so this is a missing consumer rather than a wrong number, and the row
          does hold the operator's words.
          Label: blocks a pilot. It does not stop a demo, but the operator's own
          words are the data of record and here they are write-only.

A53 OPEN  Found 2026-11-24 during A14's escrow recon. Two key files exist:
          /etc/koorsus-backup.key (48 bytes, 2026-11-17) and /etc/arkiv-backup.key
          (27 bytes, 2026-11-15). Both backup scripts default to the first:
          deploy/backup/backup.sh writes the appliance archive with it, and
          /usr/local/sbin/koorsus/backup.sh writes the Koorsus index archive with
          it. /usr/local/sbin/koorsus/restore.sh defaults to
          ${ARKIV_BACKUP_KEY:-/etc/arkiv-backup.key}, and no unit and no
          /etc/default entry sets ARKIV_BACKUP_KEY, so the restore path opens
          with a key the archives were never written with. A recovery run reports
          a bad decrypt on a good archive, and the natural conclusion is that the
          backup is corrupt. setup-backup-key.sh carries the same default, so it
          writes a key that nothing reads for backup.
          The evidence that the live passphrase is the 48-byte one: the only
          Koorsus archive on the box (2026-11-17T10:41) was written fifteen
          minutes after that key was created, and the other key is two days older
          than the archive it would have to have encrypted.
          Not fixed here. restore.sh lives in /usr/local/sbin/koorsus, which is
          the Koorsus product's tree and not this repository; the repair is one
          default in one script and belongs to whoever owns that tree. What this
          repository can do is say so, which ESCROW.md now does, along with the
          workaround: set ARKIV_BACKUP_KEY=/etc/koorsus-backup.key when restoring,
          or let escrow-check.sh tell you which passphrase opens the file.
          Label: blocks a pilot. A restore that fails on a good archive is the
          worst failure this product has, because it happens on the day nothing
          else can be tried.

## S4

A28 FIXED 2026-11-24. There were 41 .bak files, not five. Six in the bot package,
          including changeover.py.bak_20261114, which this entry never listed,
          and roughly twenty template backups under myarr_v2/templates/ and
          myarr_v2/static/. Every one was gitignored, so none was ever in
          history: they were litter on the disk that a grep would trip over, and
          five was the part of the mess somebody had noticed. Removed, along with
          every __pycache__ directory.

A29 FIXED 2026-11-24. Deleted: myarr_v2/bot_live.py, bot_v3.py, both
          telegram_bot.py, test_intent.py, test_scenarios.py,
          test_scenarios_v3.py, telegram-bot.service, myarr_archive/, and the
          archive/ tree of old Jeeves code. Nothing live referenced any of them,
          and that was checked rather than assumed: the bot unit runs
          myarr_v2/bot_live_v3.py, which imports myarra_settings, bot.db and
          bot.dispatch and not bot_v3, despite its own docstring claiming
          otherwise (A36).

A30 FIXED 2026-11-24. intent.py is deleted with both of its consumers, bot_v3.py
          and test_intent.py. The can-line station list and the "bottles" wording
          describe nothing that runs, and now they describe nothing at all, so
          the future grep this entry was written for cannot happen.

A31 FIXED 2026-11-24. Client-Demo-backup/ is deleted, about forty files
          including its own config.py and its own copy of the rag package.

A32 FIXED 2026-11-24. Answered as well as closed: .pyc files were committed,
          inside Client-Demo-backup, and the tree also carried __pycache__
          directories beside live modules. All are gone from the tip. They remain
          reachable in history, which is why the directory is 22MB for 299 files;
          removing them needs a history rewrite and this repository forbids one.
          A clone is clean, a clone's .git is not.

A33 OPEN  Name collisions: db.py twice, config.py three times, app.py twice,
          telegram_bot.py twice. New rule adopted: a new module gets a name
          unique across the whole repository. Progress 2026-11-24: the
          telegram_bot.py collision is gone, and config.py is not tracked at all
          any more, only config.example.py, because the real one holds
          credentials. What remains is myarr_v2/app.py beside the root app.py,
          and db.py in myarr_v2 beside bot/db.py. The root app.py belongs to the
          Koorsus product on port 5000 and moves only when those units move.

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

52 findings. 18 fixed and verified: A05, A07, A08, A09, A12, A13 and A27 on
2026-11-20, A06, A45 and A49 on 2026-11-22, A01, A50 and A52 on 2026-11-24, and
the repository cleanup of A28, A29, A30, A31 and A32 later the same day.
34 open. A45, A47, A48 and A49 were written down on 2026-11-22, and A50, A51,
A52 and A53 on 2026-11-24, found while proving and repairing A01, A50 and A14.
A46 is still unaccounted for.

Tools that produced them, all in the repository and all re-runnable:
tools/test_csv_roundtrip.py, tools/test_pages.py, tools/test_herbie_cards.py,
tools/test_floor_start.py, tools/test_rates.py, tools/test_bot_rates.py.

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

End and toggles. Done 2026-11-22. end_job closes the job and returns the line
to idle in one transaction, calling variance_refusal first, so the gate cannot
be skipped by closing from the tablet. toggle_line_state throws lunch,
maintenance or CIP and throws it back, carrying the job id on the event, so the
off-time the gate subtracts is written by the person who was there. C27 is
closed.

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

  toggle  Built. Three switches in one form, so the pressed button supplies the
          state and one name picker serves all three. Throwing one closes the
          production event and opens that state carrying the job id; throwing
          it back reads the job id off the event and returns to production. No
          new storage. A line in an off-time state is no longer rendered as
          idle, which it was, so it used to offer a Start panel and then refuse.

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
