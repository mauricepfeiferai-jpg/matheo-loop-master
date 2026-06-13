#!/usr/bin/env python3
"""Workflow Engine — chained workflows mit optionaler Verifier-Pruefung.

Jeder Step kann auf vorherige Steps zugreifen.
Steps mit *rubric* werden automatisch durch einen separaten Grader verifiziert.
"""
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

# Verifier import — hecate/ liegt im selben Verzeichnis
_HECATE_DIR = Path(__file__).resolve().parent
try:
    from verifier import verify as _verify
    _HAS_VERIFIER = True
except Exception:
    _HAS_VERIFIER = False

BUS = Path("/var/lib/loop-master/findings.jsonl")

@dataclass
class WorkflowStep:
    id: str
    name: str
    action: Callable[[dict], dict]
    depends_on: list[str] = field(default_factory=list)
    status: str = "pending"  # pending | running | ok | failed
    result: dict = field(default_factory=dict)
    rubric: list[str] | None = None  # optional — wenn gesetzt, wird verify() ausgefuehrt

class Workflow:
    def __init__(self, name: str):
        self.name = name
        self.steps: list[WorkflowStep] = []
        self.context: dict = {}

    def add(self, step: WorkflowStep) -> "Workflow":
        self.steps.append(step)
        return self

    def run(self) -> dict:
        print(f"Workflow '{self.name}' startet ({len(self.steps)} steps)")
        completed = set()
        for step in self.steps:
            # Check dependencies
            if not all(d in completed for d in step.depends_on):
                print(f"  ⏳ {step.id}: Warte auf {step.depends_on}")
                step.status = "pending"
                continue
            step.status = "running"
            try:
                step.result = step.action(self.context)

                # ---- Verifier-Pruefung (falls Rubric gesetzt) ----
                if step.rubric and _HAS_VERIFIER:
                    print(f"  🔍 {step.id}: Verifier laeuft...")
                    artifact = json.dumps(step.result, ensure_ascii=False, indent=2)
                    verdict = _verify(artifact, step.rubric, artifact_type="json")
                    step.result["_verdict"] = {
                        "verdict": verdict.verdict,
                        "score": verdict.score,
                        "gaps": verdict.gaps,
                        "suggestions": verdict.suggestions,
                    }
                    if verdict.verdict != "pass":
                        raise RuntimeError(
                            f"Verifier FAILED (score={verdict.score}): "
                            f"gaps={verdict.gaps}; suggestions={verdict.suggestions}"
                        )
                    print(f"  ✅ {step.id}: OK (verifier score={verdict.score})")
                else:
                    print(f"  ✅ {step.id}: OK")

                self.context[step.id] = step.result
                step.status = "ok"
                completed.add(step.id)
            except Exception as e:
                step.status = "failed"
                step.result["error"] = str(e)
                print(f"  ❌ {step.id}: {e}")
                self._emit_finding(step, str(e))
        return self.context

    def _emit_finding(self, step: WorkflowStep, error: str):
        finding = {
            "sensor": "workflow",
            "severity": "hoch",
            "f_class": f"workflow.{step.id}.failed",
            "subject": f"Workflow '{self.name}' Step '{step.id}' failed",
            "evidence": error[:200],
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        with open(BUS, "a") as f:
            f.write(json.dumps(finding, ensure_ascii=False) + "\n")

def example_workflow():
    """Demo: Health-Check Workflow mit Verifier"""
    wf = Workflow("health_check")
    wf.add(WorkflowStep("check_disk", "Disk Check", lambda ctx: {"disk_pct": 79.2}))
    wf.add(WorkflowStep(
        "check_memory", "Memory Check", lambda ctx: {"mem_pct": 45.0},
        rubric=["Result contains mem_pct", "mem_pct is a number", "mem_pct <= 100"],
    ))
    wf.add(WorkflowStep(
        "check_sensors", "Sensor Check", lambda ctx: {"sensors_alert": True},
        depends_on=["check_disk", "check_memory"],
    ))
    return wf


if __name__ == "__main__":
    wf = example_workflow()
    ctx = wf.run()
    print("Context:", json.dumps(ctx, indent=2))
