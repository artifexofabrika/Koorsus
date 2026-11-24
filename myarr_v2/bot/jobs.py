"""bot/jobs.py — Job lifecycle: start, end, pause, resume, variance.

THE BRIDGE THIS DOCSTRING DESCRIBED WAS ALREADY GONE (A35, corrected 2026-11-24)
It said that resolve_job, _explain_no_job, _fuzzy_note, next_job_hour and
cont_end_minutes were "imported from bot_v2" and would be extracted into
bot/resolve.py in a follow-up session. By the time anyone read it, none of that
was true. The first four are imported from bot/resolve.py on line 18, which is
where the extraction landed on 2026-11-13. cont_end_minutes is not imported from
anywhere: it is defined in this file, four hundred lines down. And bot_v2.py no
longer exists, having been deleted on 2026-11-24.

It stood long enough to cost a session a morning. A reader took it as proof that
the live parser was still bot_v2's, and went looking for a module that had not
existed for eleven days. The live path is bot_live_v3.py -> bot.dispatch -> here,
and this note is the only warning anyone needs: there is no bridge, there never
was one after 2026-11-13, and nothing in this file depends on bot_v2.

The handlers in this module are new and use bot/db.py for all state.
"""
import re
from datetime import datetime, timedelta

from . import db
from parsers import parse_job_number, parse_all_job_numbers, parse_int

from .resolve import resolve_job, _explain_no_job, _fuzzy_note, next_job_hour


def check_start(conn, job, line_id=None):
    """The three start checks, shared by the bot and the /floor page.

    Returns a refusal sentence, or None when the job may start.

    line_id is the line the job is about to run on, which is not always the
    line the job carries: a moved work order runs somewhere else, and the
    operator says so (FLOOR-MODEL, Choosing the job). Checking the job's own
    line instead would let a start on a busy line close the open event of
    whatever is already running there, silently, with no refusal.
    """
    status = (job.get('status') or '').lower()
    if status == 'completed':
        return job['job_number'] + ' is completed. It cannot be started again.'
    if status == 'paused':
        return (job['job_number'] + ' is paused. Say resume '
                + job['job_number'] + ' to resume it.')
    target = line_id or job['line_id']
    cur = db.current_line_event(conn, target)
    if cur and cur['job_id'] and cur['job_id'] != job['id']:
        other = conn.execute("SELECT job_number FROM jobs WHERE id=?",
                             (cur['job_id'],)).fetchone()
        other_no = other['job_number'] if other else 'another job'
        return (
            f"Line {target} is currently running "
            f"{other_no} ({cur['state']}). "
            f"You must complete a changeover before starting {job['job_number']}."
        )
    return None

# ---------------------------------------------------------------------------
# The variance gate. One implementation, called by the bot and the floor.
# ---------------------------------------------------------------------------


def _variance_tolerance(conn, default=0.05):
    """job_variance_tolerance as a float, never raising.

    Stored as a fraction, 0.05, not 5. The inline read this replaces called
    float() on whatever the settings table held, so a value typed as 5% or
    with a decimal comma raised ValueError and took the whole close path down.
    A setting that cannot be read falls back to the default rather than
    stopping an operator from closing a job.

    A value stored as 5 instead of 0.05 means 500 percent and the gate will
    never fire. That is a data question, not a code one, and it is deliberately
    not guessed at here.
    """
    try:
        row = conn.execute(
            "SELECT value FROM settings WHERE key='job_variance_tolerance'").fetchone()
        raw = str(row['value']).strip() if row and row['value'] is not None else ''
        if raw.endswith('%'):
            return float(raw[:-1].strip().replace(',', '.')) / 100.0
        if raw:
            return float(raw.replace(',', '.'))
    except Exception:
        pass
    return default


def scheduled_window(job):
    """A job's scheduled run time: (minutes, start, end, reason).

    minutes is None when there is no usable window, and reason says which of
    the three ways that happened.

    The window is the weekly schedule feed, by Odoo or by the jobs.csv upload
    in the import section. Both write scheduled_start and scheduled_end, and a
    re-upload updates them on an existing job number (onboarding._ingest_jobs).

    A customer Excel that hands over date-only cells puts the same date in
    both columns. That is a zero span, not a zero-length shift, so it is
    reported as no window rather than used as a denominator (A45).
    """
    raw_start = job.get('scheduled_start')
    raw_end = job.get('scheduled_end')
    if not raw_start or not raw_end:
        return None, None, None, 'no scheduled window on the job'
    try:
        start = datetime.fromisoformat(str(raw_start).strip())
        end = datetime.fromisoformat(str(raw_end).strip())
    except (TypeError, ValueError):
        return None, None, None, ('scheduled window is not a date: '
                                  + str(raw_start) + ' to ' + str(raw_end))
    if (start.tzinfo is None) != (end.tzinfo is None):
        start = start.replace(tzinfo=None)
        end = end.replace(tzinfo=None)
    minutes = int(round((end - start).total_seconds() / 60.0))
    if minutes <= 0:
        return None, None, None, ('scheduled window is ' + str(minutes)
                                  + ' minutes, so it cannot be a denominator')
    return minutes, start, end, ''


