PRAGMA foreign_keys=OFF;
DROP TABLE IF EXISTS co_event_steps;
DROP TABLE IF EXISTS co_events;
DROP TABLE IF EXISTS co_steps_v2;
DROP TABLE IF EXISTS co_procedures_v2;
DROP TABLE IF EXISTS downtime_events;
DROP TABLE IF EXISTS hourly_runs;
PRAGMA foreign_keys=ON;

CREATE TABLE hourly_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  line_id INTEGER, sku_id INTEGER,
  shift TEXT, period TEXT, phase TEXT DEFAULT 'run',
  recorded_at TEXT, bottles_filled INTEGER NOT NULL,
  scrap_bottles INTEGER DEFAULT 0,
  operator TEXT, raw_text TEXT, source TEXT DEFAULT 'telegram');

CREATE TABLE downtime_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id INTEGER REFERENCES hourly_runs(id),
  station TEXT, reason TEXT, minutes REAL NOT NULL, note TEXT);

CREATE TABLE co_procedures_v2 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  line_id INTEGER, from_sku_id INTEGER, to_sku_id INTEGER,
  version INTEGER DEFAULT 1, name TEXT,
  aggregate_standard_min REAL NOT NULL,
  effective_from TEXT, effective_to TEXT, is_baseline INTEGER DEFAULT 1, notes TEXT);

CREATE TABLE co_steps_v2 (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  procedure_id INTEGER REFERENCES co_procedures_v2(id),
  seq INTEGER, step_name TEXT NOT NULL, station TEXT,
  standard_min REAL NOT NULL, is_serial INTEGER DEFAULT 1);

CREATE TABLE co_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  procedure_id INTEGER REFERENCES co_procedures_v2(id),
  line_id INTEGER, started_at TEXT, ended_at TEXT,
  aggregate_actual_min REAL, bottles_to_mixer INTEGER,
  operator TEXT, raw_text TEXT, source TEXT DEFAULT 'telegram');

CREATE TABLE co_event_steps (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  event_id INTEGER REFERENCES co_events(id),
  step_id INTEGER REFERENCES co_steps_v2(id),
  actual_min REAL NOT NULL, note TEXT);

-- SHIFT 2: eight hours running WW-750-Mer
INSERT INTO hourly_runs (id,line_id,sku_id,shift,period,phase,recorded_at,bottles_filled,operator,raw_text) VALUES
 (1,1,2,'2','H1','run','2026-10-20 16:00:00',34272,'line lead','WW-750-Mer 34272 bottles, 3 min down labeler stuck label'),
 (2,1,2,'2','H2','run','2026-10-20 17:00:00',27472,'line lead','WW-750-Mer 27472 bottles, 7 min down labeler stuck label'),
 (3,1,2,'2','H3','run','2026-10-20 18:00:00',34800,'line lead','WW-750-Mer 34800 bottles, 2 min down labeler'),
 (4,1,2,'2','H4','run','2026-10-20 19:00:00',33600,'line lead','WW-750-Mer 33600 bottles, 4 min down labeler'),
 (5,1,2,'2','H5','run','2026-10-20 20:00:00',31200,'line lead','WW-750-Mer 31200 bottles, 8 min down labeler'),
 (6,1,2,'2','H6','run','2026-10-20 21:00:00',28800,'line lead','WW-750-Mer 28800 bottles, 5 min down labeler'),
 (7,1,2,'2','H7','run','2026-10-20 22:00:00',34200,'line lead','WW-750-Mer 34200 bottles, 3 min down labeler'),
 (8,1,2,'2','H8','run','2026-10-20 23:00:00',29400,'line lead','WW-750-Mer 29400 bottles, 11 min down labeler');

