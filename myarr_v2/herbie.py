"""herbie.py - The AI Counselor.

Named after Herbie in The Goal: the constraint that limits the system,
and the thing you must find before you can improve anything.

The math is done in Python. The LLM only narrates. Every number the
narrative references must be present in the HARD NUMBERS block. The LLM
is forbidden from adding, subtracting, or deriving new numbers.

Diagnostic principle: a standard that has been run to for months is
not wrong because one shift underperformed. When the capacity gap is
large and the accounted losses are small, the correct diagnosis is
"the data is incomplete, revisit with the line lead," not "the
standard may need reevaluation."
"""
import json
import re
import requests
import sqlite3

from db import DB_PATH
from myarra_settings import LLM_URL
LLM_TIMEOUT = 60


INTENT_NOTES = {
    "changeover": """CHANGEOVER-SPECIFIC RULES:
- The 'summary' field is the authoritative characterization. Paraphrase it; do not contradict it.
- variance_min = (actual - standard). A NEGATIVE variance means FASTER than standard (GOOD). A POSITIVE variance means SLOWER (BAD). The summary field already states the direction correctly.
- The ONLY fields that exist for changeover questions are: event_id, line_id, procedure_name, from_job, to_job, started_at, actual_min, standard_min, variance_min, variance_pct, steps, summary.
- Do NOT mention FTQ, P2P, capacity_gap, losses_unexplained, scrap_units, downtime, or lost capacity. Those fields do not exist for changeovers. If you mention them, you are inventing data.
- actual_min is the changeover duration, NOT lost capacity. Do not confuse the two.
- The steps list is supporting detail. Mention the two or three largest deviations, but the summary field is the primary source.
""",
    "jobs_over": """TOP-DOWNTIME-JOBS SPECIFIC RULES:
- The 'summary' field is the authoritative answer. Paraphrase it; do not contradict or re-rank it.
- The summary already names the count and the top three jobs in the correct order. Quote them in that order.
- Do not list any job that is not in the summary.
- The jobs array is supporting data. Do not enumerate it.
""",
    "unaccounted": """UNACCOUNTED-MINUTES SPECIFIC RULES:
- unaccounted_min is the minutes of production loss with no logged reason.
- pct_unaccounted is unaccounted as a percentage of total lost time (recorded + unaccounted).
- The by_shift breakdown shows the same for each shift separately.
- unrated_min is time on hours with no rate for that SKU, so it could not be
  scored at all. When it is above zero, say that the unaccounted figure covers
  only the hours that could be scored, and that the rest are not in it.
- If pct_unaccounted is above 25, state that it is a significant gap.
""",
    "line_day": """DAY-SPECIFIC RULES:
- OPERATOR NOTES are one row per hour. Never generalise one hour's note to
  another hour or to the whole day. A note that states a duration describes
  that hour and nothing else. If H3 says 32 minutes and run_minutes is 152,
  the line did not run 32 minutes an hour, and saying so is a false statement
  about a day you can see the whole of.
- run_minutes is the total recorded across the day's hours. It is shorter than
  the shift when the day is still running, and that is normal rather than a
  loss. Do not call it lost time.
- An hour marked partial is in progress or was cut short. Say so if you mention
  it, and do not treat it as representative of the others.
- standard_rate of 0 means no rate is loaded for this SKU on this line. When it
  is 0, capacity_gap still compares production with the target and may be
  quoted as a gap. losses_accounted and losses_unexplained are null rather than
  zero, because recorded downtime cannot be valued in parts without a rate. Say
  the loss figures were not computed, and do not reconcile the gap or describe
  the loss data as complete.
- p2p is actual_units over the target of the jobs scheduled that day. When no
  job was scheduled there is nothing to compare, which is not the same as the
  line producing nothing.
""",
    "job": """JOB-SPECIFIC RULES:
Write about this job using these fields and nothing else: job_number, line_id,
line_name, sku_description, status, target_units, actual_units, scrap_units,
run_minutes, recorded_downtime_min, unaccounted_min, ftq, p2p, and the hourly
rows. If a quantity is not in that list it does not exist for this answer, and
there is no need to say so.

Every field keeps its own unit. target_units, actual_units and scrap_units are
counts of parts: write them as parts. run_minutes, recorded_downtime_min and
unaccounted_min are durations: write them as minutes and leave them as minutes.
A duration stays a duration through the whole sentence.

ftq is the percentage of produced parts that were good. p2p is produced parts
as a percentage of the target. Both are percentages of parts, neither is a
speed, and neither should be called a rate.

A job with no recorded downtime beside a non-zero unaccounted_min is the
ordinary case this product exists to catch: time was lost and no reason was
written down. Say that in one sentence, then name the largest hour it happened
in from the hourly rows, using that hour's own unaccounted_min.

If the hourly rows carry operator notes, quote one with its hour. Mention that
notes are absent only when every hour's note is empty.

unrated_min is time on hours with no rate for that SKU, which could not be
scored. When it is above zero, say that unaccounted_min covers only the hours
that could be scored.

Close with what the line lead should go and find out, if anything.
""",
}


