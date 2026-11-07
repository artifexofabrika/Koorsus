"""Myarra views — the shared measure layer for /reconciliation and Stage C.

WHY THIS FILE EXISTS
The same numbers are consumed by /reconciliation today and by /ask in
Stage D. Inline SQL in Flask would drift between the two consumers.
Views return per-line-per-day components only; ratios are computed by
the consumer (recon.py). Agreed 2026-11-06.

UNSCHEDULED IS A PLACEHOLDER (agreed 2026-11-06)
The OEE denominator includes unscheduled_min, currently 0 because no
source table exists yet. It is reserved for unaccounted availability
losses once they have a source. Until then this is conditional OEE.
Unaccounted minutes have their own view: v_unaccounted_by_line_day.

THE COALESCE SCAR (do not simplify)
hourly_runs.sku_id was null on all 285 demo rows when this view was
first written; the join through jobs.sku_id was the workaround. The
generator now writes sku_id at source (commit 372c697), but the
COALESCE stays as belt-and-braces for any install whose generator
predates that fix. A future editor who "cleans up" the join will
break those installs. Leave it.

Run once: python3 views.py. Idempotent: drops and recreates all nine.
"""
from db import get_db_connection

V_OEE = """
CREATE VIEW v_oee_by_line_day AS
WITH
line_days AS (
    SELECT line_id, date(recorded_at) AS day FROM hourly_runs WHERE recorded_at IS NOT NULL
    UNION
    SELECT line_id, date(started_at) AS day FROM co_events WHERE started_at IS NOT NULL
    UNION
    SELECT line_id, date(started_at) AS day FROM maintenance_events WHERE started_at IS NOT NULL
    UNION
    SELECT line_id, date(started_at) AS day FROM line_events WHERE started_at IS NOT NULL
),
prod AS (
    SELECT r.line_id, date(r.recorded_at) AS day,
           SUM(r.duration_min) AS production_min,
           SUM(r.units_filled) AS actual_units,
           SUM(COALESCE(r.scrap_units, 0)) AS scrap_units,
           SUM(r.duration_min * COALESCE(lsr.ideal_rate, 0) / 60.0) AS expected_units
    FROM hourly_runs r
    LEFT JOIN jobs j ON j.id = r.job_id
    LEFT JOIN line_sku_rates lsr
           ON lsr.line_id = r.line_id
          AND lsr.sku_id  = COALESCE(r.sku_id, j.sku_id)
    WHERE r.recorded_at IS NOT NULL
    GROUP BY r.line_id, date(r.recorded_at)
),
co AS (
    SELECT line_id, date(started_at) AS day,
           SUM(aggregate_actual_min) AS changeover_min
    FROM co_events
    WHERE started_at IS NOT NULL AND aggregate_actual_min IS NOT NULL
    GROUP BY line_id, date(started_at)
),
mt AS (
    SELECT line_id, date(started_at) AS day,
           SUM(aggregate_actual_min) AS unplanned_maint_min
    FROM maintenance_events
    WHERE started_at IS NOT NULL
      AND category = 'unplanned'
      AND aggregate_actual_min IS NOT NULL
    GROUP BY line_id, date(started_at)
),
le AS (
    SELECT line_id, date(started_at) AS day,
           SUM(CASE WHEN state = 'idle' THEN
               (julianday(COALESCE(ended_at, datetime('now'))) - julianday(started_at)) * 24 * 60
           ELSE 0 END) AS idle_min
    FROM line_events
    WHERE started_at IS NOT NULL
    GROUP BY line_id, date(started_at)
)
SELECT
    ld.line_id,
    ld.day,
    COALESCE(p.production_min, 0)      AS production_min,
    COALESCE(c.changeover_min, 0)      AS changeover_min,
    COALESCE(m.unplanned_maint_min, 0) AS unplanned_maint_min,
    COALESCE(l.idle_min, 0)            AS idle_min,
    0                                  AS unscheduled_min,
    COALESCE(p.actual_units, 0)        AS actual_units,
    COALESCE(p.scrap_units, 0)         AS scrap_units,
    COALESCE(p.expected_units, 0)      AS expected_units
FROM line_days ld
LEFT JOIN prod p ON p.line_id = ld.line_id AND p.day = ld.day
LEFT JOIN co c   ON c.line_id = ld.line_id AND c.day = ld.day
LEFT JOIN mt m   ON m.line_id = ld.line_id AND m.day = ld.day
LEFT JOIN le l   ON l.line_id = ld.line_id AND l.day = ld.day
"""

V_OP = """
CREATE VIEW v_operator_perf_by_line_day AS
SELECT line_id, day,
       production_min + changeover_min + idle_min + unscheduled_min AS operator_available_min,
       production_min, changeover_min, unplanned_maint_min,
       idle_min, unscheduled_min,
       actual_units, expected_units, scrap_units
FROM v_oee_by_line_day
"""