def off_time_minutes(conn, line_id, start, end):
    """Minutes the line spent in lunch, maintenance or CIP inside a window.

    Measured from the events already written, not from a configured lunch
    duration: FLOOR-MODEL, The switches, says off-time comes from the moment
    the switch was thrown because a toggle pair cannot lie about when it
    happened. Overlap is clipped to the window, so an event that began before
    the job did is not counted twice.
    """
    if not line_id or end <= start:
        return 0
    rows = conn.execute(
        "SELECT started_at, ended_at FROM line_events "
        "WHERE line_id = ? AND state IN ('lunch', 'maintenance', 'cip') "
        "AND started_at < ? AND (ended_at IS NULL OR ended_at > ?)",
        (line_id, end.isoformat(), start.isoformat())).fetchall()
    total = 0.0
    for r in rows:
        try:
            ev_start = datetime.fromisoformat(str(r['started_at']))
            ev_end = (datetime.fromisoformat(str(r['ended_at']))
                      if r['ended_at'] else end)
        except (TypeError, ValueError):
            continue
        if ev_start.tzinfo is not None:
            ev_start = ev_start.replace(tzinfo=None)
        if ev_end.tzinfo is not None:
            ev_end = ev_end.replace(tzinfo=None)
        lo = ev_start if ev_start > start else start
        hi = ev_end if ev_end < end else end
        if hi > lo:
            total += (hi - lo).total_seconds() / 60.0
    return int(round(total))


def variance_allowance(conn, job, now=None):
    """The gate's arithmetic, adjusted for time the line was not due to run.

    FLOOR-MODEL, The arithmetic: ten hours at 100 an hour is 1,000 parts, and
    thirty minutes of lunch makes it 9.5 hours and 950 parts. The expectation
    falls with the off-time, so the gate compares against the smaller figure.
    A flat five percent against the unadjusted target lets lunch alone trip
    it, and then demands the reason the PDCA reads (A45).

    Returns target, allowed, actual, off_minutes, window, note and variance.
    variance is None when there is nothing to compare against.
    """
    now = now or datetime.now()
    actual = conn.execute(
        "SELECT SUM(units_filled) FROM hourly_runs WHERE job_id=? "
        "AND (superseded IS NULL OR superseded=0)",
        (job['id'],)).fetchone()[0] or 0
    target = job.get('target_quantity') or 0
    window, start, end, note = scheduled_window(job)
    off = 0
    if window:
        if now < start:
            end = start
        elif now < end:
            end = now
        if job.get('actual_end'):
            try:
                closed = datetime.fromisoformat(str(job['actual_end']).strip())
                if closed.tzinfo is not None:
                    closed = closed.replace(tzinfo=None)
                if closed < end:
                    end = closed
            except (TypeError, ValueError):
                pass
        off = off_time_minutes(conn, job.get('line_id'), start, end)
    if not window:
        allowed = target
    elif off >= window:
        allowed = 0
    else:
        allowed = int(round(target * (window - off) / float(window)))
    variance = None if allowed <= 0 else (actual - allowed) / float(allowed)
    return {'target': target, 'allowed': allowed, 'actual': actual,
            'off_minutes': off, 'window': window, 'note': note,
            'variance': variance}


def variance_refusal(conn, job, tolerance=None, now=None):
    """The sentence an operator has to answer, or None when within tolerance.

    One gate and two callers: the Telegram close in h_ending_job, and the floor
    end action when it exists. Keeping it here is what stops the gate being
    built twice (A45) and stops it being skippable from the tablet, which the
    2026-11-20 decisions require.

    A job with no schedule still gates. It compares against the raw target and
    says so in the sentence, because skipping the gate whenever the weekly
    schedule was never loaded would make the gate skippable by omission.

    A job with no target does not gate. That is a master-data defect, and
    forcing a reason for it would spend the operator's patience on the plant's
    mistake rather than on the record.
    """
    if job.get('completion_variance_reason'):
        return None
    v = variance_allowance(conn, job, now=now)
    if v['target'] <= 0:
        return None
    tol = _variance_tolerance(conn) if tolerance is None else tolerance
    if v['allowed'] <= 0:
        return (job['job_number'] + ' has ' + str(v['off_minutes'])
                + ' off-time minutes against a ' + str(v['window'] or 0)
                + ' minute window, so nothing can be compared. '
                'Please provide a reason to close.')
    if abs(v['variance']) <= tol:
        return None
    if v['window']:
        detail = (' after ' + str(v['off_minutes']) + ' off-time minutes: '
                  + str(v['allowed']) + ' allowed of ' + str(v['target']))
    else:
        detail = ' (' + v['note'] + ', so no allowance for off-time was applied)'
    return (job['job_number'] + ' is off target by '
            + format(v['variance'] * 100.0, '+.1f') + '%'
            + detail + '. Please provide a reason to close.')
def start_job(conn, job, line_id, user_id=None, source='telegram', reason=None):
    """Start a job on a line. Status and line event in one transaction.

    A crash cannot leave the job running with no event (A06), nor the line
    closed and unopened (A47).
    """
    refusal = check_start(conn, job, line_id=line_id)
    if refusal:
        return refusal
    now = datetime.now().isoformat()
    try:
        conn.execute(
            "UPDATE jobs SET status='running', actual_end=NULL, "
            "actual_start=COALESCE(actual_start, ?) WHERE id=?", (now, job['id']))
        db.transition_line_nc(conn, line_id, 'production', job_id=job['id'],
                              user_id=user_id, source=source, reason=reason)
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return None

def end_job(conn, job, line_id, user_id=None, source='floor', reason=None,
            now=None):
    """End one job and return its line to idle, in one transaction.

    The gate runs first and it is variance_refusal, the same function the
    Telegram close uses, so a job cannot be closed from the tablet without a
    reason when it is out of tolerance (A45, and the 2026-11-20 decision that
    the gate must not be skippable).

    A reason typed on a job that turns out to be within tolerance is kept and
    does not flag the job. Flagging it would make completion_flagged mean
    "somebody typed in the box" rather than "this job missed and here is why",
    and the flag is what the PDCA reads.

    The line must already be running this job. A line in lunch, maintenance or
    CIP is refused rather than silently closed, because the switch has to be
    thrown back first and the events are the record of that.
    """
    now = now or datetime.now()
    cur = db.current_line_event(conn, line_id)
    state = cur['state'] if cur else 'idle'
    if not cur or cur['state'] != 'production' or cur['job_id'] != job['id']:
        return (job['job_number'] + ' is not the job running on Line '
                + str(line_id) + '. The line is in ' + state
                + '. End or switch that first.')

    refusal = variance_refusal(conn, job, now=now)
    if refusal and not reason:
        return refusal

    existing_reason = job.get('completion_variance_reason')
    existing_flag = job.get('completion_flagged') or 0
    try:
        conn.execute(
            "UPDATE jobs SET status='completed', actual_end=?, "
            "completion_variance_reason=?, completion_flagged=? WHERE id=?",
            (now.isoformat(),
             reason if reason else existing_reason,
             1 if refusal else existing_flag,
             job['id']))
        db.transition_line_nc(conn, line_id, 'idle', user_id=user_id,
                              source=source,
                              reason='ended ' + job['job_number'])
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return None


def toggle_line_state(conn, line_id, state, user_id=None, source='floor'):
    """Throw one of lunch, maintenance or CIP, or throw it back.

    FLOOR-MODEL, The switches: lunch, maintenance and CIP are operator defined
    on and off switches against the running job. They exist to subtract time
    from the scheduled window and they are not a module and not a reason code.
    The duration comes from the moment the switch was thrown, because a toggle
    pair cannot lie about when it happened.

    Pressing the switch the line is already in returns it to production with
    the job id read off the open event. Pressing a different one moves the line
    to that state, carrying the same job id. No new storage and no new table:
    the events are the record, and variance_allowance already subtracts them.

    Returns a sentence for the floor either way, refusal or confirmation. A
    refusal names what it found rather than saying that it cannot.
    """
    state = (state or '').strip().lower()
    if state not in ('lunch', 'maintenance', 'cip'):
        return "That is not one of the three switches: " + str(state) + "."

    cur = db.current_line_event(conn, line_id)
    if not cur:
        return ("Nothing is running on Line " + str(line_id)
                + ", so there is no job to take time from.")
    if not cur['job_id']:
        return ("Line " + str(line_id) + " is " + str(cur['state'])
                + " with no job on it, so there is nothing to take time from.")

    job_id = cur['job_id']
    back = cur['state'] == state
    target = 'production' if back else state
    try:
        db.transition_line_nc(conn, line_id, target, job_id=job_id,
                              user_id=user_id, source=source)
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    if back:
        return "Line " + str(line_id) + " is back in production."
    return "Line " + str(line_id) + " is now in " + state + "."


