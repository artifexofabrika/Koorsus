"""Myarra Stage B2 views. Run once: python3 views.py. Idempotent."""
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

def ensure_views(conn):
    conn.execute("DROP VIEW IF EXISTS v_operator_perf_by_line_day")
    conn.execute("DROP VIEW IF EXISTS v_oee_by_line_day")
    conn.execute(V_OEE)
    conn.execute(V_OP)
    conn.commit()

if __name__ == "__main__":
    conn = get_db_connection()
    ensure_views(conn)
    conn.close()
    print("views created")