FIELD_GLOSSARY = [
    ("actual_units", "parts produced, scrap included"),
    ("gross_production", "parts produced, scrap included: the same count as "
                         "actual_units, because scrap is a subset of it and is "
                         "never added on top"),
    ("target_units", "the target this figure is measured against: the job's own "
                     "target, or the sum of the job targets scheduled that day"),
    ("scrap_units", "produced parts that failed first time; already counted "
                    "inside actual_units"),
    ("run_minutes", "total minutes recorded. A day or job still running is short, "
                    "and an individual hour in it may be partial"),
    ("recorded_downtime_min", "minutes an operator logged as downtime"),
    ("downtime_min", "minutes an operator logged as downtime"),
    ("downtime_by_station", "logged downtime minutes, per station"),
    ("unaccounted_min", "minutes of production loss with no logged reason"),
    ("pct_unaccounted", "unaccounted as a percentage of total lost time"),
    ("by_shift", "the same figures split by shift"),
    ("standard_rate", "the line's rate for the SKU, weighted by minutes. Zero "
                      "means no rate is loaded for that SKU on that line, and "
                      "every rate-derived figure below is meaningless rather "
                      "than zero"),
    ("rate_mixed", "true when more than one rate applied"),
    ("theoretical_capacity", "parts that could have been made in the recorded "
                             "minutes at the standard rate"),
    ("capacity_gap", "variance against target in parts; negative is under target"),
    ("lost_capacity", "parts lost to recorded downtime at the standard rate"),
    ("losses_accounted", "scrap parts plus lost capacity parts. Null means the "
                         "figure was not computed, because no rate is loaded"),
    ("losses_unexplained", "capacity_gap minus losses_accounted. Null means the "
                           "figure was not computed, because no rate is loaded"),
    ("rate_loaded", "true when every recorded hour on this day has a rate for "
                    "its SKU on this line. False means the rate-derived loss "
                    "figures below are null rather than zero"),
    ("unrated_min", "minutes recorded on hours with no rate for that SKU on this "
                    "line. Those minutes are not scored and are not part of any "
                    "rate-derived total"),
    ("unrated_downtime_min", "recorded downtime minutes on hours with no rate. "
                             "The time is real and logged; only its cost in parts "
                             "is unknown"),
    ("reconciliation", "a sentence stating which figures could not be computed "
                       "and why. Quote or paraphrase it; do not contradict it"),
    ("ftq", "First Time Quality: good parts as a percentage of parts produced"),
    ("p2p", "Produce to Plan: parts produced as a percentage of target"),
    ("actual_min", "how long something took, in minutes"),
    ("standard_min", "how long it is supposed to take, in minutes"),
    ("variance_min", "actual minus standard, in minutes"),
    ("variance_pct", "variance as a percentage of standard"),
    ("summary", "the authoritative characterisation of this answer; paraphrase "
                "it, never contradict it"),
]


def _glossary_for(payload):
    """Only definitions for fields this payload actually carries.

    The glossary used to be a fixed block naming capacity_gap, losses_accounted
    and losses_unexplained for every intent. Only the line card carries those,
    so the job and jobs_over cards were handed three definitions they had no
    legitimate use for and reached for them, producing figures nobody computed
    and, on the line card, two adjacent sentences that contradicted each other.
    A card cannot misuse a field it was never told about (A03).
    """
    keys = payload.keys() if isinstance(payload, dict) else []
    lines = ["- %s: %s" % (k, d) for (k, d) in FIELD_GLOSSARY if k in keys]
    return "\n".join(lines) if lines else "- no numeric fields in this answer"


GENERIC_NARRATIVE_PROMPT = """You are Herbie, a Lean manufacturing counselor.

Every number below was calculated in Python. You may quote these numbers
exactly as written. You may NOT add, subtract, multiply, divide, or otherwise
derive new numbers. If you need a total, it is already computed and listed.

DIAGNOSTIC PRINCIPLE:
- A standard that has been run to for months is not wrong because one shift
  underperformed. Do not tell the manager the standard may need reevaluation.
- When losses_unexplained is larger than losses_accounted, the correct
  diagnosis is that the data is incomplete. Tell the manager to revisit the
  job with the line lead and find out what happened that was not captured.
- Quote a relevant operator note verbatim and attribute it to its hour. A note
  belongs to one hour; it is never evidence about the others.

RULES:
- Be direct. No fluff.
- Never blame the operator.
- Under 180 words.
- FTQ is First Time Quality. P2P is Produce to Plan (Actual / Target).
- If you cannot answer something from the data, say so.

DATA (Python-computed, quote numbers exactly):
{data}

FIELD GLOSSARY. These are every field in this answer, with the only meanings
they have. A quantity that is not defined here is not part of this data, and
does not belong in the answer.

{glossary}

CONTEXT:
{context}

INTENT-SPECIFIC RULES:
{intent_notes}

Manager question: {question}
"""


