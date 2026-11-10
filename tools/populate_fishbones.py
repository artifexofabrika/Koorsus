import sqlite3

DB_PATH = "/mnt/lake/myarra.db"
conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# Clear any existing rows for the three demo PDCAs (safe if empty)
c.execute("DELETE FROM fishbone_causes WHERE experiment_id IN (1, 2, 3)")

causes = [
    # PDCA 1: Reduce Filler 2 Changeover
    (1, 'Method',    'No standard work instruction for pre-staging', 0),
    (1, 'Method',    'Labels and caps fetched from warehouse mid-changeover', 1),
    (1, 'Machine',   'Filler tooling requires manual adjustment at each swap', 0),
    (1, 'Man',       'Operators trained on old procedure only', 0),
    (1, 'Material',  'Labels stored 3 aisles away, no staging cart', 0),
    (1, 'Environment', 'Insufficient staging space at line head', 0),

    # PDCA 2: Reduce Silkscreen Setup Time
    (2, 'Environment', 'Bins poorly lit and unlabeled', 0),
    (2, 'Method',      'No standard work for screen retrieval', 0),
    (2, 'Man',         'New operators not trained on setup sequence', 0),
    (2, 'Machine',     'Squeegee alignment is done by eye, not by gauge', 0),
    (2, 'Measurement', 'Setup time not recorded, only felt', 0),

    # PDCA 3: Improve Assembly Kitting Rate
    (3, 'Environment', 'Kitting bins positioned 4 feet behind operator', 0),
    (3, 'Environment', 'North side of station poorly lit', 1),
    (3, 'Method',      'No standard work sequence for kitting', 0),
    (3, 'Method',      'Bins refilled once per shift, run empty mid-shift', 1),
    (3, 'Man',         'Operator rotation not scheduled, fatigue at hour 6+', 0),
    (3, 'Machine',     'Taping machine jams when box is misfolded', 0),
    (3, 'Material',    'Jars and cloths arrive as separate totes', 0),
    (3, 'Measurement', 'Rate measured end-of-shift only, not hourly', 0),
]

for exp_id, category, cause_text, seq in causes:
    c.execute(
        "INSERT INTO fishbone_causes (experiment_id, category, cause_text, seq) VALUES (?, ?, ?, ?)",
        (exp_id, category, cause_text, seq)
    )

conn.commit()

for exp_id in (1, 2, 3):
    n = c.execute("SELECT COUNT(*) FROM fishbone_causes WHERE experiment_id=?", (exp_id,)).fetchone()[0]
    print(f"PDCA {exp_id}: {n} fishbone causes")

conn.close()
print("Fishbones populated for PDCAs 1, 2, and 3.")