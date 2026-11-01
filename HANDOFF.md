# MYARRA — PROJECT HANDOFF

Last updated: 2026-11-01 (Sunday morning)
Owner: Randy Wolf, Columbus, Ohio
Prepared by: Jeeves, after the 2026-10-31 / 2026-11-01 session

READ SECTION 1 FIRST. It records the architectural decision that reshaped
everything else. Then Section 5 for how to resume.

---

## 1. THE GOVERNING ARCHITECTURE (new, as of 2026-11-01)

Myarra is not an ERP. It is not an MRP. It is not a BOM management system.

Myarra is a production-to-standard tracker with two measurable events:

  1. PRODUCTION — how did this hour run against its standard?
  2. CHANGEOVER — how well did we change from SKU A to SKU B?

Plus a future third event (MAINTENANCE) — not built, not scoped.

The BOM is INPUT, not subject. It tells us which components change during a
changeover. Where those components come from (pre-silk-screened, in-house,
procured) is not our concern.

The product is the loop: PDCA experiments that change procedure and prove
whether the change paid off.

Any feature that belongs to an ERP is out of scope. When in doubt, ask:
"does this help a plant manager run production to standard, or is it an
accounting/inventory function?" If the latter, defer.

---

## 2. THE BUSINESS

Artifexo Fabrika — lean manufacturing consultancy, Columbus, Ohio. Founded by
Randy Wolf (30 years in lean, startups, operations).

Pitch: "We do not sell software. We assess your operation, install open-source
AI tools on hardware you own, and maintain them for you. No subscriptions.
No data leaving the building. No dependence on Big Tech."

Brand hierarchy:
  - Artifexo Fabrika = the consultancy (the workshop)
  - Koorsus         = the document platform (Latin "cursus" = course/path)
  - Myarra          = the metrics platform (Polish "miara" = measure)
  - Jeeves           = future AI Valet product, reserved, NOT part of this

Target market (per 2026-11-01): Central Ohio.
  - Cosmetics contract packagers (New Albany: Accel, Anomatic, Voyant Beauty,
    KDC/One, Axiun, Alene Candles)
  - Beverage canning (breweries, cideries)
  - Not bottling — insufficient facility density in the region

Pricing:
  - Operational Diagnostic: $2,500
  - Inventory & Cash Flow Review: $3,500
  - Private AI Appliance: Starting at $5,500 installed
  - Fractional Operations Leadership: Starting at $8,000/month
  - Day rate: $1,385/day (9 hours including travel)
  - Turnkey AI Employee: $299/month

Landing page: https://www.artifexofabrika.com (Carrd, Pro Standard tier)
  - Dark palette #1a1a1a, gold accent #c0a878, Georgia serif
  - Formspree endpoint: https://formspree.io/f/xdarnqnj
  - Diagnostic anchor: artifexofabrika.com/#diagnostic

---

## 3. HARDWARE & NETWORK

Device: NVIDIA Jetson Orin Nano 8GB, 256GB NVMe
Hostname: koorsus
OS: Ubuntu 22.04.5 LTS, L4T 36.5.2 (JetPack 6.2.3), headless

The internal Realtek Wi-Fi card is DEFECTIVE. Bypassed entirely with a
BENFEI USB-C to Gigabit Ethernet adapter.

Network (working as of 2026-11-01):
  - Windows Ethernet adapter "Ethernet 7": 192.168.100.1 (static)
  - Jetson "Wired connection 1": 192.168.100.2/24 (static, manual)
  - Gateway: 192.168.100.1
  - DNS: 8.8.8.8, 1.1.1.1 (ipv4.ignore-auto-dns=yes)
  - SSH: ssh jeeves@192.168.100.2

PowerShell NAT for internet sharing (Windows ICS is buggy, do not use):
  New-NetNat -Name "JetsonNAT" -InternalIPInterfaceAddressPrefix "192.168.100.0/24"
  Set-NetIPInterface -InterfaceAlias "Ethernet 7" -Forwarding Enabled
  Set-NetIPInterface -InterfaceAlias "Wi-Fi" -Forwarding Enabled
  # Run in PowerShell as Administrator
  # If NAT already exists: Remove-NetNat -Name "JetsonNAT" -Confirm:$false

