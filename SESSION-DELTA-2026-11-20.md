# SESSION DELTA 2026-11-20 - FOUNDATION, BACKUP, INSTALLER, AUDIT

Follows SESSION-DELTA-2026-11-13-AFTERNOON.md, the last technical record.
There is no record between 2026-11-14 and 2026-11-19, and the code is the
only authority for that week.

Read alongside PHILOSOPHY.md and the four documents created this session in
deploy/: AUDIT.md, STATE.md, INSTALL.md, FLOOR-MODEL.md. Those four carry the
detail. This delta records what was decided and what must not be re-litigated.

All commits pushed to origin/main. HEAD at close: 8d546de.

## What was done

### Config extraction

myarra_settings.py now owns DB_PATH, LLM_URL, TELEGRAM_BOT_TOKEN, ODOO_TOKEN
and check_llm(). intent.py, ask.py, herbie.py and bot_live_v3.py read from it.
ask.py and herbie.py take DB_PATH from db.py instead of hardcoding it, which
they had been doing. bot_live_v3.py no longer imports the Koorsus config, so
Myarra no longer depends on Koorsus to start.

app.py logs LLM reachability at startup and verify.py surfaces it on
/setup/verify. Proven by overriding LLM_URL to a dead port: all four readers
agreed and check_llm returned False.

Before this, LLM_URL existed as four independent copies and DB_PATH as four.

### Backup and restore

deploy/backup/ holds backup.sh, restore.sh, verify.sh and two manifests.
One encrypted archive covers Myarra and Koorsus at one vintage. SQLite goes
through sqlite3 .backup so a live write cannot tear it. sha256 beside every
archive, thirty retained, and a missing artifact exits 2 rather than being
silently omitted.

appliance-backup.timer runs daily at 03:30 and verifies the archive it has just
written, in the same run.

Proven twice: a scratch restore via APPLIANCE_RESTORE_ROOT, and an in-place
restore with identical content hashes before and after (a0fd9bd7... and
6e9a416e...), services active again, routes serving.

### Installer

deploy/install.sh, modes appliance and --koorsus. It refuses on a failed
precondition, never overwrites appliance.env, normalises BOM and CRLF out of
the Koorsus scripts, generates the backup passphrase once, and starts
certificate-dependent services last.

Run twice in Koorsus mode and once in appliance mode, EXIT=0 every time, with
myarr, myarra-bot and koorsus-app active and both ports answering.

### Tests, and what they found

tools/test_csv_roundtrip.py, tools/test_pages.py, tools/test_herbie_cards.py,
all committed and re-runnable.

CSV round trip, 8 checks. Found and fixed: decoding with errors='replace'
silently corrupted any Windows-1252 upload; part numbers and component types
resolved case-sensitively while the rest of the product does not.

Page sweep, 26 routes. Found and fixed: /pdca returned 500 because a changeover
step with a NULL actual_min reached the trend chart; /favicon.ico served from
the wrong directory.

Herbie cards, 5 cards. Found and recorded, not fixed: the model computed a
percentage instead of quoting it, intermittently; and the line_day card
misstates losses_accounted, repeatably. Both are prompt and payload problems.

### The floor page, first half

Fixed: units_filled carried min="1" and required, so a zero-production hour
could not be recorded at all. Now accepts zero. /floor wrote shift='1' as a
literal and left source at its column default of 'seed'; it now derives the
shift from the clock via _current_shift and writes source='floor' and a
user_id from a picker. duration_min comes from the form, prefilled 60. The
report and board pages looped range(1, 9), so ten and twelve hour shifts
produced periods that never displayed; the ceiling now comes from _shift_hours.

Still open: no line_events row, so the tablet cannot start or end anything.

### The record corrected

AUDIT.md replaces the audit of 2026-11-13, which was never saved. Forty-four
findings, seven fixed and verified, thirty-seven open, each naming a file. It
states plainly which parts of the code were never read.

## Decisions taken 2026-11-20, do not re-litigate

The appliance is Myarra plus Koorsus. Arkiv is a separate product and never
ships with Myarra. Koorsus may be sold alone; Myarra is never sold without
Koorsus.

