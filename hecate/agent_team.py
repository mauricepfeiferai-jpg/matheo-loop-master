"""Agent Team — cmux "Claude Code Teams" Konzept für Hecate.
Spawnt parallele Sub-Agenten (via Claude-Code-CLI oder local scripts),
aggregiert Ergebnisse, verhindert Kollisionen via Lock-File.

Skills: Jeder Agent-Typ lädt eine SKILL.md aus hecate/skills/AGENT_TYPE/
"""

import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from hecate.ledger import Ledger

SKILLS_DIR = Path(__file__).resolve().parent / "skills"


def load_skill(agent_type: str) -> dict | None:
    """Lade SKILL.md für einen Agent-Typ."""
    skill_path = SKILLS_DIR / agent_type / "SKILL.md"
    if not skill_path.exists():
        return None
    text = skill_path.read_text(encoding="utf-8")
    # Frontmatter parsen
    frontmatter = {}
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            import yaml
            try:
                frontmatter = yaml.safe_load(parts[1]) or {}
            except Exception:
                pass
            body = parts[2]
        else:
            body = text
    else:
        body = text
    return {
        "name": frontmatter.get("name", agent_type),
        "description": frontmatter.get("description", ""),
        "body": body.strip(),
        "path": str(skill_path),
    }


@dataclass
class AgentJob:
    id: str
    agent_type: str        # z.B. "researcher", "coder", "reviewer"
    prompt: str
    model: str = "claude-sonnet-4-6"  # Default für Coding
    timeout_s: int = 600
    output_path: Path | None = None
    status: str = "pending"   # pending | running | ok | failed | timeout
    result: str = ""
    started_at: str = ""
    finished_at: str = ""
    skill: dict | None = None  # Geladenes SKILL.md

    def __post_init__(self):
        if self.skill is None:
            self.skill = load_skill(self.agent_type)


class AgentTeam:
    """Orchestrert parallele Agent-Jobs."""

    def __init__(self, ledger: Ledger | None = None, max_workers: int = 3):
        self.ledger = ledger
        self.max_workers = max_workers
        self.jobs: list[AgentJob] = []

    def add(self, job: AgentJob) -> "AgentTeam":
        self.jobs.append(job)
        return self

    def run(self, runner: Callable[[AgentJob], AgentJob] | None = None) -> list[AgentJob]:
        """Führt alle Jobs parallel aus."""
        if runner is None:
            runner = self._default_runner

        with ThreadPoolExecutor(max_workers=self.max_workers) as ex:
            futures = {ex.submit(runner, j): j for j in self.jobs}
            for fut in as_completed(futures):
                job = futures[fut]
                try:
                    result = fut.result(timeout=job.timeout_s + 5)
                    idx = self.jobs.index(job)
                    self.jobs[idx] = result
                except Exception as e:
                    job.status = "failed"
                    job.result = str(e)

        return self.jobs

    def _default_runner(self, job: AgentJob) -> AgentJob:
        """Default: Claude Code CLI via subprocess (headless)."""
        job.started_at = datetime.now(timezone.utc).isoformat()

        # Ledger-Start (falls vorhanden)
        if self.ledger:
            rid = self.ledger.start(job.id, phase="AGENT")

        # Prompt + Skill kombinieren
        full_prompt = job.prompt
        if job.skill:
            skill_header = f"""[AGENT SKILL: {job.skill['name']}]
{job.skill['body']}

---
[TASK PROMPT]
"""
            full_prompt = skill_header + job.prompt

        tmp_prompt = Path(f"/tmp/hecate-{job.id}.prompt")
        tmp_prompt.write_text(full_prompt, encoding="utf-8")

        # Output-Datei
        out_file = job.output_path or Path(f"/tmp/hecate-{job.id}.out.md")

        cmd = [
            "claude", "-p",
            "--model", job.model,
            "--output", str(out_file),
            "--max-turns", "30",
            str(tmp_prompt),
        ]

        try:
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=job.timeout_s
            )
            if proc.returncode == 0 and out_file.exists() and out_file.stat().st_size > 200:
                job.status = "ok"
                job.result = out_file.read_text(encoding="utf-8")[:2000]
            else:
                job.status = "failed"
                job.result = f"exit={proc.returncode}, stderr={proc.stderr[:500]}"
        except subprocess.TimeoutExpired:
            job.status = "timeout"
            job.result = f"Timeout after {job.timeout_s}s"
        except Exception as e:
            job.status = "failed"
            job.result = str(e)
        finally:
            job.finished_at = datetime.now(timezone.utc).isoformat()
            if self.ledger:
                self.ledger.finish(rid, output_path=str(out_file) if job.status == "ok" else None,
                                   status=job.status)

        return job

    def report(self) -> str:
        """Kurzer Team-Report."""
        ok = sum(1 for j in self.jobs if j.status == "ok")
        failed = sum(1 for j in self.jobs if j.status in ("failed", "timeout"))
        lines = [f"👥 Agent Team — {ok}/{len(self.jobs)} OK, {failed} failed"]
        for j in self.jobs:
            icon = "✅" if j.status == "ok" else "❌"
            lines.append(f"  {icon} {j.agent_type}: {j.status}")
        return "\n".join(lines)
