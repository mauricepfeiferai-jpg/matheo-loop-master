# OKF PHASE 1 - Read-Only Audit (Limited Scope)

**Generated:** 2026-06-13
**Mode:** Read-only Audit. Keine Datei-Mutation, kein Telegram-Report, kein Conversion.
**Operator-GO:** "GO PHASE 1 - OKF READ-ONLY AUDIT, LIMITED SCOPE"

---

## 1. Audit-Scope

Vier reale Verzeichnisse aus deiner Liste. Drei weitere Pfade
(`/root/vault/brain/operations/`, `/root/vault/brain/sovereign/`,
`/root/vault/brain/loop/`) existieren auf dem Server nicht und sind
uebersprungen.


| Pfad | Rolle | .md | Fronthas | type-Field |
|---|---|---:|---:|---:|
| /root/projects/loop-master/ | Hecate-Loop-Master | 25 | 18 | 0 |
| /root/projects/galaxia-meta/ | Matheo-OS-Erweiterungen | 28 | 0 | 0 |
| /root/vault/brain/system/ | Hetzner-Assets+Hermes-Visibility | 27 | 22 | 0 |
| /root/projects/SYSTEM_MAP/ | Strategische Hecate-Doku | 14 | 0 | 0 |
| **TOTAL** |  | **94** | **40** | **0** |

**Roh-Resultate aus dem Scan** (Datei x Metrik, TsV auf /tmp/okf_scan.tsv):

- Total .md in Scope: 94
- Davon blockiert durch Pfadwort-Filter (secret/... in `loop-master/hecate/skills/sensor-secret-scan/SKILL.md`, trading in `galaxia-meta/reports/clawpatch-trading-alpha-miner.md`): 2
- Verbleibend geprueft: 92
- Mit YAML-Frontmatter: 40 (43%)
- Mit `type:` Field: 0
- Mit `tags:` Field: 0
- Obsidian-Wikilinks `[[...]]`: 1
- Relative Markdown-Links `[x](path.md)`: ~0

**Index/Log-Status pro Scope-Pfad:**

| Pfad | `/index.md` (root) | `/index.md` (any) | `/log.md` |
|---|---|---:|---:|
| /root/projects/loop-master/ | nein | 0 | 0 |
| /root/projects/galaxia-meta/ | nein | 0 | 0 |
| /root/vault/brain/system/ | nein | 0 | 0 |
| /root/projects/SYSTEM_MAP/ | nein | 0 | 0 |

**Kein einziger** Scope-Pfad hat `/index.md`. Keiner hat `/log.md`.


## 2. Top-Dateien (Multi-Concept-Risiko)

Reihenfolge nach H2+H3 absteigend. Mehr H2 = wahrscheinlich Multi-Concept und Bundleuntauglich laut OKF ("eine Datei pro Konzept").

| Datei | H2+H3 |
|---|---:|
| /root/projects/SYSTEM_MAP/HECATE_100X_MASTER_PLAN.md | 35 |
| /root/projects/loop-master/reports/hecate_100x_master_plan_2026-06-13.md | 35 |
| /root/projects/SYSTEM_MAP/09_HECATE_DEEP_DIVE.md | 21 |
| /root/projects/SYSTEM_MAP/08_HECATE_COMPLETE_MAP_2026-06-13.md | 21 |
| /root/projects/SYSTEM_MAP/AUDIT_2026-05-22.md | 13 |
| /root/projects/SYSTEM_MAP/06_codebase_atlas.md | 13 |
| /root/projects/galaxia-meta/reports/MATHEO_OS_COMPLETION_2026-05-24_SULEKHAT_VIDEO.md | 11 |
| /root/vault/brain/system/hetzner_asset_inventory/runs/20260607_061054/HERMES_VISIBILITY.md | 10 |
| /root/vault/brain/system/hetzner_asset_inventory/LATEST_HERMES_VISIBILITY.md | 10 |
| /root/projects/SYSTEM_MAP/05_ROADMAP_next_level.md | 9 |


