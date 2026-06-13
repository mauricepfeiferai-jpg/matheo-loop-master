# HECATE 100X — Master Plan

> Lokales, serverinternes Betriebssystem für Entscheidungen.
> Read-only, local-first, Proposal-only.

**Status:** PLAN ONLY — wartet auf GO  
**Autor:** Maurice + HECATE  
**Datum:** 2026-06-13  
**Ziel:** HECATE wird zum zentralen Operator-Layer für den gesamten Hetzner-Server.

---

## 1. Architektur-Kurzfassung

```
Scan → Understand → Score → Proposal → Maurice entscheidet → HECATE führt aus
```

Statt vieler lauter Crons und Auto-Fixes gibt es **einen zentralen Entscheidungs-Loop**:

1. **Inventory** — Was gibt es auf dem Server?
2. **Understand** — Was ist das? Wofür? Ist es aktiv/alt/gefährlich/wertvoll?
3. **Score** — Welche Kategorie? (CORE, PRODUCT, LIBRARY, KNOWLEDGE, EXPERIMENT, ARCHIVE, QUARANTINE, DELETE-CANDIDATE)
4. **Decide** — Entscheidungsvorlage bauen
5. **Execute** — Nur nach Maurice-GO

---

## 2. Lokaler Model-Router

### 2.1 Modell-Rollen

| Rolle | Aufgabe | Kandidat (lokal/Cloud) |
|-------|---------|------------------------|
| **Fast Classifier** | Klassifizieren, kurze Zusammenfassungen, Log-Triage | `qwen2.5:0.5b`, `qwen2.5:1.5b` |
| **Code Analyzer** | Code verstehen, Struktur erkennen, Patch-Vorschläge | `qwen2.5-coder:7b`, `qwen2.5-coder:14b` |
| **Reasoner** | Entscheidungen bewerten, Risiken abwägen | `qwen3:8b`, `qwen3:32b` (langsam) |
| **Embedding Model** | Projekte durchsuchbar machen | `nomic-embed-text` |
| **Verifier** | Prüfen, ob Behauptungen durch Dateien/Logs gedeckt sind | `qwen2.5-coder:7b` |
| **Vision Model** | Screenshots/Dashboards prüfen | optional, aktuell nicht lokal sinnvoll |

### 2.2 Bereitstellung

- Modelle laufen über **Ollama** (bereits installiert).
- Router-Skript: `hecate/model_router.py`
- Konfiguration: `hecate/config/models.yaml`
- Default-Fallback: lokale Modelle haben Vorrang; Cloud-Modelle nur bei explizitem GO.

### 2.3 Deterministisch bleiben ohne LLM

Folgende Aufgaben brauchen **kein LLM**:

- Dateien auflisten
- Git-Status prüfen
- Cron-Einträge parsen
- systemd-Units auflisten
- Ports prüfen
- Logs nach Mustern durchsuchen
- Secrets via Regex finden
- Checksummen bilden
- Duplikate finden (Hash-basiert)

---

## 3. Gesamtprüfung alter Projekte

### 3.1 Zu scannende Bereiche

| Pfad | Inhalt |
|------|--------|
| `/root/projects/*` | Hauptprojekte |
| `/root/vault/*` | Wissensdatenbank |
| `/root/.hermes/*` | Hermes-Agent-Profile |
| `/root/.hecate/*` | HECATE-State |
| `/root` (oberste Ebene) | Skripte, Configs |
| `/etc/cron.d/*` | System-Crons |
| `/etc/systemd/system/*` | System-Services |
| `/root/.config/systemd/user/*` | User-Services |
| `/var/log/*` | Logs |

### 3.2 Pro Projekt gesammelte Metriken

```yaml
projektname:
  pfad: /root/projects/xyz
  groesse_mb: 42
  dateien: 150
  letzte_aenderung: 2026-06-10
  git_status: clean | ahead | behind | untracked | kein_repo
  sprachen: [python, javascript, yaml]
  frameworks: [fastapi, react]
  tests_vorhanden: true
  readme_vorhanden: true
  startdateien: [main.py, app.py]
  services: [xyz.service]
  crons: ["0 * * * * /root/projects/xyz/run.sh"]
  ports: [8080]
  datenbanken: [postgres/xyz]
  secrets_risiko: hoch
  produktwert: mittel
  systemwert: hoch
  duplikate: ["aether_v3"]
  empfohlene_entcheidung: MERGE_INTO_HECATE
  begruendung: "Wichtige Sensor-Logik, kann in HECATE integriert werden."
  naechster_schritt: "Module identifizieren und migrieren"
```

### 3.3 Kategorien