IMPORTANT NOTES:
  - "Ethernet 2" is a dead TunnelBear VPN adapter. Do not touch it.
  - sudo prompts fail silently if Caps Lock is on. Check Caps Lock before
    troubleshooting a password failure. Cost time twice.
  - SSH key auth was set up 2026-10-31 from the Windows side. Password auth
    still works but keys are preferred.

---

## 4. DATA MODEL

Two databases in /mnt/lake/:

  myarra.db        — CANONICAL (as of 2026-11-01). Generic schema.
  metrics.db       — Retired wine data (Oct 2026). Preserved but unused.
  demo_beverage.db — Retired beverage data (Oct 2026). Preserved but unused.

db.py points at myarra.db. BACKUP: /mnt/lake/myarra.db.bak.20261101-*

### 4.1 myarra.db schema

Generic-to-industry. Component names come from the database, not the code.

  lines              (id, name, format_type)
  skus               (id, part_number, description, case_pack, active)
  line_sku_rates     (line_id, sku_id, ideal_rate)  -- units per HOUR
  component_types    (id, name, is_serial, default_swap_min)
  sku_bom            (sku_id, component_type_id, component_value)
  jobs               (id, job_number, customer_id, sku_id, line_id,
                      target_quantity, scheduled_start, scheduled_end,
                      actual_start, actual_end, status, handover_notes)
  hourly_runs        (id, job_id, line_id, sku_id, shift, period, phase,
                      recorded_at, units_filled, scrap_bottles, duration_min,
                      operator, raw_text, source, job_seq, job_hour_start,
                      job_hour_end, user_id, notes, flagged)
  downtime_events    (id, run_id, station, reason, minutes, note)
  co_procedures_v2   (id, line_id, from_sku_id, to_sku_id, name,
                      aggregate_standard_min)  UNIQUE(line_id,from,to)
  co_steps_v2        (id, procedure_id, seq, step_name, station, standard_min,
                      is_serial)
  co_events          (id, procedure_id, line_id, started_at, ended_at,
                      aggregate_actual_min, bottles_to_mixer, operator,
                      raw_text, source, from_job_number, to_job_number,
                      from_job_id, to_job_id, user_id, notes)
  co_event_steps     (id, event_id, step_id, actual_min, note)
  experiments        (see 4.2 — extended with PDCA fields)
  experiment_actions (id, experiment_id, seq, description, owner, due_date,
                      status, completed_at)
  users              (id, name, role, line_id, telegram_id, active)
  bot_sessions       (chat_id PK, state, active_job_id, active_changeover_id,
                      pending_job_id, start_offset, pending_step_idx, shift,
                      shift_hour, pending_text, co_total_min, updated_at)
  settings           (key PK, value, description)

### 4.2 experiments — extended for the PDCA A3 form

Header/team:
  pdca_id, title, department, line_id, status, problem_severity,
  start_date, target_date, pdca_owner, management_sponsor, team_members,
  departments_involved

Body:
  current_condition, target_condition, hypothesis, root_cause,
  fishbone_category (Man/Method/Material/Machine), action_plan, action_owner

Verification:
  target_state_reached, how_known_solved, new_problems_created,
  notes_on_back, target_step_name, standard_min, target_goal_min

Priority scoring (each 1, 3, or 5):
  pri_time, pri_impact, pri_resources, pri_magnitude, pri_cost

Timestamps:
  created_at, updated_at

### 4.3 Settings

  unit_label — display label for a single unit of output. Default: "units".
               Client-settable to "bottles", "cans", "jars", "containers",
               "cases". Everything user-facing reads from here.

---

## 5. THE PDCA FORMULA

Priority total = time*10 + impact*30 + resources*30 + magnitude*30 + cost*50

Each criterion scored 1, 3, or 5. Higher priority = higher score.
Range: 150 to 750. This matches the "150–750" range in PDCA Log-Matrix.xlsx.

