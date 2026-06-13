from unittest.mock import patch

from hecate.hermes_adapter import HermesResult, chat, list_targets, run_skill, send_message, status


def test_send_message_builds_hermes_send_command():
    with patch("hecate.hermes_adapter._run") as mock_run:
        mock_run.return_value = HermesResult(ok=True, stdout="sent")
        r = send_message("telegram", "hello", quiet=True)
        assert r.ok is True
        mock_run.assert_called_once()
        args, kwargs = mock_run.call_args
        assert args[0] == ["send", "--to", "telegram", "-q"]
        assert kwargs["input_text"] == "hello"


def test_send_message_passes_non_quiet():
    with patch("hecate.hermes_adapter._run") as mock_run:
        mock_run.return_value = HermesResult(ok=True)
        send_message("discord:#ops", "deploy done", quiet=False)
        args, _ = mock_run.call_args
        assert "-q" not in args[0]


def test_status_command():
    with patch("hecate.hermes_adapter._run") as mock_run:
        mock_run.return_value = HermesResult(ok=True, stdout=" Hermes Agent v0.15.1")
        r = status()
        assert r.ok is True
        args, _ = mock_run.call_args
        assert args[0] == ["status"]


def test_status_deep():
    with patch("hecate.hermes_adapter._run") as mock_run:
        mock_run.return_value = HermesResult(ok=True)
        status(deep=True)
        args, _ = mock_run.call_args
        assert "--deep" in args[0]


def test_chat_command():
    with patch("hecate.hermes_adapter._run") as mock_run:
        mock_run.return_value = HermesResult(ok=True, stdout="answer")
        r = chat("was ist der Plan?", model="anthropic/claude-sonnet-4", skills=["research"],
                 toolsets=["none"], max_turns=5)
        assert r.ok is True
        args, _ = mock_run.call_args
        cmd = args[0]
        assert "chat" in cmd
        assert "-q" in cmd and "was ist der Plan?" in cmd
        assert "-m" in cmd and "anthropic/claude-sonnet-4" in cmd
        assert "-s" in cmd and "research" in cmd
        assert "-t" in cmd and "none" in cmd
        assert "--max-turns" in cmd and "5" in cmd
        assert "-Q" in cmd
        assert "--source" in cmd and "hecate" in cmd


def test_run_skill_uses_chat_with_skill():
    with patch("hecate.hermes_adapter._run") as mock_run:
        mock_run.return_value = HermesResult(ok=True)
        run_skill("sensor-config-drift", "analysiere config drift")
        args, _ = mock_run.call_args
        cmd = args[0]
        assert "-s" in cmd and "sensor-config-drift" in cmd
        assert "--source" in cmd and "hecate-skill" in cmd


def test_list_targets():
    with patch("hecate.hermes_adapter._run") as mock_run:
        mock_run.return_value = HermesResult(ok=True)
        list_targets("telegram")
        args, _ = mock_run.call_args
        assert args[0] == ["send", "--list", "telegram"]
