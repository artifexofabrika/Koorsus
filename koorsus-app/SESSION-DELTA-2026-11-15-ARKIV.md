# SESSION DELTA 2026-11-15 — ARKIV

Read this first. It supersedes nothing on the Myarra side; Arkiv is a
separate product with its own record. For Myarra, read the Koorsus
repository deltas.

Read alongside:
- PHILOSOPHY.md (this repo) — the five inviolable commitments
- FAQ.md (this repo) — customer-facing, the honest limits
- QUICKSTART.md — the card that ships in the box
- PROVISIONING.md — the internal runbook
- LICENSE — FSL-1.1-MIT

Repository: https://github.com/artifexofabrika/Arkiv (private)
Head at the end of this session: see `git log --oneline -1`.

## WHAT ARKIV IS

A private, on-premise document assistant for legal, medical, and
professional offices. A customer-owned appliance. The firm ingests its
documents, tags them by matter, and asks questions in plain English.
Arkiv answers from those documents, cites the source of every claim, and
refuses when the answer is not in the documents.

No cloud. No subscription. No data leaving the office. Source-available
under FSL-1.1-MIT.

It is the office counterpart to Myarra. Myarra measures the floor. Arkiv
reads the office. Same posture, different subject.

## CURRENT STATE (verified 2026-11-15)

Running as a systemd service on HTTPS port 5001, enabled at boot, two
Gunicorn workers, TLS certificate from mkcert covering 192.168.100.2,
localhost, and the Jetson hostname. No browser warning on the Windows
machine that trusts the root CA.

Working and tested today:

- Login: shared office PIN, session cookie, password-manager compatible.
  Five failed attempts per IP, fifteen-minute lockout (in-memory,
  per-worker; the persistent version is v0.2).
- Ask page: single-answer panel, matter scope dropdown, recent-questions
  history in browser localStorage (capped at 10), copy / download .txt /
  print buttons, refusal when the answer is not in the documents.
- Matter filter: proven on two matters with shared party names (Copper
  Kettle as plaintiff in Matter A, as defendant in Matter B). Every
  question answers correctly in its own scope and refuses in the wrong
  scope. This is the architectural bet and it holds.
- Ingestion: multi-file upload, uploader name and matter reference on
  every chunk, five formats (.txt .md .pdf .docx .odt), PDF extraction
  via pypdf. Collapsible library view. Uploader and matter prefill via
  localStorage.
- Encrypted backup: AES-256, PBKDF2, 200k iterations. Passphrase in
  /etc/arkiv-backup.key, root-only, set by the customer at provisioning.
  Checksum file alongside every archive. Retains 30 archives. Nightly at
  03:00 via systemd timer.
- Restore: no-argument mode finds the newest archive, shows it, asks for
  `yes`. Verifies checksum before decryption. Keeps the previous index
  for rollback. Refuses tampered archives (proven by test).
- Weekly verification: verify-backup.sh decrypts the newest archive,
  extracts to a temp directory, runs sqlite integrity_check, counts
  documents, compares to live. Writes a status file. Sunday 04:00 timer.
  Proven: live=150 backup=150.
- Factory reset: reset.sh, requires the literal word RESET, moves the
  current index aside (never deletes), creates empty, chowns to jeeves,
  restarts, verifies. Tested end to end with restore.
- Favicon matches the Myarra icon.

## WHAT IS NOT VERIFIED

- LUKS full-disk encryption. Planned at flash time, documented in
  PROVISIONING.md section 2, not yet executed on a bare Jetson. This is
  the only technical gap between the dev box and a shippable unit. Run it
  on the first bare device and correct the runbook.
- The Quickstart card claim about the office manager setting the PIN.
  There is no page for it yet. See "known gap" below.
- Per-user login. Shared PIN today.
- PWA. Browser-only today.
- VPN remote access. Planned as an upgrade tier.
- Password-manager autofill on the login form: the form has no username
  field, so some vaults (Bitwarden) prompt every time. Cosmetic, ten
  minutes, before the first customer install.

## KNOWN GAP INTRODUCED TODAY

QUICKSTART.md says "your office manager should sign in first, set a
strong 16-character PIN." There is no /settings page for that. The PIN
lives in config.py. The fix is a /settings route, a small SQLite or JSON
store for the hash, and a fallback to config.ARKIV_PIN on first run.
Until that is built, the card overstates what the customer can do. Either
build it or change the card. Building it is the right answer.

## ARCHITECTURE

