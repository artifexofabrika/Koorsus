# MYARRA — PROJECT HANDOFF

Last updated: 2026-11-03 (afternoon)
Owner: Randy Wolf, Columbus, Ohio
Prepared by: Jeeves (Claude)

READ SECTION 1 FIRST. It records the governing architecture. Then Section 14
for how to resume. If you only have five minutes, read Sections 1, 4, 5, 14.

---

## 1. THE GOVERNING ARCHITECTURE

Myarra is not an ERP. It is not an MRP. It is not a BOM management system.

Myarra is a **production-to-standard tracker** with two measurable events:

  1. PRODUCTION — how did this hour run against its standard?
  2. CHANGEOVER — how well did we change from SKU A to SKU B?

Plus a future third event (MAINTENANCE) — not built, not scoped.

The BOM is INPUT, not subject. It tells us which components change during a
changeover. Where those components come from (pre-silk-screened, in-house,
procured) is not our concern.

The product is the loop: PDCA experiments that change procedure and prove
whether the change paid off.

**The manager's frustration this product solves:** answering one question
required cross-referencing six reports. The data existed, it was not
accessible. Myarra is a dependent system, not an ERP replacement. It ingests
floor truth and makes it queryable in plain English, in one place.

Any feature that belongs to an ERP is out of scope. When in doubt, ask:
"does this help a plant manager run production to standard, or is it an
accounting/inventory function?" If the latter, defer.

---

## 2. THE BUSINESS

Artifexo Fabrika — lean manufacturing consultancy, Columbus, Ohio.
Founded by Randy Wolf (30 years in lean, startups, operations).

Pitch: "We do not sell software. We assess your operation, install open-source
AI tools on hardware you own, and maintain them for you. No subscriptions.
No data leaving the building. No dependence on Big Tech."

Brand hierarchy:
  - Artifexo Fabrika = the consultancy (the workshop)
  - Koorsus         = the document platform (Latin "cursus" = course/path)
  - Myarra          = the metrics platform (Polish "miara" = measure)
  - Jeeves           = future AI Valet product, reserved, NOT part of this

Target market: Central Ohio.
  - Cosmetics contract packagers (New Albany: Accel, Anomatic, Voyant Beauty,
    KDC/One, Axiun, Alene Candles)
  - Beverage canning (breweries, cideries)
  - Not bottling — insufficient facility density in Ohio

Pricing:
  - Operational Diagnostic: $2,500
  - On-Site Lean Training: $3,500 (8 hours, up to 20 people)
  - Private AI Appliance: Starting at $5,500 installed
  - Fractional Operations Leadership: Starting at $8,000/month
  - Day rate: $1,385/day
  - Retainers: Monitoring $250/mo, Advisory $850/mo
  - Support after initial 4 hours: $100/hour

Landing page: https://www.artifexofabrika.com
  - Served directly from GitHub Pages (docs/ folder), no Carrd iframe
  - Dark palette #1a1a1a, gold accent #c0a878, Georgia serif
  - Formspree endpoint: https://formspree.io/f/xdarnqnj
  - Custom domain: artifexofabrika.com (with k)
  - Note: artifexofabrica.com (no k) also registered, currently pointing at
    GitHub Pages via accidental A records. Should redirect to the with-k
    domain eventually. PARKING LOT.

Licensing: GPL v3. Committed. README explains the "not locked in" promise.

Marketing in flight:
  - Hand-assembled boxes (matchbook style) with chocolate coins
  - Hook: "This is what an unaccounted minute looks like"
  - 25-30 boxes, hand-written by friend Amy
  - Recipients: T3 Packaging (Christopher Dillon), ADL Technology,
    889 Global Solutions, Valence Industrial, Appian Manufacturing,
    Columbus Machine Works, Accel, Figures Packaging, GMS Industries
  - Then r/manufacturing and r/LeanManufacturing subreddits
  - Unique QR URLs per recipient for response tracking (?from=t3, etc.)

---

## 3. HARDWARE & NETWORK

Device: NVIDIA Jetson Orin Nano 8GB, 256GB NVMe
Hostname: koorsus
OS: Ubuntu 22.04.5 LTS, L4T 36.5.2 (JetPack 6.2.3), headless

