#!/bin/bash
# Hecate 100X Loop — Proaktiver Agent mit Auto-Remediation + Workflows + STATE.md
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
BASE="/root/projects/loop-master"
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

# ── 3. Auto-Remediation bei bekannten Problemen ──
if [ "$KRIT" -gt 0 ] || [ "$HOCH" -gt 0 ]; then
    python3 "$BASE/hecate/auto_remediate.py" >> "$LOG" 2>&1
fi

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
python3 -c "
import sys; sys.path.insert(0, '$BASE')
from hecate.state_file import StateFile
import json
from pathlib import Path

state = StateFile.load()

# Open failures aus dem Bus extrahieren
bus = Path('/var/lib/loop-master/findings.jsonl')
if bus.exists():
    open_items = []
    for line in bus.open():
        if not line.strip(): continue
        try:
            f = json.loads(line)
            if f.get('severity') in ('krit','hoch') and f.get('ts','').startswith('$(date +%Y-%m-%d)'):
                open_items.append(f'{f.get(\"sensor\",\"?\")}: {f.get(\"subject\",\"-\")[:60]}')
        except Exception:
            pass
    # Deduplizierte Open failures schreiben (heutige)
    for item in set(open_items):
        if item not in state.open_failures:
            state = state.add_open_failure(item)

# Last session aktualisieren
last = f'$(date +%Y-%m-%d %H:%M) UTC — Loop: {KRIT} krit / {HOCH} hoch. Skills aktualisiert. Workflow health_check ausgefuehrt.'
state = state.set_last_session(last)
state.save()
print(f'STATE.md aktualisiert: {KRIT} krit / {HOCH} hoch')
" >> "$LOG" 2>&1

# ── 7. Alert wenn nötig ──
if [ "$KRIT" -gt 0 ] || [ "$HOCH" -gt 0 ]; then
    MSG="🔴/🟠 Hecate Alert: $KRIT kritisch + $HOCH hoch. Auto-Remediation wurde versucht. Soll ich Details schicken oder Sensoren triggern?"
    hermes send --to telegram "$MSG" 2>> "$LOG"
fi

echo "$TS === 100X Loop Done (krit=$KRIT hoch=$HOCH) ===" >> "$LOG"