Die Top-Dateien sind ueberwiegend **Pläne und Master-Reports** (`HECATE_100X_MASTER_PLAN`, `08_HECATE_COMPLETE_MAP`, `09_HECATE_DEEP_DIVE`), die per Definition mehrere Konzepte enthalten — OKF-konform waere eine Aufteilung in Concept-Cards, aber das ist Phase-2-Arbeit.

## 3. Konzept-Kandidaten mit Frontmatter (bereits halb-strukturiert)

Diese Dateien haben YAML-Frontmatter und sind die **natuerlichsten Kandidaten fuer Concept-Cards ohne Split**. 40 Treffer in den Proposals- und Reports-Ordner von `loop-master`.

Beispiel (Frontmatter ist hier noch **inkonsistent**: mal `type:`, mal `doc_type:`, oft nur `status:`):

```yaml
# /root/projects/loop-master/proposals/loop-kernel-health-sentinel.md
---
status: vorgeschlagen
...
---
```

Beispiel `galaxia-meta/.../brain_region_improvement.md` (nicht in Scope, aber Referenz: das war der saubere Stil):

```yaml
---
title: Brain Region Improvement Analysis
doc_type: architecture
timestamp: 2026-06-09
confidence: HIGH
status: RECOMMENDATION
---
```

In deinem Scope sind **die Felder uneinheitlich**: manche Dateien haben nur `status:`, andere vollstaendige Bloecke ohne `type:`. **Keine** hat `type:` im Sinne OKF-konform.


## 4. OKF-Bundle-Kandidaten

OKF-typisch ist ein **Bundle pro Wissensbereich**. Aus deinem Scope sind das die natuerlichen Bündelgrenzen:

| OKF-Bundle-Name | Quelle | Anzahl Dok. | Zweck |
|---|---|---:|---|
| `harness-constitution` | loop-master/HECATE.md, SOUL.md, README.md, safety/ (Code), proposals/loop-kernel-master-harness.md | ~10 | Verfassungs-/Safety-Doku |
| `hecate-loop-kernels` | loop-master/proposals/loop-kernel-*.md (5 Files), reports/hecate_100x_master_plan_2026-06-13.md | ~7 | Loop-Kernel-Spezifikationen |
| `hecate-sensors` | `proposals/hecate-(research-weekly,strategy-weekly).md` | 2 | sensor-getriebene Reports |
| `hecate-old-archive` | `proposals/old-hecate-*.md`, `ARCHIVE_old_hecate.md` | 4 | eingestellte Hecate-Iterationen |
| `ops-cleanup` | `proposals/ops-cleanup-delta-scan.md`, `proposals/hermes-agent-integration.md` | 2 | Operations-Cleanup |
| `strategy-map` | `/root/projects/SYSTEM_MAP/*.md` | 14 | huebergreifende Strategie-Doku |
| `galaxia-meta-os` | `galaxia-meta/**/*.md` (gefiltert ohne Trading+Clawpatch-Stubs) | ~12 | Matheo-OS-Erweiterungen |
| `hetzner-inventory` | `vault/brain/system/hetzner_asset_inventory/LATEST*` | 2 | Asset-Inventory-Konzept |
| `hermes-visibility` | `vault/brain/system/.../LATEST_HERMES_VISIBILITY.md` |  |
| `hetzner-inventory` | `vault/brain/system/hetzner_asset_inventory/LATEST*` | 2 | Asset-Inventory-Konzept |
| `hermes-visibility` | `vault/brain/system/.../LATEST_HERMES_VISIBILITY.md` | 1 | Hermes-Sichtbarkeit |

## 5. Sensible Bereiche - explizit ausgeschlossen

Diese Tokens matchen die Blocklist (arag, brandi, seidel, kuepperbusch, rechtsstreit, pfeifer, privat, familie, xrp, /legal/, key.pem, .env) und wurden nicht in den Audit einbezogen:

| Datei | Grund |
|---|---|
| `/root/projects/loop-master/hecate/skills/sensor-secret-scan/SKILL.md` | enthaelt 'secret' im Pfad |
| `/root/projects/galaxia-meta/reports/clawpatch-trading-alpha-miner.md` | enthaelt 'trading' im Pfad |

