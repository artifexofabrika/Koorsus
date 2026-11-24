# SESSION DELTA 2026-11-23 — THE FLOOR LOOP CLOSED

Follows SESSION-DELTA-2026-11-20.md. HEAD at close: 515eaa7, which is fd670a5
plus this document's own commit and one state commit; the line read fd670a5 as
written, and a delta cannot name the commit that contains it. Corrected
2026-11-24. Everything below was verified on the reference Jetson unless it says
otherwise.

## What was true when the session began

Four units live, 26 routes returning 200, 406 jobs of thirty-day history, 1,659
hourly runs and thirteen line events, none of them off-time. The tablet could
log an hour and do nothing else: no start, no end, no switches. A45, A46 and
A47 were cited by name in the owner's notes and in bot/jobs.py and had never
been written down, which is why the first act of the session was to read the
code rather than the summary.

## Shipped

**The floor loop, which was the whole of C27.** Start and end on a hidden
`action` field; the record path untouched when it is absent. Both actions write
the job status and the line event in one transaction through `start_job` and
`end_job`. Lunch, maintenance and CIP as three switches in one form, direction
decided by comparing the pressed state to the line's open event, job id carried
on the event. A line in an off-time state is no longer rendered as idle, which
it was, so it used to offer a Start panel and then refuse.

**One variance gate.** `variance_refusal` with `scheduled_window` and
`off_time_minutes` beside it, called by the Telegram close and by the floor. A
600-minute window at target 1000 minus 30 minutes of lunch allows 950.

**A01's web half.** Five sites in app.py stopped substituting 600.0. A missing
rate renders as an em dash through two Jinja filters, a total with no rate is a
dash rather than a confident zero, and FTQ still reports because it needs no
rate. `tools/test_rates.py` proves it against a database with one line
deliberately missing its rate.

**A49.** The service worker served /floor cache-first, so a device served itself
the page it first saw, and because the floor forms carry job_number and period in
hidden fields a frozen page writes an hour against a job that ended days ago.
/floor is network-first now and the cache is at v2.

**Ninety days of history.** 579 jobs, 6,323 hourly runs, 3,287 line events, 563
changeovers with step actuals, 503 downtime records, five PDCA experiments, seven
fishbone causes, three maintenance repairs. Two SKU-line pairs carry no rate on
purpose, one of them with a live running job.

**Herbie.** line_day and job had no rules of their own and now do. The glossary
is filtered to the fields each payload actually carries.

## Decisions taken today, do not re-litigate

**The dash contract.** A rate-derived figure with no rate behind it is an em
dash, never a number and never a zero. Zero reads as "produced nothing", which is
a different and worse claim than "no rate was configured". FTQ and actual units
keep reporting, because neither needs a rate.

**Two measures, in units.** Capacity compares parts produced against parts due
and scrap does not enter it. Quality compares good parts against parts produced
and the target does not enter it. 1000 of 1000 with 25 scrap has lost no
capacity. 900 of 1000 with no scrap reads 100% quality and has lost 100 parts.
The capacity comparison sums `units_filled`, which includes scrap; an editor who
"corrects" it to `units_filled - scrap_units` turns a scrap-heavy hour at full
rate into a capacity failure.

**Nothing stops the line.** No screen that records production may refuse, wait,
or ask a question whose answer it does not have. The run rate proves the rule: it
does not exist until the first run measures it, so the moment a plant tries
something new is the moment the number is guaranteed absent.

**No rebase, no force-push, no amending a pushed commit.** History only grows.
A wrong commit is fixed forward.

**Restart before testing the running service.** `test_pages` and
`test_herbie_cards` make requests to gunicorn on 5002 and only tell the truth
after `systemctl restart myarr`. `test_rates`, `test_floor_start` and
`test_csv_roundtrip` build their own process from disk. A green `test_rates`
beside a red `test_pages` means new templates and an old process.

**Commit immediately after every verified install.** The base-hash check presumes
HEAD is what is deployed; a file copied but not committed breaks that and the
guard cannot then tell "already installed" from "drifted". Both mistakes were
made today.

## Four lessons about prompting a 3B model

1. **Never quote the sentence you are forbidding.** The first job-card rules
   quoted "Losses unexplained were 17.1 minutes, resulting in 17 units lost" as
   an example of what not to write. The model reproduced it verbatim in three
   consecutive runs.