Files in ~/arkiv/:
    app.py                  Flask app, port 5001, all routes and templates
    config.py               PIN, SECRET_KEY, model, paths (gitignored)
    config.example.py       template, committed
    rag/chunking.py         token-aware, section-aware text splitter
    rag/ingest.py           format extractors, file -> chunks -> store
    rag/store.py            ChromaDB client, embedder, matters()
    rag/retrieve.py         hybrid retrieval, semantic + keyword, RRF
    rag/generate.py         prompt builder, llama.cpp caller
    backup.sh               tar + openssl enc + sha256, retain 30
    restore.sh              no-arg or explicit path, checksum, rollback
    reset.sh                factory reset, RESET to confirm
    verify-backup.sh        weekly rehearsal, integrity check, count
    setup-backup-key.sh     one-time passphrase setup
    systemd/                five unit files, copied to /etc/systemd/system
    favicon.png
    README.md, LICENSE, FAQ.md, PHILOSOPHY.md
    QUICKSTART.md, PROVISIONING.md, this file

Services:
    arkiv.service           Gunicorn + TLS on 5001
    arkiv-backup.timer      daily 03:00, runs arkiv-backup.service
    arkiv-verify.timer      Sunday 04:00, runs arkiv-verify.service
    koorsus-llm.service     shared llama.cpp server on 8080 (owned by
                            the Koorsus/Myarra appliance, not Arkiv)

Data:
    /mnt/lake/arkiv_index   ChromaDB persistence
    /mnt/arkiv-backup       backup archives (USB in production)
    /etc/arkiv-backup.key   backup passphrase, root-only
    /var/log/arkiv-backup.log, /var/log/arkiv-verify.status

Ports:
    5000  Koorsus RAG (Myarra)
    5001  Arkiv
    5002  Myarra web
    8080  llama.cpp (shared by all three)

## DECISIONS TAKEN 2026-11-15

Separate product. Arkiv is its own repository, its own service, its own
port. It shares rag/ code with Koorsus but is not a blueprint or a fork
of the Myarra app.

Matter as the container. The lawyer chooses the matter before asking.
Cross-matter search ("all matters") is available but not the default.
Standard in legal RAG per the market research (Milvus, Voyager, Harvey).

Shared office PIN for the base tier. Per-user login is the upgrade tier.
The shared PIN is honest for a two-to-five-attorney firm.

Firm-held backup passphrase. Artifexo does not hold a copy. The pitch
collapses if the customer hears "we can read your backup." Stated plainly
in the Quickstart and the FAQ.

Encrypted, removable USB backup. Two protections: stolen USB is useless
without the passphrase, stolen device contains no backup. The customer
keeps the USB in their safe. Backups can also go to any cloud the firm
chooses, because they are encrypted.

Backup verified weekly by real restore. Not "the tarball looks fine."
Actually decrypted, extracted, integrity-checked, counted. This is the
answer to the 15-year-old silent corruption failure mode.

