import sqlite3
from datetime import datetime, timedelta

DB_PATH = "/mnt/lake/myarra.db"
today = datetime.now()

def ts(days_ahead):
    return (today + timedelta(days=days_ahead)).date().isoformat()

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# PDCA 1: Changeover
c.execute("""
UPDATE experiments SET
    problem_severity = 4,
    pdca_owner = 'Alice Smith',
    management_sponsor = 'Randy Wolf',
    team_members = 'Alice Smith, Bob Jones, Carol White',
    departments_involved = 'Packaging, Maintenance',
    hypothesis = 'If we pre-stage labels and caps during the previous shift, we will cut changeover time from 60 to 32 minutes.',
    target_date = ?,
    how_known_solved = 'Aggregate changeover actual drops below 35 minutes for 3 consecutive events.',
    action_plan = 'Shadow board design, install, operator training, measure next 5 changeovers.',
    pri_time = 3, pri_impact = 5, pri_resources = 2, pri_magnitude = 4, pri_cost = 3,
    baseline_value = 60.0
WHERE id = 1
""", (ts(30),))

# PDCA 2: Silkscreen
c.execute("""
UPDATE experiments SET
    problem_severity = 3,
    pdca_owner = 'Bob Jones',
    management_sponsor = 'Randy Wolf',
    team_members = 'Bob Jones, Carol White',
    departments_involved = 'Silkscreen, Warehouse',
    hypothesis = 'If we reorganize screen storage with labeled bins and lighting, setup time drops from 30 to 15 minutes.',
    target_date = ?,
    how_known_solved = 'Setup time on 3 consecutive jobs averages under 18 minutes.',
    action_plan = 'Catalog screens, order bins and lights, reorganize, train, measure.',
    pri_time = 4, pri_impact = 3, pri_resources = 3, pri_magnitude = 3, pri_cost = 2,
    baseline_value = 30.0
WHERE id = 2
""", (ts(45),))

# PDCA 3: Assembly
c.execute("""
UPDATE experiments SET
    problem_severity = 4,
    pdca_owner = 'Carol White',
    management_sponsor = 'Randy Wolf',
    team_members = 'Carol White, Dave Lee',
    departments_involved = 'Assembly, Engineering',
    hypothesis = 'If we relocate the kitting bins to within arm''s reach of the operator, we will hit 150 units/hr.',
    target_date = ?,
    how_known_solved = 'Daily kitting rate exceeds 145 units/hr for 5 consecutive days.',
    action_plan = 'Video station, time-and-motion study, prototype layout, 1-week trial, standardize.',
    pri_time = 2, pri_impact = 4, pri_resources = 4, pri_magnitude = 4, pri_cost = 2,
    baseline_value = 120.0
WHERE id = 3
""", (ts(21),))

# Actions -- using actual column names: description, owner, due_date, status, completed_at
c.execute("DELETE FROM experiment_actions WHERE experiment_id IN (1,2,3)")

actions = [
    (1, 1, 'Observe 3 changeovers, time each station', 'Alice Smith', ts(-14), 'done', ts(-14)),
    (1, 2, 'Design shadow board for caps and labels', 'Bob Jones', ts(-10), 'done', ts(-9)),
    (1, 3, 'Install shadow board at Line 3', 'Carol White', ts(-5), 'done', ts(-4)),
    (1, 4, 'Train operators on pre-staging SOP', 'Alice Smith', ts(2), 'in_progress', None),
    (1, 5, 'Measure next 5 changeover events', 'Alice Smith', ts(20), 'open', None),
    (2, 1, 'Inventory and catalog all screens', 'Bob Jones', ts(-20), 'done', ts(-18)),
    (2, 2, 'Order labeled bins and lighting', 'Bob Jones', ts(-15), 'done', ts(-14)),
    (2, 3, 'Reorganize screen storage area', 'Carol White', ts(-5), 'in_progress', None),
    (2, 4, 'Train silkscreen team on new layout', 'Bob Jones', ts(5), 'open', None),
    (2, 5, 'Measure next 5 setups', 'Bob Jones', ts(25), 'open', None),
    (3, 1, 'Video current kitting station', 'Carol White', ts(-10), 'done', ts(-9)),
    (3, 2, 'Time-and-motion study', 'Dave Lee', ts(-7), 'done', ts(-6)),
    (3, 3, 'Build prototype layout', 'Carol White', ts(-2), 'in_progress', None),
    (3, 4, 'Run 1-week trial', 'Carol White', ts(7), 'open', None),
    (3, 5, 'Measure and standardize', 'Carol White', ts(14), 'open', None),
]
for exp_id, seq, description, owner, due_date, status, completed_at in actions:
    c.execute("""
        INSERT INTO experiment_actions (experiment_id, seq, description, owner, due_date, status, completed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (exp_id, seq, description, owner, due_date, status, completed_at))

conn.commit()
conn.close()
print("PDCA fields and action plans populated for all 3 experiments.")