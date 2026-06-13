"""Hermes Adapter — HECATE nutzt Hermes Agent als Ausfuehrungs- und Messaging-Schicht.

Schnittstelle zu /usr/local/lib/hermes-agent (hermes CLI). Lese-only/notifizierende
Calls laufen direkt; Aktionen, die Hermes Code ausfuehren lassen, muessen nach GO
ueber safety.harness gehen.
"""
import subprocess
from dataclasses import dataclass


@dataclass(frozen=True)
class HermesResult:
    ok: bool
    stdout: str = ""
    stderr: str = ""
    returncode: int = 0


class HermesAdapterError(Exception):
    """Ungueltige Argumente oder unerwarteter Hermes-Fehler."""


_MAX_ARG_LEN = 4000
_MAX_TURNS = 200


def _safe_arg(value: str, name: str) -> str:
    """Prüft ein Argument gegen Option-Injection und Laengen-Grenzen."""
    if not isinstance(value, str):
        raise HermesAdapterError(f"{name} muss String sein, war {type(value).__name__}")
    stripped = value.strip()
    if not stripped:
        raise HermesAdapterError(f"{name} darf nicht leer sein")
    if stripped.startswith("-"):
        raise HermesAdapterError(f"{name} beginnt mit '-' (Option-Injection verweigert)")
    if len(stripped) > _MAX_ARG_LEN:
        raise HermesAdapterError(f"{name} zu lang ({len(stripped)} > {_MAX_ARG_LEN})")
    return stripped


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
    target = _safe_arg(target, "target")
    text = _safe_arg(text, "text")
    args = ["send", "--to", target]
    if quiet:
        args.append("-q")
    # hermes send akzeptiert entweder positional message, -f file oder stdin
    return _run(args, timeout=60, input_text=text)


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
    query = _safe_arg(query, "query")
    args = ["chat", "-q", query]
    if model is not None:
        args.extend(["-m", _safe_arg(model, "model")])
    if skills:
        args.extend(["-s", ",".join(_safe_arg(s, "skill") for s in skills)])
    if toolsets:
        args.extend(["-t", ",".join(_safe_arg(t, "toolset") for t in toolsets)])
    if not isinstance(max_turns, int) or not (1 <= max_turns <= _MAX_TURNS):
        raise HermesAdapterError(f"max_turns muss 1..{_MAX_TURNS} sein, war {max_turns!r}")
    args.extend(["--max-turns", str(max_turns)])
    if quiet:
        args.append("-Q")
    args.extend(["--source", _safe_arg(source, "source")])
    return _run(args, timeout=300)


def run_skill(skill_name: str, query: str, model: str | None = None) -> HermesResult:
    """Hermes mit genau einem Skill starten."""
    return chat(query, model=model, skills=[skill_name], max_turns=20, source="hecate-skill")


def list_targets(platform: str | None = None) -> HermesResult:
    """Verfuegbare Hermes Send-Targets auflisten."""
    args = ["send", "--list"]
    if platform is not None:
        args.append(_safe_arg(platform, "platform"))
    return _run(args, timeout=30)