def get_line_summary(conn, line_id, date):
    """The math engine. All arithmetic happens here, in Python."""
    row = conn.execute("""
        SELECT
            COALESCE(SUM(r.units_filled), 0) AS actual_units,
            COALESCE(SUM(r.scrap_units), 0)  AS scrap_units,
            COALESCE(SUM(r.duration_min), 0) AS run_minutes
        FROM hourly_runs r
        WHERE r.line_id = ?
          AND date(r.recorded_at) = ?
          AND (r.superseded IS NULL OR r.superseded = 0)
    """, (line_id, date)).fetchone()

    actual_units = row["actual_units"] if row else 0
    scrap_units = row["scrap_units"] if row else 0
    run_minutes = row["run_minutes"] if row else 0

    dt = conn.execute("""
        SELECT COALESCE(SUM(d.minutes), 0) AS downtime_min
        FROM downtime_events d
        JOIN hourly_runs r ON r.id = d.run_id
        WHERE r.line_id = ?
          AND date(r.recorded_at) = ?
    """, (line_id, date)).fetchone()
    downtime_min = dt["downtime_min"] if dt else 0

    station_rows = conn.execute("""
        SELECT d.station, COALESCE(SUM(d.minutes), 0) AS minutes
        FROM downtime_events d
        JOIN hourly_runs r ON r.id = d.run_id
        WHERE r.line_id = ?
          AND date(r.recorded_at) = ?
        GROUP BY d.station
        ORDER BY minutes DESC
    """, (line_id, date)).fetchall()
    downtime_by_station = {s["station"]: round(s["minutes"], 1) for s in station_rows}

    # Agreed 2026-11-13: the rate is a property of (line, sku), never an average.
    # Compute lost capacity per downtime event at the run's own SKU rate.
    # Agreed 2026-11-24 (A50): the rate may not exist, and a missing rate is not
    # a rate of zero. Downtime on a rated hour is valued in parts; downtime on
    # an unrated hour is counted in minutes and left unvalued, and the card says
    # which is which.
    lost_row = conn.execute("""
        SELECT
            COALESCE(SUM(CASE WHEN COALESCE(lsr.ideal_rate, 0) > 0
                              THEN d.minutes * lsr.ideal_rate / 60.0
                              ELSE 0 END), 0) AS rated_lost_capacity,
            COALESCE(SUM(CASE WHEN COALESCE(lsr.ideal_rate, 0) > 0
                              THEN 0 ELSE d.minutes END), 0) AS unrated_downtime_min
        FROM downtime_events d
        JOIN hourly_runs r ON r.id = d.run_id
        LEFT JOIN jobs j ON j.id = r.job_id
        LEFT JOIN line_sku_rates lsr
               ON lsr.line_id = r.line_id
              AND lsr.sku_id = COALESCE(r.sku_id, j.sku_id)
        WHERE r.line_id = ?
          AND date(r.recorded_at) = ?
    """, (line_id, date)).fetchone()
    rated_lost_capacity = (lost_row["rated_lost_capacity"] if lost_row else 0) or 0
    unrated_downtime_min = (lost_row["unrated_downtime_min"] if lost_row else 0) or 0

    # The hours that carry no rate at all, and which SKUs they belong to, so the
    # card can name the SKU and the line (FLOOR-MODEL: say plainly that no rate
    # is loaded, and name both).
    unrated_row = conn.execute("""
        SELECT
            COALESCE(SUM(r.duration_min), 0) AS unrated_min,
            GROUP_CONCAT(DISTINCT COALESCE(s.part_number,
                         'SKU ' || COALESCE(r.sku_id, j.sku_id))) AS unrated_skus
        FROM hourly_runs r
        LEFT JOIN jobs j ON j.id = r.job_id
        LEFT JOIN skus s ON s.id = COALESCE(r.sku_id, j.sku_id)
        LEFT JOIN line_sku_rates lsr
               ON lsr.line_id = r.line_id
              AND lsr.sku_id = COALESCE(r.sku_id, j.sku_id)
        WHERE r.line_id = ?
          AND date(r.recorded_at) = ?
          AND (r.superseded IS NULL OR r.superseded = 0)
          AND COALESCE(lsr.ideal_rate, 0) <= 0
    """, (line_id, date)).fetchone()
    unrated_min = int((unrated_row["unrated_min"] if unrated_row else 0) or 0)
    unrated_skus = (unrated_row["unrated_skus"] if unrated_row else None) or ""

    # Weighted rate is for narrative phrasing only. rate_mixed flags >1 rate.
    rate_row = conn.execute("""
        SELECT
            COALESCE(SUM(r.duration_min * lsr.ideal_rate), 0) AS weighted_rate_sum,
            COALESCE(SUM(CASE WHEN lsr.ideal_rate IS NOT NULL THEN r.duration_min ELSE 0 END), 0) AS rated_min,
            COUNT(DISTINCT lsr.ideal_rate) AS distinct_rates
        FROM hourly_runs r
        LEFT JOIN jobs j ON j.id = r.job_id
        LEFT JOIN line_sku_rates lsr
               ON lsr.line_id = r.line_id
              AND lsr.sku_id = COALESCE(r.sku_id, j.sku_id)
        WHERE r.line_id = ?
          AND date(r.recorded_at) = ?
          AND (r.superseded IS NULL OR r.superseded = 0)
    """, (line_id, date)).fetchone()
    weighted_rate_sum = (rate_row["weighted_rate_sum"] if rate_row else 0) or 0
    rated_min = (rate_row["rated_min"] if rate_row else 0) or 0
    distinct_rates = (rate_row["distinct_rates"] if rate_row else 0) or 0
    standard_rate = (weighted_rate_sum / rated_min) if rated_min else 0
    rate_mixed = distinct_rates > 1

    target = conn.execute("""
        SELECT COALESCE(SUM(target_quantity), 0) AS target
        FROM jobs
        WHERE line_id = ?
          AND date(scheduled_start) = ?
    """, (line_id, date)).fetchone()
    target_units = target["target"] if target else 0

    # lost_capacity is computed above, per run at the run's own SKU rate.
    # Agreed 2026-11-24 (A52). units_filled already contains scrap: 600 produced
    # with 20 scrap is 600 total and 580 good (the 2026-11-07 convention, stated
    # in FLOOR-MODEL and in the glossary below). This added scrap on top, so
    # every theoretical_capacity and capacity_gap built from it carried an extra
    # scrap_units, and losses_unexplained inherited it. Gross production is the
    # parts produced, and scrap is a subset of them rather than a second helping.
    gross_production = actual_units
    ftq = ((actual_units - scrap_units) / actual_units * 100) if actual_units else 0
    p2p = (actual_units / target_units * 100) if target_units else 0

    rate_loaded = (unrated_min == 0 and rated_min > 0)
    if rate_loaded:
        lost_capacity = int(round(rated_lost_capacity))
        theoretical_capacity = gross_production + lost_capacity
        capacity_gap = (theoretical_capacity - target_units) if target_units else 0
        losses_accounted = int(scrap_units + lost_capacity)
        losses_unexplained = abs(capacity_gap) - losses_accounted if capacity_gap < 0 else 0
        if losses_unexplained < 0:
            losses_unexplained = 0
    else:
        # A50, agreed 2026-11-24. capacity_gap compares production with the job
        # target, so a missing rate does not touch it. The figures that price a
        # loss in parts do, and they read as unknown rather than as zero: zero
        # says nothing was lost, which is a claim nobody can support, and it is
        # the stronger and worse of the two answers.
        lost_capacity = None
        theoretical_capacity = None
        capacity_gap = (gross_production - target_units) if target_units else 0
        losses_accounted = None
        losses_unexplained = None

    stats = {
        "line_id": line_id,
        "date": date,
        "actual_units": int(actual_units),
        "scrap_units": int(scrap_units),
        "run_minutes": int(run_minutes),
        "downtime_min": round(downtime_min, 1),
        "downtime_by_station": downtime_by_station,
        "standard_rate": round(standard_rate, 0),
        "rate_loaded": rate_loaded,
        "rate_mixed": rate_mixed,
        "target_units": int(target_units),
        "lost_capacity": lost_capacity,
        "gross_production": int(gross_production),
        "theoretical_capacity": theoretical_capacity,
        "capacity_gap": int(capacity_gap) if capacity_gap is not None else None,
        "losses_accounted": losses_accounted,
        "losses_unexplained": losses_unexplained,
        "ftq": round(ftq, 1),
        "p2p": round(p2p, 1),
    }
    if not rate_loaded:
        # The fact goes in the payload, not in a rule about the payload.
        stats["unrated_min"] = unrated_min
        stats["unrated_downtime_min"] = round(unrated_downtime_min, 1)
        stats["reconciliation"] = (
            "No rate is loaded for %s on Line %d, so %d of %d recorded minutes "
            "cannot be scored. The capacity gap of %+d parts is production "
            "against the target, not a reconciled loss: lost capacity, losses "
            "accounted for and losses unexplained were not computed."
            % (unrated_skus or "this SKU", line_id, unrated_min,
               int(run_minutes), int(capacity_gap or 0)))
    return stats


