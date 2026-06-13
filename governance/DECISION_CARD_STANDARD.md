# HECATE Decision Card Standard

> Jede hochwertige Entscheidungsvorlage in HECATE folgt diesem Schema.
> Decision Cards werden unter `/root/projects/loop-master/decision_cards/` abgelegt.

---

## Template

```markdown
# DECISION CARD

## ID
`<system>_<timestamp>_<hash>`

## Kategorie
(KEEP_ACTIVE | KEEP_REFERENCE | INTEGRATE_INTO_HECATE | EXTRACT_LIBRARY | PRODUCTIZE | OKF_BUNDLE_CANDIDATE | ARCHIVE_COLD | QUARANTINE | DELETE_CANDIDATE | DUPLICATE_REVIEW | NEEDS_HUMAN_CONTEXT)

## Risk-Level
(L0–L5)

## 100X-Impact-Score
(1–10)

## Titel
Kurzer, prägnanter Titel.

## Was wurde gefunden
Faktische Beschreibung. Keine Interpretation.

## Warum ist das wichtig
Business-/System-Argument. Warum sollte Maurice sich damit befassen?

## Beweise / Fundstellen
Konkrete Pfade, Logs, Services, Git-Status, Größen, Zeiten.

## Systemzusammenhang
Welche Crons, Services, Repos, Vaults sind betroffen?

## Option A
Titel + konkrete Schritte + Risiko.

## Option B
Titel + konkrete Schritte + Risiko.

## Option C
Titel + konkrete Schritte + Risiko.

## Empfehlung
Welche Option empfohlen wird und warum.

## Risiko
Was kann schiefgehen?

## Nichtstun-Risiko
Was passiert, wenn nichts getan wird?

## Rollback
Wie kann man zurück?

## Betroffene Dateien / Ordner / Services / Crons / Repos
Aufzählung.

## Exakte geplante Schritte
1. ...
2. ...
3. ...

## Verifikation
Wie wird Erfolg nach dem GO geprüft?

## Erfolgskriterium
Quantifizierbar.

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
```

---

## Regeln

- DELETE_CANDIDATE bedeutet nur Entscheidungsvorlage, niemals automatische Löschung.
- Jede Decision Card muss mindestens 3 Optionen haben.
- Empfehlung ist immer klar benannt.
- Beweise müssen nachprüfbar sein.
- Risk-Level muss mit Constitution übereinstimmen.
- Telegram-Nachrichten enthalten nur ID, Titel, Risk-Level, 100X-Score und Antwortoptionen.
