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
    job = conn.execute("SELECT id, job_number FROM jobs WHERE job_number = ?", (job_number,)).fetchone()
    if not job:
        return {"error": f"Job {job_number} not found."}

    job_id = job["id"]

    # Accounted downtime grouped by station
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

    # Unaccounted minutes from the view
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
            ROUND(COALESCE(SUM(v.recorded_downtime_min), 0), 1) AS total_recorded,
            ROUND(COALESCE(SUM(v.unaccounted_min), 0), 1) AS total_unaccounted
        FROM v_unaccounted_minutes_by_run v
        JOIN jobs j ON j.id = v.job_id
        LEFT JOIN lines l ON l.id = j.line_id
        WHERE date(v.recorded_at) >= date('now', ?)
        GROUP BY j.id
        HAVING total_recorded > ?
        ORDER BY total_recorded DESC
    """, (f'-{days} days', threshold_min)).fetchall()

    return {
        "threshold_min": threshold_min,
        "days": days,
        "count": len(rows),
        "jobs": [dict(r) for r in rows],
    }


def get_job_summary(conn, job_number):
    """Return FTQ, P2P, scrap, downtime, and hourly breakdown for one job."""
    job = conn.execute("""
        SELECT j.id, j.job_number, j.line_id, j.sku_id, j.target_quantity, j.status,
               s.description AS sku_description, l.name AS line_name
        FROM jobs j
        LEFT JOIN skus s ON s.id = j.sku_id
        LEFT JOIN lines l ON l.id = j.line_id
        WHERE j.job_number = ?
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


def ask_herbie(line_id, date, question=None):
    """The orchestrator. Calls the math, the context, and the LLM."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    stats = get_line_summary(conn, line_id, date)
    context = get_floor_context(conn, line_id, date)
    conn.close()

    fallback = narrate_capacity_gap(stats, context)

    if stats["actual_units"] == 0 and stats["run_minutes"] == 0:
        return {"narrative": fallback, "stats": stats, "context": context,
                "fallback": fallback, "source": "no-data"}

    if question is None:
        question = f"Summarize Line {line_id} on {date} and tell me where to look next."

    prompt = f"""You are Herbie, a Lean manufacturing counselor.

Every number below was calculated in Python. You may quote these numbers
exactly as written. You may NOT add, subtract, multiply, divide, or
otherwise derive new numbers. If you need a total, it is already computed
and listed below.

DIAGNOSTIC PRINCIPLE:
- A standard that has been run to for months is not wrong because one shift
  underperformed. Do not tell the manager the standard may need reevaluation.
- When losses_unexplained is larger than losses_accounted, the correct
  diagnosis is that the data is incomplete. Tell the manager to revisit the
  job with the line lead and find out what happened that was not captured.
- Quote the operator notes directly when they are relevant.

RULES:
- Be direct. No fluff.
- Never blame the operator by name or role.
- Under 180 words.
- FTQ is First Time Quality. P2P is Produce to Plan (Actual / Target).
- If you cannot answer something from the data, say so.

HARD NUMBERS (Python-computed, quote exactly):
{json.dumps(stats, indent=2)}

CONTEXT:
{context}

Manager's question: {question}
"""

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
        return {"narrative": narrative, "stats": stats, "context": context,
                "fallback": fallback, "source": "llm"}
    except Exception as e:
        return {"narrative": fallback, "stats": stats, "context": context,
                "fallback": fallback, "source": "fallback", "error": str(e)}


if __name__ == "__main__":
    from datetime import date as _d
    today = _d.today().isoformat()
    result = ask_herbie(7, today)
    print(f"[{result['source']}]")
    print(result["narrative"])