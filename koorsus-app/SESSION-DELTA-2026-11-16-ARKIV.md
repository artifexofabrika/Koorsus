# SESSION DELTA 2026-11-16 - ARKIV

Read this first. Self-contained handover. Written by an assistant instance
that has no memory beyond this document; assume it knows nothing you do
not state here.

Repository: https://github.com/artifexofabrika/Arkiv  (private)
Last commits: 428057b (aggregate gate), 1779cf5 (JSON errors), bfa6982 (gating)
Website repo: https://github.com/artifexofabrika/Koorsus  (docs/ folder is
  the GitHub Pages root for artifexofabrika.com)

## WHAT ARKIV IS

Private, on-premise document assistant for small law and medical offices.
A customer-owned appliance. Ingest the firm's documents, tag by matter, ask
in plain English. Answers cite the source document. Refuses when the answer
is not in the documents. No cloud, no telemetry, no subscription.
FSL-1.1-MIT. $2,500 base, $3,500-4,000 for the NX tier.

Buyer: two-to-five-attorney firms. Reference profile: a sole practitioner in
Mount Vernon, Ohio, doing bankruptcy and property, no paralegal, five or six
hours a day in documents. Not built for large firms or seven-figure cases.

## CURRENT STATE - VERIFIED 2026-11-16

Runtime
- Flask app on HTTPS port 5001, systemd enabled, Gunicorn 2 workers,
  --timeout 180, mkcert TLS. LLM client timeout is 120, correctly under the
  worker timeout.
- Ports: 5000 Koorsus RAG, 5001 Arkiv, 5002 Myarra web, 8080 llama.cpp
  (koorsus-llm.service, shared, owned by the Myarra side).
- Hardware: Jetson Orin Nano 8GB. NOTE: it powers off spontaneously every
  couple of days. Suspect undervoltage or thermal. Investigate before any
  customer unit ships.
- Data: /mnt/lake/arkiv_index (ChromaDB), /mnt/arkiv-backup,
  /etc/arkiv-backup.key, /var/log/arkiv-verify.status.

Working and tested
- PIN login, session cookie, 5-attempt lockout (in-memory, per worker, so
  effectively looser than documented and resets on restart).
- Ask page: matter scope dropdown from the JSON matter registry, archived
  toggle, recent questions in localStorage (10), copy/download/print.
- Matter lifecycle registry: active/archived, non-destructive archive,
  archived excluded from "all matters" unless opted in. Sorts A-Z.
- Ingest: five formats (.txt .md .pdf .docx .odt), uploader + matter tag on
  every chunk, collapsible library view, archive/restore buttons.
- Document-Type Gating: outcome questions ("order", "ruled", "judgment"...)
  force doc_type=order in the Chroma where filter. Verified: refuses on a
  matter with no orders, answers normal questions correctly.
- Aggregate Gating: count/list questions ("how many", "count of", "list all")
  refuse rather than answer from a top-k sample. Added after the model
  answered "how many marriage cases" by counting files in the retrieved
  slice and inventing a justification. Verified.
- /ask returns JSON on retrieval or generation failure and logs a traceback
  via app.logger.exception. First logging this app has had. Verified both
  paths by stopping and restarting koorsus-llm.
- Backup: nightly 03:00, AES-256, PBKDF2 200k, 30 archives, sha256 alongside.
- Restore: no-arg, checksum verify, decrypt, extract, previous index kept.
- Verify: Sunday 04:00, decrypts newest archive, extracts, sqlite
  integrity_check, counts documents, compares to live. Proven live=150
  backup=150.
- Factory reset: moves index aside, creates empty, chowns jeeves, restarts.
- Admin page: backup/verify/restore/reset, Python-native for restore/reset.
- Demo corpus: 113 synthetic documents, 30 matters, 481-631 chunks. Generated
  by split_and_ingest.py (committed). The corpus itself is untracked by
  design - do not commit synthetic legal filings to the product repo.

## SECURITY FINDINGS - NOT YET FIXED, TOP PRIORITY

