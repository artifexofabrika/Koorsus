"""
Myarra Phase 1 Local Test - Shift Handover & Relog Constraints
"""
import re

jobs = {
    "WO-2610-009": {"target": 288000, "produced": 0, "notes": "", "status": "running"}
}
session = {
    "state": "idle", 
    "job_number": None, 
    "logged_hours": []  # Tracks hours logged by THIS user in THIS session
}

def process_input(text):
    global session
    text = text.strip()
    lower_text = text.lower()

    # --- STATE: AWAITING HANDOVER NOTES ---
    if session["state"] == "awaiting_handover_notes":
        job_num = session["job_number"]
        jobs[job_num]["notes"] = text
        session["state"] = "idle"
        return f"Handover notes saved for {job_num}."

    # ==========================================
    # MANAGER COMMANDS
    # ==========================================
    status_match = re.search(r'status\s*job\s*(wo-\d{4}-\d{3})', lower_text)
    if status_match:
        job_num = status_match.group(1).upper()
        if job_num in jobs:
            j = jobs[job_num]
            notes = j['notes'] if j['notes'] else "None"
            return f"Job {job_num}.\nProduced: {j['produced']:,} / {j['target']:,}.\nLast notes: {notes}"
        return f"Job {job_num} not found."

    # ==========================================
    # SHIFT HANDOVER (Summary & Notes)
    # ==========================================
    handover_match = re.search(r'handover\s*job\s*(wo-\d{4}-\d{3})', lower_text)
    if handover_match:
        job_num = handover_match.group(1).upper()
        if job_num in jobs:
            j = jobs[job_num]
            hours_logged = len(session["logged_hours"])
            next_hour = max(session["logged_hours"]) + 1 if session["logged_hours"] else 1
            
            summary = f"Handover Summary for {job_num}:\n"
            summary += f"Hours logged this shift: {hours_logged} (Up to Hour {max(session['logged_hours']) if session['logged_hours'] else 0})\n"
            summary += f"Total produced: {j['produced']:,} / {j['target']:,}\n"
            summary += f"Next hour to log: {next_hour}\n"
            
            session["state"] = "awaiting_handover_notes"
            session["job_number"] = job_num
            return summary + "\nAny notes for the incoming shift?"
        return f"Job {job_num} not found."

    takeover_match = re.search(r'taking over job\s*(wo-\d{4}-\d{3})', lower_text)
    if takeover_match:
        job_num = takeover_match.group(1).upper()
        if job_num in jobs:
            j = jobs[job_num]
            notes = j['notes'] if j['notes'] else "None"
            session["job_number"] = job_num
            session["state"] = "idle"
            session["logged_hours"] = [] # Reset for the new shift
            return f"Taking over {job_num}.\nProduced so far: {j['produced']:,}.\nNotes: {notes}\nReady to log production."
        return f"Job {job_num} not found."

    # ==========================================
    # RELOG COMMAND (Shift Constraint)
    # ==========================================
    relog_match = re.search(r'relog\s*hour\s*(\d+)[,\s]+(\d+)', lower_text)
    if relog_match:
        hour_num = int(relog_match.group(1))
        new_bottles = int(relog_match.group(2))
        
        if hour_num not in session["logged_hours"]:
            return f"Denied. Hour {hour_num} was not logged by you in this session. Please contact the plant manager to make historical changes."
            
        session["state"] = "awaiting_relog_reason"
        session["pending_relog"] = (hour_num, new_bottles)
        return f"You are about to relog Hour {hour_num} to {new_bottles:,} bottles. Please state the reason."

    if session["state"] == "awaiting_relog_reason":
        reason = text
        hour_num, new_bottles = session["pending_relog"]
        job_num = session.get("job_number") or "WO-2610-009"
        
        # In a real DB, we would update the hourly_runs row and log the audit trail
        # For this test, we just update the fake cumulative total
        jobs[job_num]["produced"] = (jobs[job_num]["produced"] - (hour_num * 36000)) + new_bottles # Rough math for demo
        session["state"] = "idle"
        return f"Hour {hour_num} updated to {new_bottles:,} bottles. Reason logged: '{reason}'."

    # ==========================================
    # PRODUCTION HOUR (With Duplicate Check)
    # ==========================================
    prod_match = re.search(r'record production hour[:\s]*(\d+)[,\s]+(\d+)\s*(?:min|minutes?)[,\s]+(\d+)', lower_text)
    if prod_match:
        hour_num = int(prod_match.group(1))
        mins = float(prod_match.group(2))
        bottles = float(prod_match.group(3))
        job_num = session.get("job_number") or "WO-2610-009"
        
        # Duplicate Check
        if hour_num in session["logged_hours"]:
            session["state"] = "awaiting_duplicate_confirm"
            session["pending_hour"] = (hour_num, mins, bottles)
            return f"Hour {hour_num} is already logged. Did you mean Hour {hour_num + 1}? (Y/N)"
            
        # Capacity Check
        expected = mins * 600.0
        if bottles > expected:
            return f"Warning: {bottles:,.0f} exceeds maximum capacity of {expected:,.0f} for {mins} minutes. Is this correct? (Y/N)"
            
        # Log the hour
        session["logged_hours"].append(hour_num)
        jobs[job_num]["produced"] += int(bottles)
        gap_minutes = (expected - bottles) / 600.0
        
        reply = f"Hour {hour_num} logged.\nExpected: {expected:,.0f}. Produced: {bottles:,.0f}.\nGap: {gap_minutes:.1f} min."
        if gap_minutes > 3.0:
            reply += "\n(Over threshold. What caused the gap?)"
        return reply

    # ==========================================
    # START JOB
    # ==========================================
    start_match = re.search(r'start(?:ing)?\s*job\s*(wo-\d{4}-\d{3})', lower_text)
    if start_match:
        job_num = start_match.group(1).upper()
        if job_num not in jobs:
            jobs[job_num] = {"target": 288000, "produced": 0, "notes": "", "status": "running"}
        session["job_number"] = job_num
        session["state"] = "idle"
        return f"Started Job {job_num}. Ready to log production."

    return "Command not recognized. Try: 'Record production hour: 5, 60 minutes, 35000 bottles'"

# --- Chat Loop ---
if __name__ == "__main__":
    print("=== MYARRA PHASE 1 TEST v3 ===")
    print("Bot: Ready.\n")
    while True:
        user_input = input("You: ")
        if user_input.lower() in ['quit', 'exit']:
            break
        reply = process_input(user_input)
        print(f"Bot: {reply}\n")