The internal Realtek Wi-Fi card is DEFECTIVE. Bypassed with a BENFEI USB-C
to Gigabit Ethernet adapter. The adapter occasionally needs reseating.

Network:
  - Windows Ethernet adapter "Ethernet 7": 192.168.100.1 (static)
  - Jetson "Wired connection 1": 192.168.100.2/24 (static, manual)
  - Gateway: 192.168.100.1
  - DNS: 8.8.8.8, 1.1.1.1 (ipv4.ignore-auto-dns=yes)
  - SSH: ssh jeeves@192.168.100.2

PowerShell NAT for internet sharing (Windows ICS is buggy):
  New-NetNat -Name "JetsonNAT" -InternalIPInterfaceAddressPrefix "192.168.100.0/24"
  Set-NetIPInterface -InterfaceAlias "Ethernet 7" -Forwarding Enabled
  Set-NetIPInterface -InterfaceAlias "Wi-Fi" -Forwarding Enabled
  # Run in PowerShell as Administrator

IMPORTANT NOTES:
  - "Ethernet 2" is a dead TunnelBear VPN adapter. Do not touch it.
  - sudo prompts fail silently if Caps Lock is on. Check Caps Lock first.
  - SSH key auth is configured from the Windows side.
  - /etc/gai.conf has `precedence ::ffff:0:0/96 100` to prefer IPv4 over
    IPv6. The Jetson NAT only forwards IPv4, so this is required.

Future hardware: Orin NX 16GB. Unlocks Qwen2.5-7B or Qwen3-8B comfortably.
The Nano is only for RAG-only deployments. NX is the standard product.

---

## 4. DATA MODEL

Database: /mnt/lake/myarra.db (canonical)

Retired but preserved:
  - /mnt/lake/metrics.db (wine data, Oct 2026)
  - /mnt/lake/demo_beverage.db (beverage-only, Oct 2026)

db.py points at myarra.db.

### 4.1 Tables

  lines              (id, name, format_type)
  skus               (id, part_number, description, case_pack, active)
  line_sku_rates     (line_id, sku_id, ideal_rate)  -- UNITS PER HOUR
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
  co_steps_v2        (id, procedure_id, seq, step_name, station,
                      standard_min, is_serial)
  co_events          (id, procedure_id, line_id, started_at, ended_at,
                      aggregate_actual_min, bottles_to_mixer, operator,
                      raw_text, source, from_job_number, to_job_number,
                      from_job_id, to_job_id, user_id, notes)
  co_event_steps     (id, event_id, step_id, actual_min, note)
  co_event_changes   (id, event_id, component_type_id, from_value, to_value,
                      created_at)  -- WHICH COMPONENTS CHANGED. Backfilled
                                   -- and populated live by bot.
  line_events        (id, line_id, state, started_at, ended_at, job_id,
                      co_event_id, reason, notes, user_id, source)  -- THE
                      SPINE. One open event per line at any time.
  experiments        (see 4.2)
  experiment_actions (id, experiment_id, seq, description, owner,
                      due_date, status, completed_at)
  fishbone_causes    (id, experiment_id, category, cause_text, seq,
                      created_at)  -- 5M1E: Man, Machine, Method, Material,
                                   -- Measurement, Environment. Max 3 per
                                   -- category enforced on save.
  users              (id, name, role, line_id, telegram_id, active)
  bot_sessions       (chat_id PK, state, active_job_id,
                      active_changeover_id, pending_job_id,
                      pending_target_job_id, start_offset, pending_step_idx,
                      shift, shift_hour, pending_text, co_total_min, line_id,
                      updated_at)
  settings           (key PK, value, description)

### 4.2 experiments — extended for PDCA A3

Header/team: pdca_id, title, department, line_id, status,
  problem_severity, start_date, target_date, pdca_owner,
  management_sponsor, team_members, departments_involved

Body: current_condition, target_condition, hypothesis, root_cause,
  fishbone_category (primary category), action_plan, action_owner

Verification: target_state_reached, how_known_solved,
  new_problems_created, notes_on_back, target_step_name, standard_min,
  target_goal_min