1. `sudo -l -U jeeves` shows `(ALL : ALL) ALL` AND `(ALL) NOPASSWD: ALL`.
   The web app user has full passwordless root. The app parses uploaded PDF,
   DOCX, and ODT files. This is the single worst finding and any technical
   buyer will find it in ninety seconds.
2. /etc/arkiv-backup.key is owned jeeves:jeeves 600, so the app can decrypt
   every backup. The documented claim is "root-only." Either the claim or the
   filesystem is wrong; make the filesystem right.
3. LUKS full-disk encryption has never been executed on bare metal. The
   website previously claimed "the disk is encrypted" and "if the appliance
   is stolen your documents cannot be read." Those claims were REMOVED from
   docs/arkiv.html tonight because they are not true yet. Do not put them
   back until LUKS actually runs.

## FIRST THREE THINGS TOMORROW, IN ORDER

1. Pin sudoers. Write /etc/sudoers.d/arkiv with only: backup.sh,
   verify-backup.sh, a pinned chown for the index paths, and
   systemctl restart arkiv. Validate with `sudo visudo -c`, prove every
   command still works from a SECOND ssh session, and only then remove
   NOPASSWD: ALL. Never edit sudoers without a second shell open.
2. Move the backup key to root:root 600, and refactor _admin_restore() in
   app.py to call `sudo /home/jeeves/arkiv/restore.sh --latest --yes`
   instead of running openssl itself. This also removes the tempfile.mktemp
   TOCTOU bug.
3. Narrow store.get_collection(): it catches bare Exception and creates an
   empty collection, so a corrupt or unreadable index reports "No documents
   found" - indistinguishable from a deliberate refusal. Catch only the
   not-found case.

## KNOWN DEFECTS / PARKING LOT

- reload() after restore/reset only refreshes ONE of two Gunicorn workers.
  The other keeps a PersistentClient on a renamed directory. Run one worker,
  or have the admin action schedule a service restart after responding.
- doc_type is inferred from filename substrings with `motion` tested BEFORE
  `order`, so `order_on_motion_for_custody.txt` is tagged motion and the gate
  then refuses on a matter that contains the order. Reorder the checks and
  move classification to ingest time (store.add_chunks), not a retrofit.
- _keyword_search does collection.get() with no limit - transfers the entire
  corpus and tokenizes it on every query. Scaling ceiling. Needs SQLite FTS5
  or an in-process tokenized cache invalidated on ingest.
- Refusal is detected in ask_route by substring matching on the answer text,
  which strips sources from legitimate "the lease does not contain..."
  answers. generate.answer() should return (text, refused) instead.
- store.matters() appears to be dead code; app.py uses matters.get_matters().
  Two sources of truth for the matter list. Delete one.
- Matter tags are freehand: trailing comma on the Copper Kettle tag, case
  duplicates possible, and the tag is concatenated into innerHTML unescaped
  in the ingest library list (stored XSS). Escape it; normalize tags at the
  single ingest entry point.
- No MAX_CONTENT_LENGTH on upload. secure_filename mangles accented names.
  No dedupe - that is how the duplicate Copper Kettle packet happened.
- Chunk IDs are deterministic ({source}::{i:04d}), so re-ingesting a SHORTER
  version leaves stale high-numbered chunks as phantom content.
- PIN compared with == (not hmac.compare_digest), plaintext in config.py,
  SESSION_COOKIE_SECURE not set.
- No /settings page, so QUICKSTART.md promises the office manager a PIN
  change they cannot perform. Either build it or soften the card.
- No per-user identity, no query log. The website claim about an audit log
  was removed tonight. Per-user accounts + query log is v0.2 and is what an
  IT reviewer will ask about.
- README.md points to INSTALL.md, which does not exist.
- No tests. app.py is ~800 lines with all templates inline. The rewrite is
  the next structural job, after tests exist to protect it.
- Templates use render_template_string with inline CSS and HTML in Python
  string literals. Moving to templates/ + static/ is the point of the rewrite.

## WEBSITE STATE (Koorsus repo, docs/)

- index.html: 3-door umbrella (Arkiv, Koorsus & Myarra, Jeeves).
- arkiv.html: claims corrected tonight (audit log, disk encryption removed),
  real screenshots wired into a 2x2 grid, "Point-and-shoot ingestion" section
  with arkiv_ingest.png added.