FSL-1.1-MIT license. Source-available, no resale as a competing product,
converts to MIT two years after each release. Chosen over GPL (would
permit resale) and over proprietary (would foreclose "your IT can
maintain it").

Device swap model. Same-day before noon Eastern, next-business-day
otherwise. Prepaid return label in the box. One spare per ten deployed.
Do not stock a spare until the first sale funds it.

Pricing ladder. Nano $2,500, NX $3,500-$4,000, Thor $12,000-$14,000.
Nano for base, NX build-to-order, Thor parked (wrong use case for a law
office, right for a manufacturing facility).

Bulk purchasing. Orin Nano Super MODULE from distributor (Seeed,
qscompute, Arrow) at ~$224 at 100 units, not the retail dev kit (Micro
Center limits 1 per household). Carrier board and case are commodity.

## PARKING LOT

v0.2 (after first sale):
- Persistent failed-attempt counter in SQLite.
- Escalating delay 2s/5s/15s/60s instead of hard lockout.
- Failed-attempt log: date, time, timezone, IP, outcome. Last 20 on an
  admin section of the ingest page.
- /settings page for the office manager to change the PIN.
- Username field on login form (password-manager autofill).
- Per-user login tier: named accounts, hashed PINs, query log with
  user_id. Priced above base.
- Backup status on the ingest page (read /var/log/arkiv-verify.status).

v0.3:
- Natural-language matter scoping with confirmation. The model extracts
  candidate matter names from the question, the dropdown highlights them,
  the lawyer confirms before the query runs. Works at any model size; a
  14B makes it more accurate, not more necessary.
- Multi-matter selection. Scope a query to a chosen set of matters, not
  one and not all.

Remote access:
- WireGuard on the Jetson. Self-hosted, no subscription. Requires the
  PWA. Priced as an upgrade tier ($3,000 range discussed).

PWA:
- Phone and tablet capture and query. Not built. Two weeks of work,
  behind the VPN.

Marketing and sales:
- Arkiv one-pager for door-to-door and partner channel.
- Website page under Artifexo Fabrika, with Koorsus and Myarra on the
  other side of the page (manufacturing).
- Partner one-pager for local repair shops. 20-30% margin or referral
  fee. Two to three trusted shops, not twenty. "Call Randy first"
  instruction to the customer.
- Apify Google Maps scrape for law firms in Columbus and Central Ohio.
- Email campaign with the "RAG for less than a laptop" hook.

Business:
- Manufacturing partner for volume: not yet identified.
- Warranty: one year from delivery.
- Support contact: phone and email, to be filled in on the Quickstart.
- The LUKS dry run on a bare Jetson, before the first unit ships.

## PRE-SALE UI/UX: MATTER LIFECYCLE (Target: 2026-11-18)

A flat dropdown stops working at roughly thirty matters. A firm with a hundred active cases gets an unusable list. Design agreed 2026-11-15:

1. **Registry table.** A small SQLite table (or JSON file) for matters with: tag, display_name, status (active/archived), opened_at, last_query_at. Ingest creates the row. Dropdown reads from this, not raw Chroma counts.
2. **Status toggle.** Archived matters hidden by default. Toggle at bottom of dropdown to show them. Archive is not delete; archived matters remain fully searchable when selected.
3. **Type-ahead.** Replace select with an input that filters as you type. At 30 matters it is a convenience; at 200 it is necessary.
4. **Recent first.** Sort by last_query_at descending. Working cases float to the top.
5. **Manual archive.** Button on the ingest page. Admin panel suggests archiving matters with no query in 90 days.
6. **All matters default.** Scopes to active matters only. Archived matter search requires explicit opt-in. Protects answer quality from noise in closed cases.

Build before the first sale. The permanent solution at scale is the v0.3 natural-language matter scoping.

## EVENING UPDATE (2026-11-15)

Since the morning delta, the following was built, tested, and committed:

1. **Matter Lifecycle UI.** A new module  tracks matters in a JSON registry with active/archived states. The Ask page now has a scope dropdown populated from the registry, a checkbox for "Include archived matters (firm history)", and an exclusion filter in the retrieval code so "All matters" does not search archived files by default. Archiving is non-destructive; archived matters remain searchable when explicitly selected. Matters sort A-Z by default.

2. **Admin Page.** A  route behind the login gate with three panels: Backup status (reads the verify log), Restore Latest Backup, and Factory Reset. All three are Python-native; they do not use  or  on the shell scripts, which previously killed the web server. File ownership is handled via  in Python.

3. **30-Matter Demo Corpus.** 113 synthetic legal documents across 30 matters were generated by a prior instance, concatenated with exact  markers, split, and bulk-ingested. Total library: 605 chunks across 31 matters (one is a duplicate Copper Kettle packet, now archived). Script is . Ingest time: ~6 minutes on the Nano.

4. **Hallucination Guard (Critical).** A test revealed the 3B model could convert a *motion* ("Petitioner moves for custody") into an *order* ("The court ordered custody"). The system prompt was patched with a CRITICAL rule instructing the model to check document type before answering what a court ruled, and the refusal list was expanded to catch phrases like "I do not find a ruling." This works for now, but the architectural fix is **Document-Type Gating (v0.2)**: tagging every chunk with its document type (motion, order, affidavit, etc.) and restricting retrieval for outcome questions to order/ruling documents only. The 3B model cannot be trusted to respect prompt rules forever.

5. **Config tweaks.**  bumped from 5 to 8 to improve unscoped multi-matter queries.

6. **Website.** The umbrella landing page, Arkiv product page, and manufacturing.html are all live at artifexofabrika.com. The Arkiv page needs the four screenshots (cited answer, matter scope dropdown, refusal, multi-matter note) added to the product section.

## WORKING METHOD LEARNED TODAY

One command at a time. State which window: "Jetson window" or
"PowerShell". Do not wrap Jetson commands in ssh from PowerShell when
the Jetson window is open.

PowerShell is for exactly two things: scp from Windows to the Jetson, and
ssh-wrapped commands when the Jetson window is not open. Everything else
runs in the Jetson window as a plain command.

Very long inline python -c with nested quotes breaks. For anything over
about 40 lines, write the file on Windows with a PowerShell here-string
(`@' ... '@ | Out-File`), scp it, run it on the Jetson. This is the
method that has worked all day.

Whole-file rewrites, not patches. Do not use sed. If a script modifies a
file, the script must pre-check every anchor and refuse to write if any
is missing, so a partial patch cannot land.

Any script that runs as root and creates files the service will read must
chown to the service user (jeeves). This bug bit reset.sh today: mkdir
as root, ChromaDB cannot open its SQLite file, /matters returns 500.

When a compound bash command chains `&&` and includes a background start
or a kill, it becomes a single job and the shell messes up. Use separate
commands, one per line.

Long placeholder filenames (arkiv-YYYYMMDD-HHMMSS.tar.gz.enc) in
documentation are a trap for anyone with data-entry constraints. If a
script can find the newest file itself, it should. That is why restore.sh
now takes no argument.

## HOW TO RESUME

Jetson window:

    systemctl is-active arkiv
    systemctl list-timers "arkiv-*" --no-pager
    curl -sk -o /dev/null -w "%{http_code}\n" https://127.0.0.1:5001/login
    sudo journalctl -u arkiv -n 20 --no-pager

Expected: active, two timers, 200, no recent errors.

Test the pipeline end to end:

    curl -sk -c /tmp/cj -X POST https://127.0.0.1:5001/login -d "pin=arkiv2026" -o /dev/null
    curl -sk -b /tmp/cj https://127.0.0.1:5001/matters

Expected: the two demo matters (COPPER KETTLE BISTRO LLC, ~124 chunks;
Henderson slip and fall - CV-2025-0932, ~26 chunks).

Run a backup and a verify:

    sudo ~/arkiv/backup.sh
    sudo ~/arkiv/verify-backup.sh

Restore the demo data from the newest backup if the library is empty:

    sudo ~/arkiv/restore.sh    # type yes

Repository:

    cd ~/arkiv && git status && git log --oneline -10

## COMMERCIAL STATE

Market: small law firms in Columbus and Central Ohio, two to five
attorneys. Medical practices next.

Price: $2,500 base. The cheapest on-premise legal AI appliance on the
market is $7,500. Harvey is $12,000 to $24,000 per lawyer per year.
"The cheapest on-premise legal AI appliance on the market costs $7,500.
Ours is $2,500. It does not connect to the internet. Your documents
never leave the office."

Pitch line: "RAG for less than a laptop."

First six weeks: sales calls, not code. The appliance is ready. The
LUKS dry run is the only technical item before the first unit ships,
and it can happen while the first calls are being made.

The demo: the Copper Kettle packet (Matter A) and the Henderson packet
(Matter B) are the live corpus. Two matters, shared party names, the
filter proven. The first question to show a lawyer: "Were any violations
cited inside Copper Kettle's restaurant interior?" — the refusal that
is actually an answer (no, per Item 7 of the inspection report). The
second: "Is Meridian Holdings a party to the Henderson action?" — scoped
to Matter B, it refuses; scoped to Matter A, it names Meridian as
defendant. That is the demonstration that matters.

## DEMO CORPUS

Matter A: COPPER KETTLE BISTRO LLC, — commercial lease dispute at 418
Market Street. Complaint, city inspection, demand letter, expert report,
joint stipulation, answer, interrogatories, maintenance log, Vale
deposition. ~124 chunks.

Matter B: Henderson slip and fall - CV-2025-0932 — personal injury
against Copper Kettle as defendant. Complaint, incident report,
Nandakumar deposition. ~26 chunks.

The tag includes the trailing comma on Matter A. Cosmetic, from the
first ingest. Leave it; a matter-rename feature is v0.2.

## SESSION CLOSE

State at close of 2026-11-15:
- Appliance running, HTTPS, systemd enabled, two workers.
- Backups nightly, verified weekly, restore and reset tested.
- Repository current, private, seven commits today.
- Philosophy, FAQ, Quickstart, Provisioning, License, this delta all in
  the repo.
- Demo corpus loaded, matter filter proven both directions.

What the next instance inherits: a working appliance, a complete
operational story, and a written philosophy. The technical gap is LUKS
at provisioning. The commercial gap is that no law firm has yet seen it.

END OF DELTA.
