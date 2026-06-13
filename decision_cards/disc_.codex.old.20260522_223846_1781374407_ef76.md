# DECISION CARD

## ID
`disc_.codex.old.20260522_223846_1781374407_ef76`

## Kategorie
DELETE_CANDIDATE

## Risk-Level
L2

## 100X-Impact-Score
5

## Titel
/root/.codex.old.20260522_223846 (large_dir)

## Was wurde gefunden
Pfad `/root/.codex.old.20260522_223846` vom Typ `large_dir`. Grösse: 2.99 GB. Alter: 23.4 Tage.

## Warum ist das wichtig
Systemwert 3/10, Businesswert 3/10, Integrationspotenzial 4/10, Löschbarkeit 8/10.

## Beweise / Fundstellen
- Git-Status: no_git
- README: nein
- Tests: nein
- Docker: nein
- Sprachen: md, ts, yaml, json, py
- Entrypoints: AGENTS.md
- Services: keine
- Crons: keine

## Systemzusammenhang
Hetzner-Server, ggf. verbunden mit Services/Crons/Docker.

## Option A
DELETE CANDIDATE: delete candidate

## Option B
Als Referenz archivieren/erwähnen, aber nicht aktiv verändern.

## Option C
Ignorieren / auf später verschieben.

## Empfehlung
delete candidate

## Risiko
2/10 Risiko; keine aktiven Referenzen.

## Nichtstun-Risiko
Speicherplatz bleibt blockiert; Bloat wächst.

## Rollback
Je nach gewählter Option: Status zurücksetzen, Archiv rückgängig machen oder aus Backup wiederherstellen.

## Betroffene Dateien / Ordner / Services / Crons / Repos
/root/.codex.old.20260522_223846

## Exakte geplante Schritte
1. Dokumentation prüfen
2. Bei GO: Aktion durch safety.harness ausführen
3. Verifier prüft Ergebnis
4. Ledger-Eintrag schreiben

## Verifikation
Pfad existiert / existiert nicht wie geplant; Service/Cron-Status konsistent.

## Erfolgskriterium
Entscheidung ist umgesetzt und im Ledger vermerkt.

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
