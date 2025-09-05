import os, sqlite3
from typing import List, Dict, Any, Tuple

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.abspath(os.environ.get("DB_PATH", os.path.join(BASE_DIR, "firewall_logs.db")))

def _connect():
    con = sqlite3.connect(DB, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def _table_exists(cur, name: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def _column_exists(cur, table: str, col: str) -> bool:
    cur.execute(f"PRAGMA table_info({table})")
    return any(r["name"] == col for r in cur.fetchall())

def _migrate():
    con = _connect()
    cur = con.cursor()

    # Logs table
    if not _table_exists(cur, "logs"):
        cur.execute("""
            CREATE TABLE logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                src_ip TEXT,
                dst_ip TEXT,
                proto TEXT,
                port INTEGER,
                action TEXT
            )
        """)
    else:
        # Add any missing columns (helps during schema updates)
        if not _column_exists(cur, "logs", "proto"):
            cur.execute("ALTER TABLE logs ADD COLUMN proto TEXT")
        if not _column_exists(cur, "logs", "port"):
            cur.execute("ALTER TABLE logs ADD COLUMN port INTEGER")
        if not _column_exists(cur, "logs", "action"):
            cur.execute("ALTER TABLE logs ADD COLUMN action TEXT")
        if not _column_exists(cur, "logs", "src_ip"):
            cur.execute("ALTER TABLE logs ADD COLUMN src_ip TEXT")
        if not _column_exists(cur, "logs", "dst_ip"):
            cur.execute("ALTER TABLE logs ADD COLUMN dst_ip TEXT")
        if not _column_exists(cur, "logs", "timestamp"):
            cur.execute("ALTER TABLE logs ADD COLUMN timestamp TEXT")

    # Alerts table
    if not _table_exists(cur, "alerts"):
        cur.execute("""
            CREATE TABLE alerts(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT DEFAULT (datetime('now')),
                message TEXT,
                severity TEXT,
                status TEXT DEFAULT 'OPEN'
            )
        """)
    else:
        if not _column_exists(cur, "alerts", "severity"):
            cur.execute("ALTER TABLE alerts ADD COLUMN severity TEXT")
        if not _column_exists(cur, "alerts", "status"):
            cur.execute("ALTER TABLE alerts ADD COLUMN status TEXT DEFAULT 'OPEN'")
        if not _column_exists(cur, "alerts", "timestamp"):
            cur.execute("ALTER TABLE alerts ADD COLUMN timestamp TEXT DEFAULT (datetime('now'))")

    # Indexes
    cur.execute("CREATE INDEX IF NOT EXISTS idx_logs ON logs(src_ip, dst_ip, proto, port, action)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_alerts ON alerts(status, severity)")

    con.commit()
    con.close()

def init_db():
    _migrate()

def insert_log(ts: str, src: str, dst: str, proto: str, port: int, action: str):
    con = _connect()
    cur = con.cursor()
    cur.execute(
        "INSERT INTO logs (timestamp, src_ip, dst_ip, proto, port, action) VALUES (?,?,?,?,?,?)",
        (ts, src, dst, proto, port, action),
    )
    con.commit()
    con.close()

def fetch_logs(filters: Dict[str, Any], page: int = 1, page_size: int = 100) -> Tuple[List[sqlite3.Row], int]:
    where = []
    args: List[Any] = []

    # Apply filters
    if filters.get("q"):
        where.append("(src_ip LIKE ? OR dst_ip LIKE ?)")
        args += [f"%{filters['q']}%", f"%{filters['q']}%"]
    if filters.get("action"):
        where.append("action = ?"); args.append(filters["action"].upper())
    if filters.get("proto"):
        where.append("proto = ?"); args.append(filters["proto"].upper())
    if filters.get("port"):
        where.append("port = ?"); args.append(int(filters["port"]))
    if filters.get("ip"):
        where.append("(src_ip = ? OR dst_ip = ?)"); args += [filters["ip"], filters["ip"]]
    if filters.get("from"):
        where.append("timestamp >= ?"); args.append(filters["from"])
    if filters.get("to"):
        where.append("timestamp <= ?"); args.append(filters["to"])

    where_sql = ("WHERE " + " AND ".join(where)) if where else ""
    offset = (page - 1) * page_size

    con = _connect()
    cur = con.cursor()
    cur.execute(f"SELECT COUNT(*) AS c FROM logs {where_sql}", args)
    total = cur.fetchone()["c"]

    cur.execute(
        f"SELECT * FROM logs {where_sql} ORDER BY id DESC LIMIT ? OFFSET ?",
        args + [page_size, offset],
    )
    rows = cur.fetchall()
    con.close()
    return rows, total

def stats():
    con = _connect(); cur = con.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM logs"); total = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM logs WHERE action='ALLOW'"); allowed = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM logs WHERE action IN ('BLOCK','DENY')"); blocked = cur.fetchone()["c"]
    cur.execute("SELECT COUNT(*) AS c FROM alerts WHERE status='OPEN'"); open_alerts = cur.fetchone()["c"]
    con.close()
    return {"total": total, "allowed": allowed, "blocked": blocked, "open_alerts": open_alerts}

def top_talkers(limit: int = 50):
    con = _connect(); cur = con.cursor()
    cur.execute(
        """SELECT src_ip AS src, dst_ip AS dst, COUNT(*) AS count
           FROM logs
           GROUP BY src_ip, dst_ip
           ORDER BY count DESC
           LIMIT ?""",
        (limit,),
    )
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows

def traffic_series(minutes: int = 60):
    con = _connect(); cur = con.cursor()
    cur.execute(
        """SELECT strftime('%Y-%m-%d %H:%M', timestamp) AS minute, COUNT(*) AS count
           FROM logs
           WHERE timestamp >= datetime('now', ?)
           GROUP BY minute
           ORDER BY minute""",
        (f"-{minutes} minutes",),
    )
    data = [dict(r) for r in cur.fetchall()]
    con.close()
    return data

def create_alert(message: str, severity: str = "INFO"):
    con = _connect(); cur = con.cursor()
    cur.execute("INSERT INTO alerts (message, severity) VALUES (?,?)", (message, severity))
    con.commit(); con.close()

def fetch_alerts(status: str = None, limit: int = 100):
    con = _connect(); cur = con.cursor()
    if status:
        cur.execute("SELECT * FROM alerts WHERE status=? ORDER BY id DESC LIMIT ?", (status, limit))
    else:
        cur.execute("SELECT * FROM alerts ORDER BY id DESC LIMIT ?", (limit,))
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows

def update_alert_status(alert_id: int, status: str):
    con = _connect(); cur = con.cursor()
    cur.execute("UPDATE alerts SET status=? WHERE id=?", (status, alert_id))
    con.commit(); con.close()
