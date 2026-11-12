# MYARRA — SESSION DELTA, 2026-11-12 (Herbie Light & PWA)

This delta supersedes SESSION-DELTA-2026-11-12-HERBIE-LIGHT.md.
Read alongside PHILOSOPHY.md, HERBIE-ARCHITECTURE.md, and SESSION-DELTA-2026-11-07-REWRITE.md.

**Current entry point.** Read this first. Supersedes all earlier deltas.

**Before anything else, read PHILOSOPHY.md.** It is the governing document, never superseded.

## 0. WHAT THE PRODUCT IS

Myarra is a private, on-premise production tracker on an NVIDIA Jetson. It closes
the "Check" step of PDCA without a data janitor. Herbie is the AI Counselor.
Herbie Light is the Nano-tier interface (five fixed questions). Herbie Counselor
is the NX-tier upgrade (natural language, conversation, proactive coaching).
The PWA at /floor is the operator data entry screen and replaces Telegram for
in-building use.

## 1. WHAT WAS DONE

### Herbie Light (web interface)
- New /herbie route with AJAX submission and inline answer at top of page.
- Five tabs across one horizontal row: Job summary, Top downtime jobs,
  Unaccounted time, Changeover, Line day.
- Only active tab inputs are enabled (prevents duplicate-name field collision).
- Datalists for job numbers, populated only with jobs that have production data.
- Active tab persisted in URL hash so a reload keeps context.
- Copy / Download .txt / Print / Ask another on each answer.
- Pre-computed summary strings returned by get_changeover_summary and
  get_jobs_with_downtime_over; LLM paraphrases rather than interprets.
- For jobs_over, the jobs array is stripped from the LLM payload (replaced with
  a placeholder string) so the 3B model cannot enumerate it and re-rank it.
- Case-insensitive job lookup via COLLATE NOCASE on jobs.job_number.

### PWA (operator floor entry)
- mkcert installed, local CA generated, root CA trusted on Jetson and Windows.
- HTTPS live via Gunicorn 27 with --certfile and --keyfile flags.
- Gunicorn replaces Waitress for the systemd service (Waitress does not support
  TLS natively).
- manifest.json with 192x192 and 512x512 icons derived from the Luxo logo.
- Service worker caches only the shell pages and static assets. Never caches
  API responses or Herbie answers.
- /floor route renders a responsive tile grid, one tile per line, showing
  line name, work order, SKU, and next hour.
- Tap a tile expands to full input form; "All lines" returns to grid.
- selected_line persists after submit so the operator stays in their line.
- Text entry writes to hourly_runs exactly as if from Telegram.
- Chrome shows the install prompt. PWA installs on Windows, Android, iOS.

## 2. WHAT CHANGED (files)

- myarr_v2/app.py
    - New /herbie route (AJAX-aware, returns JSON for XHR, HTML otherwise).
    - New /floor route (tile grid, POST handler for hourly entry).
    - selected_line passed to floor.html so the expanded view persists.
    - __main__ block reverted to plain Waitress for manual dev runs.
- myarr_v2/herbie.py
    - narrate(intent, stats, context, question) added.
    - INTENT_NOTES dict with per-intent prompt rules.
    - GENERIC_NARRATIVE_PROMPT shared template.
    - _build_changeover_summary() helper for pre-computed changeover prose.
    - get_jobs_with_downtime_over now returns summary field.
    - get_changeover_summary now returns summary field.
    - HAVING clause uses full aggregate expression, not SELECT alias.
    - narrate() strips the jobs array for jobs_over intent.
- myarr_v2/templates/herbie.html — NEW, five-tab AJAX interface.
- myarr_v2/templates/floor.html — NEW, tile grid + tap-to-expand form.
- myarr_v2/templates/base.html — manifest link, apple-mobile-web-app meta tags,
  SW registration script, Herbie nav link.
- myarr_v2/static/manifest.json — NEW.
- myarr_v2/static/sw.js — NEW (caches shell only).
- myarr_v2/static/icon-192.png, icon-512.png — NEW (derived from Luxo logo).
- /etc/systemd/system/myarr.service — ExecStart now calls gunicorn with
  --bind 0.0.0.0:5002, --workers 2, --timeout 120, --certfile, --keyfile,
  app:app. WorkingDirectory unchanged.
