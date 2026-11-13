# SESSION DELTA 2026-11-13 - SPINE AUTHORITY

**Supplemented by SESSION-DELTA-2026-11-13-AFTERNOON.md.** Read both for the full day.
This delta supersedes SESSION-DELTA-2026-11-13-DEPLOYMENT-READY.md.
Read alongside PHILOSOPHY.md, HERBIE-ARCHITECTURE.md, and the audit
document delivered to the prior instance on the morning of 2026-11-13.

The audit is the reference for all open items. This delta records what
the audit led to, and the decisions taken, so the next instance does
not re-litigate them.

## What the product is (unchanged)

Myarra is the structured truth: hourly runs, OEE, operator performance,
changeover, downtime, PDCA. Koorsus is the unstructured truth: document
estate, cited answers, refusal when the answer is absent. Herbie is the
bridge. On-premise, no subscription, GPL v3. Nano for Herbie Light and
the PWA; NX for Herbie Counselor.

## What was done on 2026-11-13

Four commits. All pushed to origin/main.

| Commit  | Content |
|---------|---------|
| 6f96f2a | tools/schema.sql extracted from live DB; db.py rewritten to apply it |
| 5702ae8 | Restored fuzzy resolve; F1 awaiting_hour; confirm strip; lunch/cip handlers |
| 2faf1db | Removed unused ingest_csv import from app.py |
| 545d90b | Spine is authority: session gate removed; stale session reconcile; status-first; line in messages; notes spine fallback |

### tools/schema.sql and db.py

The live database was extracted to tools/schema.sql: 25 tables, 7
indexes. Views stay in views.py and are recreated at app load, so a view
change does not need a schema migration. Every statement in schema.sql
is IF NOT EXISTS, so the file is idempotent.

db.py now applies the schema via executescript. It refuses to run against
a pre-2026-11-13 partial schema because IF NOT EXISTS cannot add columns,
and a silent partial migration is worse than a loud refusal. DB_PATH is
read from the MYARRA_DB environment variable, matching bot/db.py, which
had used that pattern since 2026-11-07. The old init_db, init_users_table,
and ingest_csv are gone.

Verified: fresh database at /tmp/test_schema.db produced 25 tables and 7
indexes; a second run added nothing. The CSV round-trip test and the
customer install now have a path. Nothing ships to a customer before
this file is in place.

### bot/resolve.py restored

The 2026-11-07 modular extraction dropped difflib, FUZZY_THRESHOLD,
PLAUSIBILITY_LOW, PLAUSIBILITY_HIGH, and _active_jobs from resolve.py.
Any non-exact job number in start, end, pause, or resume raised NameError.
The file was imported by jobs.py, so the crash was on the live path.

Restored from bot_v2.py at commit ec65562^ (the last working version
before the modular rewrite). Verified: exact, fuzzy, and none paths all
return cleanly; fuzzy reports the interpretation in the reply.

### bot/dispatch.py, production.py, jobs.py, notes.py: spine as authority

The 2026-11-07 modular rewrite copied the session gate from h_start_job
into h_running_job. The gate existed in h_start_job in bot_v2.py and was
correct there: starting a new job while another is active is a legitimate
refusal. In h_running_job it was wrong: logging an hour against a job is
not the same as starting one, and gating it on per-operator conversational
state violates PHILOSOPHY commitment 2 (capture never blocks).

Concrete failure, 2026-11-13: operator sent 'running job WO-2610-001'.
The session held WO-2610-002, a completed job with no open line event.
The gate fired and replied 'You have WO-2610-002 active. End or pause it
first.' The plant was running seven different WO-2611 jobs. The bot
stated false information about the floor. That is worse than blocking:
it told the operator something untrue about his own line.

Agreed model (2026-11-13):
- Authority for what is running: line_events. Always.
- Authority for whether a job can receive production: jobs.status.
- bot_sessions.active_job_id is a convenience pointer for multi-step
  prompts. It is never a gate.

Fix applied:
- production.h_running_job: session gate removed. Status check first
  (completed -> say so; paused -> say so; scheduled -> auto-start on
  capture; running -> proceed). Line check stays, with line in message.
- jobs.h_start_job: status check first, then reconcile, then the session
  gate (which stays here), then the line gate. Line name added to the
  refusal.
- bot/db.reconcile_session: called at the top of dispatch on every
  message. If active_job_id or active_changeover_id points at a job with
  no open line event, clear silently. No message to the operator.
- notes.try_note: when session has no active job, fall back to the line's
  current spine job. Note attaches without asking the operator to re-state.

Verified against a throwaway session:
- T1 'running job WO-2610-001' -> 'WO-2610-001 is completed. It cannot
  receive new production.'
- T2 'running job WO-2611-197' -> 'Which hour? Say just the number.'
- T3 stale session cleared to None by reconcile_session.
- T4 Line 1 spine intact: production on job 197.

### Lunch and CIP

Handlers restored per the owner's design, 2026-11-13: lunch and cip are
the definers. A bare 'lunch' or 'cip' prompts 'Starting or ending lunch?'
Direction follows. 'end lunch' resumes prior state (production, open
changeover, or idle). 'and lunch' and 'en lunch' normalize to 'end lunch'.