Priority scoring (each 1, 3, or 5):
  pri_time, pri_impact, pri_resources, pri_magnitude, pri_cost

Measurement (added 2026-11-02):
  measurement_type — 'manual' | 'changeover_sku_pair' |
                     'changeover_component' | 'line_throughput'
  measurement_config — JSON. For changeover_sku_pair:
                     {"line_id": N, "from_sku": N, "to_sku": N}
  affected_skus — comma-separated SKU ids this PDCA touches
  baseline_value — manual baseline if measurement_type='manual'
  baseline_frozen_at — when baseline was frozen (optional)

Closure: closed_at, close_reason. "Failure is a learning opportunity"
  is the intended spirit. Closed experiments retain their reason.

Timestamps: created_at, updated_at

### 4.3 Settings currently seeded

  unit_label       = "containers"
  case_label       = "cases"
  shift_1_start    = "07:00"    shift_1_end = "15:00"
  shift_2_start    = "15:00"    shift_2_end = "23:00"
  shift_3_start    = "23:00"    shift_3_end = "07:00"
  lunch_minutes    = "30"

Shift structure: 8 hours elapsed, 30 min lunch, 7.5 hours production per
shift. Three shifts = 24h elapsed, 22.5h production, 1.5h lunch.

---

## 5. THE PDCA FORMULA

Priority total = time*10 + impact*30 + resources*30 + magnitude*30 + cost*50

Each criterion scored 1, 3, or 5. Range: 150 to 750.

  Time to Implement     × 10   (1=4+wks, 3=2-4wks, 5=1-2wks)
  Impact to Process     × 30   (1=Machine, 3=Machine&Process, 5=Process)
  Resources Needed      × 30   (1=3+depts, 3=2depts, 5=1dept)
  Magnitude of Problem  × 30   (1=<1hr DT/day, 3=1-3hr, 5=3+hr)
  Cost of Downtime      × 50   (1=<$200, 3=$200-$500, 5=$500+)

The A3 page shows each input, its contribution, and the total.

---

## 6. THE BOT (Telegram — development and demo channel)

One bot, one token, one poller: @KoorsusTheBot
Owner Telegram ID: 7451582244 (in users table, id=1)

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

Fast path: messages beginning with a known structured keyword go directly
to bot_v2.dispatch, bypassing the LLM. List:
  running, run, record, end/ending/finish/finishing, close*, start/starting/
  begin/beginning, changeover, status, sop/ask/question, handover,
  taking over/take over/took over, pause*, resume*, back to, cancel/stop/
  quit/exit, confirm

SLOW path (natural language): messages that do not match a structured
pattern go to Qwen (intent.py), which returns a structured intent and
fields. bot_v3 rebuilds a canonical message and passes to bot_v2.

Mid-flow: if session state is not 'idle', goes straight to the state
machine. No LLM call for "5" or "1800".

Voice-to-text normalization in dispatch():
  "and lunch" / "en lunch" → "end lunch" (and cip, maintenance, change,
  job, shift, work order, order)

### 6.3 Fuzzy job resolution (added 2026-11-02)

resolve_job(conn, job_number) tries:
  1. Exact match on job_number
  2. If no exact: candidates where the last 3 digits match
  3. If one candidate: accept
  4. If multiple: accept the one with ≥90% string similarity
  5. If none ≥90%: refuse with "Did you mean one of these?" listing
     active jobs

Every handler that takes a work order from the user goes through
resolve_job. On a fuzzy match, the reply says "(interpreting
'WO-0026-001' as WO-2026-001)" so the operator knows.

Structural, not a patch. One function, all handlers inherit.

### 6.4 Trigger set (T1-T12)

  running job WO-XXXX-XXX, hour N, UNITS [N min down STATION reason]
  record production hour N, M minutes, UNITS
  start WO-XXXX-XXX | start job WO-XXXX-XXX
  end WO-XXXX-XXX [changeover to WO-XXXX-XXX]
  end changeover
  pause WO-XXXX-XXX | resume WO-XXXX-XXX
  lunch | end lunch
  cip | end cip
  maintenance <reason> | end maintenance
  idle <reason> | unscheduled <reason>
  status WO-XXXX-XXX | status line N
  end shift
  handover job WO-XXXX-XXX | taking over job WO-XXXX-XXX
  sop, your question
  cancel
  confirm <command>  — overrides plausibility check

