import os
from flask import Flask, render_template, request, jsonify
from storage.db_handler import init_db, stats, fetch_logs, fetch_alerts, update_alert_status, top_talkers, traffic_series

app = Flask(__name__, static_folder="static", template_folder="templates")
init_db()

# Frontend pages
@app.route("/")
def home():
    return render_template("index.html")

@app.route("/logs")
def logs_page():
    return render_template("logs.html")

@app.route("/alerts")
def alerts_page():
    return render_template("alerts.html")

@app.route("/graph")
def graph_page():
    return render_template("graph.html")

@app.route("/compliance")
def compliance_page():
    return render_template("compliance.html")

# API endpoints
@app.get("/api/stats")
def api_stats():
    return jsonify(stats())

@app.get("/api/top-talkers")
def api_top_talkers():
    limit = int(request.args.get("limit", 50))
    return jsonify(top_talkers(limit))

@app.get("/api/traffic")
def api_traffic():
    minutes = int(request.args.get("minutes", 60))
    return jsonify(traffic_series(minutes))

@app.get("/api/logs")
def api_logs():
    page = int(request.args.get("page", 1))
    page_size = int(request.args.get("page_size", 50))
    filters = {
        "q": request.args.get("q"),
        "action": request.args.get("action"),
        "proto": request.args.get("proto"),
        "port": request.args.get("port"),
        "ip": request.args.get("ip"),
        "from": request.args.get("from"),
        "to": request.args.get("to"),
    }
    rows, total = fetch_logs(filters, page, page_size)
    data = [dict(r) for r in rows]
    return jsonify({"data": data, "total": total, "page": page, "page_size": page_size})

@app.get("/api/alerts")
def api_alerts():
    status_q = request.args.get("status")
    limit = int(request.args.get("limit", 100))
    return jsonify(fetch_alerts(status_q, limit))

@app.post("/api/alerts/<int:alert_id>/status")
def api_alert_status(alert_id: int):
    status_body = request.json.get("status", "CLOSED")
    update_alert_status(alert_id, status_body)
    return jsonify({"ok": True})

if __name__ == "__main__":
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", "5000"))
    app.run(host=host, port=port)
