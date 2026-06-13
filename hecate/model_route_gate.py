"""Model Route Gate — entscheidet lokal vs cloud fuer HECATE-Tasks.

Ziele:
1. Lokal ist Default. Cloud nur bei Bedarf.
2. Tracking von Erfolg, Kosten, Latenz pro Modell.
3. Nach 3 lokalen Fehlversuchen automatisch Cloud-Fallback.
4. Sicherheit: keine Secrets im Code, keine Cloud-Calls ohne explizite Erlaubnis.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from hecate.reasoning_router import ReasoningRouter, ReasoningError, TaskType
from hecate.config import load_config

ROUTE_DB_PATH = Path("/var/lib/loop-master/model_route.db")


@dataclass(frozen=True)
class RouteDecision:
    model: str
    provider: str  # "ollama" oder "claude"
    reason: str
    estimated_cost_usd: float


class ModelRouteGate:
    """Entscheidet, welches Modell fuer einen Task verwendet wird.

    Regeln:
    - Lokal, wenn Ollama laeuft und Task nicht auf Blocklist.
    - Cloud, wenn lokal 3x hintereinander fuer denselben Task-Typ gefailed ist.
    - Cloud, wenn Task explizit cloud_required ist (z.B. Architektur, Security).
    """

    CLOUD_REQUIRED_TASKS = {"vision", "security_review", "architecture"}
    LOCAL_TASKS = {"classify", "code_analyze", "reason", "verify"}

    def __init__(
        self,
        router: Optional[ReasoningRouter] = None,
        db_path: Path = ROUTE_DB_PATH,
        cloud_enabled: bool = False,
    ):
        self.router = router or ReasoningRouter()
        self.db_path = db_path
        self.cloud_enabled = cloud_enabled
        self._init_db()

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS route_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ts TEXT NOT NULL,
                task_type TEXT NOT NULL,
                model TEXT NOT NULL,
                provider TEXT NOT NULL,
                success INTEGER NOT NULL,
                latency_ms INTEGER,
                error TEXT,
                prompt_len INTEGER,
                response_len INTEGER
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_route_task ON route_log(task_type, ts)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_route_success ON route_log(success)")
        conn.commit()
        conn.close()

    def recent_failures(self, task_type: str, window: int = 10) -> int:
        """Anzahl der letzten fehlgeschlagenen lokalen Laeufe fuer einen Task-Typ."""
        if not self.db_path.exists():
            return 0
        conn = sqlite3.connect(str(self.db_path))
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) FROM route_log
            WHERE task_type = ? AND provider = 'ollama'
            ORDER BY ts DESC LIMIT ?
        """, (task_type, window))
        recent = cur.fetchone()[0]
        cur.execute("""
            SELECT success FROM route_log
            WHERE task_type = ? AND provider = 'ollama'
            ORDER BY ts DESC LIMIT ?
        """, (task_type, window))
        fails = sum(1 for row in cur.fetchall() if row[0] == 0)
        conn.close()
        return fails

    def decide(self, task_type: str, force_local: bool = False) -> RouteDecision:
        """Entscheidet lokal vs cloud.

        Args:
            task_type: z.B. 'classify', 'reason', 'vision'
            force_local: true = immer lokal, auch bei Cloud-Tasks
        Returns:
            RouteDecision mit Modell, Provider und Begruendung
        """
        cfg = load_config()
        cloud_default = cfg.get("model_routing", {}).get("cloud_default_model", "claude-sonnet-4-6")

        if force_local:
            return RouteDecision(
                model=self.router.models[TaskType(task_type)].name,
                provider="ollama",
                reason="force_local",
                estimated_cost_usd=0.0,
            )

        if task_type in self.CLOUD_REQUIRED_TASKS:
            return RouteDecision(
                model=cloud_default,
                provider="claude",
                reason="cloud_required_task",
                estimated_cost_usd=0.05,
            )

        ollama_alive = self.router.is_ollama_alive()
        if not ollama_alive:
            return RouteDecision(
                model=cloud_default,
                provider="claude",
                reason="ollama_unavailable",
                estimated_cost_usd=0.05,
            )

        fails = self.recent_failures(task_type, window=3)
        if fails >= 3 and self.cloud_enabled:
            return RouteDecision(
                model=cloud_default,
                provider="claude",
                reason="local_failures_exceeded",
                estimated_cost_usd=0.05,
            )

        local_model = self.router.models[TaskType(task_type)].name
        return RouteDecision(
            model=local_model,
            provider="ollama",
            reason="local_default",
            estimated_cost_usd=0.0,
        )

    def log_attempt(
        self,
        task_type: str,
        decision: RouteDecision,
        success: bool,
        latency_ms: int,
        error: str = "",
        prompt_len: int = 0,
        response_len: int = 0,
    ) -> None:
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            INSERT INTO route_log
                (ts, task_type, model, provider, success, latency_ms, error, prompt_len, response_len)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            datetime.now(timezone.utc).isoformat(),
            task_type,
            decision.model,
            decision.provider,
            1 if success else 0,
            latency_ms,
            error,
            prompt_len,
            response_len,
        ))
        conn.commit()
        conn.close()

    def run(
        self,
        task_type: str,
        prompt: str,
        context: str = "",
        force_local: bool = False,
    ) -> dict:
        """Fuehrt einen Task mit der gewaehlten Route aus.

        Returns:
            Dict mit response, decision, latency_ms, success
        """
        decision = self.decide(task_type, force_local=force_local)
        start = datetime.now(timezone.utc)
        error = ""
        response = ""
        success = False

        if decision.provider == "ollama":
            try:
                response = self.router.generate(TaskType(task_type), prompt, context)
                success = True
            except ReasoningError as exc:
                error = str(exc)
        else:
            # Cloud-Fallback: wir dokumentieren, aber rufen hier NICHT selbst auf.
            # Der Aufrufer muss entscheiden, ob er Cloud wirklich nutzen will.
            error = "cloud_fallback_selected_but_not_executed"

        latency_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
        self.log_attempt(
            task_type=task_type,
            decision=decision,
            success=success,
            latency_ms=latency_ms,
            error=error,
            prompt_len=len(prompt) + len(context),
            response_len=len(response),
        )

        return {
            "response": response,
            "decision": {
                "model": decision.model,
                "provider": decision.provider,
                "reason": decision.reason,
            },
            "latency_ms": latency_ms,
            "success": success,
            "error": error,
        }

    def stats(self) -> dict:
        """Liefert Aggregierte Route-Statistiken."""
        if not self.db_path.exists():
            return {"total": 0, "local": 0, "cloud": 0, "success_rate": 0.0}
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN provider = 'ollama' THEN 1 ELSE 0 END) as local_runs,
                SUM(CASE WHEN provider = 'claude' THEN 1 ELSE 0 END) as cloud_runs,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
                AVG(latency_ms) as avg_latency_ms
            FROM route_log
        """)
        r = cur.fetchone()
        conn.close()
        total = r["total"] or 0
        successes = r["successes"] or 0
        return {
            "total": total,
            "local": r["local_runs"] or 0,
            "cloud": r["cloud_runs"] or 0,
            "success_rate": successes / total if total else 0.0,
            "avg_latency_ms": round(r["avg_latency_ms"] or 0, 2),
        }


def main() -> int:
    import sys
    gate = ModelRouteGate()
    if len(sys.argv) > 2 and sys.argv[1] == "run":
        task = sys.argv[2]
        prompt = sys.argv[3] if len(sys.argv) > 3 else "Hello"
        result = gate.run(task, prompt)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    if len(sys.argv) > 1 and sys.argv[1] == "stats":
        print(json.dumps(gate.stats(), indent=2, ensure_ascii=False))
        return 0
    print("Usage: python3 -m hecate.model_route_gate run <task> [prompt] | stats")
    return 1


if __name__ == "__main__":
    import sys
    sys.exit(main())
