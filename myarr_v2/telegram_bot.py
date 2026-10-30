"""
Myarra Telegram Bot - Conversational Data Entry
"""
import time, sys, os, re, sqlite3, requests
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
import config
from db import get_db_connection

BOT_TOKEN = config.TELEGRAM_BOT_TOKEN
API = f"https://api.telegram.org/bot{BOT_TOKEN}"

def send_message(chat_id, text):
    try:
        requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except Exception as e:
        print(f"Send error: {e}")

def get_user(chat_id):
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE telegram_id=? AND active=1", (str(chat_id),)).fetchone()
    conn.close()
    return user

def clear_session(conn, chat_id):
    conn.execute("DELETE FROM bot_sessions WHERE chat_id=?", (str(chat_id),))
    conn.commit()

def start_changeover(conn, chat_id, text):
    # Look for: job 8104 to job 8105 (case insensitive)
    # Fallback: just find the first two 4-digit numbers
    match = re.search(r'job\s*(\d{4})\s*to\s*job\s*(\d{4})', text, re.IGNORECASE)
    if not match:
        jobs = re.findall(r'\b\d{4}\b', text)
        if len(jobs) >= 2:
            from_job, to_job = jobs[0], jobs[1]
        else:
            return "I couldn't find two job numbers. Please say: Changeover job 8104 to job 8105"
    else:
        from_job, to_job = match.group(1), match.group(2)
    
    # Find the job and procedure
    fj = conn.execute("SELECT * FROM jobs WHERE job_number=?", (from_job,)).fetchone()
    tj = conn.execute("SELECT * FROM jobs WHERE job_number=?", (to_job,)).fetchone()
    
    if not fj or not tj:
        return "One or both job numbers not found in the database."
        
    proc = conn.execute("SELECT * FROM co_procedures_v2 WHERE from_sku_id=? AND to_sku_id=?", (fj["sku_id"], tj["sku_id"])).fetchone()
    if not proc:
        return f"No changeover procedure defined from Job {from_job} to {to_job}."
        
    steps = conn.execute("SELECT id, step_name FROM co_steps_v2 WHERE procedure_id=? ORDER BY seq", (proc["id"],)).fetchall()
    if not steps:
        return "Procedure found, but it has no steps defined."
        
    # Create event
    cur = conn.cursor()
    cur.execute("INSERT INTO co_events (procedure_id, line_id, started_at, from_job_number, to_job_number, raw_text) VALUES (?, ?, datetime('now'), ?, ?, ?)",
                (proc["id"], proc["line_id"], from_job, to_job, text))
    event_id = cur.lastrowid
    
    # Setup session
    pending = ",".join(str(s["id"]) for s in steps[1:])
    current = steps[0]
    conn.execute("INSERT INTO bot_sessions (chat_id, state, event_id, pending_steps, current_step_id) VALUES (?, 'awaiting_yn', ?, ?, ?)",
                 (str(chat_id), event_id, pending, current["id"]))
    conn.commit()
    
    return f"Starting changeover Job {from_job} to {to_job}.\nDid you change the {current['step_name']}? (Y/N)"

def handle_yn(conn, session, text):
    ans = text.strip().upper()
    if ans not in ['Y', 'N', 'YES', 'NO']:
        return "Please answer Y or N."
        
    current_id = session["current_step_id"]
    
    if ans in ['N', 'NO']:
        # Log 0 minutes
        conn.execute("INSERT INTO co_event_steps (event_id, step_id, actual_min, note) VALUES (?, ?, 0, 'Skipped')", (session["event_id"], current_id))
        return advance_session(conn, session)
    else:
        # Ask for minutes
        conn.execute("UPDATE bot_sessions SET state='awaiting_mins' WHERE chat_id=?", (session["chat_id"],))
        conn.commit()
        step = conn.execute("SELECT step_name FROM co_steps_v2 WHERE id=?", (current_id,)).fetchone()
        return f"How many minutes did the {step['step_name']} take?"

def handle_mins(conn, session, text):
    try:
        mins = float(re.search(r'(\d+(?:\.\d+)?)', text).group(1))
    except:
        return "Please enter a number (e.g., 15 or 15.5)."
        
    conn.execute("INSERT INTO co_event_steps (event_id, step_id, actual_min) VALUES (?, ?, ?)", (session["event_id"], session["current_step_id"], mins))
    return advance_session(conn, session)

