# SESSION DELTA 2026-11-17 - ARKIV

Supersedes the 2026-11-16 delta. Repository artifexofabrika/Arkiv, HEAD 62ec8cb.

## WHAT IT IS
On-premise document assistant for small law offices. Matter-tagged ingest,
plain-English questions, cited answers, refusal when the answer is absent. No
cloud, no subscription. FSL-1.1-MIT. $2,500 base, $375 reseller margin.

## CHANGED TODAY
Monolith split: app.py is a 28-line factory; routes in auth.py, ask_routes.py,
ingest_routes.py, admin_routes.py, users_routes.py; HTML in templates_html.py
and templates_users.py; CSS in static/arkiv.css; rag/doctype.py added.

Accounts: PBKDF2 200k, per-user salt, 8-char minimum. Query log records every
question with user, matter, time, refusal and source count. /users does
self-service PIN change; admins add users, deactivate (history preserved), and
delete a user log as a separate act. CSV export.

Security: blanket sudo gone, seven pinned commands, scripts in
/usr/local/sbin/arkiv root-owned. restore-index.sh replaces the Python restore
that could not read a root-only key. Passphrase root:root 600. X-Forwarded-For
ignored. One Gunicorn worker.

Gating: both directions tested. Henderson answers from
order_matter_05_granting_summary_judgment.txt and reports the partial grant;
Jenkins refuses. NOT_FOUND sentinel primary, phrase list secondary. Refusals
carry no citations. judgement and judgment both gated.

Backups: USB export/import scripts pinned and wired to Admin buttons with
in-page confirmation. UNTESTED WITH A REAL STICK. Mounting is an operator act;
scripts only look for a mountpoint under /media or /mnt/usb.

Nightly: arkiv-smoke.timer 04:30 runs smoke-check.sh, writes
/var/log/arkiv-smoke.status (OK|time|n/n) shown on Admin. Removes its own log
rows afterward.

## TESTS
smoke.py: 14 end-to-end checks, about four seconds. Covers login, page
rendering, both gate directions, refusal without citations, aggregate refusal,
users page, CSV export, malformed body. Run python3 ~/arkiv/smoke.py. Red is a
stop. No coverage of upload POST, archive, reset or USB.

## OPEN, BLOCKING A SALE
1. LUKS never run on bare metal. Website claims removed; do not restore them.
2. USB path untested with hardware. Test before Thursday.
3. No reseller agreement: margin, support split, liability, passphrase holder.
4. Accounts lack admin reset, expiry and users-page lockout.

## PARKING LOT
Remove smoke and Test Account (PIN 4242) before shipping. Duplicate Henderson
matters. Re-head the generated judgment and probate order or discard them.
Login guard redirect list is hand-maintained. Prose refusal detection wants a
JSON schema or GBNF grammar from llama.cpp. Keyword search full-scan needs
FTS5. Stale chunk ids on shorter re-ingest. Upload size cap, tag
normalization, dedupe. Website still inside the Koorsus repo. SSH drops are the
USB-C Ethernet adapter, not reboots. Cookie lacks Secure. README points at a
missing INSTALL.md.

## METHOD
Dictated input; expect garbles, reconstruct rather than asking for a retype.
One command at a time, name the window. Whole-file writes, no sed. Verify byte
counts with wc -c after every transfer. PowerShell -Encoding utf8 writes a BOM
that breaks shell shebangs; use ascii, and strip BOM and CRLF regardless.
Jetson terminal pastes drop long lines and long blocks: keep pastes small and
prefer written files. Run anything once after transfer and read its output.
Commit and push after each verified fix.

## RESUME
systemctl is-active arkiv
systemctl list-timers "arkiv-*" --no-pager
cat /var/log/arkiv-smoke.status
python3 ~/arkiv/smoke.py
cd ~/arkiv && git status --short
Expect active, three timers, OK 14/14, clean tree.

## COMMERCIAL
Thursday is a first look with a local IT firm serving law offices. Not a sale.
Demo: unplug the cable and ask; the same question in two matters; a refusal;
the two status lines on the Admin page. Arkiv and Koorsus are one codebase with
two markets; Koorsus is next to the same standard. Subsistence is $1,000 a
month, about $1,400 net per unit, so ten units a year. About 600 firms within
twenty-five miles. The constraint is conversations, not code.

END OF DELTA.