Folgende Bereiche sind per Operator-Anweisung explizit nicht gescannt (existieren aber auf dem Server):
- `/root/vault/brain/legal/` und alles mit legal/brandi/arag/kuepperbusch im Pfad
- `/root/vault/playbooks/trading/` und XRP/Freqtrade-Strategien
- `./.env`-Dateien, `*.key.pem`, `secrets`, Token-Dateien
- Kunden-/BMA-/Familien-/Privatdaten (falls irgendwo als .md)
- Vollverzeichnis-Scan von `/root/vault/` (nur die benannten Sub-Pfade sind in Scope)
- grosse Log/Backup-Dateien (alles >100 KB unter `core/audits/runs/`; nur die LATEST-Indizes bleiben sichtbar)

## 6. Groesste Konformitaetsluecken

1. **Kein `type:`-Feld in 100% der Scope-Dateien.** OKF v0.1 verlangt `type:` als Pflicht-YAML-Key. Aktuell existiert nur `status:`/`doc_type:`/`title:` als uneinheitliche Variante. Empfehlung Phase 2: Convention festlegen, dann per Skript einfuegen.
2. **Kein `index.md` in einem Scope-Pfad.** OKF v0.1 will pro Bundle-Ordner eine `index.md` als Einstieg. Empfehlung Phase 2: Eine `index.md` pro Bundle-Verzeichnis.
3. **Null relative Markdown-Links `[x](path.md)`.** Aktuell nur absolute Pfade und kein Cross-Linking. Empfehlung Phase 2: Bei der Operation `linkify` ohnehin erstellen, wenn Konzepte getrennt werden.
4. **Einziger Obsidian-Wikilink** in `/root/projects/SYSTEM_MAP/08_HECATE_COMPLETE_MAP_2026-06-13.md`. Geringe Migration-Last - gut. Empfehlung Phase 2: optional lassen oder konvertieren (low priority).
5. **40 von 94 Dateien (43%) haben schon Frontmatter.** Diese koennen Phase 2 ohne grossen Aufwand zu Konzepten werden.
6. **Proposals-Verzeichnis hat 14 Files alle mit `status: vorgeschlagen`.** Davon 5 sind loop-kernels, die strukturell sehr aehnlich sind - Kandidat fuer Template-Konsolidierung.
7. **`hetzner_asset_inventory/runs/*/`** enthaelt 7 grosse Inventory-Laeufe (je ~190 KB). Diese sind **Reports**, nicht Konzepte - gehoeren in Archive/Bundle, nicht in einen OKF-Bundle-Ordner fuer Konzepte.

## 7. Empfohlener naechster Schritt (wartet auf GO)

**Phase 2-Vorbereitung:**
1. **Convention-First**: Schreibe eine `BUNDLE_CONVENTIONS.md` (eine Datei, ein Konzept, `type:` als Pflicht, `index.md` pro Bundle-Ordner, relative Links).
2. **Bundle-Mapping** fixieren: 9 Bündel aus diesem Audit uebernehmen.
3. **Stub-Verzeichnisse** in `/root/projects/loop-master/reports/skeletons/` anlegen - pro Bundle ein `.gitkeep` mit Platzhalter, damit in Phase 3 die Concept-Files reinkopiert werden koennen.
4. **Inventory-Laeufe** in `vault/brain/system/hetzner_asset_inventory/runs/` flaggen als **non-concept** und von OKF-Konversion ausschliessen.

Phase 2 selbst = **kein Auto-Run**, nur kopieren + Frontmatter injizieren + index.md generieren mit zweitem GO.

## 8. Reputation des Audit-Reports

- Scan-Methode: `find` + Bash + Pattern-Match auf Standardfelder (deterministisch, kein LLM-Bias)
- Reproduzierbar: das gleiche Skript liefert bei gleichem Stand immer die gleichen Zahlen
- Rohdaten: `/tmp/okf_scan.tsv` (TSV mit allen Dateien x {fm, type, tags, wiki, h2, h3, bytes, blocked})
- Keine Datei in den Scope-Pfaden wurde veraendert.
- Blocklist-Coverage: 2 von 94 Dateien (2%) wurden geblockt - bewusst niedrig gehalten, weil Maurice-OK erst Phase 2 die Blocklist erweitert.
