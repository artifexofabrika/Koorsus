PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS metrics (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT NOT NULL UNIQUE,
  unit TEXT NOT NULL,
  direction TEXT NOT NULL CHECK (direction IN ('higher_better','lower_better')),
  baseline_value REAL,
  target_value REAL,
  target_date TEXT,
  created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  metric_id INTEGER NOT NULL REFERENCES metrics(id),
  value REAL NOT NULL,
  note TEXT,
  recorded_at TEXT NOT NULL DEFAULT (datetime('now')),
  line TEXT,
  period TEXT,
  source TEXT,
  raw_text TEXT
);

CREATE INDEX IF NOT EXISTS idx_entries_metric_time ON entries(metric_id, recorded_at);

INSERT OR IGNORE INTO metrics (name, unit, direction) VALUES
  ('line speed', 'parts/hour', 'higher_better'),
  ('changeover time', 'minutes', 'lower_better'),
  ('scrap rate', 'percent', 'lower_better'),
  ('downtime', 'minutes', 'lower_better'),
  ('OEE', 'percent', 'higher_better'),
  ('on-time delivery', 'percent', 'higher_better');