- ~/myarra-certs/myarra-cert.pem and myarra-key.pem — NEW (mkcert generated,
  valid for koorsus, 192.168.100.2, localhost, 127.0.0.1, expires 2029-02-12).
- ~/.local/share/mkcert/rootCA.pem — the mkcert root CA. Must be installed on
  any device that will open the PWA.

## 3. WHAT IS VERIFIED

- Herbie Light: all five cards tested end to end. Card 2 returns 29 jobs at
  20m/7d, top three correctly ranked starting WO-2611-153. Card 4 says
  "FASTER than standard, 46.7% improvement" with per-station savings.
- HTTPS: curl -k https://192.168.100.2:5002/ returns the app HTML. The
  certificate is valid for the names we generated.
- PWA: manifest, sw.js, and both icons serve with HTTP 200. Chrome shows the
  install prompt ("Install floor"). Install dialog opens.
- /floor: tile grid renders, tap behavior expands to input form, "All lines"
  returns to grid, POST writes to hourly_runs.
- mkcert root CA trusted on Windows via certutil -addstore -user Root.

## 4. WHAT IS NOT VERIFIED

- Voice entry. Whisper is not installed. /floor is text-only for now.
- Install prompt has not been tested on Android or iOS. Expected to work
  (same manifest and SW; iOS uses Share -> Add to Home Screen).
- No offline capability beyond shell caching. If the Jetson is down, the PWA
  will not submit.
- Not tested on multiple tablets simultaneously.
- Service worker caching has not been tested with a page refresh while the
  Jetson is unavailable.
- No backup protocol. If the NVMe fails, all data is lost.
- Odoo work order notes are not yet imported into jobs.handover_notes.

## 5. NEXT INSTANCE MUST DO

1. Install Whisper (faster-whisper or whisper.cpp) on the Jetson.
2. Add /api/transcribe endpoint that accepts an audio blob and returns text.
3. Add a microphone button to /floor that records, uploads, and fills notes.
   Parse units and scrap from the transcript using the existing bot parsers.
4. Extend /api/odoo/jobs to accept and store the Odoo note field into
   jobs.handover_notes (strip HTML before storing).
5. Follow up with Hillary Clark at Kingswood if no reply by Friday 2026-11-14.
6. Revisit the Odoo partner program in Q1 2027. The $4,000 + $4,000 + 60h
   training offer is not appropriate for the current stage.

## 6. LESSONS / WORKING METHOD ADDITIONS

### Waitress and TLS
Waitress does not support TLS natively. Passing ssl_context to serve() raises
"Unknown adjustment 'ssl_context'". Use Gunicorn with --certfile and --keyfile
for HTTPS. Gunicorn is a drop-in WSGI replacement for Waitress in systemd.

### Small-model reliability (Herbie, continued from 11-12-2026-HERBIE-LIGHT)
On a 3B model you cannot tell the LLM to ignore data that is in the prompt.
It will read the forbidden data anyway. The escalation ladder:
  1. Prompt rule.
  2. Pre-compute the summary in Python; instruct the model to paraphrase.
  3. Strip the offending field from the payload before formatting.
  4. Skip the LLM entirely for that intent; return the summary verbatim.

### SQLite HAVING clause
The HAVING clause resolves column names to underlying table columns, not to
SELECT aliases. HAVING alias_name > ? will silently compare the wrong value.
Always use the full aggregate expression in HAVING. This bug cost hours.

### PWA prerequisites
A PWA requires a secure context. An HTTP LAN address will not register a
service worker, will not install, and will not access the microphone.
mkcert plus a trusted root CA is the local-only path. Tailscale or Headscale
are the remote-access path, but both introduce either a subscription or a
coordination server. For an appliance that promises no monthly fees, the
mkcert local path is the correct choice for the in-building use case.

### Patch discipline
When patches on a single file exceed three in one day, stop and rewrite the
whole file. Herbie Light went through four patches on herbie.py before we
stopped and rewrote it; every bug after the rewrite was diagnosable in one
step. This rule is now proven twice in two days.

### Multi-tenancy of PWA entry
The /floor route currently shows all lines. For a 15-line plant the tile grid
will still fit (minmax(150px, 1fr) auto-fill), but a customer may want each
tablet locked to a single line. That is a URL parameter decision
(/floor/2) or a users.line_id lookup. Neither is implemented today.

END OF DELTA.