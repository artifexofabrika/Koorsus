"""bot/db.py — Database access layer for the Myarra bot.

WHY THIS FILE EXISTS
bot_v2.py accumulated to 1400+ lines across five instances and dozens of
patches. Every patch risked silent anchor failures. This module is the
foundation of a clean modular rewrite: one file per concern, each small
enough to rewrite whole. bot_v2.py remains on disk and running until the
new package survives a full demo day.

Agreed 2026-11-07: modular rewrite. bot/db.py first.

PUBLIC INTERFACE
    Session, get_user, ensure_schema
    ideal_rate, case_pack, case_count, unit_label, case_label, setting
    current_line_event, close_line_event, transition_line, derive_line
    parse_scrap, write_hour

No other module should import sqlite3 or open its own connection.
"""
import os
import re
import sqlite3
from datetime import datetime

DB_PATH = os.environ.get("MYARRA_DB", "/mnt/lake/myarra.db")

UNACC_THRESHOLD = 5.0

# Agreed 2026-11-07: override_reason is in the schema and must be in the
# Python list, or session saves silently drop it. This was a live bug.
SESSION_FIELDS = [
    'state', 'active_job_id', 'active_changeover_id',
    'pending_job_id', 'pending_target_job_id',
    'start_offset', 'pending_step_idx',
    'shift', 'shift_hour', 'pending_text', 'co_total_min',
    'line_id', 'override_reason',
]


# ============================================================
# Session
# ============================================================

