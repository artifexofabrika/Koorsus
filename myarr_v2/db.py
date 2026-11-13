# Myarra Database Module
# Canonical connection and bootstrap.
# Agreed 2026-11-13: replaces the stale partial init_db and init_users_table.
# tools/schema.sql is the sole source of truth for table structure.
import os
import sqlite3

DB_PATH = os.environ.get('MYARRA_DB', '/mnt/lake/myarra.db')

_SCHEMA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'tools', 'schema.sql')

# Columns whose absence means the database predates the schema extraction.
# IF NOT EXISTS cannot add columns, so init_db refuses rather than skipping.
_REQUIRED_COLUMNS = {
    'hourly_runs': ['scrap_units', 'duration_min', 'sku_id', 'source',
                    'superseded', 'override_reason',
                    'job_hour_start', 'job_hour_end'],
    'jobs': ['scheduled_start', 'scheduled_end', 'actual_start',
             'actual_end', 'handover_notes'],
    'line_events': ['maintenance_event_id'],
}

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _check_old_schema(conn):
    missing = []
    for table, required in _REQUIRED_COLUMNS.items():
        cols = {r[1] for r in conn.execute('PRAGMA table_info(' + table + ')').fetchall()}
        if not cols:
            continue
        for col in required:
            if col not in cols:
                missing.append((table, col))
    return missing

def init_db():
    if not os.path.exists(_SCHEMA_FILE):
        raise FileNotFoundError('Schema file not found at ' + _SCHEMA_FILE)
    conn = get_db_connection()
    try:
        missing = _check_old_schema(conn)
        if missing:
            details = ', '.join(t + '.' + c for t, c in missing)
            raise RuntimeError('Existing database uses a stale schema (missing: '
                               + details + '). Refusing to bootstrap.')
        with open(_SCHEMA_FILE, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()
    print('Schema applied from ' + _SCHEMA_FILE + ' to ' + DB_PATH + '.')

if __name__ == '__main__':
    init_db()
