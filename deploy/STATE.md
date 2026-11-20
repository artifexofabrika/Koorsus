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
answering 302. Appliance mode has never been run.

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
- Appliance-mode rehearsal of install.sh. Never run.
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