def get_floor_context(conn, line_id, date):
    """The context engine. Returns a string of operator notes and maintenance."""
    notes = conn.execute("""
        SELECT period, notes, duration_min
        FROM hourly_runs
        WHERE line_id = ?
          AND date(recorded_at) = ?
          AND notes IS NOT NULL
          AND notes != ''
        ORDER BY period
    """, (line_id, date)).fetchall()

    maintenance = conn.execute("""
        SELECT station, symptom, resolution, aggregate_actual_min
        FROM maintenance_events
        WHERE line_id = ?
          AND date(started_at) = ?
        ORDER BY started_at
    """, (line_id, date)).fetchall()

    pdca = conn.execute("""
        SELECT title, hypothesis
        FROM experiments
        WHERE line_id = ? AND status = 'active'
    """, (line_id,)).fetchall()

    parts = []
    if notes:
        parts.append("OPERATOR NOTES (verbatim, hour by hour):")
        for n in notes:
            # A partial hour is the single most misread row on this page: in
            # progress at the moment of asking, it looks like a whole hour of
            # poor performance. Say which it is in the payload rather than
            # relying on a rule to stop the model inferring it (A03).
            mins = n['duration_min'] or 60
            if mins < 60:
                parts.append(f"  {n['period']} [partial hour, {mins} of 60 min]: {n['notes']}")
            else:
                parts.append(f"  {n['period']}: {n['notes']}")

    if maintenance:
        parts.append("MAINTENANCE EVENTS:")
        for m in maintenance:
            parts.append(f"  {m['station']}: {m['symptom']} -> {m['resolution']} ({m['aggregate_actual_min']:.0f}m)")

    if pdca:
        parts.append("ACTIVE PDCAs:")
        for p in pdca:
            parts.append(f"  {p['title']}: {p['hypothesis'] or 'no hypothesis'}")

    return "\n".join(parts) if parts else "No operator notes, maintenance events, or active PDCAs for this day."