def h_start_job(conn, s, text, user):
    job_no = parse_job_number(text)
    job, conf, alts = resolve_job(conn, job_no)
    if not job:
        return _explain_no_job(conn, job_no or text, conf, alts)

    refusal = check_start(conn, job)
    if refusal:
        return refusal

    db.reconcile_session(conn, s)

    if s.get('active_job_id') and s['active_job_id'] != job['id']:
        active = conn.execute(
            "SELECT job_number, line_id FROM jobs WHERE id=?", (s['active_job_id'],)).fetchone()
        if active:
            return ('You have ' + active['job_number'] + ' active on Line '
                    + str(active['line_id']) + '. End or pause it first, '
                    'or say status line ' + str(active['line_id']) + '.')

    conn.execute("UPDATE jobs SET status='running', actual_end=NULL WHERE id=?",
                 (job['id'],))
    conn.commit()

    s.set('pending_job_id', job['id'])
    s.set('line_id', job['line_id'])
    s.set('state', 'awaiting_start_minutes')
    s.save()

    note = _fuzzy_note(job_no, conf, job)
    return f"Starting {job['job_number']}{note}. Minutes into the current hour when it started?"


def cont_start_minutes(conn, s, text, user):
    mins = parse_int(text)
    if mins is None:
        return "Just a number, please. Minutes into hour?"

    job_id = s.get('pending_job_id')
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        s.set('state', 'idle')
        s.set('pending_job_id', None)
        s.save()
        return "Job lost. Please start over."
    job = dict(job)

    conn.execute(
        "UPDATE jobs SET status='running', actual_end=NULL, "
        "actual_start=COALESCE(actual_start, ?) WHERE id=?",
        (datetime.now().isoformat(), job_id))
    conn.commit()

    line_id = db.derive_line(conn, job, s, user)
    db.transition_line(conn, line_id, 'production', job_id=job_id,
                       user_id=user['id'] if user else None)

    s.set('active_job_id', job_id)
    s.set('pending_job_id', None)
    s.set('state', 'idle')
    s.set('start_offset', float(mins))
    s.save()

    return (f"Started {job['job_number']} at +{mins} min into the hour. "
            f"Log the first hour when ready.")


def h_ending_job(conn, s, text, user):
    jobs_found = parse_all_job_numbers(text)
    ending_no = jobs_found[0] if jobs_found else None
    target_no = jobs_found[1] if len(jobs_found) > 1 else None

    if ending_no:
        job, conf, alts = resolve_job(conn, ending_no)
        if not job:
            return _explain_no_job(conn, ending_no, conf, alts)
    elif s.get('active_job_id'):
        r = conn.execute("SELECT * FROM jobs WHERE id=?",
                         (s['active_job_id'],)).fetchone()
        job = dict(r) if r else None
        conf = 'exact'
    else:
        return "Which job is ending? Say: 'end WO-2026-001'."
    if not job:
        return "Job not found."

    # Variance gate: refuse to close without a reason outside tolerance.
    refusal = variance_refusal(conn, job)
    if refusal:
        s.set('state', 'awaiting_variance_reason')
        s.set('pending_job_id', job['id'])
        s.set('pending_target_job_id', None)
        s.save()
        return refusal

    line_id = db.derive_line(conn, job, s, user)
    cur = db.current_line_event(conn, line_id)
    if cur and cur['state'] != 'production':
        return (f"Line {line_id} is in {cur['state'].upper()}, not production. "
                f"End that state first.")

    target_id = None
    if target_no:
        tj, tconf, talts = resolve_job(conn, target_no)
        if not tj:
            return _explain_no_job(conn, target_no, tconf, talts)
        target_id = tj['id']

    s.set('pending_job_id', job['id'])
    s.set('pending_target_job_id', target_id)
    s.set('state', 'awaiting_end_minutes')
    s.save()

    note = _fuzzy_note(ending_no, conf, job)
    return (f"Ending {job['job_number']}{note}. Minutes into the current hour "
            f"so far? (say 0 if at the top)")


