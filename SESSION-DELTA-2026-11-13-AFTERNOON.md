# SESSION DELTA 2026-11-13 - AFTERNOON (RECORD FLOW, RATE FIXES, JOB-HOURS)

This delta supplements SESSION-DELTA-2026-11-13-SPINE-AUTHORITY.md.
Read the morning delta first, then this one. Together they record the
full day. Neither supersedes the other; each is current on its subject.

Read alongside PHILOSOPHY.md, HERBIE-ARCHITECTURE.md, and the audit
document delivered to the prior instance on 2026-11-13.

## What was done in the afternoon

Four commits. All pushed to origin/main.

| Commit  | Content |
|---------|---------|
| 5002152 | Rate per run, not averaged: herbie and shift reconciliation score each run at its SKU's rate |
| 363abe1 | Align v_oee_summary with recon.py; ask refuses ambiguity; swap allowlist to canonical unaccounted view |
| d651576 | Record flow: hour lookbehind, word numbers, bare confirm, state machine |
| 62fb9c8 | Guard _next_job_hour against NULL job_hour_end |

### Rate per run (5002152)

Two functions were wrong for any line that ran more than one SKU rate
across sequential jobs.

herbie.get_line_summary used AVG(lsr.ideal_rate) across every SKU the
line could run, whether or not the SKU actually ran that day. Line 1 has
600/hr and 400/hr on file. On 2026-11-03 it ran only the 400/hr SKU with
43.3 min downtime. Old code reported 361 units lost capacity (averaged
500/hr). Fixed code reports 288, matching the independent per-run truth.
A 20 percent error on a number a plant manager acts on.

shift.compute_reconciliation took the first run's rate for the entire
shift. A shift that ran two sequential jobs at different rates scored
all of the second job at the first job's rate. The residual fired for
reasons the operator could not explain, and the operator either invented
a reason or said "unknown," smudging the record for nothing.

Both now compute per run: each hourly run scored at its own SKU's rate,
line totals are sums of correctly scored runs. The unaccounted view
(v_unaccounted_minutes_by_run) already did this correctly; the two
functions now follow the pattern the views established.

Verified: Line 1 on 2026-11-03, 288 fixed vs 289 independent truth vs
361 old averaged code. MATCH.

### /ask alignment (363abe1)

Two fixes plus one prompt change.

v_oee_summary omitted unscheduled_min from the OEE availability
denominator, while recon.py included it. Today unscheduled is always 0
so the difference is invisible; the moment a source table exists, /ask
and /reconciliation would disagree silently. Both now match recon.py.

ask.AVAILABLE_VIEWS listed v_unaccounted_by_line_day (which does not
net recorded downtime) and omitted v_unaccounted_minutes_by_run (which
does). Swapped. /ask and Herbie now give the same unaccounted answer.

The ambiguity prompt changed. Was: "If the question is ambiguous, make a
reasonable assumption and return the SQL." Now: "If the question is
ambiguous, or the answer is not derivable from these views with
confidence, return UNANSWERABLE. Do not guess." The refusal message is:
"I do not have the data to answer that question. The views available do
not cover it." This honors PHILOSOPHY 3 on the Nano. The 3B model cannot
parse ambiguity gracefully; refusing honestly is the better product than
guessing fluently. On the NX this may be revisited.

### Record flow (d651576)

The one-shot form "record H5, 60 minutes, 409 units, 2 scrap" already
worked. The conversational form did not. Missing fields prompted, but
set no state, so the operator's next message landed on "I did not
understand." Same class of trap as the awaiting_hour state fixed in the
morning.

Now state-driven:
    record H5              -> Hour 5: how many minutes?
    60                     -> Hour 5 (60 min): how many units produced?
    409                    -> Hour 5 (60 min, 409 units): scrap or rework?
    2 (or Two, or skip)    -> either final reply, or downtime prompt
    skip (if prompted)     -> final reply with the equation

The final reply shows the full arithmetic:
    Recorded: WO-2611-197 H5, 17 cases (409 containers, 2 scrap), 60 min.
    Expected 400 at 400/hr. Gap: -9 units (-1.3 min).
    Job-hours 8.0-9.0. FTQ 99.5%.

Three fixes inside the flow:

1. HOUR_PREFIX_RE uses a lookbehind (?<![a-zA-Z]) instead of \b. Voice-
   to-text glues the hour to the job number ("WO-2611-197h5"), and \b
   does not match between a digit and a letter. The lookbehind catches
   "197h5", "H5", "h5", and does not match inside a word.

2. Word numbers in scrap entry. _parse_small_number handles "two", "to"
   (a common voice-to-text mangle), "too", "for" (mangled "four"),
   "zero" through "twelve", and any digit or digit-containing sequence.
   On the test, "To scrap" and "Two" were both rejected as "Just a
   number please." They are now accepted as 2.

3. Bare "confirm" retries the pending record with force=True. Was: the
   dispatch regex required a space or comma after "confirm", so bare
   "Confirm" fell to "I did not understand." Now it finds the pending
   record in bot_sessions.pending_text and re-runs h_record_hour with
   force=True, honoring the plausibility check's promise.