- jeeves.html: rewritten tonight. bespoke_travel.jpeg as centerpiece
  (jeeves_object.jpeg), architectural_modernist.jpeg as hero (jeeves_hero.jpeg).
  Mail removed from the hero. "Air-gapped" replaced with "runs entirely on
  your own network". Trading card revised to paper simulation with no
  brokerage credentials. GitHub link now points to
  github.com/artifexofabrika/Jeeves---public (the repo name has three
  hyphens; a plain /jeeves does not resolve).
- Two stray index.html.bak files were moved out of docs/. They were never
  tracked (the .gitignore already had *.bak*), so nothing was ever published.
- Screenshots from 2026-11-16 16:43-16:45 were taken AFTER the gating and
  aggregate fixes and show current behavior. The 11/15 screenshots show
  refusal wording the app no longer produces. Refresh the site images.
- Website lives inside the Koorsus repo. Should eventually be its own repo.
- Uncommitted change exists at myarr_v2/bot/support.py - NOT ours, likely
  another instance. Never `git add -A` in the Koorsus repo.

## WORKING METHOD (learned, follow it)

- The user has a disability that makes typing painful and uses dictation.
  Expect garbled words; reconstruct rather than ask them to retype. Keep
  commands short enough to speak. One command at a time, and always name
  which window: "PowerShell" or "Jetson."
- PowerShell is for two things: scp/rsync from Windows, and ssh-wrapped
  commands when no Jetson window is open. Everything else runs in the Jetson
  window as a plain command.
- Long inline `python3 -c "..."` with nested quotes breaks. For anything over
  ~40 lines use a `cat > /tmp/x.py <<'PYEOF' ... PYEOF` heredoc, then
  `python3 /tmp/x.py`.
- Whole-file rewrites, not sed. Any script that modifies a file must pre-check
  every anchor and refuse to write if any is missing, so a partial patch
  cannot land.
- Any script running as root that creates files the service reads must chown
  to jeeves, or ChromaDB cannot open its SQLite file and routes return 500.
- Commit and push after every fix. Uncommitted work is how a patch nearly got
  lost on 11/15.
- No `&&` chains that mix background starts or kills into one job.
- If a script can find the newest file itself, it should - do not make the
  user type a timestamped filename.

## HOW TO RESUME

    systemctl is-active arkiv
    systemctl list-timers "arkiv-*" --no-pager
    curl -sk -o /dev/null -w "%{http_code}\n" https://127.0.0.1:5001/login
    sudo journalctl -u arkiv -n 20 --no-pager
    cd ~/arkiv && git status --short && git log --oneline -5

Expected: active, two timers, 200, no recent errors, clean tree.

End-to-end check:
    curl -sk -c /tmp/cj -X POST https://127.0.0.1:5001/login -d "pin=<PIN>" -o /dev/null
    curl -sk -b /tmp/cj https://127.0.0.1:5001/matters

## COMMERCIAL STATE

Thursday: a meeting with an IT person for a small firm. Not a sale. Be
explicit that polish items remain. Strongest demo artifacts, in order:
1) unplug the Ethernet cable and ask a question - it answers and cites;
2) the same question scoped to two matters giving opposite answers;
3) ask for a court ruling that is not in the documents and watch it refuse;
4) the weekly verify status file showing live=150 backup=150.

Expect these questions: where the data lives and whether it is encrypted at
rest (answer honestly: not yet, LUKS is at provisioning); what the TLS cert
is (mkcert is a dev convenience - have a shipping answer); what the PIN is
and how it changes (provisioning forces a change); who can read backups
(nobody - firm-held passphrase).

Jeeves: separate luxury personal appliance, $4,500+, Orin NX / AGX Thor,
"coming soon" waitlist live. Its API-key and mail-module history is not
relevant to Arkiv. Do not mix the codebases.

## WHAT THE NEXT INSTANCE INHERITS

A working appliance with a real refusal gate, committed and pushed, a
website with honest claims, and a precisely documented security debt led by
the sudoers file. The technical path to a shippable unit is short and
specific. The commercial gap is that no firm has yet seen it.