Criteria and their multipliers (from the template):
  Time to Implement     × 10   (1=4+wks, 3=2-4wks, 5=1-2wks)
  Impact to Process     × 30   (1=Machine, 3=Machine&Process, 5=Process)
  Resources Needed      × 30   (1=3+depts, 3=2depts, 5=1dept)
  Magnitude of Problem  × 30   (1=<1hr DT/day, 3=1-3hr DT/day, 5=3+hr)
  Cost of Downtime      × 50   (1=<$200, 3=$200-$500, 5=$500+)

The design intent: triage issues on the floor. Top-five by priority tells
management where to spend the next week.

---

## 6. THE BOT (Telegram)

One bot, one token, one poller: @KoorsusTheBot
Telegram ID of owner: 7451582244 (in users table, id=1)

### 6.1 Files

  bot_live_v3.py  — polling loop. systemd unit: myarra-bot.service
  bot_v3.py       — LLM-augmented dispatch, falls back to regex
  bot_v2.py       — all handlers, session state, plausibility, writes
  parsers.py      — regex fallback parsers
  intent.py       — Qwen extraction
  test_parsers.py — 26 unit tests, all pass
  test_intent.py  — 18 extraction cases against local Qwen, all pass
  test_scenarios_v3.py — 16 end-to-end scenarios, 16/16 pass

### 6.2 Routing

Every message goes to Qwen 2.5-3B on port 8080 first (via intent.py).
The model returns a structured intent + fields. bot_v3 rebuilds a
canonical message and hands it to bot_v2.dispatch().

If Qwen returns intent='unknown' or errors, falls back to bot_v2 regex.
If the session is mid-flow (awaiting a numeric answer), goes straight to
the state machine. No LLM call for "35" or "18000".

### 6.3 Trigger set (T1–T12)

  T1  running job WO-XXXX-XXX, hour N, UNITS [N min down STATION reason]
  T2  record production hour N, M minutes, UNITS
  T3  ending job WO-XXXX-XXX
  T4  changeover job WO-XXXX-XXX to WO-XXXX-XXX
  T5  end changeover
  T6  start job WO-XXXX-XXX
  T7  status job WO-XXXX-XXX
  T8  status line N
  T9  sop, your question  (proxies to Koorsus /ask on port 5000)
  T10 (anything unrecognized → help text)
  T11 handover job WO-XXXX-XXX
  T12 taking over job WO-XXXX-XXX
  Also: "cancel", "confirm <command>" for plausibility override

### 6.4 Two-clock model

  shift-hour — H1..H8, resets at shift change
  job-hour   — cumulative production on a job, resets at JOB change

Job-hours carry forward across handovers (same job, new lead).
Job-hours reset when a changeover completes (new job).

### 6.5 Changeover aggregation — CRITICAL

co_events.aggregate_actual_min = the WALL CLOCK the operator stated.
It is NEVER the sum of step times. Step times are per-station, kept
independently on co_event_steps.

Reason: verification runs INSIDE packaging on many lines. Steps overlap.
A single station can be inside another station's time. Summing would
double-count.

The aggregate is what compares to the standard. The per-step times are
what show which station helped and which hurt.

### 6.6 Plausibility safeguard

When an operator logs "hour 5, 3022 units" on a 600-unit/hr line, the bot
refuses to accept silently. It replies:

  "3,022 is far below the ~36,000 expected. Re-say the full number, or
   prefix with 'confirm' to accept."

Operator can reply "confirm running job WO-2026-001, hour 5, 3022 units"
to override. Range: 50% to 110% of expected. Outside that band, refuse
without 'confirm'.

Reason this exists: voice-to-text loses digits. An operator cannot be
trusted to catch their own transcription loss. The bot must not log a lie.

### 6.7 Voice-to-text mangling (accepted, not fought)

Qwen 2.5-3B handles:
  - w0-2610-008 (letter O → zero)
  - hour five (word form)
  - thirty-four thousand (words, not digits)
  - "logging 008 hour 6" (no job-number prefix, just last 3 digits)
  - "labeler is throwing an E44" (unseen phrasing → sop intent)

This is the reason for the swap from Llama 3.2 to Qwen 2.5.

---

## 7. THE WEB APP

