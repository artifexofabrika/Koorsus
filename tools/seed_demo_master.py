import sqlite3
import random
from datetime import datetime, timedelta

DB_PATH = "/mnt/lake/myarra.db"

def seed():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    tables = [
        "co_event_changes", "co_event_steps", "co_events", "co_steps_v2", "co_procedures_v2",
        "maintenance_events", "downtime_events", "line_events", "hourly_runs", "jobs", 
        "line_sku_stations", "line_sku_rates", "sku_bom", "component_types", "skus", "lines", 
        "experiments", "fishbone_causes", "experiment_actions"
    ]
    for t in tables:
        c.execute(f"DELETE FROM {t}")

    lines = [
        (1, "Silkscreen", "Manual"),
        (2, "Filler Line 1 (Legacy)", "Automated"),
        (3, "Filler Line 2 (New)", "Automated"),
        (4, "Assembly", "Manual"),
        (5, "Winery Bottling", "Automated"),
        (6, "Beer Canning", "Automated"),
        (7, "Cosmetics Filling", "Automated")
    ]
    c.executemany("INSERT INTO lines (id, name, format_type) VALUES (?, ?, ?)", lines)

    skus = [
        (1, "JC-8OZ", "Jewelry Cleaner 8oz", 12),
        (2, "JC-4OZ", "Jewelry Cleaner 4oz", 12),
        (3, "CLOTH-PRT", "Printed Cloth", 50),
        (4, "JAR-PRT", "Printed Jar", 24),
        (5, "WINE-CAB", "Cabernet Sauvignon", 6),
        (6, "WINE-CHARD", "Chardonnay", 6),
        (7, "BEER-IPA", "India Pale Ale", 24),
        (8, "BEER-LAGER", "Lager", 24),
        (9, "COS-FDN", "Foundation 1oz", 12),
        (10, "COS-LIP", "Lip Balm", 24)
    ]
    c.executemany("INSERT INTO skus (id, part_number, description, case_pack) VALUES (?, ?, ?, ?)", skus)

    rates = [
        (1, 3, 600), (1, 4, 400),
        (2, 1, 600), (2, 2, 800),
        (3, 1, 1200), (3, 2, 1500),
        (4, 1, 120), (4, 2, 150),
        (5, 5, 3000), (5, 6, 3000),
        (6, 7, 4000), (6, 8, 4000),
        (7, 9, 1200), (7, 10, 2000)
    ]
    c.executemany("INSERT INTO line_sku_rates (line_id, sku_id, ideal_rate) VALUES (?, ?, ?)", rates)

    stations = [
        (1, 3, 1, "Printer"), (1, 3, 2, "Dryer"), (1, 3, 3, "Pack"),
        (1, 4, 1, "Printer"), (1, 4, 2, "Dryer"), (1, 4, 3, "Pack"),
        (2, 1, 1, "Rinser"), (2, 1, 2, "Filler"), (2, 1, 3, "Capper"), (2, 1, 4, "Labeler"), (2, 1, 5, "Case Packer"),
        (2, 2, 1, "Rinser"), (2, 2, 2, "Filler"), (2, 2, 3, "Capper"), (2, 2, 4, "Labeler"), (2, 2, 5, "Case Packer"),
        (3, 1, 1, "Rinser"), (3, 1, 2, "Filler"), (3, 1, 3, "Capper"), (3, 1, 4, "Labeler"), (3, 1, 5, "Case Packer"),
        (3, 2, 1, "Rinser"), (3, 2, 2, "Filler"), (3, 2, 3, "Capper"), (3, 2, 4, "Labeler"), (3, 2, 5, "Case Packer"),
        (4, 1, 1, "Kitting"), (4, 1, 2, "Taping"), (4, 1, 3, "Case Packer"),
        (4, 2, 1, "Kitting"), (4, 2, 2, "Taping"), (4, 2, 3, "Case Packer"),
        (5, 5, 1, "Rinser"), (5, 5, 2, "Filler"), (5, 5, 3, "Corker"), (5, 5, 4, "Foiler"), (5, 5, 5, "Labeler"), (5, 5, 6, "KD Case Packer"),
        (5, 6, 1, "Rinser"), (5, 6, 2, "Filler"), (5, 6, 3, "Corker"), (5, 6, 4, "Foiler"), (5, 6, 5, "Labeler"), (5, 6, 6, "KD Case Packer"),
        (6, 7, 1, "Depalletizer"), (6, 7, 2, "Filler"), (6, 7, 3, "Seamer"), (6, 7, 4, "Labeler"), (6, 7, 5, "Case Packer"),
        (6, 8, 1, "Depalletizer"), (6, 8, 2, "Filler"), (6, 8, 3, "Seamer"), (6, 8, 4, "Labeler"), (6, 8, 5, "Case Packer"),
        (7, 9, 1, "Filler"), (7, 9, 2, "Capper"), (7, 9, 3, "Labeler"), (7, 9, 4, "Cartoner"),
        (7, 10, 1, "Filler"), (7, 10, 2, "Capper"), (7, 10, 3, "Labeler"), (7, 10, 4, "Cartoner")
    ]
    c.executemany("INSERT INTO line_sku_stations (line_id, sku_id, seq, station) VALUES (?, ?, ?, ?)", stations)

    today = datetime.now()
    pdca_start = (today - timedelta(days=7)).date().isoformat()
    
    c.execute("""
        INSERT INTO experiments (id, title, department, line_id, status, measurement_type, start_date, 
        standard_min, target_goal_min, root_cause, current_condition, target_condition, pdca_id, hypothesis)
        VALUES (1, 'Reduce Filler 2 Changeover', 'Packaging', 3, 'active', 'manual', ?, 
        60.0, 30.0, 'Inefficient staging', '60 min', '30 min', 'PDCA-001', 'Pre-staging will cut internal time.')
    """, (pdca_start,))

    c.execute("""
        INSERT INTO experiments (id, title, department, line_id, status, measurement_type, start_date, 
        standard_min, target_goal_min, root_cause, current_condition, target_condition, pdca_id)
        VALUES (2, 'Reduce Silkscreen Setup Time', 'Silkscreen', 1, 'active', 'manual', ?, 
        30.0, 15.0, 'Screens stored poorly', '30 min setup', '15 min setup', 'PDCA-002')
    """, (pdca_start,))

    c.execute("""
        INSERT INTO experiments (id, title, department, line_id, status, measurement_type, start_date, 
        standard_min, target_goal_min, root_cause, current_condition, target_condition, pdca_id)
        VALUES (3, 'Improve Assembly Kitting Rate', 'Assembly', 4, 'active', 'manual', ?, 
        120.0, 150.0, 'Poor ergonomics', '120 units/hr', '150 units/hr', 'PDCA-003')
    """, (pdca_start,))

    c.execute("INSERT INTO co_procedures_v2 (id, line_id, from_sku_id, to_sku_id, name, aggregate_standard_min) VALUES (1, 3, 1, 2, '8oz to 4oz', 60.0)")
    c.executemany("INSERT INTO co_steps_v2 (id, procedure_id, seq, step_name, station, standard_min) VALUES (?, ?, ?, ?, ?, ?)", [
        (1, 1, 1, "Rinse Line", "Rinser", 15.0),
        (2, 1, 2, "Swap Tooling", "Filler", 20.0),
        (3, 1, 3, "Swap Cap Chute", "Capper", 10.0),
        (4, 1, 4, "Swap Label Roll", "Labeler", 10.0),
        (5, 1, 5, "Adjust Case Packer", "Case Packer", 5.0)
    ])

    start_date = today - timedelta(days=14)
    end_date = today + timedelta(days=14)
    current_date = start_date
    monthly_seq = 1

    while current_date <= end_date:
        is_today = (current_date.date() == today.date())
        is_past = (current_date.date() < today.date())
        day_str = current_date.strftime('%y%m')
        line_prev_jobs = {}
        
        for line_id in range(1, 8):
            line_skus = [r[1] for r in rates if r[0] == line_id]
            if not line_skus: continue
            
            for shift_idx, shift_name in enumerate(['1', '2']):
                status = 'completed' if is_past else ('in_progress' if is_today and shift_idx == 0 else 'scheduled')
                shift_start = current_date.replace(hour=7 if shift_idx==0 else 15, minute=0, second=0, microsecond=0)
                
                sku_id = random.choice(line_skus)
                job_num = f"WO-{day_str}-{monthly_seq:03d}"
                monthly_seq += 1
                
                prev_job = line_prev_jobs.get(line_id, "WO-2600-000")
                line_prev_jobs[line_id] = job_num
                
                bpm = next(r[2] for r in rates if r[0] == line_id and r[1] == sku_id)
                
                c.execute("""
                    INSERT INTO jobs (job_number, sku_id, line_id, target_quantity, scheduled_start, status)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (job_num, sku_id, line_id, bpm * 8, shift_start.isoformat(), status))
                job_id = c.lastrowid

                if is_today and shift_idx == 0:
                    c.execute("""
                        INSERT INTO line_events (line_id, state, started_at, job_id, source)
                        VALUES (?, 'production', ?, ?, 'seed')
                    """, (line_id, shift_start.isoformat(), job_id))

                hours_to_run = 0
                if is_past: hours_to_run = 8
                elif is_today and shift_idx == 0: hours_to_run = 8
                elif is_today and shift_idx == 1: hours_to_run = 4

                for h in range(1, hours_to_run + 1):
                    variance = random.uniform(0.88, 1.05)
                    units = int(bpm * variance)
                    scrap = int(units * random.uniform(0.005, 0.04))
                    
                    if variance < 0.92:
                        station = random.choice([r[3] for r in stations if r[0] == line_id and r[1] == sku_id])
                        comments = f"Minor issue at {station}, resolved."
                    else:
                        comments = random.choice(["Running well", "All good", "Hit target", ""])

                    recorded_at = shift_start + timedelta(hours=h-1)
                    
                    c.execute("""
                        INSERT INTO hourly_runs (job_id, line_id, sku_id, shift, period, recorded_at, units_filled, scrap_units, duration_min, notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 60, ?)
                    """, (job_id, line_id, sku_id, shift_name, f"H{h}", recorded_at.isoformat(), units, scrap, comments))
                    run_id = c.lastrowid

                    unaccounted_target = {1: 0.28, 2: 0.20, 3: 0.18, 4: 0.32, 5: 0.12, 6: 0.10, 7: 0.22}
                    gap_units = bpm - units
                    if gap_units > 0:
                        gap_mins = round((gap_units / bpm) * 60, 1)
                        if random.random() > unaccounted_target.get(line_id, 0.20):
                            station = random.choice([r[3] for r in stations if r[0] == line_id and r[1] == sku_id])
                            c.execute("""
                                INSERT INTO downtime_events (run_id, station, reason, minutes)
                                VALUES (?, ?, ?, ?)
                            """, (run_id, station, "Unplanned stop", gap_mins))

                if line_id == 3 and shift_idx == 1:
                    if current_date.date() >= datetime.strptime(pdca_start, '%Y-%m-%d').date():
                        total_co = 32.0
                        steps = [15.0, 15.0, 2.0, 0.0, 0.0]
                    else:
                        total_co = 60.0
                        steps = [15.0, 20.0, 10.0, 10.0, 5.0]
                    
                    c.execute("""
                        INSERT INTO co_events (procedure_id, line_id, started_at, aggregate_actual_min, from_job_number, to_job_number)
                        VALUES (1, 3, ?, ?, ?, ?)
                    """, (shift_start.isoformat(), total_co, prev_job, job_num))
                    co_id = c.lastrowid
                    
                    for i, s_min in enumerate(steps):
                        c.execute("INSERT INTO co_event_steps (event_id, step_id, actual_min) VALUES (?, ?, ?)", (co_id, i+1, s_min))

        current_date += timedelta(days=1)

    conn.commit()
    conn.close()
    print(f"Seven-line factory seeded. {monthly_seq - 1} jobs created.")

if __name__ == "__main__":
    seed()