def advance_session(conn, session):
    pending = session["pending_steps"]
    if not pending:
        # All steps done, ask for notes
        conn.execute("UPDATE bot_sessions SET state='awaiting_notes' WHERE chat_id=?", (session["chat_id"],))
        conn.commit()
        return "All steps logged. Any notes for this changeover? (Or type 'None')"
        
    parts = pending.split(",")
    next_id = parts[0]
    remaining = ",".join(parts[1:]) if len(parts) > 1 else None
    
    conn.execute("UPDATE bot_sessions SET state='awaiting_yn', current_step_id=?, pending_steps=? WHERE chat_id=?", 
                 (next_id, remaining, session["chat_id"]))
    conn.commit()
    
    step = conn.execute("SELECT step_name FROM co_steps_v2 WHERE id=?", (next_id,)).fetchone()
    return f"Did you change the {step['step_name']}? (Y/N)"

def handle_notes(conn, session, text):
    notes = "" if text.lower() == 'none' else text
    conn.execute("UPDATE co_events SET notes=? WHERE id=?", (notes, session["event_id"]))
    conn.commit()
    
    # Calculate totals
    ev = conn.execute("SELECT p.aggregate_standard_min FROM co_events e JOIN co_procedures_v2 p ON p.id=e.procedure_id WHERE e.id=?", (session["event_id"],)).fetchone()
    std = ev["aggregate_standard_min"] if ev else 0
    
    actual = conn.execute("SELECT SUM(actual_min) FROM co_event_steps WHERE event_id=?", (session["event_id"],)).fetchone()[0] or 0
    
    conn.execute("UPDATE co_events SET aggregate_actual_min=? WHERE id=?", (actual, session["event_id"]))
    clear_session(conn, session["chat_id"])
    
    variance = actual - std
    status = "FLAG" if variance > 5 else "OK"
    return f"Changeover saved.\nStandard: {std}m\nActual: {actual}m\nVariance: {variance:+.0f}m [{status}]"

def process_message(chat_id, text, user):
    conn = get_db_connection()
    session = conn.execute("SELECT * FROM bot_sessions WHERE chat_id=?", (str(chat_id),)).fetchone()
    
    if session:
        if session["state"] == "awaiting_yn":
            reply = handle_yn(conn, session, text)
        elif session["state"] == "awaiting_mins":
            reply = handle_mins(conn, session, text)
        elif session["state"] == "awaiting_notes":
            reply = handle_notes(conn, session, text)
        else:
            clear_session(conn, chat_id)
            reply = "Session error cleared. Please start again."
        conn.close()
        return reply

    # New commands
    if "changeover" in text.lower():
        reply = start_changeover(conn, chat_id, text)
        conn.close()
        return reply
        
    # Default hourly parsing
    match = re.search(r'(\d{4}).*?(\d+)\s*(?:bottles?)?.*?(\d+)\s*(?:min|minutes?).*?(\w+.*)', text, re.IGNORECASE)
    if not match:
        conn.close()
        return "Format error. Use: Job 8104, 34272 bottles, 3 min down labeler"
        
    job_number, bottles, dt_min, reason = match.group(1), int(match.group(2)), float(match.group(3)), match.group(4).strip()
    job = conn.execute("SELECT * FROM jobs WHERE job_number=?", (job_number,)).fetchone()
    if not job:
        conn.close()
        return f"Job {job_number} not found."
        
    expected = 36000
    gap_min = (expected - bottles) / 600.0
    
    cur = conn.cursor()
    cur.execute("INSERT INTO hourly_runs (job_id, line_id, shift, period, recorded_at, bottles_filled, operator, raw_text) VALUES (?, ?, 'Current', 'H1', datetime('now'), ?, ?, ?)", (job["id"], job["line_id"], bottles, user["name"], text))
    run_id = cur.lastrowid
    
    if dt_min > 0:
        cur.execute("INSERT INTO downtime_events (run_id, station, reason, minutes) VALUES (?, 'Line', ?, ?)", (run_id, reason, dt_min))
        
    conn.commit()
    conn.close()
    
    unacc = gap_min - dt_min
    status = "FLAG" if unacc > 5.0 else "OK"
    return f"Logged: {bottles:,} bottles. Gap: {gap_min:.2f}m. Downtime: {dt_min}m ({reason}). Unaccounted: {unacc:.2f}m [{status}]"

def main():
    print("Myarra Telegram Bot running...")
    offset = None
    while True:
        try:
            url = f"{API}/getUpdates"
            params = {"timeout": 30}
            if offset: params["offset"] = offset
            r = requests.get(url, params=params, timeout=35)
            data = r.json()
            
            for result in data.get("result", []):
                offset = result["update_id"] + 1
                msg = result.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "").strip()
                
                if not text: continue
                
                user = get_user(chat_id)
                if not user:
                    send_message(chat_id, "Unauthorized.")
                    continue
                    
                reply = process_message(chat_id, text, user)
                send_message(chat_id, reply)
        except Exception as e:
            print(f"Loop error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