### app.py

The unused ingest_csv import was removed when db.py dropped that function.
The app failed to start until the import was cleaned up. This was my
error; the import should have been removed in the same commit as db.py.
Included in commit 2faf1db.

## The audit

115 findings, catalogued, handed to the prior instance on 2026-11-13.
The eight highest-priority items (schema, db.py, resolver, F1, confirm,
session gate, rate averaging, /ask view list) are logged there with
severity, file, and recommended fix. Six of the eight are now closed by
today's commits. The remaining two:

- Rate averaging (H1, S1): herbie.get_line_summary uses AVG(lsr.ideal_rate)
  across all SKUs on the line; shift.compute_reconciliation uses the first
  run's rate for the whole shift. Both wrong for any line that runs more
  than one SKU. Fix: compute per run, sum.
- /ask view list (K1, K2): ask.AVAILABLE_VIEWS omits v_unaccounted_minutes_by_run
  (canonical) and includes v_oee_summary (the drifted twin of recon.py).
  Fix: swap in the canonical view; drop the drifted one.

Do not attempt a general cleanup pass before these two are fixed; the
audit's severity sort is the priority order.

## Decisions taken 2026-11-13, do not re-litigate

Q1. Active job is per-line, not per-operator. The spine is authority.

Q2. The job's line wins over the operator's assignment. The operator is
informed in the reply, never refused. The existing hourly_runs.user_id and
hourly_runs.line_id already contain the evidence for later reconstruction;
no new column is needed.

Q3. A completed job never appears as active. The status check is the first
check in every handler that takes a job number. This applies to both
production capture and job start.

Q4. Multiple operators may log against one line. This is normal (shift
overlap, covering). The spine decides which job is current; sessions are
reconciled on each message.

Q5. The list of job numbers and prompts exercised in the 2026-11-12 tests
is not available and is not required. The session gate was present in the
code before 2026-11-13 and was reachable but not triggered in the demo
path. It was dormant, not introduced by any test. Closed. Future
instances: do not ask for this list again.

Auto-start. A scheduled job is auto-started when production is first logged
against it. Do not add a confirmation prompt. Capture never blocks.

Token policy. The demo Telegram token is not rotated and is treated as
non-sensitive. It may appear in journals, logs, pastes, and git history.
Reason: demo token, negligible value, non-public bot. Future instances:
do not raise this again.

Idle and the operator measure (O1). Distinguish planned no-demand idle
from unplanned idle. Planned idle does not count against the operator.
Unplanned idle does. This is a PHILOSOPHY.md amendment and is deferred
until the owner writes the amendment in his own hand. Until then,
recon.py's current behaviour (all idle charged to operator) stands and
should not be modified.

Fuzzy job resolution (O2). Repaired, not removed. Voice-to-text loses
digits; the plausibility safeguard exists for the same reason. Fuzzy
matching is the matching counterpart. Restored from git history rather
than rewritten.

## Parking lot, new entries 2026-11-13

### Plant manager relog across line leads

Seven lines, seven line leads, one Telegram ID each. A plant manager needs
to reach back over any line lead's work and correct it. Proposed form:
'relog work order 2611-005, hour 3, labor down 45 minutes'. Must record
who made the correction, the original value, the new value, and the
reason. The existing relog audit trail (hourly_runs.superseded,
hourly_runs.override_reason, audit_log) captures the shape; this extends
it to cross-lead permissions. Deferred until the line-lead path is stable.

### HANDOFF.md is stale (2026-11-03)

The handoff predates: the modular bot package, the PWA, /herbie, /ask,
the Odoo connector, the seven-line demo factory, the schema extraction,
and PHILOSOPHY.md itself. It actively misleads on the bot (it describes
bot_v2.py which no longer exists), the service (Waitress vs Gunicorn),
and the demo data (five lines vs seven). Do not read it as current until
it is rewritten whole. The audit document has the section-by-section
drift. A fresh instance should read: PHILOSOPHY.md, this delta, the
audit, then HERBIE-ARCHITECTURE.md.

### Audit items not closed today

Roughly ninety findings remain in the audit, catalogued by severity. The
two highest-priority remaining are rate averaging (H1, S1) and the /ask
view list (K1, K2). Beyond those, /floor write path correctness (C27)
must precede Whisper. The CSV round-trip test and the testing pass come
after the two rate fixes. Whisper, the Odoo master-data import, work
order notes, backup/restore, the installation procedure, and config
extraction remain on the original queue from the 2026-11-13 morning
delta.

## Session close

State at close of 2026-11-13:
- Web app: running, HTTPS on port 5002, journal clean.
- Bot: running, polling as @KoorsusTheBot, new code loaded.
- Database: untouched by today's work except the schema extraction.
- Commits: four, all pushed to origin/main, HEAD at 545d90b.
- Working tree: clean after this delta is committed.

What the next instance inherits: a schema it can reproduce, a db.py that
refuses to silently corrupt, a resolver that no longer crashes, a bot
whose session no longer lies, and a written record of the model that
produced all four. The queue is still long. The foundation is sound.

END OF DELTA.
