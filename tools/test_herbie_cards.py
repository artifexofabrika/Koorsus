#!/usr/bin/env python3
"""Herbie card sweep. Read only: no writes, no service restarts.

For each of the five cards this computes the stats in Python, asks Herbie to
narrate, and checks:
  1. narrate returned source "llm", or "vetoed" when the tracer rejected the
     model's prose and fell back to the template
  2. the narrative is not empty
  3. every number in the narrative traces to the prompt the model was shown —
     data, glossary, the context block with the operator notes, and the rules

The trace uses herbie.untraced_numbers against herbie.build_prompt, which is
the same pair the production veto uses. It used to be a second implementation
here, and it compared against the stats dictionary alone, so a correct card
quoting an operator note ("shift 1 on day 10") or the payload's own partial-hour
marker ("H3 [partial hour, 32 of 60 min]") was reported as inventing numbers.
Two copies of a check drift; one copy cannot.

A veto is reported rather than hidden. The card is correct — the template wrote
it — and the model is not, which is the distinction the sweep exists to show.

Run: /home/jeeves/jeeves-env/bin/python tools/test_herbie_cards.py
"""
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "myarr_v2"))

import herbie

DB = "/mnt/lake/myarra.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row

# Ordering hazard, A50. The code and the view changed together: herbie selects
# unrated_min, and app.py recreates the views at import. Between the commit and
# the restart the database still holds the old view, so this sweep would fail
# with "no such column" and read as a broken card. Say what it is instead.
_view_cols = {r[1] for r in conn.execute(
    "PRAGMA table_info(v_unaccounted_minutes_by_run)")}
if "unrated_min" not in _view_cols:
    print("STALE VIEWS: v_unaccounted_minutes_by_run has no unrated_min column.")
    print("The appliance is still running the views from before A50. app.py")
    print("recreates them at import, so restart myarr and run this sweep again.")
    print("Refusing to report a red card for a stale schema.")
    conn.close()
    sys.exit(2)


def one(sql, default=None):
    try:
        r = conn.execute(sql).fetchone()
        return r[0] if r and r[0] is not None else default
    except sqlite3.Error:
        return default


line_id = one("SELECT id FROM lines ORDER BY id LIMIT 1", 1)
job = one("SELECT job_number FROM jobs ORDER BY id DESC LIMIT 1")
co_job = one("SELECT to_job_number FROM co_events WHERE to_job_number IS NOT NULL "
             "ORDER BY started_at DESC LIMIT 1")
# Take the line and the date from the same row, so line_day is asked about a
# pair that actually has data rather than a date belonging to another line.
latest = conn.execute("SELECT line_id, date(recorded_at) AS d FROM hourly_runs "
                      "ORDER BY recorded_at DESC LIMIT 1").fetchone()
day_line = latest["line_id"] if latest else line_id
day = latest["d"] if latest else None

cards = []

if job:
    cards.append(("job",
                  "Summarize job %s." % job,
                  lambda: (herbie.get_job_summary(conn, job), None)))

cards.append(("jobs_over",
              "Which jobs had more than 20 minutes of downtime in the last 30 days?",
              lambda: (herbie.get_jobs_with_downtime_over(conn, 20, 30), None)))

cards.append(("unaccounted",
              "How much unaccounted time on line %d in the last 30 days?" % line_id,
              lambda: (herbie.get_unaccounted_minutes(conn, line_id, 30), None)))

if co_job:
    cards.append(("changeover",
                  "How did the changeover to job %s go?" % co_job,
                  lambda: (herbie.get_changeover_summary(conn, co_job), None)))

if day:
    cards.append(("line_day",
                  "What happened on line %d on %s?" % (day_line, day),
                  lambda: (herbie.get_line_summary(conn, day_line, day),
                           herbie.get_floor_context(conn, day_line, day))))

failed = 0
vetoed = 0
for intent, question, build in cards:
    stats, context = build()
    if isinstance(stats, dict) and "error" in stats:
        print("FAIL  %-12s stats error: %s" % (intent, stats["error"]))
        failed += 1
        continue

    result = herbie.narrate(intent, stats, context, question)
    source = result.get("source")
    narrative = (result.get("narrative") or "").strip()

    if source == "vetoed":
        # The card is correct — the template wrote it — and the model is not.
        # Reported separately so the two are never confused.
        vetoed += 1
        print("VETO  %-12s numbers=%s" % (intent, result.get("vetoed_numbers")))
        print("        rejected: " + ((result.get("rejected") or "")
                                      .replace(chr(10), " "))[:300])
        print("        template: " + narrative.replace(chr(10), " ")[:300])
        continue

    # A job with no runs legitimately has nothing to narrate. Every other
    # card must come from the model.
    empty_job = (intent == "job"
                 and stats.get("actual_units") == 0
                 and stats.get("run_minutes") == 0)
    want_source = "no-data" if empty_job else "llm"
    ok = source == want_source and bool(narrative)
    if "None" in narrative:
        print("        LITERAL None IN NARRATIVE")
        ok = False
    if not ok:
        failed += 1

    print("%s  %-12s source=%s words=%d"
          % ("PASS " if ok else "FAIL ", intent, source, len(narrative.split())))

    if not ok:
        print("        " + narrative[:200])
        continue

    prompt = herbie.build_prompt(intent, stats, context, question)
    untraced = sorted(herbie.untraced_numbers(narrative, prompt))
    if untraced:
        print("        UNTRACED NUMBERS: %s" % untraced)
        print("        " + narrative.replace(chr(10), " "))

conn.close()
print("")
print("%d cards, %d failed, %d vetoed" % (len(cards), failed, vetoed))
sys.exit(1 if (failed or vetoed) else 0)
