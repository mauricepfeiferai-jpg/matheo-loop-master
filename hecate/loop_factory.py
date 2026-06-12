"""Loop-Factory: Hecate KREIERT Loops — aber immer als Proposal, nie direkt live.
Jeder generierte Loop ist ab Geburt: (a) Ledger-instrumentiert (Output-Beweis),
(b) Harness-pflichtig bei Umsetzung, (c) gated (Status-Workflow).
Status: vorgeschlagen -> freigegeben (Maurice) -> umgesetzt -> verifiziert"""
from pathlib import Path

PROPOSALS_DIR = Path("/root/projects/loop-master/proposals")

TEMPLATE = """---
status: vorgeschlagen
loop: {name}
erstellt: durch hecate.loop_factory
---

# Loop-Proposal: {name}

**Zweck:** {purpose}
**Schedule:** `{schedule}`

## Implementierung (nach Freigabe, via safety.harness)

```bash
#!/bin/bash
# {name} — Ledger-instrumentiert ab Geburt (kein Beweis = kein Erfolg)
LEDGER="python3 -m hecate.ledger"
cd /root/projects/loop-master
RID=$($LEDGER start {name})
OUTPUT=$(mktemp /var/lib/loop-master/{name}.XXXX.out)
if {command} > "$OUTPUT" 2>&1; then
    $LEDGER finish "$RID" --output "$OUTPUT"
else
    $LEDGER finish "$RID" --status failed --note "exit != 0"
fi
```

## Abnahme (vor Status: verifiziert)
1. Ein echter Lauf erzeugt einen ok-Eintrag: `python3 -m hecate.ledger report --loop {name}`
2. Provozierter Leerlauf landet als empty_output, nie als ok
3. sensors.ledger_stale meldet den Loop, wenn er >26h keinen ok-Lauf hat

## Rollback
Cron-Zeile entfernen. Keine weiteren Spuren (Ledger-Historie bleibt als Audit).
"""


def create_proposal(name: str, purpose: str, schedule: str, command: str,
                    proposals_dir: Path = PROPOSALS_DIR) -> Path:
    proposals_dir.mkdir(parents=True, exist_ok=True)
    target = proposals_dir / f"{name}.md"
    n = 2
    while target.exists():                      # nie ueberschreiben (append-only-Geist)
        target = proposals_dir / f"{name}-{n}.md"
        n += 1
    body = TEMPLATE.format(name=name, purpose=purpose, schedule=schedule, command=command)
    body += "\n> Umsetzung NUR nach Freigabe und durch safety.harness.run() — Deny-List gilt.\n"
    target.write_text(body)
    return target
