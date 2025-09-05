import sqlite3, os, json
DB = os.path.abspath(os.environ.get("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "storage", "firewall_logs.db")))
con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
cur = con.cursor()
cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 100")
rows = [dict(r) for r in cur.fetchall()]
print(json.dumps(rows, indent=2))
con.close()
