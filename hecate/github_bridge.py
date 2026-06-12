#!/usr/bin/env python3
"""GitHub Bridge — PRs, Issues, Actions abfragen.

Braucht GITHUB_TOKEN in ENV.
"""
import json, os, subprocess
from datetime import datetime, timezone
from pathlib import Path

BUS = Path("/var/lib/loop-master/findings.jsonl")
TOKEN = os.environ.get("GITHUB_TOKEN","")

def gh_api(endpoint: str) -> dict | list:
    if not TOKEN: return {}
    cmd = ["curl", "-s", "-H", f"Authorization: token {TOKEN}",
           f"https://api.github.com{endpoint}"]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return json.loads(r.stdout)
    except Exception as e:
        return {"error": str(e)}

def check_prs(owner: str, repo: str):
    data = gh_api(f"/repos/{owner}/{repo}/pulls?state=open")
    if isinstance(data, list):
        for pr in data:
            finding = {
                "sensor": "github",
                "severity": "info" if pr.get("draft") else "mittel",
                "f_class": "github.open_pr",
                "subject": f"PR #{pr['number']}: {pr['title'][:60]}",
                "evidence": f"by {pr['user']['login']} — {pr['html_url']}",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            with open(BUS, "a") as f:
                f.write(json.dumps(finding, ensure_ascii=False) + "\n")
        print(f"GitHub: {len(data)} open PRs")
    else:
        print(f"GitHub Error: {data.get('error','')}")

def check_issues(owner: str, repo: str):
    data = gh_api(f"/repos/{owner}/{repo}/issues?state=open")
    if isinstance(data, list):
        krit_labels = {"bug", "critical", "security", "crash"}
        for issue in data:
            labels = {l["name"].lower() for l in issue.get("labels",[])}
            sev = "hoch" if labels & krit_labels else "info"
            finding = {
                "sensor": "github",
                "severity": sev,
                "f_class": "github.open_issue",
                "subject": f"Issue #{issue['number']}: {issue['title'][:60]}",
                "evidence": f"Labels: {list(labels)} — {issue['html_url']}",
                "ts": datetime.now(timezone.utc).isoformat(),
            }
            with open(BUS, "a") as f:
                f.write(json.dumps(finding, ensure_ascii=False) + "\n")
        print(f"GitHub: {len(data)} open issues")

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        check_prs(sys.argv[1], sys.argv[2])
        check_issues(sys.argv[1], sys.argv[2])
    else:
        print("github_bridge.py <owner> <repo>")
