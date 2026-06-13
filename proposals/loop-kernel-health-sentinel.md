---
status: vorgeschlagen
loop: loop-kernel-health-sentinel
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: loop-kernel-health-sentinel

**Zweck:** Server-Health-Sentinel aus loop_kernel als Sensor-Erweiterung (Docker/Disk/Memory/Load/Certs)
**Schedule:** `*/15 * * * *`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# loop-kernel-health-sentinel — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start loop-kernel-health-sentinel)
OUTPUT=$(mktemp /var/lib/loop-master/loop-kernel-health-sentinel.XXXX.out)
if bash /root/loop_kernel/health-sentinel/loop.sh > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop loop-kernel-health-sentinel`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).

> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.
