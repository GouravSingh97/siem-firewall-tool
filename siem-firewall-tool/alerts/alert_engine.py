import time
import sqlite3
import os
from datetime import datetime
from storage.db_handler import init_db

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.abspath(
    os.environ.get("DB_PATH", os.path.join(BASE_DIR, "..", "storage", "firewall_logs.db"))
)

def _connect():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def ensure_alerts_table():
    with _connect() as con:
        con.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                src_ip TEXT,
                dst_ip TEXT,
                proto TEXT,
                port INTEGER,
                severity TEXT,
                description TEXT,
                status TEXT DEFAULT 'OPEN'
            )
            """
        )
        con.execute("CREATE INDEX IF NOT EXISTS idx_alerts ON alerts(status, src_ip)")
        con.commit()

def insert_alert(src_ip, dst_ip, proto, port, severity, description):
    ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    with _connect() as con:
        con.execute(
            """
            INSERT INTO alerts (timestamp, src_ip, dst_ip, proto, port, severity, description, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'OPEN')
            """,
            (ts, src_ip, dst_ip, proto, port, severity, description),
        )
        con.commit()

def blocks_last_window(minutes=5):
    with _connect() as con:
        return con.execute(
            """SELECT src_ip, COUNT(*) c
               FROM logs
               WHERE action IN ('BLOCK','DENY') AND timestamp >= datetime('now', ?)
               GROUP BY src_ip
               ORDER BY c DESC""",
            (f"-{minutes} minutes",),
        ).fetchall()

def unique_ports_by_src(minutes=5):
    with _connect() as con:
        return con.execute(
            """SELECT src_ip, COUNT(DISTINCT port) p
               FROM logs
               WHERE timestamp >= datetime('now', ?)
               GROUP BY src_ip
               ORDER BY p DESC""",
            (f"-{minutes} minutes",),
        ).fetchall()

def latest_logs(minutes=5):
    with _connect() as con:
        return con.execute(
            """SELECT * FROM logs
               WHERE timestamp >= datetime('now', ?)""",
            (f"-{minutes} minutes",),
        ).fetchall()

def main():
    init_db()
    ensure_alerts_table()
    print("[*] Alert engine started, watching logs...")

    while True:
        try:
            # Rule 1: Too many blocks/denies
            for r in blocks_last_window(5):
                if r["c"] >= 50:
                    insert_alert(r["src_ip"], None, None, None, "HIGH",
                                 f"High number of blocks from {r['src_ip']} in last 5 min: {r['c']}")

            # Rule 2: Port scan (many unique ports from one IP)
            for r in unique_ports_by_src(5):
                if r["p"] >= 100:
                    insert_alert(r["src_ip"], None, None, None, "MEDIUM",
                                 f"Possible port scan from {r['src_ip']} hitting {r['p']} unique ports")

            # Rule 3: Suspicious localhost traffic
            for log in latest_logs(1):
                if log["src_ip"] == "127.0.0.1" and log["dst_ip"] == "127.0.0.1":
                    insert_alert(log["src_ip"], log["dst_ip"], log["proto"], log["port"], "LOW",
                                 "Unusual localhost traffic detected")

            time.sleep(10)

        except KeyboardInterrupt:
            print("[*] Alert engine stopped by user")
            break
        except Exception as e:
            print(f"[!] Error in alert engine: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