class Session:
    def __init__(self, conn, chat_id):
        self.conn = conn
        self.chat_id = str(chat_id)
        self.data = {f: None for f in SESSION_FIELDS}
        self.data['state'] = 'idle'
        row = conn.execute("SELECT * FROM bot_sessions WHERE chat_id=?", (self.chat_id,)).fetchone()
        if row:
            d = dict(row)
            for f in SESSION_FIELDS:
                if d.get(f) is not None:
                    self.data[f] = d[f]

    def get(self, k): return self.data.get(k)
    def set(self, k, v): self.data[k] = v
    def __getitem__(self, k): return self.data.get(k)
    def __setitem__(self, k, v): self.data[k] = v
    def __contains__(self, k): return k in self.data

    def save(self):
        vals = [self.data[f] for f in SESSION_FIELDS]
        exists = self.conn.execute(
            "SELECT 1 FROM bot_sessions WHERE chat_id=?", (self.chat_id,)
        ).fetchone()
        now = datetime.now().isoformat()
        if exists:
            sets = ', '.join(f"{f}=?" for f in SESSION_FIELDS)
            self.conn.execute(
                f"UPDATE bot_sessions SET {sets}, updated_at=? WHERE chat_id=?",
                vals + [now, self.chat_id])
        else:
            cols = ['chat_id'] + SESSION_FIELDS + ['updated_at']
            self.conn.execute(
                f"INSERT INTO bot_sessions ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                [self.chat_id] + vals + [now])
        self.conn.commit()

    def clear(self):
        self.conn.execute("DELETE FROM bot_sessions WHERE chat_id=?", (self.chat_id,))
        self.conn.commit()
        self.data = {f: None for f in SESSION_FIELDS}
        self.data['state'] = 'idle'


def get_user(conn, user_id):
    row = conn.execute("SELECT * FROM users WHERE id=? AND active=1", (user_id,)).fetchone()
    return dict(row) if row else None


# ============================================================
# Schema setup
# ============================================================

def ensure_schema(conn):
    """Add columns that may be missing on older databases."""
    # hourly_runs
    hr_cols = [r[1] for r in conn.execute("PRAGMA table_info(hourly_runs)").fetchall()]
    for col, typ in [('superseded', 'INTEGER DEFAULT 0'), ('override_reason', 'TEXT')]:
        if col not in hr_cols:
            conn.execute(f"ALTER TABLE hourly_runs ADD COLUMN {col} {typ}")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY,
            user_id INTEGER,
            raw_text TEXT,
            created_at TEXT
        )
    """)
    # bot_sessions
    sess_cols = [r[1] for r in conn.execute("PRAGMA table_info(bot_sessions)").fetchall()]
    for col, typ in [('shift_hour', 'INTEGER'), ('pending_text', 'TEXT'),
                     ('co_total_min', 'REAL'), ('pending_target_job_id', 'INTEGER'),
                     ('line_id', 'INTEGER'), ('override_reason', 'TEXT')]:
        if col not in sess_cols:
            conn.execute(f"ALTER TABLE bot_sessions ADD COLUMN {col} {typ}")
    conn.commit()


# ============================================================
# Settings helpers
# ============================================================

def setting(conn, key, default):
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return r['value'] if r else default


def unit_label(conn): return setting(conn, 'unit_label', 'units')
def case_label(conn): return setting(conn, 'case_label', 'cases')


# ============================================================
# SKU helpers
# ============================================================

def ideal_rate(conn, line_id, sku_id):
    r = conn.execute(
        "SELECT ideal_rate FROM line_sku_rates WHERE line_id=? AND sku_id=?",
        (line_id, sku_id)).fetchone()
    return r['ideal_rate'] if r else 600.0


def case_pack(conn, sku_id):
    r = conn.execute("SELECT case_pack FROM skus WHERE id=?", (sku_id,)).fetchone()
    return (r['case_pack'] or 1) if r else 1


def case_count(units, cp):
    return int(units // cp) if cp else units


# ============================================================
# Scrap parsing
# ============================================================

def parse_scrap(text):
    """Extract scrap from 'N scrap|bad|reject|rework'. Default 0."""
    m = re.search(r'(\d+)\s*(?:scrap|bad|reject|rework)', text, re.IGNORECASE)
    return int(m.group(1)) if m else 0


# ============================================================
# Line events
# ============================================================

def current_line_event(conn, line_id):
    return conn.execute(
        "SELECT * FROM line_events WHERE line_id=? AND ended_at IS NULL "
        "ORDER BY started_at DESC LIMIT 1",
        (line_id,)).fetchone()


def close_line_event(conn, event_id, end_iso=None):
    conn.execute(
        "UPDATE line_events SET ended_at=? WHERE id=?",
        (end_iso or datetime.now().isoformat(), event_id))
    conn.commit()


def transition_line(conn, line_id, new_state, job_id=None, co_event_id=None,
                    reason=None, user_id=None, source='telegram', end_at=None):
    cur = current_line_event(conn, line_id)
    if cur and cur['state'] == new_state:
        if new_state == 'production' and cur['job_id'] == job_id:
            return cur['id']
        if new_state == 'changeover' and cur['co_event_id'] == co_event_id:
            return cur['id']
        if new_state in ('lunch', 'cip', 'maintenance', 'idle', 'unscheduled'):
            return cur['id']
    if cur:
        close_line_event(conn, cur['id'], end_iso=end_at)
    start = end_at or datetime.now().isoformat()
    ins = conn.execute("""
        INSERT INTO line_events
        (line_id, state, started_at, ended_at, job_id, co_event_id, reason, user_id, source)
        VALUES (?, ?, ?, NULL, ?, ?, ?, ?, ?)
    """, (line_id, new_state, start, job_id, co_event_id, reason, user_id, source))
    conn.commit()
    return ins.lastrowid


def derive_line(conn, job, sess, user):
    if job and job.get('line_id'):
        sess.set('line_id', job['line_id'])
        return job['line_id']
    if sess.get('line_id'):
        return sess['line_id']
    if user and user.get('line_id'):
        return user['line_id']
    return 1


# ============================================================
# Write path
# ============================================================

def write_hour(conn, job, shift, period, units, duration, user_id, raw_text,
               jh_start, jh_end, unacc, dts, override_reason=None,
               superseded=0, scrap_units=0):
    """Insert one hourly_run. scrap_units is total produced that was bad."""
    cur = conn.execute("""
        INSERT INTO hourly_runs
        (job_id, line_id, shift, period, recorded_at, units_filled, raw_text,
         duration_min, phase, job_hour_start, job_hour_end, user_id, flagged,
         source, override_reason, superseded, scrap_units)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (job['id'], job['line_id'], shift, period, datetime.now().isoformat(),
          units, raw_text, duration, 'run', jh_start, jh_end,
          user_id, 1 if unacc > UNACC_THRESHOLD else 0, 'telegram',
          override_reason, superseded, scrap_units))
    for d in dts:
        conn.execute(
            "INSERT INTO downtime_events (run_id, station, reason, minutes) "
            "VALUES (?,?,?,?)",
            (cur.lastrowid, d['station'], d['reason'], d['minutes']))
    conn.commit()
    return cur.lastrowid


def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn
