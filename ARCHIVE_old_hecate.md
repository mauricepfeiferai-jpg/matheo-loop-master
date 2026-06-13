# Archiv — Altes HECATE v1 (reversibel pausiert)

> Datum: 2026-06-13
> Aktion: Konsolidierung auf HECATE v2 (`/root/projects/loop-master`) als kanonischen Master.
> Autorität: Maurice-Entscheidung Option B.

## Was pausiert wurde

### root-crontab (backup: `/root/.crontab-backup-2026-06-13.pre-hecate-pause`)

| # | Takt | Befehl | Zweck |
|---|------|--------|-------|
| 1 | `0 2 * * *` | `/root/hecate/workers/hermes-herkules/labors/12_cerberus/backup_head*.sh + rotate.sh` | Backup-Rotation |
| 2 | `0 4 * * *` | `/root/hecate/workers/hermes-herkules/labors/11_apples_hesperides/index_vault_v2.py` | Vault-Index |
| 3 | `*/10 * * * *` | `/root/hecate/workers/hermes-herkules/labors/02_lernean_hydra/scan.sh` | Hydra-Scan |
| 4 | `15 6 * * *` | `/root/hecate/loop/run_loop.sh` | HECATE v1 Hauptloop |
| 5 | `30 20 * * 0` | `/root/hecate/workers/hermes-herkules/evolve.sh` | Evolve-Chain |
| 6 | `30 4 * * *` | `/root/hecate/workers/hermes-herkules/labors/05_augean_stables/lint.py` | Lint |
| 7 | `30 7 * * *` | `/root/hecate/iris/iris_briefing.sh` | Daily Briefing |
| 8 | `* * * * *` | `/root/hecate/loop/cockpit_daemon.sh` | Cockpit Tick |

### `/root/loop_kernel` Crons (im selben root-crontab backup)

| # | Takt | Befehl | Zweck |
|---|------|--------|-------|
| 9 | `0 7 * * *` | `/root/loop_kernel/content-v2/loop.sh` | Content-Engine V2 |
| 10 | `*/15 * * * *` | `/root/loop_kernel/health-sentinel/loop.sh` | Health-Sentinel |
| 11 | `0 * * * *` | `/root/loop_kernel/skill-ingest/loop.sh` | Skill-Ingest |
| 12 | `0 8 * * *` | `/root/loop_kernel/lab/observatory/dashboard.sh` | Lab Dashboard |
| 13 | `*/15 * * * *` | `/root/loop_kernel/rechtsstreit-auto/loop.sh` | Rechtsstreit-Auto |

### systemd

- `hecate-fast-loop.timer` / `hecate-fast-loop.service` — `systemctl disable --now`
- Service-Dateien unter `/etc/systemd/system/` bleiben erhalten.

## Was weiterhin läuft

- `/root/projects/loop-master/hecate_loop.sh` alle 15 Minuten (`*/15 * * * *`) — HECATE v2 Master.
- Alle anderen Server-Crons (Trading, Galaxia, Content-Engine, etc.) sind unberührt.

## Revert (alles rückgängig)

```bash
# 1. Crontab wiederherstellen
crontab /root/.crontab-backup-2026-06-13.pre-hecate-pause

# 2. Fast-Loop Timer reaktivieren
systemctl enable --now hecate-fast-loop.timer

# 3. Optional: alte v1 State reaktivieren (Code liegt unverändert unter /root/hecate)
cd /root/hecate
# git status prüfen, manuell aufräumen falls nötig
```

## Migration als Proposals

Die pausierten Funktionen sind in `/root/projects/loop-master/proposals/` als gated Proposals angelegt.
Maurice kann sie gezielt freigeben (`status: vorgeschlagen` → `status: freigegeben`), um sie unter HECATE v2 wieder zu aktivieren.

## Begründung

- Doppelte HECATE-/Loop-Schichten führten zu Governance-Kollisionen und doppelten Alerts.
- `/root/projects/loop-master` hat technisch erzwungenen Safety-Harness, Ledger, 57 Tests grün.
- `/root/hecate` v1 bleibt als Code-Archiv erhalten, wird aber nicht mehr aktiv gesteuert.

## Ansprechdateien

- Kanonischer Master: `/root/projects/loop-master/HECATE.md`
- Executive Identity: `/root/projects/loop-master/SOUL.md`
- System-Landkarte: `/root/projects/SYSTEM_MAP/08_HECATE_COMPLETE_MAP_2026-06-13.md`
