import os

import pytest

from hecate.reasoning_router import ReasoningRouter, TaskType


skip_if_no_live = pytest.mark.skipif(
    os.environ.get("HECATE_TEST_LIVE_OLLAMA") != "1",
    reason="set HECATE_TEST_LIVE_OLLAMA=1 to run live Ollama tests"
)


@skip_if_no_live
def test_live_classify():
    r = ReasoningRouter()
    assert r.is_ollama_alive()
    label = r.classify("disk 95% full", ["hardware", "config", "security"])
    assert label.lower() in ("hardware", "config", "security")


@skip_if_no_live
def test_live_reason():
    r = ReasoningRouter()
    answer = r.reason("What is 2+2?")
    assert "4" in answer
