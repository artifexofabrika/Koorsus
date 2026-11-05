import sqlite3, random
from datetime import datetime, timedelta
random.seed(42)
DB = "/mnt/lake/myarra.db"
conn = sqlite3.connect(DB); conn.row_factory = sqlite3.Row
c = conn.cursor()

for t in ['experiment_actions','fishbone_causes','experiments','co_event_steps',
          'co_event_changes','co_events',
          'co_steps_v2','co_procedures_v2',
          'shift_handovers','maintenance_events',
          'line_events','downtime_events',
          'hourly_runs','jobs','sku_bom','component_types',
          'line_sku_rates','skus','lines']:
    c.execute(f"DELETE FROM {t}")
c.execute("DELETE FROM bot_sessions")
conn.commit()

LINES = [
    (1,"Cosmetics Compacts","cosmetics",7200,12),
    (2,"Cosmetics Foundation","cosmetics",5000,12),
    (3,"Beverage Cans 12oz","beverage",36000,24),
    (4,"Beverage Cans 16oz","beverage",24000,24),
    (5,"Jewelry Cleaner Jars","jewelry",4000,12),
]
for lid,name,vert,rate,cp in LINES:
    c.execute("INSERT INTO lines (id,name,format_type) VALUES (?,?,?)",(lid,name,vert))

COMPS = [
    (1,"case",0,12),(2,"formulation",1,10),(3,"shrink",0,5),(4,"box",0,8),
    (5,"can",0,12),(6,"seam",0,8),(7,"label",0,6),(8,"pak",0,5),
    (9,"jar",0,6),(10,"cap",0,4),(11,"brush",0,3),(12,"basket",0,3),
]
for row in COMPS:
    c.execute("INSERT INTO component_types (id,name,is_serial,default_swap_min) VALUES (?,?,?,?)",row)

SKUS = [
    (1,"COS-CMP-RS","Compact Rose 0.25oz",12,1,[(1,"rose-blk"),(2,"rose-pwd"),(3,"shr-rose"),(4,"bx-rose")]),
    (2,"COS-CMP-SD","Compact Sand 0.25oz",12,1,[(1,"sand-slv"),(2,"sand-pwd"),(3,"shr-sand"),(4,"bx-sand")]),
    (3,"COS-FDN-CH","Foundation Champagne 1oz",12,2,[(1,"chmp-gl"),(2,"chmp-pwd"),(3,"shr-chmp"),(4,"bx-chmp")]),
    (4,"COS-FDN-NA","Foundation Natural 1oz",12,2,[(1,"nat-gl"),(2,"nat-pwd"),(3,"shr-nat"),(4,"bx-nat")]),
    (5,"BEV-IPA-12","Hazy IPA 12oz Can",24,3,[(5,"12-sleek-ipa"),(6,"202"),(7,"ipa-lbl"),(8,"12-clip-ipa")]),
    (6,"BEV-STO-12","Stout 12oz Can",24,3,[(5,"12-sleek-sto"),(6,"202"),(7,"sto-lbl"),(8,"12-clip-sto")]),
    (7,"BEV-IPA-16","Hazy IPA 16oz Can",24,4,[(5,"16-std-ipa"),(6,"202"),(7,"ipa16-lbl"),(8,"16-clip-ipa")]),
    (8,"BEV-STO-16","Stout 16oz Can",24,4,[(5,"16-std-sto"),(6,"202"),(7,"sto16-lbl"),(8,"16-clip-sto")]),
    (9,"JWL-CLN-LV","Jewelry Cleaner Lavender 4oz",12,5,[(9,"4-gl-lav"),(10,"purple-cap"),(11,"sm-br-lav"),(12,"lav-bk"),(2,"lavender-formulation")]),
    (10,"JWL-CLN-UN","Jewelry Cleaner Unscented 4oz",12,5,[(9,"4-gl-uns"),(10,"blk-cap"),(11,"sm-br-uns"),(12,"uns-bk"),(2,"unscented-formulation")]),
]
for sid,pn,desc,cp,lid,bom in SKUS:
    c.execute("INSERT INTO skus (id,part_number,description,case_pack,active) VALUES (?,?,?,?,1)",
              (sid,pn,desc,cp))
    for cid,val in bom:
        c.execute("INSERT INTO sku_bom (sku_id,component_type_id,component_value) VALUES (?,?,?)",
                  (sid,cid,val))
    rate = next(l[3] for l in LINES if l[0]==lid)
    c.execute("INSERT INTO line_sku_rates (line_id,sku_id,ideal_rate) VALUES (?,?,?)",(lid,sid,rate))

