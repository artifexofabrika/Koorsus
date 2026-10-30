PRAGMA foreign_keys=OFF;
DROP TABLE IF EXISTS changeovers;
DROP TABLE IF EXISTS changeover_procedures;
DROP TABLE IF EXISTS component_standards;
DROP TABLE IF EXISTS line_sku_rates;
DROP TABLE IF EXISTS skus;
DROP TABLE IF EXISTS line_formats;
DROP TABLE IF EXISTS knockdowns;
DROP TABLE IF EXISTS foils;
DROP TABLE IF EXISTS corks;
DROP TABLE IF EXISTS labels;
DROP TABLE IF EXISTS glasses;
DROP TABLE IF EXISTS wines;
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS lines;
PRAGMA foreign_keys=ON;

CREATE TABLE lines (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  buffer_bottles INTEGER DEFAULT 0, notes TEXT);

CREATE TABLE customers (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, tier TEXT);

CREATE TABLE wines (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  varietal TEXT, color TEXT);

CREATE TABLE glasses (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  size_ml INTEGER, shape TEXT);

CREATE TABLE labels (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  customer_id INTEGER REFERENCES customers(id),
  adhesive TEXT, family TEXT);

CREATE TABLE corks (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  material TEXT, branded INTEGER);

CREATE TABLE foils (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL, color TEXT);

CREATE TABLE knockdowns (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  pack_size INTEGER, material TEXT);

CREATE TABLE line_formats (
  id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL,
  size_ml INTEGER, description TEXT);

CREATE TABLE skus (
  id INTEGER PRIMARY KEY, part_number TEXT UNIQUE NOT NULL,
  description TEXT, customer_id INTEGER REFERENCES customers(id),
  wine_id INTEGER REFERENCES wines(id), glass_id INTEGER REFERENCES glasses(id),
  label_id INTEGER REFERENCES labels(id), cork_id INTEGER REFERENCES corks(id),
  foil_id INTEGER REFERENCES foils(id), knockdown_id INTEGER REFERENCES knockdowns(id),
  line_format_id INTEGER REFERENCES line_formats(id),
  case_pack INTEGER NOT NULL DEFAULT 12, active INTEGER DEFAULT 1);

CREATE TABLE line_sku_rates (
  line_id INTEGER REFERENCES lines(id),
  sku_id INTEGER REFERENCES skus(id),
  ideal_bpm REAL NOT NULL,
  PRIMARY KEY (line_id, sku_id));

CREATE TABLE component_standards (
  component TEXT PRIMARY KEY, swap_min REAL NOT NULL,
  serial INTEGER DEFAULT 0, triggers_flush INTEGER DEFAULT 0, notes TEXT);

CREATE TABLE changeover_procedures (
  customer_id INTEGER PRIMARY KEY REFERENCES customers(id),
  blow_through_std_min REAL DEFAULT 20,
  verification_min REAL DEFAULT 10,
  startup_min REAL DEFAULT 30,
  blow_through_target_bottles INTEGER DEFAULT 30,
  first_pass_qa_required INTEGER DEFAULT 1,
  total_std_min REAL);

INSERT INTO lines (id,name,buffer_bottles) VALUES
 (1,'Line 1',10000),(2,'Line 2',10000),(3,'Line 3',12000);

INSERT INTO customers (id,name,tier) VALUES
 (1,'Wolf Winery','A'),(2,'Cedar Ridge','A'),(3,'Northgate Cellars','A'),
 (4,'Alder Creek','C'),(5,'Bellweather','C'),(6,'Copperline','C'),
 (7,'Dunmore','C'),(8,'Eastbrook','C'),(9,'Foxglove','C'),
 (10,'Granite Hill','C'),(11,'Hollow Ridge','C'),(12,'Ironwood','C'),
 (13,'Juniper Bend','C'),(14,'Kestrel','C');

INSERT INTO wines (id,name,varietal,color) VALUES
 (1,'Cabernet Sauvignon','Cabernet Sauvignon','red'),
 (2,'Merlot','Merlot','red'),
 (3,'Pinot Grigio','Pinot Grigio','white'),
 (4,'Chardonnay','Chardonnay','white'),
 (5,'Rosé','Rosé','rosé');

INSERT INTO glasses (id,name,size_ml,shape) VALUES
 (1,'Claret 750',750,'claret'),
 (2,'Burgundy 750',750,'burgundy'),
 (3,'Burgundy 1500',1500,'burgundy'),
 (4,'Bordeaux 375',375,'bordeaux');

INSERT INTO line_formats (id,name,size_ml,description) VALUES
 (1,'750',750,'standard 750ml run'),(2,'1500',1500,'1.5L run'),(3,'375',375,'375ml run');

INSERT INTO corks (id,name,material,branded) VALUES
 (1,'Cork Natural A','natural',0),(2,'Cork Natural B','natural',0),
 (3,'Cork Branded Wolf','natural',1),(4,'Cork Branded Cedar','natural',1),
 (5,'Cork Branded Northgate','natural',1);

