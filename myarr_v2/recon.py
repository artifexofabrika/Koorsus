"""Stage B2: OEE and operator performance summary for /reconciliation.

TWO MEASURES, BOTH CORRECT, DIFFERENT QUESTIONS (agreed 2026-11-06)
  OEE: counts every loss, including breakdowns and unscheduled maintenance
       as availability losses, and scrap against quality. The number a
       plant manager compares to benchmarks.
  Operator performance: excludes time the operator did not cause.
       Breakdowns and unplanned maintenance leave the denominator; scrap
       is not counted (quality is a process measure, not a shift measure).
Do not collapse the two into one number. The owner's objection to vOEE
(a weighted number engineered to flatter a COO) is the reason.
"""


def summary_for_window(conn, line_filter, days):
    sql = """
        SELECT l.id AS line_id, l.name AS line_name,
            COALESCE(SUM(v.production_min), 0)      AS production_min,
            COALESCE(SUM(v.changeover_min), 0)      AS changeover_min,
            COALESCE(SUM(v.unplanned_maint_min), 0) AS unplanned_maint_min,
            COALESCE(SUM(v.idle_min), 0)            AS idle_min,
            COALESCE(SUM(v.unscheduled_min), 0)     AS unscheduled_min,
            COALESCE(SUM(v.actual_units), 0)        AS actual_units,
            COALESCE(SUM(v.scrap_units), 0)         AS scrap_units,
            COALESCE(SUM(v.expected_units), 0)      AS expected_units
        FROM v_oee_by_line_day v
        JOIN lines l ON l.id = v.line_id
        WHERE v.day >= date('now', ?)
    """
    params = [f'-{days} days']
    if line_filter:
        sql += " AND v.line_id = ?"
        params.append(line_filter)
    sql += " GROUP BY l.id, l.name ORDER BY l.id"

    rows = []
    for r in conn.execute(sql, params).fetchall():
        r = dict(r)
        prod = r['production_min']
        co = r['changeover_min']
        maint = r['unplanned_maint_min']
        idle = r['idle_min']
        unsched = r['unscheduled_min']
        actual = r['actual_units']
        scrap = r['scrap_units']
        expected = r['expected_units']

        scheduled = prod + co + maint + idle + unsched
        r['scheduled_min'] = scheduled
        r['availability'] = (prod / scheduled) if scheduled else 0.0
        r['performance'] = (actual / expected) if expected else 0.0
        r['quality'] = ((actual - scrap) / actual) if actual else 0.0
        # Agreed 2026-11-05: classic A x P x Q. A = production / (production
        # + changeover + unplanned_maint + idle + unscheduled). Chosen over
        # simplified and shift variants; see SESSION-DELTA-2026-11-05.
        r['oee'] = r['availability'] * r['performance'] * r['quality']

        r['operator_available_min'] = prod + co + idle + unsched
        if prod and expected and r['operator_available_min']:
            # Agreed 2026-11-06: expected units are measured over
            # production_min; the operator is measured over production +
            # changeover + idle + unscheduled. Rescale expected units to the
            # operator's window. Do not "simplify" to actual/expected: that
            # is plain performance and collapses the two-measure design.
            r['operator_perf'] = actual / (expected * r['operator_available_min'] / prod)
        else:
            r['operator_perf'] = 0.0
        rows.append(r)
    return rows