STEP_DEFS = {
    'cosmetics':[("Change case","case_feeder",14),("Change formulation","filler",12),
                 ("Change shrink","shrink_wrap",7),("Change box","boxer",10),
                 ("Verify","line",9),("Startup","line",13)],
    'beverage':[("Change can","depalletizer",16),("Verify seam","seamer",10),
                ("Change label","labeler",9),("Change pak","packer",8),
                ("Verify","line",7),("Startup","line",8)],
    'jewelry':[("Change jar","unscrambler",8),("Change cap","capper",5),
               ("Change brush","inserter",4),("Change basket","inserter",4),
               ("Change formulation","filler",12),("Verify","line",6),("Startup","line",6)],
}
LINE_SKUS = [(1,1,2),(2,3,4),(3,5,6),(4,7,8),(5,9,10)]
for lid,a,b in LINE_SKUS:
    vert = next(l[2] for l in LINES if l[0]==lid)
    steps = STEP_DEFS[vert]
    std = sum(s[2] for s in steps)
    for fr,to in [(a,b),(b,a)]:
        c.execute("INSERT INTO co_procedures_v2 (line_id,from_sku_id,to_sku_id,name,aggregate_standard_min) VALUES (?,?,?,?,?)",
                  (lid,fr,to,f"Line {lid}: {fr}->{to}",std))
        pid = c.lastrowid
        for seq,(nm,st,m) in enumerate(steps,1):
            c.execute("INSERT INTO co_steps_v2 (procedure_id,seq,step_name,station,standard_min) VALUES (?,?,?,?,?)",
                      (pid,seq,nm,st,m))
conn.commit()

TODAY = datetime.now().replace(hour=0,minute=0,second=0,microsecond=0)
START = TODAY - timedelta(days=30)
SHIFTS = [(7,15),(15,23),(23,7)]
JOBS = []
jc = 1
for lid,sku_a,sku_b in LINE_SKUS:
    rate = next(l[3] for l in LINES if l[0]==lid)
    cp = next(l[4] for l in LINES if l[0]==lid)
    for i in range(6):
        jday = START + timedelta(days=1 + i*5 + (lid%3))
        shifts_count = random.choice([1,2])
        sku = sku_a if i%2==0 else sku_b
        target = int(rate*8*shifts_count*random.uniform(0.92,0.97))
        jn = f"WO-2026-{jc:03d}"; jc += 1
        c.execute("""INSERT INTO jobs (job_number,sku_id,line_id,target_quantity,scheduled_start,scheduled_end,status)
            VALUES (?,?,?,?,?,?,'scheduled')""",
            (jn,sku,lid,target,(jday+timedelta(hours=7)).isoformat(),
             (jday+timedelta(hours=7+8*shifts_count)).isoformat()))
        JOBS.append({'id':c.lastrowid,'jn':jn,'lid':lid,'sku':sku,'target':target,
                     'start':jday,'shifts':shifts_count,'rate':rate,'cp':cp})
conn.commit()