Port 5002, Flask under waitress, systemd: myarr.service

Routes (all 200):
  /                          Shift Reconciliation (dashboard)
  /changeover                Changeover detail (latest event only)
  /pdca                      PDCA dashboard (bar chart, sorted by priority)
  /pdca/log                  PDCA register (list, sorted by priority)
  /pdca/<int:exp_id>         A3 form
  /setup                     CSV uploader
  /admin                     User management
  /shift/<date>/<shift>      Hour-by-hour drill-down

Templates: base, dashboard, changeover, pdca, pdca_log, a3, setup, admin,
shift_detail. All in templates/.

The dashboard `/` shows shift-level reconciliation:
  Shift, Jobs (count), Filled, Expected, Gap (min), Logged (min),
  Unaccounted (min), Performance %, Status pill (reconciled/watch/FLAG)

Graded bands on unaccounted:
  green  < 2 min
  amber  2-5 min
  red    > 5 min

---

## 8. KOORSUS (the document platform)

Port 5000, Flask under waitress, systemd: koorsus.service
RAG with ChromaDB + sentence-transformers + Qwen on 8080

/ask endpoint: POST {"question": "..."} → grounded answer with source
Strict grounding: declines when the documents do not contain the answer.

Currently indexed: midwest_precision.txt, columbus_plant.txt (demo docs).
Replaceable by uploading a real client's SOPs.

The bot can query Koorsus from Telegram:
  "sop, labeler E44 error code"

---

## 9. LLM (Qwen 2.5-3B)

Model file: /home/jeeves/llama.cpp/models/qwen2.5-3b/qwen2.5-3b-instruct-q4_k_m.gguf
Served by: llama-server.service on port 8080
Command flags in the unit file include -ngl 99 (all layers to GPU) and
-ub 2048 (larger micro-batch).

One model, two jobs:
  1. Intent extraction for the bot (via intent.py)
  2. RAG generation for Koorsus (via /ask)

Run sequentially, not concurrently. This is a demo machine. Both are user
journeys, not parallel workloads.

IMPORTANT: Do NOT add LD_LIBRARY_PATH to llama-server.service. Doing so
causes NVRM_RPC_DCE driver failures. This is documented, verified, and
left clean. Do not add it back.

---

## 10. SYSTEMD SERVICES

  llama-server.service  — Qwen on port 8080
  koorsus.service       — RAG on port 5000
  myarr.service         — Flask on port 5002
  myarra-bot.service    — Telegram bot (bot_live_v3.py)

All four active after cold reboot. Verified 2026-11-01.

  telegram-bot.service  — RETIRED. The older July Koorsus bridge.
                          Not enabled, should remain inactive.

Start/stop/check:
  sudo systemctl status llama-server koorsus myarr myarra-bot
  sudo systemctl restart myarr
  sudo journalctl -u myarra-bot -n 50 --no-pager

---

## 11. THE DEMO DATABASE (myarra.db as of 2026-11-01)

Two verticals, one schema. This is the proof that the architecture is generic.

### 11.1 Line 1 — Cosmetics

SKUs:
  COS-RS-025 — Cosmetic Compact Rose 0.25oz  (case_pack 12)
  COS-SD-025 — Cosmetic Compact Sand 0.25oz  (case_pack 12)

Rate: 7,200 units/hr on Line 1

Components:
  case, formulation, shrink, box

Changeover procedure:
  COS Rose → COS Sand, line 1, standard 40 min

Steps:
  Change case (case_feeder, 12 min)
  Change formulation (filler, 10 min)
  Verify (line, 8 min)
  Startup (line, 10 min)

### 11.2 Line 2 — Beverage Canning

SKUs:
  BEV-IPA-12 — Hazy IPA 12oz Can  (case_pack 24)
  BEV-STO-12 — Stout 12oz Can      (case_pack 24)

Rate: 36,000 units/hr on Line 2

Components:
  can, seam, label, pak

Changeover procedure:
  BEV IPA → BEV Stout, line 2, standard 15 min

Steps:
  Change label (labeler, 6 min)
  Verify (line, 5 min)
  Startup (line, 4 min)