def cont_end_minutes(conn, s, text, user):
    mins = parse_int(text)
    if mins is None:
        return "Just a number, please. Minutes into the hour?"

    job_id = s.get('pending_job_id')
    target_id = s.get('pending_target_job_id')
    job = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    if not job:
        s.set('state', 'idle')
        s.set('pending_job_id', None)
        s.set('pending_target_job_id', None)
        s.save()
        return "Job lost. Nothing was closed."

    job = dict(job)
    now = datetime.now()
    hour_start = now.replace(minute=0, second=0, microsecond=0)
    end_iso = (hour_start + timedelta(minutes=mins)).isoformat()

    conn.execute(
        "UPDATE jobs SET status='completed', actual_end=? WHERE id=?",
        (end_iso, job_id))
    conn.commit()

    line_id = db.derive_line(conn, job, s, user)
    db.transition_line(conn, line_id, 'idle',
                       user_id=user['id'] if user else None)

    s.set('pending_job_id', None)
    s.set('state', 'idle')
    s.save()

    base = f"{job['job_number']} ended at +{mins} min."
    if target_id:
        tj = conn.execute("SELECT job_number FROM jobs WHERE id=?",
                          (target_id,)).fetchone()
        if tj:
            return (f"{base} Next: say 'changeover job {job['job_number']} "
                    f"to {tj['job_number']}' to start the changeover.")
    return base + " Line now idle."


def h_pause_job(conn, s, text, user):
    job_no = parse_job_number(text)
    if job_no:
        job, conf, alts = resolve_job(conn, job_no)
        if not job:
            return _explain_no_job(conn, job_no, conf, alts)
    elif s.get('active_job_id'):
        r = conn.execute("SELECT * FROM jobs WHERE id=?",
                         (s['active_job_id'],)).fetchone()
        job = dict(r) if r else None
        conf = 'exact'
    else:
        return "Which job to pause?"
    if not job:
        return "Job not found."
    if job.get('status') != 'running':
        return f"{job['job_number']} is not running (status: {job.get('status') or 'unknown'})."

    conn.execute("UPDATE jobs SET status='paused' WHERE id=?", (job['id'],))
    conn.commit()

    line_id = db.derive_line(conn, job, s, user)
    db.transition_line(conn, line_id, 'idle',
                       reason=f"paused {job['job_number']}",
                       user_id=user['id'] if user else None)

    s.set('active_job_id', None)
    s.save()
    return (f"{job['job_number']} paused. Line {line_id} now IDLE. "
            f"Resume with 'resume {job['job_number']}'.")


def h_resume_job(conn, s, text, user):
    job_no = parse_job_number(text)
    job, conf, alts = resolve_job(conn, job_no)
    if not job:
        return _explain_no_job(conn, job_no or text, conf, alts)
    if job.get('status') not in ('paused', 'completed'):
        return (f"{job['job_number']} is not paused or completed "
                f"(status: {job.get('status') or 'unknown'}).")

    conn.execute("UPDATE jobs SET status='running', actual_end=NULL WHERE id=?",
                 (job['id'],))
    conn.commit()

    line_id = db.derive_line(conn, job, s, user)
    db.transition_line(conn, line_id, 'production', job_id=job['id'],
                       user_id=user['id'] if user else None)

    s.set('active_job_id', job['id'])
    s.set('shift', None)
    s.set('shift_hour', None)
    s.save()

    note = _fuzzy_note(job_no, conf, job)
    jh = next_job_hour(conn, job['id'])
    return f"{job['job_number']}{note} resumed. Job-hour continues at {jh:.1f}."


def cont_variance_reason(conn, s, text, user):
    reason = (text or '').strip()
    if not reason:
        return "Please provide a reason to close the job."
    # Agreed 2026-11-14: refuse command-like input as a variance reason.
    # A trapped operator typing "changeover WO-X" must not have it saved as
    # a reason. Offer cancel.
    _cmd_verbs = ('changeover', 'end', 'start', 'record', 'running', 'status',
                  'note', 'relog', 'pause', 'resume', 'handover', 'maintenance',
                  'help')
    _first = reason.lower().split()[0] if reason.split() else ''
    if _first in _cmd_verbs or reason.lower().startswith('taking over'):
        return ("That looks like a command, not a reason. "
                "Give a brief reason, or say 'cancel'.")

    job_id = s.get('pending_job_id')
    if not job_id:
        s.set('state', 'idle')
        s.save()
        return "Session lost track of the job. Please try 'end WO-...' again."

    conn.execute(
        "UPDATE jobs SET completion_variance_reason=?, completion_flagged=1 WHERE id=?",
        (reason, job_id))
    conn.commit()

    job_row = conn.execute("SELECT job_number FROM jobs WHERE id=?", (job_id,)).fetchone()
    job_no = job_row['job_number'] if job_row else None

    s.set('state', 'idle')
    s.set('pending_job_id', None)
    s.save()

    if not job_no:
        return "Job closed and flagged. Please run 'status line N' to confirm."
    return h_ending_job(conn, s, f"end {job_no}", user)
