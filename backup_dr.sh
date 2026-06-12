#!/bin/bash
# Backup/DR — SQLite + JSONL + Proposals → S3/MinIO (oder lokal verschlüsselt)

TS=$(date +%Y%m%d_%H%M%S)
SRC="/var/lib/loop-master"
DEST="/backup/hecate/$TS"
mkdir -p "$DEST"

# SQLite
sqlite3 "$SRC/ledger.db" ".backup '$DEST/ledger.db'"

# JSONL
cp "$SRC/findings.jsonl" "$DEST/"
cp "$SRC/disk_trend.jsonl" "$DEST/" 2>/dev/null

# Proposals
cp -r /root/projects/loop-master/proposals "$DEST/"

# Memory
cp -r "$SRC/agent_memory" "$DEST/" 2>/dev/null

# Tar + komprimieren
tar czf "/backup/hecate/hecate_backup_$TS.tar.gz" -C /backup/hecate "$TS"
rm -rf "$DEST"

# Retention: nur letzte 7 Backups behalten
ls -t /backup/hecate/hecate_backup_*.tar.gz | tail -n +8 | xargs rm -f 2>/dev/null

echo "Backup: /backup/hecate/hecate_backup_$TS.tar.gz"