Koorsus is the Arkiv codebase deployed a second time with different
configuration, not a second codebase, and it never carries Arkiv branding,
because Arkiv is being positioned for legal and medical.

No standard image. A board is flashed with JetPack by hand and then provisioned
by install.sh. Volume units are clones of a verified board.

The model is carried on the USB stick with everything else. A plant with no
route to the internet cannot download two gigabytes.

One archive, one manifest, both products at one vintage. A restore that brings
back documents but not production data is not a restore.

Restore stops and starts the services. The original restore-index.sh did
neither and reported success while running processes served the directory it
had just moved aside.

The backup passphrase stays at /etc/koorsus-backup.key even though the archive
is named for Myarra. That is the path escrowed in the owner's vault, and
renaming a key path risks losing the only copy that matters.

config.py stays out of git because it holds credentials. config.example.py is
the tracked template a fresh clone copies from.

The floor uses a name picker, not a PIN. It records who claimed the tablet, not
who proved it. The failure we care about is capture slowing down.

Zero is a valid hour. The operator must enter it deliberately; a blank field is
not a zero.

Rework and scrap are one bucket. Both fail first time quality, and whether the
money is later recovered is a financial question this product does not ask.

The operator is the final arbiter. The tablet writes the spine, through
bot.db.transition_line and the functions beside it, so there stays one writer
and one implementation.

The bot does the arithmetic and calls out what is missing. The operator may
answer anything. No mandatory dropdown, no checkbox. If the answer is nonsense
the gap shows on the hour by hour chart and a human sees it.

Myarra is a labour tracker and a continuous improvement system, not a financial
one. Hours worked and what came out of them. No material usage.

Shifts live in settings and are read, not hardcoded. Shift length is derived
from the configured start and end, so ten and twelve hour shifts work.

Off-time for lunch, maintenance and CIP is measured from the moment the switch
was thrown. That is deliberate, and it does not contradict the line in
PHILOSOPHY about the clock ordering events rather than measuring duration,
which is about job duration.

The changeover aggregate standard is its own figure, never the sum of the step
standards, because steps run concurrently with enough people. Per-station
detail belongs to a PDCA question on a larger model, not to the Herbie card,
because a manager reading a list of per-station savings will add them.

A new module gets a name unique across the whole repository, not merely within
its folder.

## Corrections to HANDOVER.md

HANDOVER says of ~/koorsus, "a local clone of ~/arkiv. Ignore it." It is the
live Koorsus on 5003. Do not ignore it.

HANDOVER says backup and restore does not exist and blocks every install. It
exists, was verified on 2026-11-17 for Koorsus, and covers the appliance as of
2026-11-20.

HANDOVER lists four services. There are seven: the four product units plus
arkiv, the legacy koorsus on 5000, and email-agent.

HANDOVER repeats a 2026-11-06 claim of passwordless sudo. Sudo prompts.

## Open, in the order I would take it

C27 remainder: rewrite floor_view's POST as an action dispatcher covering
record, start, end and the three toggles. The plan is written against A06 in
AUDIT.md. Start with the start action alone and test it before the rest.

Two spine defects on that path: bot/jobs.py commits the job status and the
line event separately in five places, so a crash leaves one written and not the
other; and the variance gate must not be skippable from the tablet.

A01, ideal_rate falling back to 600.0 in bot/db.py and four routes in app.py.
The most dangerous constant in the product.

A04, two schema strategies. db.py refuses a stale database; bot/db.py silently
ALTERs it.

A19 and A20, the installer's env precondition and its HTTP check.

A14 and A16, the key outside the archive, and the appliance archive having no
offsite copy because the USB scripts point at /mnt/koorsus-backup.

A17 and A18, the missing document root and the missing master-data export.

A22, maintenance holding zero rows, so its page and its bot path have never
been walked.

Herbie content defects, A02, A03 and A10.

A23, rate_label unwired.

The bot path tests, which need deploy/FLOOR-MODEL.md turned into real operator
messages.

Whisper last and optional. The typed number pad is the primary path and the
floor is too loud for voice.