### 11.3 Seed data

  4 jobs (WO-2026-001..004)
  16 hourly_runs (8 per line, S1+S2)
  2 downtime_events
  4 co_events (2 per line — one baseline, one experiment)
  14 co_event_steps
  2 experiments (one per vertical, both active)
  8 experiment_actions
  1 user (Randy Wolf, Admin, telegram 7451582244)

DASHBOARD SHOWS: 2026-10-31 S1 and S2, both 98% performance, both jobs=2.
This is cosmetics and canning side-by-side on the same page. That is the
whole point of the demo.

### 11.4 Cleaning bot-written data

Bot rows write with source='telegram'. To return to pristine demo state:

  DELETE FROM downtime_events WHERE run_id IN
    (SELECT id FROM hourly_runs WHERE source='telegram');
  DELETE FROM hourly_runs WHERE source='telegram';
  DELETE FROM co_event_steps WHERE event_id IN
    (SELECT id FROM co_events WHERE source='telegram');
  DELETE FROM co_events WHERE source='telegram';
  DELETE FROM bot_sessions;

---

## 12. WHAT FAILED (do not repeat)

### 12.1 The 2026-10-31 wine→generic pivot

On 2026-10-31 the project was on wine data with a wine-specific schema:
skus.wine_id, skus.glass_id, skus.cork_id, co_procedures with
blow_through_std_min, etc. Every page and every bot handler leaked wine
vocabulary into the code.

The pivot was: rebuild the schema generically, seed two verticals
(cosmetics, canning), prove that one codebase handles both. That is what
myarra.db now holds.

Do NOT re-add wine-specific column names. Do NOT hardcode "bottle" or
"glass" or "cork" in any Python file. Those words belong in the
component_types table and in settings.unit_label.

### 12.2 Nanobot — abandoned

Installed via conda "jetson-claw" (Python 3.11). Pairing system
undocumented. Web UI expects port 8900 that the gateway does not open.
CONCLUSION: use the owner's own telegram_bot.py instead. Sixty lines,
auditable.

### 12.3 Proton Mail Bridge — abandoned

Requires compiling for ARM64. Requires graphical login on first run
(incompatible with headless). CONCLUSION: use Gmail app password when
email is needed.

### 12.4 wine database — retired, not deleted

metrics.db still on disk. Do not point the app at it. Do not delete it
without owner direction. It holds historical Treasury-adjacent demo data.

### 12.5 The /60.0 bug — occurred twice

ideal_rate is units per HOUR. When the app computed expected production
it must do:

  expected = ideal_rate * duration_min / 60.0

The divisor /60.0 was removed once (Oct 31) and reappeared in a rebuild
(Nov 1). Both times the dashboard showed absurd performance (1.6% instead
of 98%). BOTH app.py and bot_v2.py have this divisor. NEVER remove it.

---

## 13. DESIGN PRINCIPLES

  - Check what the owner already has before proposing a dependency.
  - One change at a time, verification gate between each.
  - The appliance must survive reboot. systemd, enabled, verified.
  - Strict grounding is the product. Refuse when documents do not answer.
  - No em dashes in customer-facing prose.
  - Phone-first for data entry. The tool that gets used is the one that
    fits in a pocket and takes ten seconds.
  - The aggregate actual is the wall clock. Never the sum of steps.
  - Voice-to-text is lossy. Refuse implausible entries. Confirm to override.
  - Do not hardcode industry vocabulary in Python files.
  - Test what you claim. Every service in this handoff was verified alive
    after a cold reboot at 2026-11-01 ~19:30 EDT.

---

## 14. HOW TO RESUME

SSH from Windows PowerShell:
  ssh jeeves@192.168.100.2

Check all four services:
  systemctl is-active llama-server koorsus myarr myarra-bot

Check the six main routes (returns list of 200s):
  for u in / /pdca /pdca/log /changeover /setup /admin; do
    printf "%-24s " "$u"
    curl -s -o /dev/null -w "%{http_code}\n" "http://127.0.0.1:5002$u"
  done

Check the bot is polling:
  sudo journalctl -u myarra-bot -n 20 --no-pager
  # Expect: "bot_live_v3: polling as @KoorsusTheBot"

Talk to the bot from Telegram: "status line 1"

Check the LLM directly:
  curl -s -m 10 http://127.0.0.1:8080/v1/models | head -c 200

Work in tmux to survive SSH drops:
  tmux new -s work
  # after a drop: tmux attach -t work

---

## 15. WHAT IS NOT BUILT (parking lot, in rough priority order)

### 15.1 Before Monday's marketing push

  - Screenshots for Carrd — /pdca is the money shot, /pdca/log is the
    register, / is the two-vertical demo. Take at full width.
  - T3 Packaging outreach email — drafted in the Oct 18 handoff, never sent.
    Contact: Christopher L. Dillon, cdillon@t3packaging.com, 614-946-1089.
    Offer: one pro bono Operational Diagnostic.
  - Token rotation on @KoorsusTheBot via BotFather /revoke. Currently a
    demo token; a fresh one before any client sees it.
  - Richer cosmetics demo — three SKUs, three changeovers, three
    experiments. Half an hour of seeding.

### 15.2 Before the first real client

  - Odoo / ERP API — GET /api/v1/runs, GET /api/v1/changeovers, POST /api/
    v1/readings. Documented with curl examples. This makes Myarra
    saleable as a standalone appliance.
  - Onboarding tool — the way a consultant enters a new client's lines,
    SKU BOMs, rates, and changeover matrix. Currently these are seeded
    directly into SQLite.
  - Shift handover history table — shift_handovers(job_id, from_user,
    to_user, notes, created_at). v1 only stores latest notes on
    jobs.handover_notes.

### 15.3 Longer-term

  - Maintenance as third billable event (structurally like changeover)
  - /changeover as a LIST with line + date filters and click-through to
    detail. Current page shows only the latest event.
  - / (dashboard) changeover time per shift, alongside production
  - Multi-line leads (currently one line per user)
  - Relog with mandatory override_reason audit trail (v1.1)
  - Passwordless sudo (currently not configured; ask for password)
  - Orin NX 16GB upgrade — unlocks Qwen3-4B or 8B, heavier agent stacks
  - Email skill for Gmail app password (deferred, "we have everything we
    need")
  - Standard Work Instructions as documents in Koorsus lake (partial —
    /ask already answers SOP questions)

---

## 16. THE DEMO TOMORROW MORNING — if a client were on site

  1. Open browser at http://192.168.100.2:5002
  2. Point at the dashboard: "Two product types, two lines, one appliance.
     Cosmetics on Line 1, canning on Line 2. Both at 98%. That is what
     the plant looks like from three hundred feet up."
  3. Click into a shift: "This is the hour. Expected from rate, actual
     from the line. Unaccounted time is what your downtime log cannot
     explain. That is the number your current OEE tool hides."
  4. Click /pdca: "Here is the case-parts pre-staging experiment. Baseline
     was 14 minutes. Current is 9. Two more reps and we hit the target."
  5. Click /pdca/log: "Sorted by priority. The labeler overrun is the
     top concern this week, at 590. The case pre-staging is 510."
  6. Click /pdca/1: "This is the A3. Every field your continuous
     improvement team already fills in on paper — current condition,
     target, root cause, hypothesis, action items, verification."
  7. From the phone, message the bot: "running job WO-2026-001, hour 5,
     7000 units, 4 minutes down jam at filler." Bot replies with a
     receipt. Then "sop, labeler E44 error code." Bot answers from the
     document lake, cites the source.

That is the demo. It runs from cold boot. No manual intervention.

---

## 17. CONTACT AND CANONICAL SESSION NOTES

Canonical session: the Claude instance on the desktop. If the owner says
something on a phone in the same "chat", it may live in a separate thread
that the desktop cannot see. Do not rely on cross-device context.

When in doubt: ask the owner one question at a time. Do not batch
assumptions.

Voice-to-text on this project:
  - loses digits
  - converts letters to digits (W → 20, O → 0)
  - mangles industry vocabulary
  - is unreliable at end-of-day

Read for intent, not literal. When uncertain, ask.

END OF HANDOFF.
