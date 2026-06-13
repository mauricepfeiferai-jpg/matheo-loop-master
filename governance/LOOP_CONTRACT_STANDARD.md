# HECATE Loop Contract Standard

> Jeder aktive Loop in HECATE muss diesen Contract erfüllen.
> Ohne Contract darf der Loop nicht aktiv laufen.

---

## Template

```markdown
# Loop Contract: <Name>

## 1. Basis
- **Loop Name:**
- **Zweck:**
- **Trigger:** (cron, event, manual, sensor-threshold)
- **Maker Agent:**
- **Checker Agent:**
- **Verifier:**

## 2. Daten
- **Input Sources:**
- **Output Files:**
- **Output Min Bytes:** (≥ 200 empfohlen)

## 3. Aktionen
- **Allowed Actions:**
- **Forbidden Actions:**

## 4. Risiko
- **Risk Level:** (L0–L5)
- **Approval Required:** (ja/nein)
- **Max Runtime:**
- **Max Retries:**
- **Token/Cost Budget:**

## 5. Governance
- **Stop Condition:**
- **Rollback Rule:**
- **Telegram Rule:** (nur Decision Cards / Eskalation / Digest)
- **Success Criteria:**

## 6. Status
- **Status:** proposed | approved | active | paused | deprecated
- **Approved By:**
- **Approved At:**
```

---

## Validierungsregeln

- Jeder aktive Loop muss einen gültigen Contract unter `/root/projects/loop-master/governance/contracts/` haben.
- `Allowed Actions` und `Forbidden Actions` müssen disjunkt sein.
- `Risk Level` muss mit `Approval Required` übereinstimmen: L0–L2 brauchen keine Approval, L3+ brauchen Approval.
- `Telegram Rule` muss der Constitution entsprechen.
- `Success Criteria` müssen quantifizierbar sein.

---

## Beispiel: hecate-sensors

```markdown
# Loop Contract: hecate-sensors

## 1. Basis
- **Loop Name:** hecate-sensors
- **Zweck:** Systemzustand prüfen und Findings in Bus schreiben
- **Trigger:** cron */15
- **Maker Agent:** sensors/run_all.py
- **Checker Agent:** (keiner, deterministisch)
- **Verifier:** Bus enthält Eintrag, kein Crash

## 2. Daten
- **Input Sources:** /etc, /var/log, systemd, docker, cron.d
- **Output Files:** /var/lib/loop-master/findings.jsonl
- **Output Min Bytes:** 0 (append-only)

## 3. Aktionen
- **Allowed Actions:** lesen, JSONL append
- **Forbidden Actions:** schreiben außer findings.jsonl, services restarten, crons ändern, löschen

## 4. Risiko
- **Risk Level:** L0/L1
- **Approval Required:** nein
- **Max Runtime:** 5 Minuten
- **Max Retries:** 0 (Sensor-Crash → Finding, kein Retry)
- **Token/Cost Budget:** 0 (keine LLM-Calls)

## 5. Governance
- **Stop Condition:** `touch /var/lib/loop-master/.stop_sensors`
- **Rollback Rule:** Stop-Datei entfernen reaktiviert den Loop
- **Telegram Rule:** Kein Telegram; Findings gehen in Tagesreport
- **Success Criteria:** alle 7+ Sensoren laufen, Bus enthält ≤ 5% ERROR-Einträge

## 6. Status
- **Status:** active
- **Approved By:** Maurice
- **Approved At:** 2026-06-13
```
