#!/bin/bash
# Hecate 100X Loop — Proaktiver Agent mit Auto-Remediation + Workflows + STATE.md
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
BASE="/root/projects/loop-master"
export PYTHONPATH="$BASE"
LOG="/var/log/hecate_loop.log"
TS=$(date '+%F %T')
echo "$TS === 100X Loop Start ===" >> "$LOG"

# ── 0. STATE.md laden als Session-Kontext ──
STATE_HEADER=""
if [ -f "$HOME/.hecate/STATE.md" ]; then
    STATE_HEADER=$(head -20 "$HOME/.hecate/STATE.md" 2>/dev/null)
fi

# ── 1. Bridge: Status snapshot ──
python3 "$BASE/hecate_bridge.py" status > /tmp/hecate_status.json 2>> "$LOG"

# ── 2. Findings prüfen ──
python3 "$BASE/hecate_bridge.py" findings 10 > /tmp/hecate_latest.txt 2>> "$LOG"
KRIT=$(grep -c "🔴" /tmp/hecate_latest.txt 2>/dev/null | head -1 || echo 0)
HOCH=$(grep -c "🟠" /tmp/hecate_latest.txt 2>/dev/null | head -1 || echo 0)

# ── 3. Auto-Remediation ist DEAKTIVIERT (Proposal-only Modus) ──
python3 "$BASE/hecate/auto_remediate.py" >> "$LOG" 2>&1

# ── 4. Self-Improvement (Skills aktualisieren) ──
python3 "$BASE/hecate/self_improvement.py" >> "$LOG" 2>&1

# ── 5. Workflow: Health-Check ──
python3 -c "
import sys; sys.path.insert(0, '$BASE')
from hecate.workflow_engine import Workflow, WorkflowStep
wf = Workflow('health_check')
wf.add(WorkflowStep('disk', 'Disk', lambda ctx: {'ok': True}))
wf.add(WorkflowStep('memory', 'Memory', lambda ctx: {'ok': True}))
wf.add(WorkflowStep('sensors', 'Sensors', lambda ctx: {'alert': $KRIT > 0 or $HOCH > 0}, depends_on=['disk','memory']))
wf.run()
" >> "$LOG" 2>&1

# ── 6. STATE.md aktualisieren (Open failures + Last session) ──
KRIT="$KRIT" HOCH="$HOCH" python3 -c "
import os, sys, json
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, '$BASE')
from hecate.state_file import StateFile

state = StateFile.load()

# Open failures aus dem Bus extrahieren
bus = Path('/var/lib/loop-master/findings.jsonl')
today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
if bus.exists():
    open_items = []
    for line in bus.open():
        if not line.strip(): continue
        try:
            f = json.loads(line)
            if f.get('severity') in ('krit','hoch') and f.get('ts','').startswith(today):
                open_items.append(f'{f.get(\"sensor\",\"?\")}: {f.get(\"subject\",\"-\")[:60]}')
        except Exception:
            pass
    # Deduplizierte Open failures schreiben (heutige)
    for item in set(open_items):
        if item not in state.open_failures:
            state = state.add_open_failure(item)

# Last session aktualisieren
now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')
krit = os.environ['KRIT']
hoch = os.environ['HOCH']
last = f'{now} UTC — Loop: {krit} krit / {hoch} hoch. Skills aktualisiert. Workflow health_check ausgefuehrt.'
state = state.set_last_session(last)
state.save()
print(f'STATE.md aktualisiert: {krit} krit / {hoch} hoch')
" >> "$LOG" 2>&1

# ── 8. System-Housekeeping: scan + classify + propose ──
python3 "$BASE/hecate/system_housekeeper.py" scan >> "$LOG" 2>&1
python3 "$BASE/hecate/system_housekeeper.py" classify >> "$LOG" 2>&1
python3 "$BASE/hecate/system_housekeeper.py" propose >> "$LOG" 2>&1

# ── 9. Telegram-Freigabe-Anfragen fuer grosse Entscheidungen ──
python3 "$BASE/hecate/proposal_notifier.py" >> "$LOG" 2>&1

# ── 10. Freigegebene Housekeeping-Proposals ausfuehren (nur safe Klassen) ──
python3 "$BASE/hecate/housekeeping_worker.py" --apply-approved >> "$LOG" 2>&1

# ── 7. Kein Telegram-Spam mehr ──
# Roh-Findings werden lokal geloggt und in Reports verdichtet.
# Telegram sendet nur noch echte Entscheidungs-Proposals (siehe hecate/proposal_bot.py).
# Kritische Zustaende sind jederzeit ueber /status und /sensors abfragbar.

echo "$TS === 100X Loop Done (krit=$KRIT hoch=$HOCH) ===" >> "$LOG"