### 6.5 Two-clock model

  shift-hour — H1..H8, resets at shift change (from settings)
  job-hour   — cumulative production on a job, resets at JOB change

Job-hours carry forward across handovers and lunch/CIP/maintenance.
Job-hours reset when a changeover completes (new job).

### 6.6 Changeover aggregation — CRITICAL

co_events.aggregate_actual_min = the WALL CLOCK the operator stated.
It is NEVER the sum of step times. Step times are per-station, kept
independently on co_event_steps.

Reason: verification runs INSIDE packaging on many lines. Steps overlap.
Summing would double-count.

The aggregate compares to the standard. Per-step times show which
station helped and which hurt.

### 6.7 Plausibility safeguard

When an operator logs "hour 5, 3022 units" on a 7200/hr line, the bot
refuses:

  "3,022 is far below the ~7,200 expected. Re-say the full number, or
   prefix with 'confirm' to accept."

Range: 50% to 110% of expected. Outside that band, refuse without
'confirm'. Reason: voice-to-text loses digits and the operator cannot
be trusted to catch their own transcription loss.

### 6.8 Line-state resumption (added 2026-11-02)

`end lunch`, `end cip`, `end maintenance` look at the PREVIOUS line
event and resume that state:
  - If previous was production on a job: back to production on that job
  - If previous was changeover and it is not finished: back to changeover
  - Otherwise: idle with reason post-<context>

### 6.9 co_event_changes at creation (added 2026-11-02)

When the bot creates a changeover, it calls _log_changeover_changes()
which compares the two SKUs' BOMs and writes one row to co_event_changes
per component that differs. This is what makes "show me all label
changeovers" queryable.

Silently no-ops if co_event_changes table is missing or if the two SKUs
have identical BOMs (which is a data problem, not a code problem).

---

## 7. THE WEB APP (port 5002)

Flask under waitress, systemd: myarr.service

Routes (all 200 as of 2026-11-02):
  /                          Live Line Status (dashboard)
  /reconciliation            Job Reconciliation (one row per work order)
  /job/<job_number>          Hour-by-hour drill-down for one job
  /changeover                Changeover Log (list, filterable)
  /changeover/<id>           Changeover detail (steps + components changed)
  /pdca                      PDCA dashboard (bar chart, sorted by priority)
  /pdca/log                  PDCA register (list, sorted by priority)
  /pdca/<int:exp_id>         A3 form (read-only, with fishbone SVG)
  /pdca/<int:exp_id>/edit    A3 edit form
  /setup                     CSV uploader + stats
  /admin                     User management
  /shift/<date>/<shift>      Legacy hour-by-hour view
  /favicon.ico               Favicon

Templates: base, dashboard, reconciliation, job_detail, changeover_list,
changeover, pdca, pdca_log, a3, a3_edit, setup, admin, shift_detail.

### 7.1 The dashboard `/`

Live Line Status. One row per line. Shows current state (from line_events,
the open event for each line) plus context:
  - production: running job, cases produced / target, percent complete,
    elapsed time
  - changeover: from→to, elapsed vs standard
  - lunch/cip/maintenance/idle/unscheduled: reason, elapsed

Shows the flexibility story: five lines, five verticals, one page.

### 7.2 Reconciliation `/reconciliation`

One row per work order. Columns: Date, Shift, Line, Job, SKU, Cases,
Expected, Variance, Perf, Status. Click through to /job/<number>.

Filter by line, by window (1/3/7/30 days). Newest first.

Unit is the JOB, not the shift. A shift row that aggregates five different
jobs on five different lines is arithmetic without a question behind it.

### 7.3 Changeover list `/changeover`

One row per changeover event. Filter by line, by COMPONENT CHANGED
(populated from co_event_changes), by window (7/14/30/90 days).

The component filter is what answers "show me all label changes last
month" — one click, one answer. The list of available components is
derived from co_event_changes, so it automatically adapts to whatever
component_types the customer has defined.

