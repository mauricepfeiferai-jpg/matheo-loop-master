# HECATE Enterprise Agent OS Blueprint

> Status: Plan + Governance-Entwürfe
> Nächster GO benötigt: Decision Card Loop aktivieren
> Noch nicht aktiv: Kein Total-Legacy-Scan, keine Mac-Aktionen, keine Mutationen.

---

## 1. Ziel

HECATE wird das einzige AI-/Agenten-Ökosystem.

Statt:

```
Hecate + Hermes + OpenClaw + alte Miner + alte Crons + alte Mac-Projekte + verstreute Agenten
```

wird es:

```
HECATE
├── Constitution / Governance
├── Decision Queue
├── Plugin-/Skill-Marketplace
├── Worker-Rollen
├── Project Atlas
├── Knowledge Atlas
├── Risk Atlas
├── Integration Proposals
├── Decommission Proposals
└── Ledger / Verifier / Lessons Learned
```

---

## 2. Kernzyklus (gated)

```
DISCOVER
  → MAP
  → UNDERSTAND
  → CLUSTER
  → SCORE
  → PROPOSE
  → WAIT FOR MAURICE GO
  → EXECUTE ONLY AFTER GO
  → VERIFY
  → LEDGER
  → LESSONS LEARNED
```

**Nicht erlaubt:**

- DISCOVER → AUTO DELETE
- DISCOVER → AUTO INTEGRATE
- DISCOVER → AUTO RESTART
- DISCOVER → AUTO CRON
- DISCOVER → AUTO PUBLISH

---

## 3. Governance-Dokumente (angelegt)

| Dokument | Zweck |
|----------|-------|
| `/root/projects/loop-master/governance/HECATE_CONSTITUTION.md` | Autonomie-Stufen L0–L5, Telegram-Regeln, lokale Modelle zuerst |
| `/root/projects/loop-master/governance/LOOP_CONTRACT_STANDARD.md` | Jeder aktive Loop braucht einen Contract |
| `/root/projects/loop-master/governance/DECISION_CARD_STANDARD.md` | Format für hochwertige Entscheidungsvorlagen |
| `/root/projects/loop-master/governance/PLUGIN_SKILL_MARKETPLACE_PLAN.md` | Alte Projekte → Skills / Sensoren / Worker / Archiv / Delete |
| `/root/projects/loop-master/governance/HECATE_TRUST_BOUNDARY.md` | Was HECATE lesen/schreiben/sendern darf und was nie |

---

## 4. Worker-Rollen (geplant)

| Rolle | Aufgabe |
|-------|---------|
| HECATE Orchestrator | Koordiniert Worker, keine offene Autonomie |
| Cartographer | Findet Pfade, Projekte, Daten, Repos, Services, Crons, Modelle |
| Repo Analyst | Versteht Codebases, Tests, README, Git-Status |
| System Auditor | Verknüpft Projekte mit Crons, systemd, Docker, Ports, Logs |
| Risk Auditor | Erkennt Secrets, Legal-, Kunden-, Trading-, Privatriskien |
| Value Evaluator | Bewertet Business-, System-, Content-, Produktpotenzial |
| Duplicate Hunter | Findet doppelte Projekte, verwaiste Varianten |
| Integration Architect | Prüft Skill/Sensor/Worker/Dashboard/OKF-Potenzial |
| Decommission Planner | Archive, Quarantine, Delete-Candidate-Vorschläge |
| Decision Writer | Erstellt Decision Cards |
| Strategy Critic | Greift Vorschläge an, bevor sie Maurice vorgelegt werden |
| Verifier | Prüft Befunde mit Dateien, Logs, Services, Git-Status |

---

## 5. Lokale Modell-Rollen (geplant)

- **Fast Classifier** (qwen2.5:0.5b / 1.5b)
- **Code Analyzer** (qwen2.5-coder:7b)
- **Log Summarizer** (qwen3:8b)
- **Risk Auditor** (deterministisch + qwen2.5-coder Review)
- **Decision Writer** (qwen3:8b)
- **Strategy Critic** (qwen3:8b)
- **Verifier** (deterministisch)
- **Embedding Model** (nomic-embed-text)

---

## 6. Erster Pilot: HECATE_DECISION_CARD_LOOP

### Aufgabe
Vorhandene Findings/Reports/Queues verdichten zu hochwertigen Decision Cards.

### Input
- `/var/lib/loop-master/findings.jsonl`
- `/var/lib/loop-master/proposal_notifications.jsonl`
- `/root/projects/loop-master/proposals/*.md`
- `/var/lib/loop-master/ledger.db`
- `/root/projects/loop-master/HECATE.md` / `STATE.md`

### Output
- `/var/lib/loop-master/decision_queue.jsonl`
- `/root/projects/loop-master/decision_cards/*.md`
- Daily Digest (Top-3)
- Telegram nur bei echter Entscheidung

### Erfolgskriterien
- 0 Cronjob-Responses an Telegram
- 0 SILENT-Meldungen
- 0 rohe Logs an Telegram
- Jede Telegram-Nachricht hat GO/NO/DETAILS/PLAN ONLY
- Jede Erfolgsmeldung hat Verifier-Beleg
- Jede L4/L5-Aktion braucht GO
- Mindestens 3 hochwertige Decision Cards aus vorhandenen Findings
- Keine Dateiänderung außerhalb erlaubter Reports/Standards

---

## 7. Wichtigste Risiken

| Risiko | Level | Maßnahme |
|--------|-------|----------|
| Telegram-Spam durch viele Proposals | hoch | Batch-Notifications mit Buttons, Rate-Limit 4h |
| Auto-Delete durch Klassifikator | kritisch | Deterministische Regeln + L5 für Delete |
| Secrets in Reports/Telegram | kritisch | Redaction + Trust Boundary |
| Mac-Daten unautorisiert lesen | kritisch | Mac erst nach L5 GO |
| Lokale Modelle zu langsam/unzuverlässig | mittel | Benchmark + Fallback-Policy |
| HECATE wird selbst zu Bloat | mittel | Loop Contracts + Decommission-Regeln |

---

## 8. Nächster empfohlener GO

**GO für Phase 0/1:**

1. Governance-Dokumente reviewen/approven (dieser Blueprint + 5 Standards).
2. HECATE_DECISION_CARD_LOOP bauen und aktivieren.
3. Nach erfolgreichem Pilot: GO für Total Legacy Discovery (Hetzner read-only).

**Nicht freigeben:** Auto-Delete, Auto-Integrate, Mac-Zugriff, Service-Restarts, Cron-Änderungen.

---

## 9. Was noch nicht passiert

- Kein Scan gestartet.
- Keine alten Projekte analysiert.
- Keine Mac-Aktion.
- Keine Dateiänderungen außerhalb Plan-/Standard-Dokumente.
- Keine Crons geändert.
- Keine Services gestartet/gestoppt/restartet.
- Keine Watchdogs umgebaut.
- Keine Auto-Remediation.
- Keine Daten gelöscht.
- Keine GitHub-Aktion.
- Keine OKF-Konvertierung.
- Keine Legal-/Trading-/Kunden-/Privatdaten angetastet.
- Keine Secrets ausgegeben.

---

*Erstellt: 2026-06-13*
*Wartet auf Maurice GO für nächsten Schritt.*
