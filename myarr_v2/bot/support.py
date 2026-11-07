"""bot/support.py — Status queries, help text, and SOP proxy."""
import requests

from . import db


def h_help(conn, s, text, user):
    return (
        "Commands:\n"
        "  running job WO-XXXX-XXX, hour N, U parts[, S scrap]\n"
        "  record production hour N, M minutes, U parts\n"
        "  start WO-XXXX-XXX | end WO-XXXX-XXX\n"
        "  pause WO-XXXX-XXX | resume WO-XXXX-XXX\n"
        "  changeover job WO-A to WO-B | end changeover\n"
        "  maintenance <station> <symptom> | end maintenance\n"
        "  idle <reason> | unscheduled <reason>\n"
        "  note: TEXT | note hour N: TEXT\n"
        "  relog job WO-X hour N, U parts[, S scrap]\n"
        "  status line N | status WO-XXXX-XXX\n"
        "  handover job WO-XXXX | taking over job WO-XXXX\n"
        "  start shift | end shift\n"
        "  sop, your question\n"
        "  help | cancel"
    )


def h_unknown(conn, s, text, user):
    return "I did not understand. Say 'help' for the command list."


def h_status_job(conn, s, text, user):
    from parsers import parse_job_number
    job_no = parse_job_number(text)
    if not job_no:
        return "Say: 'status WO-XXXX-XXX'."
    job = conn.execute("SELECT * FROM jobs WHERE job_number=?", (job_no,)).fetchone()
    if not job:
        return f"No job found for '{job_no}'."

    total = conn.execute(
        "SELECT SUM(units_filled) AS u, SUM(scrap_units) AS s FROM hourly_runs "
        "WHERE job_id=? AND (superseded IS NULL OR superseded=0)",
        (job['id'],)).fetchone()
    units = (total['u'] or 0) if total else 0
    scrap = (total['s'] or 0) if total else 0
    cp = db.case_pack(conn, job['sku_id'])
    cases = db.case_count(units, cp)
    tgt_cases = db.case_count(job['target_quantity'] or 0, cp)
    pct = (units / job['target_quantity'] * 100) if job['target_quantity'] else 0

    sku = conn.execute("SELECT description FROM skus WHERE id=?", (job['sku_id'],)).fetchone()
    desc = sku['description'] if sku else ''

    return (
        f"{job['job_number']} — {desc}\n"
        f"Status: {job['status'].upper()}\n"
        f"Line {job['line_id']}\n"
        f"{cases:,} of {tgt_cases:,} cases ({pct:.1f}%)\n"
        f"Scrap: {scrap:,} units"
    )


def h_status_line(conn, s, text, user):
    from parsers import parse_line_number
    lid = parse_line_number(text)
    if lid is None:
        lid = s.get('line_id') or (user.get('line_id') if user else None)
    if lid is None:
        return "Say: 'status line N'."

    line = conn.execute("SELECT * FROM lines WHERE id=?", (lid,)).fetchone()
    if not line:
        return f"No line {lid} found."

    cur = db.current_line_event(conn, lid)
    if not cur:
        return f"Line {lid} ({line['name']}) — IDLE (no active event)."

    state = cur['state'].upper()
    out = [f"Line {lid} ({line['name']}) — {state}"]

    if cur['state'] == 'production' and cur['job_id']:
        j = conn.execute("SELECT * FROM jobs WHERE id=?", (cur['job_id'],)).fetchone()
        if j:
            t = conn.execute(
                "SELECT SUM(units_filled) AS u FROM hourly_runs WHERE job_id=? "
                "AND (superseded IS NULL OR superseded=0)",
                (j['id'],)).fetchone()
            units = (t['u'] or 0) if t else 0
            cp = db.case_pack(conn, j['sku_id'])
            out.append(f"Running: {j['job_number']} ({db.case_count(units, cp):,} cases)")
    elif cur['state'] == 'changeover' and cur['co_event_id']:
        ev = conn.execute("SELECT from_job_number, to_job_number FROM co_events WHERE id=?",
                          (cur['co_event_id'],)).fetchone()
        if ev:
            out.append(f"Changeover: {ev['from_job_number']} -> {ev['to_job_number']}")
    elif cur['reason']:
        out.append(f"Reason: {cur['reason']}")

    return "\n".join(out)


def h_sop(conn, s, text, user):
    import re
    q = re.sub(r'^(sop|ask|question)[,:\s]+', '', text, flags=re.IGNORECASE).strip()
    if not q:
        return "What is your question?"
    try:
        r = requests.post("http://127.0.0.1:5000/ask", json={'question': q}, timeout=60)
        if r.status_code == 200:
            d = r.json()
            return d.get('answer') or d.get('response') or str(d)
        return f"Document service returned {r.status_code}."
    except Exception as e:
        return f"Document service unavailable: {e}"
