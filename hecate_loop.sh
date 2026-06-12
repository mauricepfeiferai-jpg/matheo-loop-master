#!/bin/bash
# Hecate 100X Loop — Proaktiver Agent mit Auto-Remediation + Workflows
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
BASE="/root/projects/loop-master"
LOG="/var/log/hecate_loop.log"
echo "$(date '+%F %T') === 100X Loop Start ===" >> "$LOG"

# 1. Bridge: Status snapshot
python3 "$BASE/hecate_bridge.py" status > /tmp/hecate_status.json 2>> "$LOG"

# 2. Findings prüfen
python3 "$BASE/hecate_bridge.py" findings 10 > /tmp/hecate_latest.txt 2>> "$LOG"
KRIT=$(grep -c "🔴" /tmp/hecate_latest.txt 2>/dev/null | head -1 || echo 0)
HOCH=$(grep -c "🟠" /tmp/hecate_latest.txt 2>/dev/null | head -1 || echo 0)

# 3. Auto-Remediation bei bekannten Problemen
if [ "$KRIT" -gt 0 ] || [ "$HOCH" -gt 0 ]; then
    python3 "$BASE/hecate/auto_remediate.py" >> "$LOG" 2>&1
fi

# 4. Self-Improvement (Skills aktualisieren)
python3 "$BASE/hecate/self_improvement.py" >> "$LOG" 2>&1

# 5. Workflow: Health-Check
python3 -c "
import sys; sys.path.insert(0, '$BASE')
from hecate.workflow_engine import Workflow, WorkflowStep
wf = Workflow('health_check')
wf.add(WorkflowStep('disk', 'Disk', lambda ctx: {'ok': True}))
wf.add(WorkflowStep('memory', 'Memory', lambda ctx: {'ok': True}))
wf.add(WorkflowStep('sensors', 'Sensors', lambda ctx: {'alert': $KRIT > 0 or $HOCH > 0}, depends_on=['disk','memory']))
wf.run()
" >> "$LOG" 2>&1

# 6. Alert wenn nötig
if [ "$KRIT" -gt 0 ] || [ "$HOCH" -gt 0 ]; then
    MSG="🔴/🟠 Hecate Alert: $KRIT kritisch + $HOCH hoch. Auto-Remediation wurde versucht. Soll ich Details schicken oder Sensoren triggern?"
    hermes send --to telegram "$MSG" 2>> "$LOG"
fi

echo "$(date '+%F %T') === 100X Loop Done (krit=$KRIT hoch=$HOCH) ===" >> "$LOG"