def narrate_capacity_gap(stats, context):
    """The fallback. Rigid, templated, no LLM.

    Since 2026-11-24 this is also what the tracer veto emits, so it must never
    raise and never print a figure that does not exist: an unknown loss is an em
    dash with the reason beside it, and a missing rate is stated in words rather
    than formatted as a number (A50).
    """
    s = stats
    if s["actual_units"] == 0 and s["run_minutes"] == 0:
        return f"Line {s['line_id']} on {s['date']}: no production recorded. Nothing to diagnose."

    gap = s.get("capacity_gap")
    gap_text = f"{gap:+,}" if isinstance(gap, int) else "\u2014"
    rate_missing = not s.get("rate_loaded", True)

    parts = [
        f"Line {s['line_id']} on {s['date']}.",
        f"Target: {s['target_units']:,}. Actual output: {s['actual_units']:,}, "
        f"of which {s['scrap_units']:,} scrap.",
    ]

    if rate_missing:
        parts.append(s.get("reconciliation")
                     or "No rate is loaded for this line and SKU, so the loss "
                        "figures were not computed.")
        parts.append(f"Recorded downtime: {s['downtime_min']} minutes.")
        parts.append(f"Capacity gap: {gap_text} units against target.")
        parts.append("Losses accounted for: \u2014 not computed without a rate.")
        parts.append("Losses unexplained: \u2014 not computed, because the "
                     "accounted loss is unknown.")
    else:
        if s.get('rate_mixed'):
            downtime_line = (f"Downtime: {s['downtime_min']} minutes across runs at the rates "
                             f"on file is {s['lost_capacity']:,} units of lost capacity.")
        else:
            downtime_line = (f"Downtime: {s['downtime_min']} minutes, which at "
                             f"{s['standard_rate']:,.0f}/hr is {s['lost_capacity']:,} units of lost capacity.")
        parts.append(downtime_line)
        parts.append(f"Capacity gap: {gap_text} units against target.")
        parts.append(f"Losses accounted for: {s['losses_accounted']:,} units (scrap plus lost capacity).")
        parts.append(f"Losses unexplained: {s['losses_unexplained']:,} units.")

    if (not rate_missing and s["losses_unexplained"] is not None
            and s["losses_accounted"] is not None
            and s["losses_unexplained"] > s["losses_accounted"]):
        parts.append("The unexplained loss exceeds the accounted loss. Revisit this job with the line lead to find what was not captured.")
    elif s["downtime_by_station"]:
        top = sorted(s["downtime_by_station"].items(), key=lambda x: -x[1])[0]
        parts.append(f"Largest single downtime source: {top[0]} at {top[1]} minutes.")

    parts.append(f"FTQ: {s['ftq']}%. P2P: {s['p2p']}%.")
    parts.append("")
    parts.append("Context:")
    parts.append(context)
    return "\n".join(parts)


def get_downtime_attribution(conn, job_number):
    """Return accounted downtime by station and total unaccounted minutes for a job."""
    job = conn.execute("SELECT id, job_number FROM jobs WHERE job_number = ? COLLATE NOCASE", (job_number,)).fetchone()
    if not job:
        return {"error": f"Job {job_number} not found."}

    job_id = job["id"]

    station_rows = conn.execute("""
        SELECT d.station, COALESCE(SUM(d.minutes), 0) AS minutes
        FROM downtime_events d
        JOIN hourly_runs r ON r.id = d.run_id
        WHERE r.job_id = ?
        GROUP BY d.station
        ORDER BY minutes DESC
    """, (job_id,)).fetchall()

    by_station = {r["station"]: round(r["minutes"], 1) for r in station_rows}
    total_recorded = sum(by_station.values())

    unacc_row = conn.execute("""
        SELECT COALESCE(SUM(unaccounted_min), 0) AS unaccounted,
               COALESCE(SUM(unrated_min), 0) AS unrated_min
        FROM v_unaccounted_minutes_by_run
        WHERE job_id = ?
    """, (job_id,)).fetchone()
    total_unaccounted = round(unacc_row["unaccounted"], 1) if unacc_row else 0.0
    total_unrated = round(unacc_row["unrated_min"], 1) if unacc_row else 0.0

    return {
        "job_number": job["job_number"],
        "recorded_downtime_min": round(total_recorded, 1),
        "downtime_by_station": by_station,
        "unaccounted_min": total_unaccounted,
        "unrated_min": total_unrated,
    }


def _build_changeover_summary(actual, standard, variance, variance_pct, steps):
    """Pre-compute the changeover narrative so the LLM paraphrases instead of interpreting."""
    parts = []
    if actual is not None and standard is not None and variance is not None:
        if variance == 0:
            parts.append(f"Total changeover was {actual:.1f} minutes, exactly at the standard of {standard:.1f} minutes.")
        elif variance < 0:
            parts.append(f"Total changeover was {actual:.1f} minutes against a standard of {standard:.1f}. "
                         f"This is {abs(variance):.1f} minutes FASTER than standard, a {abs(variance_pct):.1f}% improvement.")
        else:
            parts.append(f"Total changeover was {actual:.1f} minutes against a standard of {standard:.1f}. "
                         f"This is {variance:.1f} minutes SLOWER than standard, a {variance_pct:.1f}% overrun.")

    highlights = []
    for s in steps:
        std = s.get("standard_min")
        act = s.get("actual_min")
        var = s.get("variance_min")
        if std is None or act is None or var is None:
            continue
        if abs(var) < 0.5:
            continue
        station = s.get("station") or s.get("step_name") or "unknown"
        if var < 0:
            highlights.append(f"{station} SAVED {abs(var):.1f} minutes (actual {act:.1f}m vs standard {std:.1f}m).")
        else:
            highlights.append(f"{station} ran {var:.1f} minutes OVER standard (actual {act:.1f}m vs standard {std:.1f}m).")
    if highlights:
        parts.append(" ".join(highlights[:4]))
    return " ".join(parts)


