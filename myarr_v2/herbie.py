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
import requests
import sqlite3

DB_PATH = "/mnt/lake/myarra.db"
LLM_URL = "http://127.0.0.1:8080/v1/chat/completions"
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
- If pct_unaccounted is above 25, state that it is a significant gap.
""",
}


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
- Quote the operator notes directly when they are relevant.

RULES:
- Be direct. No fluff.
- Never blame the operator.
- Under 180 words.
- FTQ is First Time Quality. P2P is Produce to Plan (Actual / Target).
- If you cannot answer something from the data, say so.

DATA (Python-computed, quote numbers exactly):
{data}

FIELD GLOSSARY (use these definitions, never invent alternatives):
- recorded_downtime_min: minutes the operator logged as downtime
- unaccounted_min: minutes of production loss with no logged explanation
- lost_capacity: theoretical unit capacity lost due to recorded downtime
- capacity_gap: variance against target in units (negative = under target)
- losses_accounted: scrap units + lost_capacity units
- losses_unexplained: capacity_gap minus losses_accounted
- ftq: First Time Quality (%)
- p2p: Produce to Plan, Actual divided by Target (%)

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

    rate = conn.execute("""
        SELECT COALESCE(AVG(lsr.ideal_rate), 0) AS rate
        FROM line_sku_rates lsr
        WHERE lsr.line_id = ?
    """, (line_id,)).fetchone()
    standard_rate = rate["rate"] if rate else 0

    target = conn.execute("""
        SELECT COALESCE(SUM(target_quantity), 0) AS target
        FROM jobs
        WHERE line_id = ?
          AND date(scheduled_start) = ?
    """, (line_id, date)).fetchone()
    target_units = target["target"] if target else 0

    lost_capacity = (downtime_min / 60.0) * standard_rate if standard_rate else 0
    gross_production = actual_units + scrap_units
    theoretical_capacity = gross_production + lost_capacity
    capacity_gap = (theoretical_capacity - target_units) if target_units else 0
    ftq = ((actual_units - scrap_units) / actual_units * 100) if actual_units else 0
    p2p = (actual_units / target_units * 100) if target_units else 0

    losses_accounted = scrap_units + lost_capacity
    losses_unexplained = abs(capacity_gap) - losses_accounted if capacity_gap < 0 else 0
    if losses_unexplained < 0:
        losses_unexplained = 0

    return {
        "line_id": line_id,
        "date": date,
        "actual_units": int(actual_units),
        "scrap_units": int(scrap_units),
        "run_minutes": int(run_minutes),
        "downtime_min": round(downtime_min, 1),
        "downtime_by_station": downtime_by_station,
        "standard_rate": round(standard_rate, 0),
        "target_units": int(target_units),
        "lost_capacity": int(lost_capacity),
        "gross_production": int(gross_production),
        "theoretical_capacity": int(theoretical_capacity),
        "capacity_gap": int(capacity_gap),
        "losses_accounted": int(losses_accounted),
        "losses_unexplained": int(losses_unexplained),
        "ftq": round(ftq, 1),
        "p2p": round(p2p, 1),
    }


def get_floor_context(conn, line_id, date):
    """The context engine. Returns a string of operator notes and maintenance."""
    notes = conn.execute("""
        SELECT period, notes
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
    """The fallback. Rigid, templated, no LLM."""
    s = stats
    if s["actual_units"] == 0 and s["run_minutes"] == 0:
        return f"Line {s['line_id']} on {s['date']}: no production recorded. Nothing to diagnose."

    parts = [
        f"Line {s['line_id']} on {s['date']}.",
        f"Target: {s['target_units']:,}. Actual good output: {s['actual_units']:,}. Scrap: {s['scrap_units']:,}.",
        f"Downtime: {s['downtime_min']} minutes, which at {s['standard_rate']:,.0f}/hr is {s['lost_capacity']:,} units of lost capacity.",
        f"Capacity gap: {s['capacity_gap']:+,} units against target.",
        f"Losses accounted for: {s['losses_accounted']:,} units (scrap plus lost capacity).",
        f"Losses unexplained: {s['losses_unexplained']:,} units.",
    ]

    if s["losses_unexplained"] > s["losses_accounted"]:
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
        SELECT COALESCE(SUM(unaccounted_min), 0) AS unaccounted
        FROM v_unaccounted_minutes_by_run
        WHERE job_id = ?
    """, (job_id,)).fetchone()
    total_unaccounted = round(unacc_row["unaccounted"], 1) if unacc_row else 0.0

    return {
        "job_number": job["job_number"],
        "recorded_downtime_min": round(total_recorded, 1),
        "downtime_by_station": by_station,
        "unaccounted_min": total_unaccounted,
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
            ROUND(COALESCE(SUM(v.unaccounted_min), 0), 1) AS unaccounted
        FROM v_unaccounted_minutes_by_run v
        WHERE v.line_id = ?
          AND date(v.recorded_at) >= date('now', ?)
        GROUP BY v.shift
        ORDER BY v.shift
    """, (line_id, f'-{days} days')).fetchall()

    total_recorded = totals["recorded"] if totals else 0
    total_unaccounted = totals["unaccounted"] if totals else 0
    total_lost = round(total_recorded + total_unaccounted, 1)
    pct_unaccounted = round((total_unaccounted / total_lost * 100), 1) if total_lost else 0

    return {
        "line_id": line_id,
        "days": days,
        "shift_filter": shift,
        "job_count": totals["job_count"] if totals else 0,
        "recorded_min": total_recorded,
        "unaccounted_min": total_unaccounted,
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
               recorded_downtime_min, unaccounted_min, gap_min
        FROM v_unaccounted_minutes_by_run
        WHERE job_id = ?
        ORDER BY recorded_at, period
    """, (job_id,)).fetchall()

    total_downtime = sum(r["recorded_downtime_min"] for r in hourly)
    total_unaccounted = sum(r["unaccounted_min"] for r in hourly)

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


def narrate(intent, stats, context=None, question=""):
    """Generic narrator for the /herbie web route. LLM-driven with template fallback."""
    if isinstance(stats, dict) and stats.get("actual_units") == 0 and stats.get("run_minutes") == 0 and stats.get("line_id"):
        return {"narrative": f"Line {stats.get('line_id')} on {stats.get('date')}: no production recorded.",
                "source": "no-data"}

    if isinstance(stats, dict) and "error" in stats:
        return {"narrative": stats["error"], "source": "error"}

    intent_notes = INTENT_NOTES.get(intent, "(none)")
    # For jobs_over, the raw jobs array confuses small models. Strip it.
    # The summary field already contains the authoritative answer.
    payload = dict(stats)
    if intent == "jobs_over" and isinstance(payload.get("jobs"), list):
        payload["jobs"] = f"[{len(payload['jobs'])} jobs - see summary]"
    prompt = GENERIC_NARRATIVE_PROMPT.format(
        data=json.dumps(payload, indent=2, default=str),
        context=context or "(none)",
        intent_notes=intent_notes,
        question=question
    )

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