| Status | Bedeutung |
|--------|-----------|
| **CORE** | Gehört zu HECATE / Matheo OS / MauriceAI |
| **PRODUCT** | Kann Geld, Kunden oder Reichweite bringen |
| **LIBRARY** | Wiederverwendbarer Baustein |
| **KNOWLEDGE** | Lern-/Research-Material |
| **EXPERIMENT** | Interessant, aber nicht produktiv |
| **ARCHIVE** | Aufbewahren, aber nicht aktiv |
| **QUARANTINE** | Risiko: Secrets, kaputte Crons, unklare Services |
| **DELETE-CANDIDATE** | Nur Löschvorschlag, niemals automatisch löschen |

---

## 4. Server Knowledge Graph

### 4.1 Knotentypen

- `Repo`
- `Service`
- `Cron`
- `Log`
- `Port`
- `Database`
- `Telegram-Bot`
- `Secret`
- `Model`
- `User`

### 4.2 Kantentypen

```
Repo → contains → File
Repo → has_service → Service
Repo → has_cron → Cron
Service → writes_to → Log
Service → listens_on → Port
Repo → connects_to → Database
Repo → sends_to → Telegram-Bot
Repo → contains_risk → Secret
Repo → uses_model → Model
```

### 4.3 Beispiel-Abfragen

- "Welche Projekte haben aktive Crons, aber wurden seit 6 Monaten nicht mehr geändert?"
- "Welche Services hören auf öffentliche Ports?"
- "Welche Projekte enthalten Secrets und haben aktive Services?"
- "Welche drei Projekte machen fast dasselbe?"

### 4.4 Speicherung

- Graph: `/var/lib/loop-master/knowledge_graph.jsonl`
- Embeddings: lokale Qdrant- oder Chroma-Datenbank
- Indizes: `project_index`, `code_index`, `log_index`

---

## 5. Proposal-only Telegram Governance

### 5.1 Erlaubte Telegram-Nachrichten

Nur noch folgende Formate:

```
PROPOSAL-ID: CLEANUP-001
Titel: Alte Backups archivieren
Warum jetzt: Disk > 85%
Befund: /backups/2024/ enthält 80 GB alte Dateien
Vorgeschlagene Aktion: Nach /archive/backups/2024 verschieben
Risiko: niedrig
Rollback: mv /archive/backups/2024 /backups/2024
Betroffene Dateien/Services: /backups/2024
Exakte Befehle: nur nach GO
Empfehlung: GO
Antwortoptionen:
  ✅ GO
  ❌ NO
  📄 DETAILS
  📝 PLAN ONLY
```

### 5.2 Verboten in Telegram

- Keine langen Reports
- Keine Cronjob-Erfolgsmeldungen
- Keine SILENT-Meldungen
- Keine normalen Service-/Watchdog-/Healthcheck-Meldungen
- Keine Roh-Findings

### 5.3 Antwort-Handler

| Antwort | Aktion |
|---------|--------|
| ✅ GO | Proposal ausführen (via safety.harness) |
| ❌ NO | Proposal auf `abgelehnt` setzen |
| 📄 DETAILS | Langer Report als Datei senden |
| 📝 PLAN ONLY | Ausführungsplan senden, nichts ausführen |

---

## 6. Projekt-Entscheidungsmatrix

| Projekt | Kategorie | Risiko | Wert | Entscheidung |
|---------|-----------|--------|------|--------------|
| loop-master | CORE | mittel | hoch | behalten/ausbauen |
| video-miner | PRODUCT/KNOWLEDGE | niedrig | hoch | integrieren |
| old-hecate | ARCHIVE | mittel | mittel | read-only sichern |
| mem0-starter | LIBRARY | niedrig | mittel | prüfen/ggf. mergen |
| demo-site | EXPERIMENT | niedrig | niedrig | archivieren |
| altes kaputtes Repo | QUARANTINE | hoch | niedrig | Lösch-Proposal |

(Die Tabelle ist ein Beispiel. Tatsächliche Werte folgen aus der Inventur.)

---

## 7. Sicherheitsmodell

### 7.1 Harte Regeln

- **Read-only Default** — alle Scans nur lesend
- **Keine Deletes** ohne separates GO
- **Keine Service-Restarts** ohne GO
- **Keine Cron-Aktivierung** ohne GO
- **Keine Legal-Dateien verändern**
- **Kein Live-Trading**
- **Keine Secrets ausgeben** (nur Hashes/Pfade)
- **Alle Änderungen nur über Proposal + Rollback**

### 7.2 Rollen

| Rolle | Verantwortlichkeit |
|-------|-------------------|
| **Cartographer** | Findet und kartiert alles |
| **Classifier** | Ordnet Projekte ein |
| **Risk Auditor** | Sucht Secrets, Crons, Ports, Gefahren |
| **Value Evaluator** | Bewertet Umsatz-/Content-/Systemwert |
| **Proposal Writer** | Baut Entscheidungsvorlagen |
| **Executor** | Führt nur nach GO aus |

