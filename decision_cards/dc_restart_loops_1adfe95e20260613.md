# DECISION CARD

## ID
`dc_restart_loops_1adfe95e20260613`

## Kategorie
DECOMMISSION

## Risk-Level
L5

## 100X-Impact-Score
9

## Titel
restart_loops: 8 Finding(s) erfordern Entscheidung

## Was wurde gefunden
8 Finding(s) aus Sensor 'restart_loops' in den letzten 24h/letzten Läufen.

## Warum ist das wichtig
Dieser Sensor meldet 8 Befunde. Bei kritischen/hohen Severity ist schnelles Handeln nötig, da HECATE sonst selbst blind wird oder das System Risiken ansammelt.

## Beweise / Fundstellen
[krit] gpe-arena-30.service: 299 Restarts/h (NRestarts 32420->32462) — Restart heilt die Ursache nicht
[krit] tailscale-watchdog.service: 57 Restarts/h (NRestarts 65259->65267) — Restart heilt die Ursache nicht
[info] tailscale-watchdog.service: 60 Restarts/h mit Exit 0 — Restart=always als Timer missbraucht
[info] tailscale-watchdog.service: 60 Restarts/h mit Exit 0 — Restart=always als Timer missbraucht
[info] tailscale-watchdog.service: 60 Restarts/h mit Exit 0 — Restart=always als Timer missbraucht

## Systemzusammenhang
Sensor restart_loops, Severity-Count: {'krit': 4, 'hoch': 0, 'mittel': 0, 'info': 4}

## Option A
Cron/Service archivieren/reparieren

## Option B
Proposal erstellen

## Option C
Beobachten

## Empfehlung
A) priorisieren, wenn kritisch/hoch; sonst B) in Tagesreport aufnehmen.

## Risiko
Falsche Klassifikation; wichtige Befunde werden übersehen.

## Nichtstun-Risiko
Sensoren laufen ins Leere; Risiken bleiben unerkannt; HECATE verliert Vertrauen.

## Rollback
Card auf 'deferred' setzen; ursprüngliche Findings bleiben im Bus.

## Betroffene Dateien / Ordner / Services / Crons / Repos
journalctl, tailscale-watchdog.service

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
