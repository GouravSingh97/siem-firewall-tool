import os, re, time, datetime
from storage.db_handler import insert_log, init_db

LOG_FILE = os.environ.get("LOG_FILE", "/var/log/ufw.log")

ts_re = re.compile(r"^([A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})")
kv_re = re.compile(r"(\bSRC=([0-9a-fA-F\.:]+)|\bDST=([0-9a-fA-F\.:]+)|\bPROTO=([A-Z0-9]+)|\bDPT=(\d+))")
block_re = re.compile(r"\bBLOCK\b|\bDENY\b|\bREJECT\b", re.IGNORECASE)
allow_re = re.compile(r"\bALLOW\b|\bACCEPT\b", re.IGNORECASE)

def parse_line(line: str):
    ts_match = ts_re.search(line)
    if ts_match:
        ts_str = ts_match.group(1)
        now_year = datetime.datetime.now().year
        ts = datetime.datetime.strptime(f"{now_year} {ts_str}", "%Y %b %d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    else:
        ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    src = dst = ""
    proto = ""
    port = 0

    for m in kv_re.finditer(line):
        if m.group(2):
            src = m.group(2)
        if m.group(3):
            dst = m.group(3)
        if m.group(4):
            proto = m.group(4).upper()
        if m.group(5):
            try:
                port = int(m.group(5))
            except:
                port = 0

    action = "BLOCK" if block_re.search(line) else ("ALLOW" if allow_re.search(line) else "UNKNOWN")
    return ts, src, dst, proto, port, action

def follow(path):
    with open(path, "r", errors="ignore") as f:
        f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if not line:
                time.sleep(0.5)
                continue
            yield line

def main():
    init_db()
    path = LOG_FILE if os.path.isfile(LOG_FILE) else os.environ.get("LOG_FILE_FALLBACK", "sample_logs/firewall.log")
    for line in follow(path):
        ts, src, dst, proto, port, action = parse_line(line)
        if src or dst or proto or port or action != "UNKNOWN":
            insert_log(ts, src, dst, proto, port, action)

if __name__ == "__main__":
    main()
