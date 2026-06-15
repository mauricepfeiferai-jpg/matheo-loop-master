#!/usr/bin/env bash
# Daily read-only smoke run for the 5 Hetzner watchdog agents.
# This script does NOT install cron or systemd. It does NOT send Telegram.
# It only creates reports in reports/ and raw_trace entries in the Learning Ledger.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

STOP_FILE="/var/lib/loop-master/.stop_daily_agent_smoke"
if [[ -f "$STOP_FILE" ]]; then
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) [daily-agent-smoke] STOP file present ($STOP_FILE). Exiting."
  exit 0
fi

LOG_PREFIX="$(date -u +%Y-%m-%dT%H:%M:%SZ) [daily-agent-smoke]"

agents=(
  archivist
  cost_guard
  security_scanner
  backup_checker
  performance_profiler
)

failures=0
for agent in "${agents[@]}"; do
  echo "$LOG_PREFIX Running $agent ..."
  if python3 -m hecate.agent_smoke "$agent"; then
    echo "$LOG_PREFIX $agent OK"
  else
    echo "$LOG_PREFIX $agent FAILED (exit $?)"
    failures=$((failures + 1))
  fi
done

if [[ $failures -gt 0 ]]; then
  echo "$LOG_PREFIX Finished with $failures failure(s)."
  exit 1
fi

echo "$LOG_PREFIX All agents OK."