INSERT INTO downtime_events (run_id,station,reason,minutes,note) VALUES
 (1,'labeler','label jam',3.0,'stuck label'),
 (2,'labeler','label jam',7.0,'stuck label'),
 (3,'labeler','label jam',2.0,'stuck label'),
 (4,'labeler','label jam',4.0,'stuck label'),
 (5,'labeler','label jam',8.0,'stuck label'),
 (6,'labeler','label jam',5.0,'stuck label'),
 (7,'labeler','label jam',3.0,'stuck label'),
 (8,'labeler','label jam',11.0,'stuck label');

-- SHIFT 3: four hours finishing the job
INSERT INTO hourly_runs (id,line_id,sku_id,shift,period,phase,recorded_at,bottles_filled,operator,raw_text) VALUES
 (9,1,2,'3','H1','run','2026-10-21 00:00:00',35400,'line lead','WW-750-Mer 35400 bottles, 1 min down labeler'),
 (10,1,2,'3','H2','run','2026-10-21 01:00:00',33000,'line lead','WW-750-Mer 33000 bottles, 5 min down labeler'),
 (11,1,2,'3','H3','run','2026-10-21 02:00:00',34800,'line lead','WW-750-Mer 34800 bottles, 2 min down labeler'),
 (12,1,2,'3','H4','run','2026-10-21 03:00:00',34200,'line lead','WW-750-Mer 34200 bottles, 3 min down labeler');

INSERT INTO downtime_events (run_id,station,reason,minutes,note) VALUES
 (9,'labeler','label jam',1.0,'stuck label'),
 (10,'labeler','label jam',5.0,'stuck label'),
 (11,'labeler','label jam',2.0,'stuck label'),
 (12,'labeler','label jam',3.0,'stuck label');

-- CHANGEOVER: WW-750-Mer -> WW-750-CS, 04:00 to 06:20
INSERT INTO co_procedures_v2 (id,line_id,from_sku_id,to_sku_id,name,aggregate_standard_min,effective_from,is_baseline,notes) VALUES
 (3,1,2,1,'WW-750-Mer -> WW-750-CS',120,'2026-10-01',1,'wine, label, foil and KD change. Glass and cork stay.');
INSERT INTO co_steps_v2 (id,procedure_id,seq,step_name,station,standard_min,is_serial) VALUES
 (101,3,1,'Blow-through','filler',45,1),
 (102,3,2,'Change label','labeler',62,0),
 (103,3,3,'Change foil','foiler',25,0),
 (104,3,4,'Change knockdown','packaging',25,0),
 (105,3,5,'Verification','line',10,1),
 (106,3,6,'Startup and QA signoff','line',30,1);

INSERT INTO co_events (id,procedure_id,line_id,started_at,ended_at,aggregate_actual_min,bottles_to_mixer,operator,raw_text) VALUES
 (1,3,1,'2026-10-21 04:00:00','2026-10-21 06:20:00',140,28,'line lead','Changeover to CS. KD part broke, maintenance called. Labeler went well.');
INSERT INTO co_event_steps (event_id,step_id,actual_min,note) VALUES
 (1,101,45,NULL),
 (1,102,27,'fast, worked first try'),
 (1,103,15,NULL),
 (1,104,80,'part broke, maintenance called'),
 (1,105,10,NULL),
 (1,106,30,NULL);

-- POST-CHANGEOVER: ramp then first run hour on WW-750-CS
INSERT INTO hourly_runs (id,line_id,sku_id,shift,period,phase,recorded_at,bottles_filled,operator,raw_text) VALUES
 (13,1,1,'3','R1','ramp','2026-10-21 06:20:00',33000,'line lead','Ramp to 600bpm, 5 min'),
 (14,1,1,'3','H1','run','2026-10-21 07:20:00',35400,'line lead','WW-750-CS 35400 bottles, 1 min down labeler');
INSERT INTO downtime_events (run_id,station,reason,minutes,note) VALUES
 (13,'filler','ramp',5.0,'dialling in filler after format change'),
 (14,'labeler','label jam',1.0,'stuck label');
