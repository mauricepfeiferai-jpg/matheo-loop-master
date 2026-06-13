# DECISION CARD

## ID
`dc_config_drift_44a3afab20260613`

## Kategorie
INTEGRATE_INTO_HECATE

## Risk-Level
L5

## 100X-Impact-Score
7

## Titel
config_drift: 80 Finding(s) erfordern Entscheidung

## Was wurde gefunden
80 Finding(s) aus Sensor 'config_drift' in den letzten 24h/letzten Läufen.

## Warum ist das wichtig
Dieser Sensor meldet 80 Befunde. Bei kritischen/hohen Severity ist schnelles Handeln nötig, da HECATE sonst selbst blind wird oder das System Risiken ansammelt.

## Beweise / Fundstellen
[hoch] ollama.service: OLLAMA_HOST mehrfach mit UNTERSCHIEDLICHEN Werten (/etc/systemd/system/ollama.service.d/override-host.conf, /etc/systemd
[info] ollama.service: OLLAMA_MAX_LOADED_MODELS redundant identisch definiert (/etc/systemd/system/ollama.service.d/override.conf, /etc/systemd
[info] ollama.service: OLLAMA_FLASH_ATTENTION redundant identisch definiert (/etc/systemd/system/ollama.service.d/override.conf, /etc/systemd/s
[info] ollama.service: OLLAMA_NUM_CTX redundant identisch definiert (/etc/systemd/system/ollama.service.d/override.conf, /etc/systemd/system/ol
[krit] ollama:/root/.local/bin: /root (mode 0o700, owner uid 0) ist fuer User ollama nicht traversierbar — exakt die ollama-Klasse vom 2026-06-09

## Systemzusammenhang
Sensor config_drift, Severity-Count: {'krit': 10, 'hoch': 10, 'mittel': 0, 'info': 60}

## Option A
Sensor/Fix in HECATE integrieren

## Option B
Als Proposal vormerken

## Option C
Ignorieren

## Empfehlung
A) priorisieren, wenn kritisch/hoch; sonst B) in Tagesreport aufnehmen.

## Risiko
Falsche Klassifikation; wichtige Befunde werden übersehen.

## Nichtstun-Risiko
Sensoren laufen ins Leere; Risiken bleiben unerkannt; HECATE verliert Vertrauen.

## Rollback
Card auf 'deferred' setzen; ursprüngliche Findings bleiben im Bus.

## Betroffene Dateien / Ordner / Services / Crons / Repos
Daten, Verlierer-Drop-in

## Exakte geplante Schritte
1) Befunde bestätigen 2) Option wählen 3) Bei A: L4/L5 GO einholen 4) Umsetzen + Verifier

## Verifikation
Sensor zeigt nach Aktion weniger krit/hoch Befunde; Ledger-Eintrag vorhanden.

## Erfolgskriterium
0 kritische Befunde für diesen Sensor nach Umsetzung OR Begründung im Ledger

## Antwortoptionen
- [ ] GO
- [ ] NO
- [ ] DETAILS
- [ ] PLAN ONLY
- [ ] DEFER

## Genehmigt
- **Status:** vorgeschlagen
- **Genehmigt von:**
- **Genehmigt am:**
