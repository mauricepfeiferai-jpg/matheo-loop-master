#!/bin/bash
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
BASE="/root/projects/loop-master"
LOG="/var/log/hecate_digest.log"
HOUR=$(date +%H)
echo "$(date '+%F %T') Digest (hour=$HOUR)" >> "$LOG"

if [ "$HOUR" -eq "08" ]; then
    python3 -c "
import sys; sys.path.insert(0, '$BASE')
from hecate.executive_report import generate_executive_report
from hecate.telegram_enhanced import send_message
report = generate_executive_report()
send_message(report)
" >> "$LOG" 2>&1
elif [ "$HOUR" -eq "20" ]; then
    python3 -c "
import sys; sys.path.insert(0, '$BASE')
from hecate.trend_analyzer import analyze_findings_trend
from hecate.telegram_enhanced import send_message
f = analyze_findings_trend(24)
text = f'Tagesbericht\n\n🔴 Kritisch: {f[\"counts\"][\"krit\"]}\n🟠 Hoch: {f[\"counts\"][\"hoch\"]}\nTrend: {f[\"trend\"]}\n\nBefehle: /status /sensors /findings /dashboard /help'
send_message(text)
" >> "$LOG" 2>&1
fi
echo "$(date '+%F %T') Digest Done" >> "$LOG"
