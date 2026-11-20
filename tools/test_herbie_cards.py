#!/usr/bin/env python3
"""Herbie card sweep. Read only: no writes, no service restarts.

For each of the five cards this computes the stats in Python, asks Herbie to
narrate, and checks:
  1. narrate returned source == "llm", not the template fallback
  2. the narrative is not empty
  3. every number in the narrative traces to the stats dictionary

Check 3 reports rather than fails. A 3B model will occasionally write a
number that is not in the data, and that is exactly what the HARD NUMBERS
rule exists to prevent. Seeing it listed is the value.

Run: /home/jeeves/jeeves-env/bin/python tools/test_herbie_cards.py
"""
import os
import re
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "myarr_v2"))

import herbie

DB = "/mnt/lake/myarra.db"

conn = sqlite3.connect(DB)
conn.row_factory = sqlite3.Row


def one(sql, default=None):
    try:
        r = conn.execute(sql).fetchone()
        return r[0] if r and r[0] is not None else default
    except sqlite3.Error:
        return default


def numbers_in_text(text):
    # "WO-2611-201" reads as two negative numbers. Strip job numbers before
    # looking for figures the model invented.
    text = re.sub(r"WO-?\d+-\d+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)
    # "P2P" contains a 2 that is not a figure.
    text = text.replace("P2P", " ")
    out = set()
    for m in re.finditer(r"-?\d[\d,]*(?:\.\d+)?", text):
        try:
            out.add(float(m.group(0).replace(",", "")))
        except ValueError:
            pass
    return out


def numbers_in_obj(obj):
    out = set()
    if isinstance(obj, dict):
        for v in obj.values():
            out |= numbers_in_obj(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            out |= numbers_in_obj(v)
    elif isinstance(obj, bool):
        pass
    elif isinstance(obj, str):
        # Pre-computed fields such as "summary" carry numbers as text. Those
        # are numbers the model is allowed to quote.
        out |= numbers_in_text(obj)
    elif isinstance(obj, (int, float)):
        out.add(float(obj))
    return out


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
for intent, question, build in cards:
    stats, context = build()
    if isinstance(stats, dict) and "error" in stats:
        print("FAIL  %-12s stats error: %s" % (intent, stats["error"]))
        failed += 1
        continue

    result = herbie.narrate(intent, stats, context, question)
    source = result.get("source")
    narrative = (result.get("narrative") or "").strip()

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

    untraced = sorted(numbers_in_text(narrative) - numbers_in_obj(stats))
    if untraced:
        print("        UNTRACED NUMBERS: %s" % untraced)
        print("        " + narrative.replace(chr(10), " "))

conn.close()
print("")
print("%d cards, %d failed" % (len(cards), failed))
sys.exit(1 if failed else 0)
