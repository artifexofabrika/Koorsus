"""bot/support.py — Status queries, help text, and SOP proxy."""
import os

import requests

from . import db

# A44, agreed 2026-11-24. SOP answers used to come from the legacy Koorsus on
# port 5000, which had no authentication at all and is being retired. The live
# Koorsus on 5003 requires it, so the bot presents the appliance's local token.
# Both the URL and the token path are overridable so a test never has to touch a
# real service.
SOP_URL = os.environ.get("KOORSUS_SOP_URL", "https://127.0.0.1:5003/ask")
SOP_TOKEN_FILE = os.environ.get("KOORSUS_LOCAL_TOKEN_FILE",
                               "/home/jeeves/.koorsus-local.token")


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
    # Agreed 2026-11-14: remember the line the operator queried, so the next
    # record command targets the same line.
    if parse_line_number(text) is not None:
        s.set('line_id', lid)
        s.save()

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


def _sop_token():
    try:
        with open(SOP_TOKEN_FILE) as fh:
            return fh.read().strip()
    except OSError:
        return ""


def h_sop(conn, s, text, user):
    import re
    q = re.sub(r'^(sop|ask|question)[,:\s]+', '', text, flags=re.IGNORECASE).strip()
    if not q:
        return "What is your question?"
    token = _sop_token()
    if not token:
        return ("The document service is not set up on this appliance: there is "
                "no local token at " + SOP_TOKEN_FILE + ", so the question was "
                "not sent.")
    try:
        # The peer is this same machine and the certificate is its own, so
        # verification is off rather than pointed at a CA that does not exist.
        # Nothing here crosses a network. If this ever moves to another host,
        # this line is the first thing that has to change.
        r = requests.post(SOP_URL, json={'question': q},
                          headers={'X-Koorsus-Token': token},
                          timeout=60, verify=False)
        if r.status_code == 200:
            d = r.json()
            return d.get('answer') or d.get('response') or str(d)
        if r.status_code == 401:
            return ("The document service rejected the bot's token. Check that "
                    + SOP_TOKEN_FILE + " holds the same value the Koorsus app "
                    "reads, and that the app has been restarted since.")
        return f"Document service returned {r.status_code}."
    except Exception as e:
        return f"Document service unavailable: {e}"