def get_changeover_summary(conn, identifier):
    """Return changeover actual vs standard, per-station breakdown, and a pre-computed summary."""
    event = None
    try:
        event_id = int(identifier)
        event = conn.execute("""
            SELECT e.id, e.line_id, e.started_at, e.ended_at, e.aggregate_actual_min,
                   e.from_job_number, e.to_job_number, p.name AS procedure_name,
                   p.aggregate_standard_min AS standard_min
            FROM co_events e
            LEFT JOIN co_procedures_v2 p ON p.id = e.procedure_id
            WHERE e.id = ?
        """, (event_id,)).fetchone()
    except (ValueError, TypeError):
        pass

    if not event:
        event = conn.execute("""
            SELECT e.id, e.line_id, e.started_at, e.ended_at, e.aggregate_actual_min,
                   e.from_job_number, e.to_job_number, p.name AS procedure_name,
                   p.aggregate_standard_min AS standard_min
            FROM co_events e
            LEFT JOIN co_procedures_v2 p ON p.id = e.procedure_id
            WHERE e.to_job_number = ? COLLATE NOCASE OR e.from_job_number = ? COLLATE NOCASE
            ORDER BY e.started_at DESC LIMIT 1
        """, (identifier, identifier)).fetchone()

    if not event:
        return {"error": f"No changeover found for '{identifier}'."}

    event_id = event["id"]
    actual = event["aggregate_actual_min"]
    standard = event["standard_min"]

    variance = None
    variance_pct = None
    if actual is not None and standard is not None and standard > 0:
        variance = round(actual - standard, 1)
        variance_pct = round((variance / standard) * 100, 1)

    steps_rows = conn.execute("""
        SELECT s.station, s.step_name, s.standard_min, es.actual_min,
               ROUND(es.actual_min - s.standard_min, 1) AS variance_min
        FROM co_event_steps es
        JOIN co_steps_v2 s ON s.id = es.step_id
        WHERE es.event_id = ?
        ORDER BY s.seq
    """, (event_id,)).fetchall()
    steps = [dict(s) for s in steps_rows]

    summary = _build_changeover_summary(actual, standard, variance, variance_pct, steps)

    return {
        "event_id": event_id,
        "line_id": event["line_id"],
        "procedure_name": event["procedure_name"],
        "from_job": event["from_job_number"],
        "to_job": event["to_job_number"],
        "started_at": event["started_at"],
        "actual_min": round(actual, 1) if actual is not None else None,
        "standard_min": round(standard, 1) if standard is not None else None,
        "variance_min": variance,
        "variance_pct": variance_pct,
        "summary": summary,
        "steps": steps,
    }


def get_unaccounted_minutes(conn, line_id, days=30, shift=None):
    """Return total recorded and unaccounted downtime for a line over a window."""
    params = [line_id, f'-{days} days']
    shift_clause = ''
    if shift is not None:
        shift_clause = ' AND v.shift = ?'
        params.append(str(shift))

    totals = conn.execute(f"""
        SELECT
            ROUND(COALESCE(SUM(v.recorded_downtime_min), 0), 1) AS recorded,
            ROUND(COALESCE(SUM(v.unaccounted_min), 0), 1) AS unaccounted,
            ROUND(COALESCE(SUM(v.unrated_min), 0), 1) AS unrated_min,
            COUNT(DISTINCT v.job_id) AS job_count
        FROM v_unaccounted_minutes_by_run v
        WHERE v.line_id = ?
          AND date(v.recorded_at) >= date('now', ?)
          {shift_clause}
    """, params).fetchone()

    by_shift = conn.execute("""
        SELECT
            v.shift,
            ROUND(COALESCE(SUM(v.recorded_downtime_min), 0), 1) AS recorded,
            ROUND(COALESCE(SUM(v.unaccounted_min), 0), 1) AS unaccounted,
            ROUND(COALESCE(SUM(v.unrated_min), 0), 1) AS unrated_min
        FROM v_unaccounted_minutes_by_run v
        WHERE v.line_id = ?
          AND date(v.recorded_at) >= date('now', ?)
        GROUP BY v.shift
        ORDER BY v.shift
    """, (line_id, f'-{days} days')).fetchall()

    total_recorded = totals["recorded"] if totals else 0
    total_unaccounted = totals["unaccounted"] if totals else 0
    total_unrated = (totals["unrated_min"] if totals else 0) or 0
    total_lost = round(total_recorded + total_unaccounted, 1)
    pct_unaccounted = round((total_unaccounted / total_lost * 100), 1) if total_lost else 0

    return {
        "line_id": line_id,
        "days": days,
        "shift_filter": shift,
        "job_count": totals["job_count"] if totals else 0,
        "recorded_min": total_recorded,
        "unaccounted_min": total_unaccounted,
        "unrated_min": total_unrated,
        "total_lost_min": total_lost,
        "pct_unaccounted": pct_unaccounted,
        "by_shift": [dict(r) for r in by_shift],
    }


def get_jobs_with_downtime_over(conn, threshold_min, days=30):
    """Return jobs whose total recorded downtime exceeds threshold_min within the last N days."""
    rows = conn.execute("""
        SELECT
            j.job_number,
            j.line_id,
            l.name AS line_name,
            MAX(date(v.recorded_at)) AS last_date,
            ROUND(COALESCE(SUM(v.recorded_downtime_min), 0), 1) AS recorded_downtime_min,
            ROUND(COALESCE(SUM(v.unaccounted_min), 0), 1) AS unaccounted_min
        FROM v_unaccounted_minutes_by_run v
        JOIN jobs j ON j.id = v.job_id
        LEFT JOIN lines l ON l.id = j.line_id
        WHERE date(v.recorded_at) >= date('now', ?)
        GROUP BY j.id
        HAVING ROUND(COALESCE(SUM(v.recorded_downtime_min), 0), 1) > ?
        ORDER BY recorded_downtime_min DESC
    """, (f'-{days} days', threshold_min)).fetchall()

    jobs_list = [dict(r) for r in rows]
    count = len(jobs_list)
    if count == 0:
        summary = f"No jobs exceeded {threshold_min} minutes of recorded downtime in the last {days} days."
    else:
        top = jobs_list[:3]
        top_str = "; ".join(
            f"{t['job_number']} on {t['line_name'] or 'unknown line'} with {t['recorded_downtime_min']} minutes recorded and {t['unaccounted_min']} minutes unaccounted"
            for t in top
        )
        summary = f"{count} jobs exceeded {threshold_min} minutes of recorded downtime in the last {days} days. The top three by recorded downtime: {top_str}."
    
    return {
        "threshold_min": threshold_min,
        "days": days,
        "count": count,
        "summary": summary,
        "jobs": jobs_list,
    }


