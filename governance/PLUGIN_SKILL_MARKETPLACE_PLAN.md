# HECATE Plugin / Skill Marketplace Plan

> HECATE wird zu einem internen Marketplace, in dem vorhandene Projekte entweder Skill, Plugin, Worker, Connector, Knowledge-Bundle, Sensor, Dashboard, Archiv, Quarantäne oder Delete Candidate werden.

---

## Ziel

Alte Projekte und Scripts werden nicht als „alte Ordner“ behandelt, sondern klassifiziert und in HECATE integriert, archiviert oder zur Löschung vorgeschlagen.

---

## Kategorien

| Kategorie | Beschreibung | Beispiel-Candidate |
|-----------|--------------|--------------------|
| Governance Skill | Constitution, Risk, Trust Boundary, Audit | HECATE selbst |
| Decision Skill | Decision Cards, Strategy Critic, Verifier | napoleon.py (blackhole) |
| Sensor Skill | Systemzustand, Crons, Services, Secrets | sensors/ (loop-master) |
| Repo Analysis Skill | Codebase verstehen, Tests, README | gpe-core paper-mcp |
| Risk Audit Skill | Secrets, Legal, Trading, Privatdaten | secret_scan.py |
| Knowledge / OKF Skill | Wissensgraph, Scoring, Bundles | blackhole graph.py |
| Content Skill | X-Posts, Newsletter, Pitches | blackhole x_automation.py |
| Sales Skill | CRM, Airtable, Vertriebs-OS | gpe-core crm/ |
| Local Model Worker | Ollama-Routing, Benchmark, Caching | hecate reasoning_router.py |
| Mac Connector | Sicherer Mac-Export/Connector | (noch nicht gebaut) |
| Decommission Skill | Archive, Quarantine, Delete Candidates | system_housekeeper.py |

---

## Bewertungsmatrix

Jeder Fund wird nach diesen Dimensionen gescort (1–10):

1. **Systemwert:** Macht es HECATE stärker?
2. **Businesswert:** Umsatz, Content, Authority, Produkt?
3. **Risiko:** Secrets, Legal, Kunden, Trading, private Daten?
4. **Integrationspotenzial:** Skill, Sensor, Worker, Dashboard, OKF-Bundle?
5. **Löschbarkeit:** Duplikat, alt, nicht referenziert, kein Service/Cron?
6. **100X-Impact:** Reduziert Chaos, spart Aufmerksamkeit, erhöht lokale Autonomie?

---

## Entscheidungsklassen

- **KEEP_ACTIVE:** läuft weiter, wird ggf. in HECATE integriert
- **KEEP_REFERENCE:** nur dokumentiert, nicht aktiv
- **INTEGRATE_INTO_HECATE:** wird zu Skill/Sensor/Worker/Connector
- **EXTRACT_LIBRARY:** Code wird als wiederverwendbare Library isoliert
- **PRODUCTIZE:** wird zu faceless Produkt / Productized Service
- **OKF_BUNDLE_CANDIDATE:** Wissensbundle für Vault/Content
- **ARCHIVE_COLD:** nach `/root/_archive` verschieben
- **QUARANTINE:** isoliert, nicht löschen, nicht aktiv
- **DELETE_CANDIDATE:** Löschvorschlag (nur nach GO)
- **DUPLICATE_REVIEW:** mehrere Varianten, eine behalten
- **NEEDS_HUMAN_CONTEXT:** Maurice muss erklären, was das war

---

## Erste Kandidaten (nur Plan)

| Pfad | Vermutete Kategorie | Begründung |
|------|---------------------|------------|
| `/root/projects/loop-master` | Governance + Orchestrator | HECATE selbst, Zielsystem |
| `/root/projects/gpe-core/empire-live-trader/paper-mcp` | INTEGRATE_INTO_HECATE | Beweislich sicheres Paper-Trading-Backbone |
| `/root/projects/gpe-core/llm/` | EXTRACT_LIBRARY | Provider-Router + Cost-Tracking |
| `/root/projects/blackhole/core/graph.py` | INTEGRATE_INTO_HECATE | Knowledge-Graph mit Scoring |
| `/root/projects/blackhole/core/napoleon.py` | Decision Skill | Strategie-/Priorisierungslogik |
| `/root/projects/blackhole/intake/scanner.py` | Sensor Skill | Ingest-Scanner |
| `/root/projects/blackhole/products/x_automation.py` | Content Skill | X-Content-Generator |
| `/root/gpe` | DELETE_CANDIDATE / QUARANTINE | Veraltet, keine Tests |
| `/root/projects/gpe-core/arena_blitz/` | DELETE_CANDIDATE | 79 MB Log, nicht aktiv |
| `/root/projects/gpe-core/neural_engine/` | NEEDS_HUMAN_CONTEXT | Unklar, ob überholt oder nutzbar |
| `/root/projects/gpe-core/apps/trading-arena/` | DUPLICATE_REVIEW | Arena-Varianten |

---

## Nächste Schritte

1. Decision Card Loop bauen (Pilot).
2. Total Legacy Discovery nach GO durchführen.
3. Jeden Fund einer Entscheidungsklasse zuweisen.
4. Für INTEGRATE_INTO_HECATE: Plugin-/Skill-Specs schreiben.
5. Für DELETE_CANDIDATE: separate L5 Decision Cards.
