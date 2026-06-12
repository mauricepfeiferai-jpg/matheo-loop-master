"""S6: TLS-Ablauf. NUR echte Endpunkte (NIE localhost:443 — genau dieser
refused-Check toetete health-sentinel 225/225 Mal). Plus Disk-Cert-Check:
nginx-Sites nutzen das Tailscale-Cert OHNE Renewal-Cron (Ablauf 2026-07-22)."""
import socket
import ssl
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from sensors.bus import Finding

SERVERNAME = "ubuntu-2404-noble-amd64-base.tail1ca9fd.ts.net"
ENDPOINTS = [
    ("100.124.239.46", 443),   # tailscaled serve (auto-renew)
    ("127.0.0.1", 8771),       # nginx crm-rietberg
    ("127.0.0.1", 18444),      # nginx pdf-splitter
]
DISK_CERT = Path(f"/var/lib/tailscale/certs/{SERVERNAME}.crt")
WARN_DAYS = 14
INFO_DAYS = 30


def days_left(enddate_line: str, now: datetime | None = None) -> int:
    val = enddate_line.split("=", 1)[1].strip()
    exp = datetime.strptime(val, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
    now = now or datetime.now(timezone.utc)
    return (exp - now).days


def judge(subject: str, expiry: datetime) -> Finding | None:
    d = (expiry - datetime.now(timezone.utc)).days
    if d > INFO_DAYS:
        return None
    sev = "krit" if d <= WARN_DAYS else "info"
    return Finding(sensor="cert_expiry", severity=sev,
                   f_class="cert.expiring", subject=subject,
                   evidence=f"Cert laeuft in {d} Tagen ab",
                   suggested_fix="tailscale cert erneuern + nginx reload (KEIN Renewal-Cron vorhanden!)")


def probe_endpoint(host: str, port: int, servername: str = SERVERNAME, timeout: float = 10.0) -> datetime | None:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=servername) as tls:
                der = tls.getpeercert(binary_form=True)
    except (OSError, ssl.SSLError):
        return None
    r = subprocess.run(["openssl", "x509", "-enddate", "-noout", "-inform", "DER"],
                       input=der, capture_output=True, timeout=10)
    line = r.stdout.decode().strip()
    if not line.startswith("notAfter="):
        return None
    val = line.split("=", 1)[1].strip()
    return datetime.strptime(val, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)


def disk_cert_expiry(path: Path = DISK_CERT) -> datetime | None:
    if not path.exists():
        return None
    r = subprocess.run(["openssl", "x509", "-enddate", "-noout", "-in", str(path)],
                       capture_output=True, text=True, timeout=10)
    line = r.stdout.strip()
    if not line.startswith("notAfter="):
        return None
    val = line.split("=", 1)[1].strip()
    return datetime.strptime(val, "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)


def collect() -> list[Finding]:
    findings: list[Finding] = []
    live: dict[str, datetime] = {}
    for host, port in ENDPOINTS:
        subject = f"{host}:{port}"
        exp = probe_endpoint(host, port)
        if exp is None:
            findings.append(Finding(sensor="cert_expiry", severity="info",
                                    f_class="cert.endpoint-unreachable", subject=subject,
                                    evidence="TLS-Handshake fehlgeschlagen/Endpunkt down"))
            continue
        live[subject] = exp
        f = judge(subject, exp)
        if f:
            findings.append(f)
    disk = disk_cert_expiry()
    if disk:
        for subject, exp in live.items():
            if subject.startswith("127.0.0.1") and abs((exp - disk).total_seconds()) > 86400:
                findings.append(Finding(sensor="cert_expiry", severity="hoch",
                                        f_class="cert.live-disk-mismatch", subject=subject,
                                        evidence="Live-Cert != Disk-Cert — nginx-Reload nach Renewal vergessen",
                                        suggested_fix="systemctl reload nginx"))
    return findings
