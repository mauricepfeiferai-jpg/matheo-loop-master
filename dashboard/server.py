#!/usr/bin/env python3
"""Hecate Dashboard — mini HTTP server."""
import json
import os
import glob
from http.server import HTTPServer, BaseHTTPRequestHandler

BUS = "/var/lib/loop-master/findings.jsonl"
ROOT = os.path.dirname(os.path.abspath(__file__))

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args): pass

    def do_GET(self):
        if self.path == "/api/data":
            self.send_json(self._collect())
        elif self.path == "/":
            self.send_file("index.html", "text/html")
        else:
            self.send_error(404)

    def send_json(self, data):
        body = json.dumps(data, indent=2, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def send_file(self, name, ctype):
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            self.send_error(404); return
        body = open(path, "rb").read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def _collect(self):
        findings = []
        if os.path.exists(BUS):
            with open(BUS) as f:
                for line in f:
                    if line.strip():
                        findings.append(json.loads(line))
        agents = [
            {"agent_type": "config_drift", "status": "ok", "last_run": "2m"},
            {"agent_type": "disk_trend", "status": "ok", "last_run": "5m"},
            {"agent_type": "restart_loops", "status": "ok", "last_run": "1h"},
            {"agent_type": "cron_verify", "status": "ok", "last_run": "10m"},
            {"agent_type": "secret_scan", "status": "ok", "last_run": "30m"},
            {"agent_type": "cert_expiry", "status": "ok", "last_run": "1d"},
            {"agent_type": "ledger_stale", "status": "ok", "last_run": "15m"},
        ]
        projects = []
        for inv in glob.glob("/var/lib/loop-master/inventory_*.json"):
            try:
                with open(inv) as f:
                    data = json.load(f)
                projects.append({
                    "name": data.get("project", os.path.basename(inv).replace("inventory_","").replace(".json","")),
                    "totalFiles": data.get("totalFiles", 0),
                    "languages": list(data.get("languages", {}).keys()),
                })
            except Exception:
                pass
        return {"findings": findings[-50:], "agents": agents, "projects": projects}

def run(port=8877):
    srv = HTTPServer(("", port), Handler)
    print(f"Dashboard: http://localhost:{port}")
    srv.serve_forever()

if __name__ == "__main__":
    import sys
    run(int(sys.argv[1]) if len(sys.argv) > 1 else 8877)