for job in JOBS:
    total_jh = 0.0
    for sh_i in range(job['shifts']):
        sh_h = SHIFTS[sh_i][0]
        sh_start = job['start'].replace(hour=sh_h,minute=0,second=0,microsecond=0)
        sh_end = sh_start + timedelta(hours=8)
        shift_val = str(sh_i+1)
        for h in range(7):
            if h == 4: continue
            hour_start = sh_start + timedelta(hours=h)
            period = f"H{h+1}"
            units = int(job['rate'] * random.uniform(0.93, 0.99))  # NO ×60
            c.execute("""INSERT INTO hourly_runs (job_id,line_id,shift,period,recorded_at,units_filled,
                duration_min,phase,job_hour_start,job_hour_end,user_id,flagged,source)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (job['id'],job['lid'],shift_val,period,hour_start.isoformat(),units,60,
                 'run',total_jh/60,(total_jh+60)/60,1,0,'seed'))
            total_jh += 60
        hour8_start = sh_start + timedelta(hours=7)
        units8 = int(job['rate'] * 0.5 * random.uniform(0.93, 0.99))  # NO ×60
        c.execute("""INSERT INTO hourly_runs (job_id,line_id,shift,period,recorded_at,units_filled,
            duration_min,phase,job_hour_start,job_hour_end,user_id,flagged,source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (job['id'],job['lid'],shift_val,'H8',hour8_start.isoformat(),units8,30,
             'run',total_jh/60,(total_jh+30)/60,1,0,'seed'))
        total_jh += 30
        prod_end = sh_start + timedelta(minutes=450)
        lunch_end = prod_end + timedelta(minutes=30)
        c.execute("""INSERT INTO line_events (line_id,state,started_at,ended_at,job_id,user_id,source)
            VALUES (?,?,?,?,?,?,'seed')""",
            (job['lid'],'production',sh_start.isoformat(),prod_end.isoformat(),job['id'],1))
        c.execute("""INSERT INTO line_events (line_id,state,started_at,ended_at,reason,user_id,source)
            VALUES (?,?,?,?,?,?,'seed')""",
            (job['lid'],'lunch',prod_end.isoformat(),lunch_end.isoformat(),'scheduled',1))
        c.execute("UPDATE jobs SET status='completed',actual_end=? WHERE id=?",(sh_end.isoformat(),job['id']))
conn.commit()

def write_co_event_changes(cur, event_id, from_sku_id, to_sku_id):
    """Write one co_event_changes row per component whose BOM value differs."""
    a = {r[0]: r[1] for r in cur.execute(
        "SELECT component_type_id, component_value FROM sku_bom WHERE sku_id=?",
        (from_sku_id,)).fetchall()}
    b = {r[0]: r[1] for r in cur.execute(
        "SELECT component_type_id, component_value FROM sku_bom WHERE sku_id=?",
        (to_sku_id,)).fetchall()}
    for cid in sorted(set(a) | set(b)):
        va, vb = a.get(cid), b.get(cid)
        if va != vb:
            cur.execute(
                "INSERT INTO co_event_changes (event_id, component_type_id, from_value, to_value, created_at) "
                "VALUES (?,?,?,?,?)",
                (event_id, cid, va, vb, datetime.now().isoformat()))


co_count = 0
for lid in range(1,6):
    lj = [j for j in JOBS if j['lid']==lid]
    for i in range(len(lj)-1):
        fr = lj[i]; to = lj[i+1]
        if fr['sku'] == to['sku']: continue
        proc = c.execute("SELECT * FROM co_procedures_v2 WHERE line_id=? AND from_sku_id=? AND to_sku_id=?",
                         (lid,fr['sku'],to['sku'])).fetchone()
        if not proc: continue
        co_start = fr['start'] + timedelta(days=2,hours=16)
        co_actual = int(proc['aggregate_standard_min']*random.uniform(0.85,1.30))
        co_end = co_start + timedelta(minutes=co_actual)
        c.execute("""INSERT INTO co_events (procedure_id,line_id,started_at,ended_at,aggregate_actual_min,
            from_job_number,to_job_number,source) VALUES (?,?,?,?,?,?,?,'seed')""",
            (proc['id'],lid,co_start.isoformat(),co_end.isoformat(),co_actual,fr['jn'],to['jn']))
        co_id = c.lastrowid
        write_co_event_changes(c, co_id, fr['sku'], to['sku'])
        for s in c.execute("SELECT * FROM co_steps_v2 WHERE procedure_id=? ORDER BY seq",(proc['id'],)).fetchall():
            c.execute("INSERT INTO co_event_steps (event_id,step_id,actual_min) VALUES (?,?,?)",
                      (co_id,s['id'],round(s['standard_min']*random.uniform(0.7,1.4),1)))
        c.execute("""INSERT INTO line_events (line_id,state,started_at,ended_at,co_event_id,user_id,source)
            VALUES (?,?,?,?,?,?,'seed')""",
            (lid,'changeover',co_start.isoformat(),co_end.isoformat(),co_id,1))
        co_count += 1
conn.commit()

# CURRENT SHIFT — staggered start per line, live production, then target set realistically
NOW = datetime.now()
STAGGER = [3.0, 2.2, 1.5, 4.1, 2.7]
for i, lid in enumerate(range(1,6)):
    lj = [j for j in JOBS if j['lid']==lid]
    last = max(lj,key=lambda j:j['start'])
    started = (NOW - timedelta(hours=STAGGER[i])).replace(minute=0,second=0,microsecond=0)
    c.execute("""INSERT INTO line_events (line_id,state,started_at,ended_at,job_id,user_id,source)
        VALUES (?,?,?,NULL,?,?,'seed')""",(lid,'production',started.isoformat(),last['id'],1))
    c.execute("UPDATE jobs SET status='running',actual_end=NULL WHERE id=?",(last['id'],))
    hours_elapsed = int(STAGGER[i])
    for h in range(hours_elapsed):
        hr = started + timedelta(hours=h)
        units = int(last['rate'] * random.uniform(0.93, 0.99))  # NO ×60
        c.execute("""INSERT INTO hourly_runs (job_id,line_id,shift,period,recorded_at,units_filled,
            duration_min,phase,job_hour_start,job_hour_end,user_id,flagged,source)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (last['id'],lid,'1',f"H{h+5}",hr.isoformat(),units,60,'run',h,h+1,1,0,'seed'))
    # SET TARGET: aim for 55-65% complete, based on actual production
    total_units = c.execute("SELECT SUM(units_filled) FROM hourly_runs WHERE job_id=?", (last['id'],)).fetchone()[0] or 0
    progress_factor = random.uniform(0.55, 0.65)
    new_target = int(total_units / progress_factor)
    c.execute("UPDATE jobs SET target_quantity=? WHERE id=?", (new_target, last['id']))
conn.commit()

EXPS = [
    (1,"Pre-stage case parts on shadow board","Production",1,"Change case","2026-10-10",12,8,"Method"),
    (2,"Pre-load label roll before end of run","Production",3,"Change label","2026-10-10",6,4,"Method"),
    (3,"Reduce seamer parts retrieval time","Production",3,"Verify seam","2026-10-10",8,5,"Machine"),
    (4,"Standardize jar changeover","Production",5,"Change jar","2026-10-10",6,4,"Method"),
    (5,"Reduce formulation flush time","Production",2,"Change formulation","2026-10-10",10,7,"Method"),
]
for eid,t,d,lid,ts,sd,std,goal,cat in EXPS:
    c.execute("""INSERT INTO experiments (id,title,department,line_id,status,target_step_name,
        start_date,standard_min,target_goal_min,fishbone_category)
        VALUES (?,?,?,?,'active',?,?,?,?,?)""",(eid,t,d,lid,ts,sd,std,goal,cat))
conn.commit()

print("SEED COMPLETE")
for t in ['lines','skus','jobs','hourly_runs','line_events','co_events','co_event_steps','co_event_changes','experiments']:
    print(f"  {t:20s} {c.execute(f'SELECT COUNT(*) FROM {t}').fetchone()[0]}")

print("\nSanity — currently running jobs:")
for r in c.execute("""SELECT j.job_number, j.line_id, j.target_quantity,
    (SELECT SUM(units_filled) FROM hourly_runs WHERE job_id=j.id) as produced
    FROM jobs j WHERE status='running' ORDER BY j.line_id"""):
    pct = (r['produced'] / r['target_quantity'] * 100) if r['target_quantity'] else 0
    print(f"  Line {r['line_id']} {r['job_number']}: {r['produced']:,} / {r['target_quantity']:,} = {pct:.1f}%")
conn.close()
