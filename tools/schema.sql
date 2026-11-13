-- Myarra canonical schema. Extracted from live DB 2026-11-13.
-- IF NOT EXISTS added for idempotence. Views are in views.py.

CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY,
        user_id INTEGER,
        raw_text TEXT,
        created_at TEXT
    );
CREATE TABLE IF NOT EXISTS bot_sessions (chat_id TEXT PRIMARY KEY, state TEXT NOT NULL,
    active_job_id INTEGER, active_changeover_id INTEGER, pending_job_id INTEGER,
    start_offset REAL, pending_step_idx INTEGER, shift TEXT, shift_hour INTEGER,
    pending_text TEXT, co_total_min REAL, updated_at TEXT, pending_target_job_id INTEGER, line_id INTEGER, override_reason TEXT);
CREATE TABLE IF NOT EXISTS co_event_changes (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL,
    component_type_id INTEGER NOT NULL,
    from_value TEXT,
    to_value TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS co_event_steps (id INTEGER PRIMARY KEY, event_id INTEGER, step_id INTEGER,
    actual_min REAL NOT NULL, note TEXT);
CREATE TABLE IF NOT EXISTS co_events (id INTEGER PRIMARY KEY, procedure_id INTEGER, line_id INTEGER,
    started_at TEXT, ended_at TEXT, aggregate_actual_min REAL, units_to_mixer INTEGER,
    operator TEXT, raw_text TEXT, source TEXT DEFAULT 'seed',
    from_job_number TEXT, to_job_number TEXT, from_job_id INTEGER, to_job_id INTEGER,
    user_id INTEGER, notes TEXT);
CREATE TABLE IF NOT EXISTS co_procedures_v2 (id INTEGER PRIMARY KEY, line_id INTEGER,
    from_sku_id INTEGER, to_sku_id INTEGER, name TEXT,
    aggregate_standard_min REAL NOT NULL, UNIQUE (line_id, from_sku_id, to_sku_id));
CREATE TABLE IF NOT EXISTS co_steps_v2 (id INTEGER PRIMARY KEY, procedure_id INTEGER,
    seq INTEGER NOT NULL, step_name TEXT NOT NULL, station TEXT, standard_min REAL NOT NULL);
CREATE TABLE IF NOT EXISTS component_types (id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
    is_serial INTEGER DEFAULT 0, default_swap_min REAL);
CREATE TABLE IF NOT EXISTS downtime_events (id INTEGER PRIMARY KEY, run_id INTEGER, station TEXT,
    reason TEXT, minutes REAL, note TEXT);
CREATE TABLE IF NOT EXISTS experiment_actions (
    id INTEGER PRIMARY KEY,
    experiment_id INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    description TEXT NOT NULL,
    owner TEXT,
    due_date TEXT,
    status TEXT DEFAULT 'open',
    completed_at TEXT
);
CREATE TABLE IF NOT EXISTS experiments (id INTEGER PRIMARY KEY, title TEXT, department TEXT,
    line_id INTEGER, status TEXT DEFAULT 'active', target_step_name TEXT,
    start_date TEXT, standard_min REAL, target_goal_min REAL, root_cause TEXT,
    fishbone_category TEXT, action_plan TEXT, action_owner TEXT, notes TEXT, pdca_id TEXT, created_at TEXT, updated_at TEXT, problem_severity INTEGER, pdca_owner TEXT, management_sponsor TEXT, team_members TEXT, departments_involved TEXT, current_condition TEXT, target_condition TEXT, hypothesis TEXT, target_date TEXT, target_state_reached INTEGER DEFAULT 0, how_known_solved TEXT, new_problems_created TEXT, notes_on_back TEXT, pri_time INTEGER, pri_impact INTEGER, pri_resources INTEGER, pri_magnitude INTEGER, pri_cost INTEGER, measurement_type TEXT, measurement_config TEXT, affected_skus TEXT, baseline_value REAL, baseline_frozen_at TEXT, closed_at TEXT, close_reason TEXT, parent_pdca_id INTEGER);
CREATE TABLE IF NOT EXISTS fishbone_causes (
    id INTEGER PRIMARY KEY,
    experiment_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    cause_text TEXT NOT NULL,
    seq INTEGER DEFAULT 0,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS hourly_runs (id INTEGER PRIMARY KEY, job_id INTEGER, line_id INTEGER,
    sku_id INTEGER, shift TEXT, period TEXT, phase TEXT DEFAULT 'run',
    recorded_at TEXT, units_filled INTEGER NOT NULL, scrap_units INTEGER DEFAULT 0,
    duration_min INTEGER DEFAULT 60, operator TEXT, raw_text TEXT,
    source TEXT DEFAULT 'seed', job_hour_start REAL, job_hour_end REAL,
    user_id INTEGER, notes TEXT, flagged INTEGER DEFAULT 0, superseded INTEGER DEFAULT 0, override_reason TEXT);
CREATE TABLE IF NOT EXISTS jobs (id INTEGER PRIMARY KEY, job_number TEXT UNIQUE NOT NULL,
    customer_id INTEGER, sku_id INTEGER, line_id INTEGER, target_quantity INTEGER,
    scheduled_start TEXT, scheduled_end TEXT, actual_start TEXT, actual_end TEXT,
    status TEXT DEFAULT 'scheduled', handover_notes TEXT, completion_variance_reason TEXT, completion_flagged INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS line_events (
    id INTEGER PRIMARY KEY,
    line_id INTEGER NOT NULL,
    state TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    job_id INTEGER,
    co_event_id INTEGER,
    reason TEXT,
    notes TEXT,
    user_id INTEGER,
    source TEXT DEFAULT 'manual'
, maintenance_event_id INTEGER);
CREATE TABLE IF NOT EXISTS line_sku_rates (line_id INTEGER, sku_id INTEGER, ideal_rate REAL NOT NULL,
    PRIMARY KEY (line_id, sku_id));
CREATE TABLE IF NOT EXISTS line_sku_stations (
    id INTEGER PRIMARY KEY,
    line_id INTEGER NOT NULL,
    sku_id INTEGER NOT NULL,
    seq INTEGER NOT NULL,
    station TEXT NOT NULL,
    UNIQUE (line_id, sku_id, seq)
);
CREATE TABLE IF NOT EXISTS lines (id INTEGER PRIMARY KEY, name TEXT NOT NULL, format_type TEXT);
CREATE TABLE IF NOT EXISTS maintenance_events (
    id INTEGER PRIMARY KEY,
    line_id INTEGER NOT NULL,
    job_id INTEGER,
    station TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    aggregate_actual_min REAL,
    category TEXT DEFAULT 'unplanned',
    symptom TEXT,
    resolution TEXT,
    parts_used TEXT,
    technician TEXT,
    called_by TEXT,
    reason_code TEXT,
    notes TEXT,
    source TEXT DEFAULT 'manual',
    user_id INTEGER,
    raw_text TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT
);
CREATE TABLE IF NOT EXISTS shift_handovers (
    id INTEGER PRIMARY KEY,
    job_id INTEGER NOT NULL,
    line_id INTEGER,
    from_user_id INTEGER,
    to_user_id INTEGER,
    notes TEXT,
    open_issues TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    taken_at TEXT
);
CREATE TABLE IF NOT EXISTS shift_reconciliations (
        id INTEGER PRIMARY KEY,
        line_id INTEGER NOT NULL,
        shift_date TEXT NOT NULL,
        shift_code TEXT NOT NULL,
        usable_min REAL NOT NULL,
        actual_units INTEGER DEFAULT 0,
        scrap_units INTEGER DEFAULT 0,
        downtime_min REAL DEFAULT 0,
        production_time_min REAL DEFAULT 0,
        scrap_time_min REAL DEFAULT 0,
        residual_min REAL DEFAULT 0,
        explanation TEXT,
        created_at TEXT NOT NULL
    );
CREATE TABLE IF NOT EXISTS sku_bom (sku_id INTEGER, component_type_id INTEGER,
    component_value TEXT NOT NULL, PRIMARY KEY (sku_id, component_type_id));
CREATE TABLE IF NOT EXISTS skus (id INTEGER PRIMARY KEY, part_number TEXT UNIQUE NOT NULL,
    description TEXT, case_pack INTEGER DEFAULT 1, active INTEGER DEFAULT 1);
CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, role TEXT DEFAULT 'Operator',
    line_id INTEGER, telegram_id TEXT UNIQUE, active INTEGER DEFAULT 1);
CREATE INDEX IF NOT EXISTS idx_co_event_changes_event ON co_event_changes(event_id);
CREATE INDEX IF NOT EXISTS idx_co_event_changes_type ON co_event_changes(component_type_id);
CREATE INDEX IF NOT EXISTS idx_fishbone_exp ON fishbone_causes(experiment_id, category);
CREATE INDEX IF NOT EXISTS idx_handovers_job ON shift_handovers(job_id, created_at);
CREATE INDEX IF NOT EXISTS idx_line_events_line_time ON line_events(line_id, started_at);
CREATE INDEX IF NOT EXISTS idx_line_events_open ON line_events(line_id) WHERE ended_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_maint_line_time ON maintenance_events(line_id, started_at);