### 7.4 PDCA A3 `/pdca/<id>`

Read-only rendered A3 with:
  - Header meta as boxed fields (six: severity, start date, owner,
    sponsor, team, departments)
  - Measurement & Trend section. For changeover_sku_pair experiments,
    baseline and current are computed automatically from co_events:
    baseline = AVG of events before start_date, current = AVG of events
    since. No manual entry needed.
  - Current Condition / Target Condition side by side
  - **Fishbone diagram (5M1E) as SVG**. Six ribs (Man, Method, Machine top;
    Measurement, Material, Environment bottom), up to 3 causes per rib.
  - Root Cause summary (free text) with Primary Category
  - Action Plan table (from experiment_actions)
  - Hypothesis / Verification & Follow-up
  - Priority breakdown: each input, its contribution, the total
  - Notes on Back

Editable at /pdca/<id>/edit. Everything except ID and start_date is
editable. Closing as failed is valid: status='closed' + close_reason.

CSS in a3.html and a3_edit.html uses HARDCODED hex colors — no var()
dependencies. This was necessary because style.css defines --bg and --text
in ways that made the A3 unreadable (black on black). Do not change to
var() without checking style.css first.

### 7.5 Fishbone categories

FISHBONE_CATEGORIES = ['Man', 'Machine', 'Method', 'Material',
                       'Measurement', 'Environment']
FISHBONE_MAX_PER_CATEGORY = 3

Measurement is its own category, not folded under Method. The distinction:
  - Method asks "is the procedure correct?"
  - Measurement asks "is the number we trust actually correct?"

Classic example from the owner's experience: tolerance written for carbon
steel, applied to fiber mat, held to the wrong spec, huge kickback. The
Method was right. The Measurement system was wrong. That is why they are
separate ribs.

---

## 8. KOORSUS (the document platform)

Port 5000, Flask under waitress, systemd: koorsus.service
RAG with ChromaDB + sentence-transformers + Qwen on 8080

/ask endpoint: POST {"question": "..."} → grounded answer with source
Strict grounding: declines when the documents do not contain the answer.

Currently indexed: midwest_precision.txt, columbus_plant.txt,
labeler_sop.txt (contains E44 = software mismatch, requires maintenance).

The bot can query Koorsus from Telegram: "sop, labeler E44 error code"

---

## 9. LLM (Qwen 2.5-3B)

Model file:
  /home/jeeves/llama.cpp/models/qwen2.5-3b/qwen2.5-3b-instruct-q4_k_m.gguf

Served by: llama-server.service on port 8080

Note on naming: llama-server is the NAME OF THE SOFTWARE (llama.cpp's server
binary). Qwen is the MODEL it loads. Confusing but not a bug.

IMPORTANT: Do NOT add LD_LIBRARY_PATH to llama-server.service. Doing so
causes NVRM_RPC_DCE driver failures. Documented, verified, left clean.

One model, two jobs:
  1. Intent extraction for the bot (via intent.py)
  2. RAG generation for Koorsus (via /ask)

Run sequentially, not concurrently.

Future: rename llama-server.service to koorsus-llm.service for clarity.
PARKING LOT.

---

## 10. SYSTEMD SERVICES

  llama-server.service  — Qwen on port 8080
  koorsus.service       — RAG on port 5000
  myarr.service         — Flask on port 5002
  myarra-bot.service    — Telegram bot (bot_live_v3.py)

All four active after cold reboot. Verified 2026-11-01.

  telegram-bot.service  — RETIRED (July Koorsus RAG bridge). Inactive,
                          disabled. Do not re-enable; conflicts on token.

Start/stop/check:
  sudo systemctl status llama-server koorsus myarr myarra-bot
  sudo systemctl restart myarr
  sudo journalctl -u myarra-bot -n 50 --no-pager

---

## 11. THE DEMO DATA (myarra.db as of 2026-11-03)

Five lines, five verticals, one schema. Proof that architecture is generic.

  Line 1  Cosmetics Compacts    7200/hr, case_pack 12
  Line 2  Cosmetics Foundation  5000/hr, case_pack 12
  Line 3  Beverage Cans 12oz   36000/hr, case_pack 24
  Line 4  Beverage Cans 16oz   24000/hr, case_pack 24
  Line 5  Jewelry Cleaner Jars  4000/hr, case_pack 12

10 SKUs (2 per line), 30 work orders (6 per line, spread over 30 days).
~250 hourly runs, ~25 changeovers, 5 experiments (one per line-ish).

Current shift: all five lines running, staggered start times, each at
55-65% complete. This is the "live" demo state.

Line 5 SKUs (9, 10) now have formulation component in BOM (lavender vs
unscented) so changeover log records the component change.

### 11.1 Cleaning bot-written data

Bot rows write with source='telegram'. To return to pristine demo state:

  DELETE FROM downtime_events WHERE run_id IN
    (SELECT id FROM hourly_runs WHERE source='telegram');
  DELETE FROM hourly_runs WHERE source='telegram';
  DELETE FROM co_event_changes WHERE event_id IN
    (SELECT id FROM co_events WHERE source='telegram');
  DELETE FROM co_event_steps WHERE event_id IN
    (SELECT id FROM co_events WHERE source='telegram');
  DELETE FROM line_events WHERE source='telegram';
  DELETE FROM co_events WHERE source='telegram';
  DELETE FROM bot_sessions;

### 11.2 Regenerating the seed

/tmp/seed_5lines.py (if it still exists; otherwise recreate from this
handoff section). Key fix from the earlier version: units = rate * factor,
NOT rate * 60 * factor. The rate is already per-hour.

---

## 12. WHAT FAILED (do not repeat)

### 12.1 The /60.0 bug — happened THREE times
ideal_rate is units per HOUR. When computing expected production:

  expected = ideal_rate * duration_min / 60.0

The divisor /60.0 was removed and re-added three times in the seed and in
the app code. Each time the dashboard showed absurd performance (1.6% or
5787% instead of 98%). The divisor must ALWAYS be present.

### 12.2 Session not subscriptable
The Session class originally had .get() and .set() but not __getitem__.
Several handlers used s['active_job_id'] which crashed. Fixed by adding
__getitem__, __setitem__, __contains__ to Session. Same class of bug will
return if anyone adds a handler that uses dictionary syntax without
checking the class.

