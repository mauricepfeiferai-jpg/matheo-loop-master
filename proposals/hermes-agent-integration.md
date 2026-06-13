---
status: vorgeschlagen
loop: hermes-agent-integration
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: hermes-agent-integration

**Zweck:** Hermes Agent (Nous Research) vollstaendig in HECATE integrieren: Adapter, Skill-Router, Gateway, Subagent-Delegation
**Schedule:** `*/30 * * * *`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# hermes-agent-integration — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start hermes-agent-integration)
OUTPUT=$(mktemp /var/lib/loop-master/hermes-agent-integration.XXXX.out)
if python3 -m hecate.hermes_adapter_check > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop hermes-agent-integration`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).

> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.
