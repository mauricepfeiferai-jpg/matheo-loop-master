"""Hermes Adapter — HECATE nutzt Hermes Agent als Ausfuehrungs- und Messaging-Schicht.

Schnittstelle zu /usr/local/lib/hermes-agent (hermes CLI). Lese-only/notifizierende
Calls laufen direkt; Aktionen, die Hermes Code ausfuehren lassen, muessen nach GO
ueber safety.harness gehen.
"""
import subprocess
from dataclasses import dataclass
from pathlib import Path


class HermesError(Exception):
    """Hermes CLI lieferte Exit != 0 oder Timeout."""


@dataclass(frozen=True)
class HermesResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


def _run(args: list[str], timeout: int = 120, input_text: str | None = None) -> HermesResult:
    """Fuehre hermes-Subprozess aus."""
    r = subprocess.run(
        ["hermes", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
        input=input_text,
    )
    return HermesResult(ok=r.returncode == 0, stdout=r.stdout, stderr=r.stderr, returncode=r.returncode)


def send_message(target: str, text: str, quiet: bool = True) -> HermesResult:
    """Sende Nachricht ueber Hermes Gateway (Telegram/Discord/Slack/Signal/Email).

    target: z.B. 'telegram', 'telegram:-1001234567890', 'discord:#ops'
    """
    args = ["send", "--to", target]
    if quiet:
        args.append("-q")
    # hermes send akzeptiert entweder positional message, -f file oder stdin
    r = _run(args, timeout=60, input_text=text)
    return r


def status(deep: bool = False) -> HermesResult:
    """Hermes Agent Status abfragen."""
    args = ["status"]
    if deep:
        args.append("--deep")
    return _run(args, timeout=60)


def chat(query: str, model: str | None = None, skills: list[str] | None = None,
         toolsets: list[str] | None = None, max_turns: int = 10,
         quiet: bool = True, source: str = "hecate") -> HermesResult:
    """Hermes im nicht-interaktiven Chat-Modus aufrufen.

    VORSICHT: Hermes kann Tools ausfuehren. Dieser Adapter startet Hermes als
    Subprozess, nicht im safety.harness. Für destruktive/file-schreibende
    Aktionen muss der Aufrufer selbst safety.harness.run() verwenden.
    """
    args = ["chat", "-q", query]
    if model:
        args.extend(["-m", model])
    if skills:
        args.extend(["-s", ",".join(skills)])
    if toolsets:
        args.extend(["-t", ",".join(toolsets)])
    args.extend(["--max-turns", str(max_turns)])
    if quiet:
        args.append("-Q")
    args.extend(["--source", source])
    return _run(args, timeout=300)


def run_skill(skill_name: str, query: str, model: str | None = None) -> HermesResult:
    """Hermes mit genau einem Skill starten."""
    return chat(query, model=model, skills=[skill_name], max_turns=20, source="hecate-skill")


def list_targets(platform: str | None = None) -> HermesResult:
    """Verfuegbare Hermes Send-Targets auflisten."""
    args = ["send", "--list"]
    if platform:
        args.append(platform)
    return _run(args, timeout=30)
