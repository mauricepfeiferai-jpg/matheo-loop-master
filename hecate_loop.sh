#!/bin/bash
# Hecate Proaktiver Loop — alle 15 Minuten via cron
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
BRIDGE="/root/projects/loop-master/hecate_bridge.py"
LOG="/var/log/hecate_loop.log"
echo "$(date '+%F %T') Start" >> "$LOG"
$BRIDGE findings 5 > /tmp/hecate_latest.txt 2>> "$LOG"
KRIT=$(grep -c "🔴" /tmp/hecate_latest.txt 2>/dev/null | head -1 || echo 0)
HOCH=$(grep -c "🟠" /tmp/hecate_latest.txt 2>/dev/null | head -1 || echo 0)
# Stelle sicher dass es Zahlen sind
KRIT=${KRIT:-0}
HOCH=${HOCH:-0}
if [ "$KRIT" -gt 0 ] || [ "$HOCH" -gt 0 ]; then
    MSG="🔴/🟠 Hecate Alert: $KRIT kritisch + $HOCH hoch. Soll ich Sensoren triggern oder Details schicken?"
    hermes send --to telegram "$MSG" 2>> "$LOG"
fi
echo "$(date '+%F %T') Done (krit=$KRIT hoch=$HOCH)" >> "$LOG"