---

## 8. Lokale Modelle — konkrete Auswahl

| Aufgabe | Modell | Größe | RAM bei 4-bit | Hinweis |
|---------|--------|-------|---------------|---------|
| Klassifizierung | qwen2.5:0.5b | 397 MB | ~600 MB | Schnell, gut für Labels |
| Klassifizierung | qwen2.5:1.5b | 986 MB | ~1,2 GB | Besser für kurze Zusammenfassungen |
| Code-Analyse | qwen2.5-coder:7b | 4,7 GB | ~2,5 GB | Haupt-Code-Modell |
| Code-Analyse | qwen2.5-coder:14b | 9,0 GB | ~4,5 GB | Für komplexe Analysen |
| Reasoning | qwen3:8b | 5,2 GB | ~3 GB | Entscheidungen, Risiken |
| Reasoning | qwen3:32b | 20 GB | ~11 GB | Langsam, nur bei Bedarf |
| Embeddings | nomic-embed-text | 274 MB | ~400 MB | Semantic Search |

**Empfehlung:** Starten mit `qwen2.5:1.5b` für Klassifizierung, `qwen2.5-coder:7b` für Code, `nomic-embed-text` für Embeddings.

---

## 9. Implementierungsphasen

### Phase 0 — Fundament (bereits teilweise vorhanden)

- [x] HECATE v2 als Master etabliert
- [x] Safety-Harness
- [x] Ledger
- [x] Sensoren
- [x] Proposals
- [ ] Proposal-only Telegram Governance vervollständigen

### Phase 1 — Model-Router aufbauen

- [ ] `hecate/model_router.py` bauen
- [ ] `hecate/config/models.yaml` anlegen
- [ ] Wrapper für deterministische vs. LLM-Aufgaben

### Phase 2 — Inventory Scanner

- [ ] `hecate/inventory/scanner.py` — Dateien, Git, Services, Crons, Ports
- [ ] `hecate/inventory/classifier.py` — Kategoriezuordnung
- [ ] `hecate/inventory/risk_auditor.py` — Secrets, Gefahren
- [ ] `hecate/inventory/value_evaluator.py` — Wertung

### Phase 3 — Knowledge Graph

- [ ] Graph-Datenmodell
- [ ] Embedding-Index
- [ ] Query-Interface

### Phase 4 — Proposal Engine

- [ ] Projekt-Entscheidungsmatrix generieren
- [ ] Proposal-Format konsolidieren
- [ ] Telegram-Versand nur noch für Proposals

### Phase 5 — Ausführung nach GO

- [ ] `/approve`, `/reject`, `/details`, `/plan_only` Callbacks
- [ ] Executor via `safety.harness`
- [ ] Rollback- und Audit-Log

---

## 10. Betroffene Komponenten

- `/root/projects/loop-master/hecate/*`
- `/root/projects/loop-master/sensors/*`
- `/root/projects/loop-master/proposals/*`
- `/root/projects/loop-master/hecate_loop.sh`
- `/root/projects/SYSTEM_MAP/`
- `/var/lib/loop-master/`

---

## 11. Risiken

| Risiko | Wahrscheinlichkeit | Auswirkung | Mitigation |
|--------|-------------------|------------|------------|
| Lokale Modelle zu langsam | hoch | gering | Batch-Nacht-Modus, Cloud nur bei GO |
| Falsche Kategorisierung | mittel | mittel | Mensch prüft vor GO |
| Secrets werden doch geleakt | niedrig | hoch | Nur Hashes/Pfade, keine Werte |
| Veraltete Daten | mittel | mittel | Täglicher Re-Scan |
| Verwirrung durch viele alte Projekte | hoch | mittel | Klare Matrix + Priorisierung |

---

## 12. Nächster empfohlener Schritt

**GO für Phase 1: Model-Router aufbauen.**

Konkret:
1. `hecate/model_router.py` erstellen
2. `hecate/config/models.yaml` anlegen
3. Einen Wrapper bauen, der deterministische Aufgaben ohne LLU erledigt
4. Test: Ein Projekt klassifizieren lassen

---

## 13. Report-Datei

Dieser Plan liegt unter:

```
/root/projects/SYSTEM_MAP/HECATE_100X_MASTER_PLAN.md
```

Kopien nach:
- `/root/projects/loop-master/reports/hecate_100x_master_plan_2026-06-13.md`

---

## 14. Wartet auf GO

- [ ] GO Phase 1: Model-Router aufbauen
- [ ] GO Phase 2: Inventory Scanner bauen
- [ ] GO Phase 3: Knowledge Graph aufbauen
- [ ] GO Phase 4: Proposal Engine bauen
- [ ] GO Phase 5: Executor nach GO bauen
