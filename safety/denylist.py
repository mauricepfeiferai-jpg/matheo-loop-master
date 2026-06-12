"""Harte Deny-List: physisch nicht-reversible / freigabepflichtige Aktionen.
Diese laufen NIE automatisch, auch nicht im 'aggressiv-autonom'-Modus."""
import re

DENY_PATTERNS = [
    (r"\brm\s+-[a-z]*r[a-z]*f?\b(?!.*/_trash/)", "rm -rf ausserhalb _trash"),
    (r"\bgit\s+push\b.*(--force|-f)\b", "git push --force"),
    (r"\bgit\s+reset\s+--hard\b", "git reset --hard"),
    (r"\bapt(-get)?\b", "apt (Paket-Aenderung, nur Maurice)"),
    (r"/root/vault/brain/legal/|/root/projects/legal/", "Legal-Datei (read-only)"),
    (r"\b(buy|sell|order|live[_-]?trade|broker)\b", "Trading-Kapital (Paper only)"),
]


def is_denied(cmd: str) -> str | None:
    """Gibt den Deny-Grund zurueck, oder None wenn erlaubt."""
    for pattern, reason in DENY_PATTERNS:
        if re.search(pattern, cmd, flags=re.IGNORECASE):
            return reason
    return None
