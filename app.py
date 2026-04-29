from flask import Flask, render_template, request, jsonify, session
import sqlite3, os, json
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'ffl-sustainability-2026-secret')
DB_PATH = os.environ.get('DB_PATH', 'ffl.db')
EDIT_PASSWORD = os.environ.get('EDIT_PASSWORD', 'FFL2030')

# ── DB helpers ──────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS monthly (
        id TEXT PRIMARY KEY, label TEXT, yr INT, mo INT, qtr INT,
        production REAL, dyeing_prod REAL, sample_prod REAL, washing_prod REAL,
        energy_mj REAL, dyeing_energy REAL, sample_energy REAL, washing_energy REAL,
        carbon REAL, scope1 REAL, scope2 REAL, carbon_intensity REAL, carbon_per_kg REAL,
        water REAL, dyeing_water REAL, sample_water REAL, washing_water REAL,
        water_intensity REAL, solar REAL, solar_pct REAL, rainwater REAL,
        ng REAL, electricity REAL, diesel REAL, gasoline REAL,
        egb REAL, egb_pct REAL, shipment INTEGER,
        manpower INTEGER, male_w INTEGER, female_w INTEGER, staffs INTEGER,
        est INTEGER DEFAULT 0, ts TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS workforce (
        id TEXT PRIMARY KEY, label TEXT, yr INT, mo INT,
        rmg_male INT DEFAULT 0, rmg_female INT DEFAULT 0,
        staff_male INT DEFAULT 0, staff_female INT DEFAULT 0,
        leave_male INT DEFAULT 0, leave_female INT DEFAULT 0,
        onboard_male INT DEFAULT 0, onboard_female INT DEFAULT 0,
        ts TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS brands (
        bid TEXT PRIMARY KEY, name TEXT, color TEXT,
        water_intensity REAL, energy_intensity REAL, carbon_per_kg REAL
    );
    """)
    # Seed brands
    for bid, name, color in [('hm','H&M','#e63946'),('ca','C&A','#f77f00'),('inditex','Inditex','#2a9d8f')]:
        c.execute("INSERT OR IGNORE INTO brands(bid,name,color) VALUES(?,?,?)", (bid, name, color))
    # Seed monthly data
    seed = [
        ('2025-01','Jan 2025',2025,1,1,1660264,1199577,21883,438804,48847000,35000000,2000000,11847000,2953,2263,690,60.46,1.779,134968,100000,5000,29968,81.3,306294,21.1,0,937467,1143863,18537,4241,None,None,None,None,None,None,None,1),
        ('2025-02','Feb 2025',2025,2,1,1136447,820000,15000,301447,59300000,42000000,1500000,15800000,3427,2945,482,57.79,3.016,119855,88000,4200,27655,105.5,339085,29.8,100,911299,798793,18411,4932,None,None,None,None,None,None,None,1),
        ('2025-03','Mar 2025',2025,3,1,1297531,940000,18000,339531,51597000,37000000,1800000,12797000,3109,2508,601,60.24,2.396,101724,75000,3600,23124,78.4,422702,29.8,3,679071,995473,16656,5137,None,None,None,None,None,None,None,1),
        ('2025-04','Apr 2025',2025,4,2,1473209,1060000,20000,393209,73623000,53000000,2000000,18623000,4211,3682,529,57.21,2.859,109700,80000,3900,25800,74.5,428557,32.8,438,1128367,877250,33046,5618,None,None,None,None,None,None,None,1),
        ('2025-05','May 2025',2025,5,2,1662321,1200000,22000,440321,78875000,57000000,2200000,19675000,4703,4024,679,59.63,2.828,137119,100000,4900,32219,82.5,410876,26.7,2105,882667,1124750,65603,6809,None,None,None,None,None,None,None,1),
        ('2025-06','Jun 2025',2025,6,2,1317561,950000,18500,349061,65012000,47000000,1850000,16162000,3716,3061,655,57.16,2.820,100132,73000,3600,23532,76.0,411033,27.5,626,1379387,1085645,15261,5491,None,None,None,None,None,None,None,1),
        ('2025-07','Jul 2025',2025,7,3,1593259,1150000,21000,422259,81416000,59000000,2100000,20316000,4213,3999,214,51.75,2.644,125088,91000,4500,29588,78.5,378256,51.6,2232,1957562,355355,15085,4694,None,None,None,None,None,None,None,1),
        ('2026-01','Jan 2026',2026,1,1,1846452,1350000,24000,472452,88236930,64000000,2400000,21836930,4403,3685,718,49.90,2.384,138309,100000,5000,33309,74.9,305220,9.54,0,None,None,None,None,998.25,6.52,5368286,15466,8899,6567,2418,0),
        ('2026-02','Feb 2026',2026,2,1,1323024,955000,17000,351024,68027196,49000000,1700000,17327196,3621,3031,590,53.22,2.737,104076,75000,3700,25376,78.7,332278,11.91,0,None,None,None,None,523.71,4.41,4041859,15496,8908,6588,2401,0),
        ('2026-03','Mar 2026',2026,3,1,1515436,1100000,20000,395436,74473588,54000000,2000000,18473588,3975,3327,648,53.38,2.623,116286,84000,4200,28086,76.7,358898,11.27,240,None,None,None,None,617.83,4.73,5018374,15402,8884,6518,2399,0),
    ]
    cols = 'id,label,yr,mo,qtr,production,dyeing_prod,sample_prod,washing_prod,energy_mj,dyeing_energy,sample_energy,washing_energy,carbon,scope1,scope2,carbon_intensity,carbon_per_kg,water,dyeing_water,sample_water,washing_water,water_intensity,solar,solar_pct,rainwater,ng,electricity,diesel,gasoline,egb,egb_pct,shipment,manpower,male_w,female_w,staffs,est'
    placeholders = ','.join(['?']*len(cols.split(',')))
    for row in seed:
        c.execute(f"INSERT OR IGNORE INTO monthly({cols}) VALUES({placeholders})", row)
    # Seed workforce
    for wrow in [
        ('2026-01','Jan 2026',2026,1,8899,6567,2326,92,245,178,89,62),
        ('2026-02','Feb 2026',2026,2,8908,6588,2310,91,212,163,76,55),
        ('2026-03','Mar 2026',2026,3,8884,6518,2308,91,198,151,68,48),
    ]:
        c.execute("INSERT OR IGNORE INTO workforce(id,label,yr,mo,rmg_male,rmg_female,staff_male,staff_female,leave_male,leave_female,onboard_male,onboard_female) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", wrow)
    conn.commit()
    conn.close()

# ── Auth decorator ────────────────────────────────────────────────────────
def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('ffl_auth'):
            return jsonify({'ok': False, 'msg': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated

# ── Routes ─────────────────────────────────────────────────────────────────
@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/data')
def api_data():
    conn = get_db()
    monthly = [dict(r) for r in conn.execute("SELECT * FROM monthly ORDER BY yr, mo").fetchall()]
    workforce = [dict(r) for r in conn.execute("SELECT * FROM workforce ORDER BY yr, mo").fetchall()]
    brands = [dict(r) for r in conn.execute("SELECT * FROM brands").fetchall()]
    conn.close()
    return jsonify({'monthly': monthly, 'workforce': workforce, 'brands': brands,
                    'auth': bool(session.get('ffl_auth'))})

@app.route('/api/auth', methods=['POST'])
def api_auth():
    data = request.get_json()
    action = data.get('action')
    if action == 'login':
        if data.get('password') == EDIT_PASSWORD:
            session['ffl_auth'] = True
            return jsonify({'ok': True})
        return jsonify({'ok': False, 'msg': 'Incorrect password'})
    elif action == 'logout':
        session.pop('ffl_auth', None)
        return jsonify({'ok': True})
    elif action == 'check':
        return jsonify({'auth': bool(session.get('ffl_auth'))})
    return jsonify({'ok': False})

@app.route('/api/save/month', methods=['POST'])
@require_auth
def save_month():
    d = request.get_json()
    if not d.get('id'):
        return jsonify({'ok': False, 'msg': 'Missing id'})
    conn = get_db()
    # Upsert
    fields = ['label','yr','mo','qtr','production','dyeing_prod','sample_prod','washing_prod',
              'energy_mj','dyeing_energy','sample_energy','washing_energy',
              'carbon','scope1','scope2','carbon_intensity','carbon_per_kg',
              'water','dyeing_water','sample_water','washing_water','water_intensity',
              'solar','solar_pct','rainwater','ng','electricity','diesel','gasoline',
              'egb','egb_pct','shipment','manpower','male_w','female_w','staffs','est']
    conn.execute("INSERT OR IGNORE INTO monthly(id) VALUES(?)", (d['id'],))
    for f in fields:
        if f in d and d[f] != '':
            conn.execute(f"UPDATE monthly SET {f}=? WHERE id=?", (d[f], d['id']))
    conn.execute("UPDATE monthly SET ts=CURRENT_TIMESTAMP WHERE id=?", (d['id'],))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/save/workforce', methods=['POST'])
@require_auth
def save_workforce():
    d = request.get_json()
    conn = get_db()
    conn.execute("""INSERT OR REPLACE INTO workforce
        (id,label,yr,mo,rmg_male,rmg_female,staff_male,staff_female,
         leave_male,leave_female,onboard_male,onboard_female,ts)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,CURRENT_TIMESTAMP)""",
        (d['id'], d.get('label',''), d.get('yr',0), d.get('mo',0),
         d.get('rmg_male',0), d.get('rmg_female',0),
         d.get('staff_male',0), d.get('staff_female',0),
         d.get('leave_male',0), d.get('leave_female',0),
         d.get('onboard_male',0), d.get('onboard_female',0)))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/save/brand', methods=['POST'])
@require_auth
def save_brand():
    d = request.get_json()
    conn = get_db()
    conn.execute("UPDATE brands SET water_intensity=?,energy_intensity=?,carbon_per_kg=? WHERE bid=?",
                 (d.get('water_intensity'), d.get('energy_intensity'), d.get('carbon_per_kg'), d['bid']))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