### 12.3 Dark on dark A3
The A3 CSS originally used var(--text, #eee) which fell back to a dark
value defined in style.css. Result: invisible text. Fixed by hardcoding
every color in a3.html and a3_edit.html. Do not revert to var() without
checking style.css.

### 12.4 Nanobot — abandoned
Pairing system undocumented. Web UI expects port 8900 that gateway does
not open. Use owner's own bot code instead.

### 12.5 Proton Mail Bridge — abandoned
Requires compiling for ARM64. Requires graphical login on first run.
Use Gmail app password when email is needed (deferred).

### 12.6 The wine → generic pivot (2026-10-31)
Earlier schema was wine-specific (skus.wine_id, cork_id, glass_id,
co_procedures with blow_through_std_min). Every page leaked wine
vocabulary. Rebuilt generically. Seeded cosmetics + canning + jewelry.

Do NOT re-add industry-specific column names. Component names live in
component_types. Display labels live in settings.

### 12.7 voice-to-text "and" for "end"
Repeatedly turned "end lunch" into "and lunch". Fixed in dispatch() with
a regex that normalizes "and lunch"/"en lunch" to "end lunch" for the
known command objects. Extend the pattern if a new state command is added.

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
  - **Rewrite whole files, not patches.** The owner has stated this
    explicitly. "Whole file, one paste" is the working method. Patching
    leads to compounding failures and hours of debugging.
  - Test what you claim. Do not assert what has not been checked.
  - Every answer cites its source document by name, exactly as it appears.

---

## 14. HOW TO RESUME

SSH from Windows PowerShell:
  ssh jeeves@192.168.100.2

Check all four services:
  systemctl is-active llama-server koorsus myarr myarra-bot

Check the main routes (should print 200 for each):
  for u in / /reconciliation /changeover /pdca /pdca/log /setup /admin; do
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

Repository:
  cd ~/Client-Demo
  git log --oneline -10
  git status --short

The repo is at github.com/artifexofabrika/Koorsus (public, GPL v3).
Push requires username artifexofabrika + personal access token as password.

---

## 15. WHAT IS NEXT (as of 2026-11-03)

### 15.1 The very next piece — onboarding templates

This is what turns "demo" into "installable at a customer site."

Build:
  1. /setup page rewritten:
     - "Download templates" section listing ten CSVs, each with two
       example rows showing the format
     - Upload section expanded to accept all ten plus weekly schedule
     - "Onboarding instructions" section: three sentences on the workflow

  2. Ten template CSVs served from memory (send_file from io.BytesIO):
     - lines.csv              (id, name, format_type)
     - skus.csv               (id, part_number, description, case_pack, active)
     - component_types.csv    (id, name, is_serial, default_swap_min)
     - sku_bom.csv            (sku_id, component_type_id, component_value)
     - line_sku_rates.csv     (line_id, sku_id, ideal_rate)
     - co_procedures.csv      (line_id, from_sku_id, to_sku_id, name,
                               aggregate_standard_min)
     - co_steps.csv           (procedure_key, seq, step_name, station,
                               standard_min)  where procedure_key is
                               "line-from-to" so uploader can join
     - jobs_weekly.csv        (job_number, sku_part_number, line_id,
                               target_quantity, scheduled_start,
                               scheduled_end)  with INSERT OR REPLACE so
                               weekly uploads update existing jobs
     - users.csv              (name, role, line_id, telegram_id, active)
     - settings.csv           (key, value, description)

  3. /setup/verify page: shows what was uploaded, table by table, so the
     owner can confirm the data landed correctly without opening SQL.

  4. onboarding.py helper module: template definitions + CSV parsing +
     per-row error reporting with exact failing line number.

Roughly half a day of work in one paste.

### 15.2 November roadmap (owner has stated: no other projects this month)

In order:
  1. Onboarding templates (above)
  2. Query-level reporting over the data lake — the /ask page with
     text-to-SQL. Read-only, scoped to known tables, refuses when
     ambiguous. This answers the manager's "six reports" frustration
     directly. Natural language in, structured query out.
  3. Recommendations on top of the queries, once queries are trustworthy
  4. PWA (Phase 2 or later — see 16.1 below)

### 15.3 The vision, recorded in the owner's words

"My frustration as a manager was having to cross-reference six reports
to pull the data I wanted. If we have everything in the data lake and
chunked and indexed properly, technically the AI should be able to pull
out whatever I want. Changeovers, production runs, work orders, job
numbers, inventory lists, all of that. Not superseding an ERP, but
taking the data collected by an ERP and making it much more accessible
and usable."

That is the product statement for Phase 2 onward.

---

## 16. PARKING LOT

### 16.1 PWA with PIN pairing (Phase 2 or later)

Replaces Telegram for customer deployments. Design settled, not built.

  - /lead route, form, POST to dispatch, cookie-based identity
  - First visit: enter name + 4-digit PIN, phone remembers
  - Every visit after: tap home-screen icon, app opens full-screen
  - Works on Android, iPhone, Windows — one codebase
  - Two days of work
  - No Telegram account. No spam. No setup call with each line lead.
  - Local network only; phone talks directly to Jetson

Telegram stays as development and demo channel after PWA exists. Bot
does not care which door a message comes through.

### 16.2 Artifexo Fabrica (no k) redirect
  - artifexofabrica.com has stray GitHub A records from accidental edit
  - Should redirect to artifexofabrika.com
  - DNS work, defer until quiet moment

### 16.3 Rename llama-server.service to koorsus-llm.service
  - Naming clarity. The binary is llama-server; the model is Qwen.
  - Cosmetic. Five minutes.

### 16.4 Passwordless sudo
  - Not configured. Real security trade-off. Revisit before client install.

### 16.5 .gitattributes for clean future diffs
  - `* text=auto eol=lf`
  - One-time normalization pass over the project
  - Cosmetic but prevents whitespace churn

### 16.6 cert.pem / key.pem in git history
  - Self-signed, dead IP (192.168.232.102), 10-year validity from July 2026
  - Removed from tip but remain in history
  - Low risk. Could rewrite history with git-filter-repo if desired.

### 16.7 Telegram token rotation
  - Demo token, in git history, currently in use
  - Owner has decided: rotate at end, not now
  - Demo token, low value, acceptable

### 16.8 Co_event_changes for other measurement types
  - Currently co_event_changes only populated for changeover_sku_pair
  - For changeover_component and line_throughput measurement types,
    the trend computation in _compute_trend returns "manual" with a note
  - Build when a real experiment needs it

### 16.9 Priority score visible inputs
  - DONE on A3 (each input and its contribution shown)
  - Still missing: contribution math on /pdca/log and /pdca list view

### 16.10 Onboarding template download from appliance
  - DONE as part of section 15.1
  - Show format by example, not by manual

### 16.11 Fully-accounted shift reconciliation
  - line_events already captures all states
  - The /reconciliation page currently shows production only
  - Add a per-shift fully-accounted view: production / changeover /
    lunch / cip / maintenance / idle / unscheduled / unaccounted,
    using line_events
  - Replaces the older shift-level view on /shift/<date>/<shift>

### 16.12 Work order history with notes (mostly done)
  - /job/<number> exists with hour-by-hour and downtime
  - Add: search, and a notes view (handover_notes on jobs table)
  - Small.

### 16.13 Odoo/ERP API
  - GET /api/v1/line_state/<line_id> first (the gap Odoo cannot fill)
  - Then GET /api/v1/runs, GET /api/v1/changeovers
  - Documented with curl examples
  - Makes Myarra saleable as a standalone appliance

### 16.14 Maintenance as third billable event
  - Structurally like changeover
  - Not built, not scoped
  - After Phase 2

### 16.15 Shift handovers history table
  - shift_handovers(job_id, from_user, to_user, notes, created_at)
  - v1 stores latest handover_notes on jobs table only
  - Not blocking

### 16.16 Relog with audit trail
  - Relog with mandatory override_reason
  - Only hours from current session
  - Deferred to v1.1

### 16.17 Multi-line leads
  - Currently one line per user (users.line_id)
  - Explicit "line 2" prefix for multi-line leads
  - After Phase 2

### 16.18 Email / customer support agents
  - Exist as separate offerings, not integrated into appliance
  - Not part of Koorsus/Myarra core
  - Add when a client asks and pays

### 16.19 Data lake text-to-SQL (/ask)
  - See section 15.2 item 2. This is the big one.

### 16.20 Orin NX 16GB upgrade
  - Awaiting funds
  - Unlocks Qwen2.5-7B or Qwen3-8B, heavier agent stacks, OpenClaw

### 16.21 Carrd subscription
  - No longer needed. GitHub Pages serves the site.
  - Cancel at renewal.

### 16.22 Hostname rename
  - jeeves-desktop.local → something neutral
  - Cosmetic.

### 16.23 Silicon / glass change sub-types
  - Wine had claret vs burgundy, 750 vs 1.5L as separate glass changes
  - Current schema uses single glass standard
  - Refine when real data shows variance

---

## 17. CONTACT AND SESSION NOTES

Canonical session: this Claude instance on the desktop. Phone
conversations may be in a separate thread that the desktop cannot see.
Do not rely on cross-device context.

When in doubt: ask the owner one question at a time. Do not batch
assumptions.

Voice-to-text on this project:
  - loses digits ("35022" → "3022")
  - converts letters to digits (W → 20, O → 0)
  - mangles industry vocabulary ("lean manufacturing" → "Arlene
    Manufacturing", "end lunch" → "and lunch")
  - is unreliable at end-of-day

Read for intent, not literal. When uncertain, ask.

**The working method the owner has asked for:**
  - Talk before coding. Show the plan, get approval, then write.
  - One instruction at a time. No stacking commands.
  - Push back on bad architecture. The owner explicitly asked for this.
  - Rewrite whole files, not patches.
  - No em dashes in customer-facing prose.
  - Verify with SQL before patching Flask.
  - Stop and diagnose if something is broken. Do not flail.

---

END OF HANDOFF.