2. **Never list field names that do not exist.** Naming `capacity_gap`,
   `losses_accounted` and `losses_unexplained` to a card that has none of them
   seeds the vocabulary it was meant to forbid.
3. **Put the fact in the payload, not in a rule.** An in-progress hour is now
   emitted as `H3 [partial hour, 32 of 60 min]`. A model told a fact does not
   have to infer it, and inference is where it went wrong.
4. **Filter the glossary to the payload.** A card cannot misuse a field it was
   never told about. This is the only change that removes a capability rather
   than asking for restraint, and therefore the only one likely to survive a
   model swap.

## The data, and where it came from

`tools/gen_myarra_90d.py` was written by another instance against a copy of the
schema, and is committed on the strength of a proof run: nineteen of its own
checks plus five independent ones, on a scratch database, before it touched the
appliance. It takes `--db`, `--now` and `--init-schema`, deletes only rows marked
`source=gen90`, and derives targets from the runs — `target = actual · window /
((1+v)(window − off))` — which is `variance_refusal` inverted, so lunch does not
trip the gate.

`tools/seed_improvement_layer.py` adds the improvement layer the generator does
not write: five experiments, seven fishbone causes, three maintenance events on
jobs inside the last twenty-one days. It writes no maintenance line events,
deliberately, because the generated timeline is continuous with one open event
per line and splicing a repair into a past production window would break the
invariant everything else rests on.

## What is unproven

**The glass.** No human has tapped the floor. Every claim about start, end and
the switches rests on Flask's test client. A gloved thumb at arm's length is the
only test that has never run.

**The bot write paths.** The audit calls them the largest unexamined surface and
says expect more. Ninety days of data now exists to walk them against, and nobody
has.

**A02 and A03.** Intermittent by nature. A green card run is not evidence.

## Order of work to pilot-ready

1. `bot/db.py`'s `ideal_rate()` still returns 600.0 for the Telegram path, into
   four call sites in `production.py` and one in `shift.py`, each of which does
   arithmetic on the result. Own test file, own commit.
2. The tracer veto. CORRECTED 2026-11-24: the sentence that it "already detects
   a narrative containing a number the payload does not carry, and only warns"
   was false. Nothing in the product traced anything. The only tracer in the
   repository was a print inside tools/test_herbie_cards.py, and it compared the
   narrative against the stats dictionary rather than the prompt, so it also
   flagged correct cards that quoted an operator note. What was built on
   2026-11-24: the trace runs against the whole prompt including the context
   block, an untraced figure replaces the narrative with the template, and the
   card sweep calls the same functions instead of keeping its own copy. This is
   the change that decides whether a model can be put in front of a plant
   manager at all.
3. A14 and A16: the backup passphrase exists only on the machine and in the
   owner's Downloads, and the appliance archive has no offsite copy.
4. A device, a plant, a lead, five minutes.

Then for a product that can ship without the owner present: A18 master-data
export, A04's two schema strategies, A19 and A20 in the installer, a reset of the
Koorsus collection so no unit ships with our test documents, and the printed
installation procedure.

## Parking lot

A48's five double-commit sites on the bot conversational path. A47 in
`db.transition_line`'s other callers. `h_start_job` committing running with no
event until the minutes prompt is answered. A46 unaccounted for and not reused. A
switch left on overnight carrying an open lunch event into the next shift. The
paused refusal saying "Say resume" on glass. The picker empty on a plant that
never fed `scheduled_start`. `job_variance_tolerance` absent from
`demo-data/settings.csv`. Agentic Herbie, parked behind an Orin NX or an AGX,
with its two rules: read authority separate from act authority, and an allowlist
of named verbs rather than a shell.

## Corrections to earlier documents

A01 is five sites in app.py, not four. The "115-finding audit" in STATE.md was a
different audit that was never saved; AUDIT.md is the record, 48 findings with 11
fixed. `views.py` creates twelve views and its docstring says nine. The
`generate_demo_history.py` comment claiming jobs run one full shift stops being
true the moment there are more than six jobs per line.

## Two housekeeping facts

Another instance was live on the owner's machine during the session, working the
Jeeves product in `Desktop\Jeeves`. It left a copy of that project inside this
repository under a directory literally named `:USERPROFILE\Desktop\Jeeves`,
created by an scp whose `$env:` prefix did not expand. Removed, never committed.
It also installed Python 3.13 user-scope on the laptop to test with, which is
local to that machine.