def get_job_summary(conn, job_number):
    """Return FTQ, P2P, scrap, downtime, and hourly breakdown for one job."""
    job = conn.execute("""
        SELECT j.id, j.job_number, j.line_id, j.sku_id, j.target_quantity, j.status,
               s.description AS sku_description, l.name AS line_name
        FROM jobs j
        LEFT JOIN skus s ON s.id = j.sku_id
        LEFT JOIN lines l ON l.id = j.line_id
        WHERE j.job_number = ? COLLATE NOCASE
    """, (job_number,)).fetchone()

    if not job:
        return {"error": f"Job {job_number} not found."}

    job_id = job["id"]

    totals = conn.execute("""
        SELECT COALESCE(SUM(units_filled), 0) AS actual_units,
               COALESCE(SUM(scrap_units), 0) AS scrap_units,
               COALESCE(SUM(duration_min), 0) AS run_minutes
        FROM hourly_runs
        WHERE job_id = ? AND (superseded IS NULL OR superseded = 0)
    """, (job_id,)).fetchone()

    actual_units = totals["actual_units"]
    scrap_units = totals["scrap_units"]
    run_minutes = totals["run_minutes"]

    hourly = conn.execute("""
        SELECT period, shift, units_filled, scrap_units, notes,
               recorded_downtime_min, unaccounted_min, unrated_min, gap_min
        FROM v_unaccounted_minutes_by_run
        WHERE job_id = ?
        ORDER BY recorded_at, period
    """, (job_id,)).fetchall()

    total_downtime = sum(r["recorded_downtime_min"] for r in hourly)
    # unaccounted_min is NULL for an hour with no rate (A50), so it cannot be
    # summed raw: sum(None, 3.0) raises, which would take the whole card down.
    total_unaccounted = sum((r["unaccounted_min"] or 0) for r in hourly)
    unrated_min = sum((r["unrated_min"] or 0) for r in hourly)

    target_units = job["target_quantity"] or 0
    ftq = ((actual_units - scrap_units) / actual_units * 100) if actual_units else 0
    p2p = (actual_units / target_units * 100) if target_units else 0

    return {
        "job_number": job["job_number"],
        "line_id": job["line_id"],
        "line_name": job["line_name"],
        "sku_description": job["sku_description"],
        "status": job["status"],
        "target_units": int(target_units),
        "actual_units": int(actual_units),
        "scrap_units": int(scrap_units),
        "run_minutes": int(run_minutes),
        "recorded_downtime_min": round(total_downtime, 1),
        "unaccounted_min": round(total_unaccounted, 1),
        "unrated_min": round(unrated_min, 1),
        "ftq": round(ftq, 1),
        "p2p": round(p2p, 1),
        "hourly": [dict(r) for r in hourly],
    }


def _fallback_narrative(intent, stats):
    """Template fallback for each intent type when the LLM is unavailable."""
    if intent == "job":
        return (f"Job {stats.get('job_number', '?')}: FTQ {stats.get('ftq', 0)}%, P2P {stats.get('p2p', 0)}%. "
                f"Actual {stats.get('actual_units', 0):,} units, scrap {stats.get('scrap_units', 0):,}, "
                f"recorded downtime {stats.get('recorded_downtime_min', 0)}m, unaccounted {stats.get('unaccounted_min', 0)}m.")
    if intent == "jobs_over":
        return (f"{stats.get('count', 0)} jobs exceeded {stats.get('threshold_min', 0)}m of recorded downtime "
                f"in the last {stats.get('days', 0)} days.")
    if intent == "unaccounted":
        return (f"Line {stats.get('line_id', '?')} last {stats.get('days', 0)} days: "
                f"{stats.get('recorded_min', 0)}m recorded, {stats.get('unaccounted_min', 0)}m unaccounted "
                f"({stats.get('pct_unaccounted', 0)}% of total lost time).")
    if intent == "changeover":
        summary = stats.get("summary", "")
        if summary:
            return summary
        return (f"Changeover {stats.get('from_job', '?')} to {stats.get('to_job', '?')}: "
                f"actual {stats.get('actual_min', 0)}m vs standard {stats.get('standard_min', 0)}m "
                f"({stats.get('variance_min', 0)}m variance, {stats.get('variance_pct', 0)}%).")
    if intent == "line_day":
        return narrate_capacity_gap(stats, "")
    return str(stats)


# ============================================================
# The tracer, and the veto (item 2, agreed 2026-11-24)
# ============================================================

_JOB_NUMBER_RE = re.compile(r"WO-?\d+-\d+", re.IGNORECASE)
_ISO_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}")
_LIST_MARKER_RE = re.compile(r"(?m)^[ \t]*\d{1,2}[.)][ \t]")
_FIGURE_RE = re.compile(r"-?\d[\d,]*(?:\.\d+)?")