V_STAGE_C = """
CREATE VIEW IF NOT EXISTS v_changeover_by_station AS
SELECT
    e.line_id,
    date(e.started_at) AS day,
    e.id AS co_event_id,
    p.name AS procedure_name,
    e.from_job_number,
    e.to_job_number,
    s.station,
    s.step_name,
    s.standard_min,
    es.actual_min,
    ROUND(es.actual_min - s.standard_min, 1) AS variance_min,
    CASE WHEN s.standard_min > 0
         THEN ROUND((es.actual_min - s.standard_min) / s.standard_min, 3)
         ELSE NULL END AS variance_pct
FROM co_events e
JOIN co_procedures_v2 p ON p.id = e.procedure_id
JOIN co_event_steps es ON es.event_id = e.id
JOIN co_steps_v2 s ON s.id = es.step_id
WHERE e.started_at IS NOT NULL
  AND e.aggregate_actual_min IS NOT NULL
  AND s.standard_min IS NOT NULL;


CREATE VIEW IF NOT EXISTS v_oee_daily AS
SELECT * FROM v_oee_by_line_day;

CREATE VIEW IF NOT EXISTS v_operator_performance AS
SELECT * FROM v_operator_perf_by_line_day;

CREATE VIEW IF NOT EXISTS v_production_vs_standard AS
SELECT line_id, day,
       actual_units, expected_units,
       (actual_units - expected_units) AS variance_units,
       CASE WHEN expected_units > 0
            THEN 1.0*actual_units/expected_units ELSE NULL END AS pct_vs_standard
FROM v_oee_by_line_day;

CREATE VIEW IF NOT EXISTS v_unaccounted_by_line_day AS
WITH per_run AS (
    SELECT r.line_id, date(r.recorded_at) AS day,
           r.duration_min,
           CASE WHEN COALESCE(lsr.ideal_rate, 0) > 0
                THEN r.duration_min - (r.units_filled * 60.0 / lsr.ideal_rate)
                ELSE NULL END AS gap_min
    FROM hourly_runs r
    LEFT JOIN jobs j ON j.id = r.job_id
    LEFT JOIN line_sku_rates lsr
           ON lsr.line_id = r.line_id
          AND lsr.sku_id  = COALESCE(r.sku_id, j.sku_id)
    WHERE r.recorded_at IS NOT NULL
)
SELECT line_id, day,
       SUM(duration_min) AS scheduled_prod_min,
       ROUND(SUM(gap_min), 1) AS unaccounted_min,
       CASE WHEN SUM(duration_min) > 0
            THEN ROUND(SUM(gap_min)/SUM(duration_min), 3) ELSE NULL END AS unaccounted_pct
FROM per_run
GROUP BY line_id, day;

CREATE VIEW IF NOT EXISTS v_changeover_variance AS
SELECT e.line_id, date(e.started_at) AS day,
       e.procedure_id,
       p.name AS procedure_name,
       p.aggregate_standard_min AS standard_min,
       ROUND(AVG(e.aggregate_actual_min), 1) AS actual_min,
       COUNT(*) AS event_count,
       ROUND(AVG(e.aggregate_actual_min) - p.aggregate_standard_min, 1) AS variance_min,
       ROUND((AVG(e.aggregate_actual_min) - p.aggregate_standard_min) / p.aggregate_standard_min, 3) AS variance_pct
FROM co_events e
JOIN co_procedures_v2 p ON p.id = e.procedure_id
WHERE e.started_at IS NOT NULL
  AND e.aggregate_actual_min IS NOT NULL
  AND p.aggregate_standard_min IS NOT NULL
  AND p.aggregate_standard_min > 0
GROUP BY e.line_id, date(e.started_at), e.procedure_id, p.name, p.aggregate_standard_min;

CREATE VIEW IF NOT EXISTS v_maintenance_by_station AS
SELECT line_id, station, date(started_at) AS day,
       COUNT(*) AS event_count,
       ROUND(SUM(aggregate_actual_min), 1) AS total_min,
       ROUND(AVG(aggregate_actual_min), 1) AS avg_min,
       GROUP_CONCAT(DISTINCT category) AS categories,
       MAX(reason_code) AS latest_reason_code
FROM maintenance_events
WHERE started_at IS NOT NULL
GROUP BY line_id, station, date(started_at);

CREATE VIEW IF NOT EXISTS v_pdca_trend AS
SELECT e.id AS experiment_id, e.pdca_id, e.title,
       date(ev.started_at) AS day,
       ROUND(AVG(es.actual_min), 2) AS avg_actual_min,
       COUNT(*) AS n_samples
FROM experiments e
JOIN co_steps_v2 s ON s.step_name = e.target_step_name
JOIN co_event_steps es ON es.step_id = s.id
JOIN co_events ev ON ev.id = es.event_id
WHERE e.target_step_name IS NOT NULL
  AND ev.started_at IS NOT NULL
GROUP BY e.id, e.pdca_id, e.title, date(ev.started_at);
"""

# ORDER MATTERS. Dependents drop first. v_operator_perf_by_line_day and
# v_operator_performance SELECT from v_oee_by_line_day, so they must drop
# before it. CREATE order is separate: V_OEE, then V_OP, then V_STAGE_C
# (the aliases in V_STAGE_C reference v_oee_by_line_day).
ALL_VIEWS = [
    "v_operator_perf_by_line_day",
    "v_operator_performance",
    "v_oee_by_line_day",
    "v_oee_daily",
    "v_production_vs_standard",
    "v_changeover_by_station",
    "v_changeover_variance",
    "v_unaccounted_by_line_day",
    "v_maintenance_by_station",
    "v_pdca_trend",
]

# Drops everything first, then recreates in dependency order, in one
# transaction: on any failure SQLite rolls back and no view is left
# half-built. Called from app.py at module load.
def ensure_views(conn):
    for name in ALL_VIEWS:
        conn.execute(f"DROP VIEW IF EXISTS {name}")
    conn.execute(V_OEE)
    conn.execute(V_OP)
    conn.executescript(V_STAGE_C)
    conn.commit()

if __name__ == "__main__":
    conn = get_db_connection()
    ensure_views(conn)
    conn.close()
    print(f"all {len(ALL_VIEWS)} views created")