### Job-hours guard and backfill (62fb9c8)

Seed rows for the seven-line factory had NULL in job_hour_start and
job_hour_end. _next_job_hour asked MAX(job_hour_end), got NULL, started
at 0.0. A record of H6 replied "Job-hours 1.0-2.0" instead of 5.0-6.0.

Two fixes:
- Backfill. One UPDATE walked every job's hourly_runs in order and
  computed cumulative hours from duration_min. 1,654 rows across 406
  jobs. Verified on WO-2611-197: H1-H8 show 0.0-1.0 through 7.0-8.0,
  the two test records from today show 8.0-9.0 and 9.0-10.0.
- Guard. _next_job_hour now falls back to SUM(duration_min)/60 when
  MAX(job_hour_end) is NULL. Prevents the same failure on any future
  seed or import that lacks the cumulative values.

## Decisions taken 2026-11-13 afternoon

Duplicate hours are allowed. A line lead may record H5 twice for the
same job. There is no refusal. The work center display shows both, the
mismatch is evident immediately, and the line lead relogs through the
existing audit-trailed path. Philosophy: capture never blocks.

Voice is optional. The PWA with a typed number pad is the primary
capture path on the shop floor. Voice via Whisper is the option when
the floor is quiet enough. Most shop floors are too loud for reliable
voice, and touchscreen number entry is faster when the operator is
entering digits anyway. The bot must accept both; neither is the only
path.

## The PowerShell and Jetson convention

Three windows were in play today. The convention was unclear and cost
time. Record it for the next instance.

- The Jetson SSH window is for anything that runs on the Jetson. This
  is nearly everything: Python scripts, SQL, git, systemctl, restarting
  services, editing files. Plain commands, no ssh prefix.
- PowerShell is for exactly two operations: scp from Windows to the
  Jetson, and ssh-wrapped commands when the Jetson window is not open.
  That is the whole reason PowerShell is involved.
- When the owner has both windows open, do not wrap Jetson commands in
  ssh from PowerShell. It asks for a password twice, it confuses the
  prompt, and it is pointless.
- When giving a command, label it: "Jetson window" or "PowerShell". Not
  "run this" with no indication.

Also recorded: the GitHub push prompt is asking for the personal access
token from the password manager, not a password. GitHub does not accept
passwords. The credential cache expires. When it prompts, retrieve the
token from the vault and paste it. Not a failure.

## Competitor watch: HIVE360 / AuditHive

HIVE360 is an AI-powered Operational Excellence platform by AuditHive,
a Canadian company. It is adjacent to Myarra, not a direct competitor.
Its centre is inspections, audits, corrective actions, shift handover
checklists, and a knowledge base ("Connected HIVE"). The conversational
assistant is called "Ask Stephanie". No OEE, no hourly production
capture, no changeover variance.

Where Myarra is genuinely different: on-premise appliance, no
subscription, customer owns the hardware, hourly free-text capture at
the point of work, two-measure OEE and operator performance, first-class
changeover event. Where HIVE360 is stronger: thirty years of domain
relationships, multi-plant enterprise features, audit-readiness.

Overlap is on the knowledge base (Koorsus on the document side) and
shift handover (a small feature in both). The philosophical difference:
HIVE360 asks "what did we learn?" Myarra asks "what happened on the
floor in the last hour and what did it cost?"

Action: watch item only. Do not mention them in marketing. If AuditHive
ever announces production-line or OEE features, reassess. Until then,
monitoring is enough.

## Remaining queue

Immediate (small, before the testing pass):

- Spine fallback for "record H5" without a job number. The record flow
  currently asks "Which job?" when the message, session, and user all
  lack one. It should fall back to the user's line and the current
  spine event, same as notes.try_note now does. Six lines in
  production.h_record_hour and h_running_job.

- Bare "confirm" phone test. The route is added and tested only in
  isolation. One live exercise: trigger plausibility with an absurd
  number, reply "confirm", verify the record writes.

- Unused audit items from the earlier audit document. Roughly ninety
  remain. The two highest-priority remaining were rate averaging and
  /ask view list, both now closed. The next priority is /floor write
  path correctness (C27): /floor writes no line_events, no source, no
  user_id, and hardcodes shift='1', duration_min=60. Must be corrected
  before Whisper lands in the same POST.

Then the testing pass (every page, every Herbie card, Odoo connector).
Then Whisper install and /api/transcribe. Then Odoo master-data import
and line-mapping setup screen. Then work order notes into
jobs.handover_notes. Then backup/restore. Then installation procedure
document. Then config extraction (DB_PATH, cert paths, LLM_URL out of
source; bot/db.py already uses MYARRA_DB env var).

## Session close

State at close of 2026-11-13 afternoon:
- Web app: running, HTTPS 5002, routes 200.
- Bot: running, polling as @KoorsusTheBot, record flow working.
- Services: four active after case installation and reboot.
- Database: intact, job-hours backfilled, guard in place.
- Commits: six today, all pushed, HEAD at 62fb9c8.
- Working tree: clean after this delta is committed.

The foundation is sound. The record flow works. The rate math is
per-run. /ask refuses ambiguity. The job-hours are truthful.

END OF DELTA.
