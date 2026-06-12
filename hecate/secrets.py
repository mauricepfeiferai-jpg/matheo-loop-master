#!/usr/bin/env python3
"""Secrets Manager — zentralisiertes Secret-Handling.

Prinzipien:
- NIE Secrets in Code
- ENV oder verschlüsselte Datei
- Rotation-Tracking
- Zugriffs-Log
"""
import json
import os
from datetime import datetime, timezone
from pathlib import Path

SECRETS_DIR = Path("/var/lib/loop-master/secrets")
SECRETS_DIR.mkdir(parents=True, exist_ok=True)
ACCESS_LOG = SECRETS_DIR / "access.jsonl"


def get(key: str, default: str = "") -> str:
    """Liest Secret aus ENV oder verschlüsselter Datei."""
    # 1. ENV
    val = os.environ.get(key, "")
    if val:
        _log_access(key, "env")
        return val

    # 2. Datei (plain für jetzt, später verschlüsselt)
    file_path = SECRETS_DIR / key
    if file_path.exists():
        val = file_path.read_text(encoding="utf-8").strip()
        _log_access(key, "file")
        return val

    return default


def set_secret(key: str, value: str, source: str = "manual") -> None:
    """Schreibt Secret in Datei + ENV."""
    file_path = SECRETS_DIR / key
    file_path.write_text(value, encoding="utf-8")
    os.chmod(file_path, 0o600)
    os.environ[key] = value
    _log_access(key, f"set:{source}")


def rotate(key: str, new_value: str) -> None:
    """Rotiert ein Secret."""
    old = get(key)
    # Backup old
    backup = SECRETS_DIR / f"{key}.bak.{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    if old:
        backup.write_text(old, encoding="utf-8")
        os.chmod(backup, 0o600)
    set_secret(key, new_value, source="rotation")


def _log_access(key: str, source: str) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "key": key,
        "source": source,
    }
    with open(ACCESS_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def list_keys() -> list:
    return [p.name for p in SECRETS_DIR.iterdir() if p.is_file() and not p.name.endswith(".bak")]