INSERT INTO foils (id,name,color) VALUES
 (1,'Foil Black','black'),(2,'Foil Gold','gold'),
 (3,'Foil Red','red'),(4,'Foil Green','green');

INSERT INTO knockdowns (id,name,pack_size,material) VALUES
 (1,'KD 12x750','12','corrugated'),(2,'KD 6x1500','6','corrugated'),
 (3,'KD 12x375','12','corrugated');

INSERT INTO labels (id,name,customer_id,adhesive,family) VALUES
 (1,'WLF-CS-LBL',1,'water','wolf'),(2,'WLF-ME-LBL',1,'water','wolf'),
 (3,'WLF-PG-LBL',1,'water','wolf'),
 (4,'CDR-CS-LBL',2,'psa','cedar'),(5,'CDR-ME-LBL',2,'psa','cedar'),
 (6,'CDR-CH-LBL',2,'psa','cedar'),
 (7,'NGT-ME-LBL',3,'psa','northgate'),(8,'NGT-RO-LBL',3,'psa','northgate'),
 (9,'NGT-CS-LBL',3,'psa','northgate'),
 (10,'ALD-CS-LBL',4,'psa','alder'),(11,'ALD-ME-LBL',4,'psa','alder'),
 (12,'BEL-CH-LBL',5,'psa','bell'),(13,'COP-PG-LBL',6,'psa','copper'),
 (14,'DUN-CS-LBL',7,'psa','dunmore'),(15,'EAS-RO-LBL',8,'psa','east');

INSERT INTO skus (id,part_number,description,customer_id,wine_id,glass_id,label_id,cork_id,foil_id,knockdown_id,line_format_id,case_pack) VALUES
 (1,'WLF-CS-750','Wolf Cab Sauv 750',1,1,1,1,3,1,1,1,12),
 (2,'WLF-ME-750','Wolf Merlot 750',1,2,1,2,3,1,1,1,12),
 (3,'WLF-PG-750','Wolf Pinot Grigio 750',1,3,2,3,3,2,1,1,12),
 (4,'CDR-CS-750','Cedar Cab Sauv 750',2,1,1,4,4,3,1,1,12),
 (5,'CDR-ME-1500','Cedar Merlot 1.5L',2,2,3,5,4,3,2,2,6),
 (6,'CDR-CH-750','Cedar Chardonnay 750',2,4,1,6,4,2,1,1,12),
 (7,'NGT-ME-750','Northgate Merlot 750',3,2,1,7,5,1,1,1,12),
 (8,'NGT-RO-1500','Northgate Rosé 1.5L',3,5,3,8,5,4,2,2,6),
 (9,'NGT-CS-750','Northgate Cab Sauv 750',3,1,1,9,5,1,1,1,12),
 (10,'ALD-CS-750','Alder Cab Sauv 750',4,1,1,10,1,1,1,1,12),
 (11,'ALD-ME-375','Alder Merlot 375',4,2,4,11,1,2,3,3,12),
 (12,'BEL-CH-750','Bellweather Chardonnay 750',5,4,2,12,2,2,1,1,12),
 (13,'COP-PG-375','Copperline Pinot Grigio 375',6,3,4,13,2,4,3,3,12),
 (14,'DUN-CS-750','Dunmore Cab Sauv 750',7,1,1,14,2,3,1,1,12),
 (15,'EAS-RO-375','Eastbrook Rosé 375',8,5,4,15,1,4,3,3,12);

INSERT INTO line_sku_rates (line_id,sku_id,ideal_bpm)
 SELECT 1,id,600 FROM skus WHERE line_format_id=1;
INSERT INTO line_sku_rates (line_id,sku_id,ideal_bpm)
 SELECT 2,id,500 FROM skus WHERE line_format_id=1;
INSERT INTO line_sku_rates (line_id,sku_id,ideal_bpm)
 SELECT 2,id,300 FROM skus WHERE line_format_id=2;
INSERT INTO line_sku_rates (line_id,sku_id,ideal_bpm)
 SELECT 3,id,800 FROM skus WHERE line_format_id=3;

INSERT INTO component_standards (component,swap_min,serial,triggers_flush,notes) VALUES
 ('blow_through',20,1,1,'wine change; flush and dump to mixer'),
 ('glass',20,0,0,'format change; rinse and filler change parts'),
 ('label',10,0,0,'label roll and web'),
 ('cork',5,0,0,'cork hopper'),
 ('foil',4,0,0,'foil roll'),
 ('knockdown',12,0,0,'packaging change');

INSERT INTO changeover_procedures (customer_id,blow_through_std_min,verification_min,startup_min,blow_through_target_bottles,total_std_min) VALUES
 (1,20,10,30,30,80),(2,20,10,30,30,80),(3,20,10,30,30,80),
 (4,20,10,30,30,80),(5,20,10,30,30,80),(6,20,10,30,30,80),
 (7,20,10,30,30,80),(8,20,10,30,30,80),(9,20,10,30,30,80),
 (10,20,10,30,30,80),(11,20,10,30,30,80),(12,20,10,30,30,80),
 (13,20,10,30,30,80),(14,20,10,30,30,80);