def numbers_in_text(text):
    """Every figure in a string, as floats. Job numbers and dates are not figures.

    "WO-2611-201" reads as two negative numbers to a naive scan and an ISO date
    reads as three, so both are removed first. P2P carries a 2 that is not one.

    Numbered list markers are removed too, and that one was learned in production
    on 2026-11-24: the jobs_over card wrote "1. WO-2026-41415 ... 2. ... 3. ..."
    and the scan read 1, 2 and 3 as figures the model had invented, so a correct
    card was vetoed for using a list. Only a marker at the start of a line
    followed by whitespace is removed, so "1.5" and "79 jobs" are untouched.
    """
    t = _JOB_NUMBER_RE.sub(" ", text or "")
    t = _ISO_DATE_RE.sub(" ", t)
    t = _LIST_MARKER_RE.sub(" ", t)
    t = t.replace("P2P", " ")
    out = set()
    for m in _FIGURE_RE.finditer(t):
        try:
            out.add(float(m.group(0).replace(",", "")))
        except ValueError:
            pass
    return out


def untraced_numbers(narrative, prompt):
    """Figures in the narrative that appear nowhere in the prompt.

    Agreed 2026-11-24, replacing the check that ran against the stats dictionary
    alone. That version called a correct card a liar: it reported [32.0, 3.0]
    and [10.0] as invented when 32 came from the payload marker "H3 [partial
    hour, 32 of 60 min]", 3 from the hour label H3, and 10 from an operator note
    reading "shift 1 on day 10". All three were in the prompt; none were in the
    stats object. Those quotes are the most valuable thing the cards produce, so
    a check that punishes them would remove the wrong thing.

    The trace is therefore the whole prompt: data, glossary, context block with
    the operator notes, intent rules and the question. A number the model was
    shown is not a number it invented.

    Residual weakness, recorded rather than hidden: the intent rules contain
    figures of their own ("Under 180 words", and the 32/152 example in the
    line_day note), so those specific numbers trace to the rule text rather than
    to the data. That is looser than a data-only trace, and it is the price of
    not vetoing quotes from context. It cannot excuse a number that appears
    nowhere.
    """
    return numbers_in_text(narrative) - numbers_in_text(prompt)


def build_prompt(intent, stats, context=None, question=""):
    """The exact prompt sent to the model. Exposed so the trace runs on it.

    Keeping one constructor is the point: a checker that rebuilds the prompt
    itself can drift from the one the model saw, and then a green check is
    evidence about the checker.
    """
    intent_notes = INTENT_NOTES.get(intent, "(none)")
    # For jobs_over, the raw jobs array confuses small models. Strip it.
    # The summary field already contains the authoritative answer.
    payload = dict(stats)
    if intent == "jobs_over" and isinstance(payload.get("jobs"), list):
        payload["jobs"] = f"[{len(payload['jobs'])} jobs - see summary]"
    return GENERIC_NARRATIVE_PROMPT.format(
        data=json.dumps(payload, indent=2, default=str),
        context=context or "(none)",
        intent_notes=intent_notes,
        glossary=_glossary_for(payload),
        question=question
    )


def narrate(intent, stats, context=None, question=""):
    """Generic narrator for the /herbie web route. LLM-driven with template fallback."""
    if isinstance(stats, dict) and stats.get("actual_units") == 0 and stats.get("run_minutes") == 0:
        # Agreed 2026-11-20: this guard belongs to the line card only. Applied
        # to a job it interpolated a date the job summary does not carry and
        # produced "Line 7 on None". A scheduled job with no runs is a normal
        # state and deserves a true sentence rather than a broken one.
        if intent == "line_day" and stats.get("line_id"):
            return {"narrative": "Line %s on %s: no production recorded."
                                 % (stats.get("line_id"), stats.get("date")),
                    "source": "no-data"}
        if intent == "job" and stats.get("job_number"):
            return {"narrative": "Job %s has no recorded production. Status: %s."
                                 % (stats.get("job_number"),
                                    stats.get("status") or "unknown"),
                    "source": "no-data"}

    if isinstance(stats, dict) and "error" in stats:
        return {"narrative": stats["error"], "source": "error"}

    prompt = build_prompt(intent, stats, context, question)

    try:
        r = requests.post(LLM_URL, json={
            "messages": [
                {"role": "system", "content": "You are a Lean manufacturing counselor. You are direct, factual, and you never invent or recompute numbers."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 500,
        }, timeout=LLM_TIMEOUT)
        r.raise_for_status()
        narrative = r.json()["choices"][0]["message"]["content"].strip()
        stray = untraced_numbers(narrative, prompt)
        if stray:
            # Agreed 2026-11-24: the tracer warned and the warning was read by
            # nobody who could act on it. A figure the model was not shown is
            # the one failure a plant manager cannot detect by reading, so the
            # narrative is replaced by the template and the model's text is
            # kept for the next session to look at rather than thrown away.
            return {"narrative": _fallback_narrative(intent, stats),
                    "source": "vetoed",
                    "vetoed_numbers": sorted(stray),
                    "rejected": narrative}
        return {"narrative": narrative, "source": "llm"}
    except Exception as e:
        return {"narrative": _fallback_narrative(intent, stats), "source": "fallback", "error": str(e)}


def ask_herbie(line_id, date, question=None):
    """The orchestrator for line/day queries. Kept for backwards compatibility."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    stats = get_line_summary(conn, line_id, date)
    context = get_floor_context(conn, line_id, date)
    conn.close()

    if question is None:
        question = f"Summarize Line {line_id} on {date} and tell me where to look next."

    return narrate("line_day", stats, context, question)


if __name__ == "__main__":
    from datetime import date as _d
    today = _d.today().isoformat()
    result = ask_herbie(7, today)
    print(f"[{result['source']}]")
    print(result["narrative"])