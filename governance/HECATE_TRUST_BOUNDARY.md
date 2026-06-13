# HECATE Trust Boundary

> Definiert, was HECATE lesen, verarbeiten und kommunizieren darf.
> Jede Überschreitung braucht eine L5 Decision Card.

---

## 1. Hetzner-Server (lokal)

### Erlaubt zu lesen

- `/root/projects/*` (Projekte, Repos, Scripts)
- `/root/vault/*` (nur Metadaten/Struktur, keine Inhalte von `legal/`, `brain/`, `maurice/`)
- `/root/.hermes/*` (nur Config, keine Secrets/Keys)
- `/root/.hecate/*` (State-Dateien)
- `/etc/cron.d/*` (Cron-Einträge)
- `/etc/systemd/system/*` (Service-Definitionen)
- `/var/log/*` (nur redacted: keine PII, keine Secrets, keine Trading-Details)
- `/var/lib/loop-master/*` (HECATE eigener State)
- `/usr/share/ollama/*` (Modell-Metadaten, keine Weights)
- Docker-Metadaten (`docker ps`, `docker system df`)

### Nie erlaubt zu lesen

- Private Schlüssel, Tokens, Passwörter (egal wo)
- Kundendaten
- Gesundheitsdaten
- Bank-/Trading-Transaktionen (außer Paper-Trading-Aggregate)
- Chat-/Message-Inhalte von Telegram/Signal/WhatsApp
- `exports/BattleBook.md` und alle Legal-Dateien Inhalt

### Erlaubt zu schreiben (nur nach GO)

- `/var/lib/loop-master/*` (HECATE State)
- `/root/projects/loop-master/*` (HECATE eigenes Repo)
- `/root/_archive/*` (L5)
- Logs/Configs außerhalb nur nach L4/L5 GO

---

## 2. Mac (Connector)

### Noch nicht erlaubt

- Kein automatischer Zugriff.
- Erst nach separater L5 Decision Card.
- Dann nur über sicheren Export/Connector.
- Keine automatische Veränderung lokaler Mac-Dateien.
- Kein Kopieren von Mac-Inhalten in Telegram.

---

## 3. Telegram

### Erlaubt zu senden

- Decision Cards (ID, Titel, Risk-Level, 100X-Score, Antwortoptionen)
- Kritische Eskalationen
- Daily Executive Digest (Top-3 offene Entscheidungen)
- Direkte Antworten auf Maurice-Anfragen

### Nie erlaubt zu senden

- Secrets
- Rohe Logs
- PII
- Trading-Details
- Legal-Inhalte
- Kunden-/Privatdaten
- Cronjob-Responses
- „OK“-Meldungen ohne Verifier

---

## 4. Redaction

- Secrets werden vor jedem Log/Report durch `REDACTED` ersetzt.
- PII wird anonymisiert (`user_1`, `client_A`).
- Legal-Dateien werden nur als Kategorie erfasst, nie als Inhalt.
- Trading-Details nur aggregiert (z. B. „5 offene Positionen“), nie Symbole/Qty/Preise.

---

## 5. Sensitive Paths (immer L5)

- `/root/.hermes/*/secrets*`
- `/root/.env*` und `.env`-Dateien in Projekten
- `/root/vault/legal/`
- `/root/vault/brain/` (Inhalt)
- `/root/projects/*/trading/` (Live-Trading)
- `/etc/litellm/`
- `/root/projects/gpe-core/empire-live-trader/` (außer paper-mcp)

---

## 6. Audit Trail

- Jeder Trust-Boundary-Zugriff wird in `ledger.db` vermerkt.
- Verstöße gegen diese Datei sind CRITICAL und stoppen den betroffenen Loop.
