#!/usr/bin/env python3
"""Telegram Operator — persoenlicher Assistent fuer Maurice.

* Versteht Freitext und Buttons.
* Nutzt lokalen Reasoning-Router fuer High-End-Antworten.
* Speichert Diskussionskontext pro Proposal.
* Sendet nur noch Entscheidungsvorlagen (kein Spam).
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from hecate.discussion_memory import DiscussionMemory
from hecate.hermes_adapter import send_message
from hecate.reasoning_router import ReasoningRouter, TaskType
from hecate.vision_engine import VisionEngine

ENV_PATH = Path("/root/.hermes/profiles/jarvis/.env")
OWNER_ID_DEFAULT = "8531161985"
DEFAULT_CWD = "/root/projects/loop-master"


def _load_env() -> dict:
    cfg = {}
    try:
        for raw in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            cfg[k.strip()] = v.strip().strip('"').strip("'")
    except FileNotFoundError:
        pass
    return cfg


ENV = _load_env()
TOKEN = ENV.get("TELEGRAM_BOT_TOKEN", "")
OWNER_ID = str(ENV.get("TELEGRAM_ALLOWED_USERS") or ENV.get("TELEGRAM_CHAT_ID") or OWNER_ID_DEFAULT)
API = f"https://api.telegram.org/bot{TOKEN}"


class TelegramOperator:
    """Polling-Operator-Bot fuer Maurice."""

    def __init__(self, router: ReasoningRouter | None = None):
        self.router = router or ReasoningRouter()
        self.memory = DiscussionMemory()
        self.vision = VisionEngine(router=self.router, memory=self.memory)
        self.offset = 0
        self.state_path = Path("/var/lib/loop-master/telegram_operator_state.json")
        self._load_state()

    def _load_state(self) -> None:
        if self.state_path.exists():
            try:
                data = json.loads(self.state_path.read_text())
                self.offset = data.get("offset", 0)
            except Exception:
                pass

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(self.state_path) + ".tmp"
        Path(tmp).write_text(json.dumps({"offset": self.offset}))
        os.replace(tmp, self.state_path)

    def _tg(self, method: str, params: dict, timeout: int = 60) -> dict:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(f"{API}/{method}", data=data)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)

    def _send(self, chat_id: str | int, text: str, buttons: list | None = None) -> bool:
        for chunk in self._chunks(text or "(leer)", 4000):
            payload = {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": "true",
            }
            if buttons:
                payload["reply_markup"] = json.dumps({"inline_keyboard": buttons})
            try:
                self._tg("sendMessage", payload)
            except Exception as exc:
                sys.stderr.write(f"send error: {exc}\n")
                return False
        return True

    def _chunks(self, text: str, limit: int = 4000) -> list[str]:
        res = []
        while len(text) > limit:
            cut = text.rfind("\n", 0, limit)
            if cut <= 0:
                cut = limit
            res.append(text[:cut])
            text = text[cut:].lstrip("\n")
        res.append(text)
        return res

    def _authorized(self, uid) -> bool:
        return str(uid) == str(OWNER_ID)

    def _typing(self, chat_id: str | int) -> None:
        try:
            self._tg("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        except Exception:
            pass

    def _answer_cb(self, cb_id: str, text: str = "") -> None:
        try:
            self._tg("answerCallbackQuery", {"callback_query_id": cb_id, "text": text})
        except Exception:
            pass

    def handle(self, chat_id: str | int, text: str) -> None:
        t = text.strip()

        # Slash-Commands
        if t.startswith("/"):
            parts = t.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            return self._handle_command(chat_id, cmd, arg)

        # Freitext → Diskussion mit Reasoning
        self._typing(chat_id)
        reply = self._think_about(text)
        self._send(chat_id, reply)

    def _handle_command(self, chat_id: str | int, cmd: str, arg: str) -> None:
        if cmd in ("/start", "/help"):
            return self._send(chat_id, self._help_text())

        if cmd == "/vision":
            topic = arg or "Wie kann HECATE sich selbst weiterentwickeln?"
            self._typing(chat_id)
            result = self.vision.generate_vision(topic)
            proposal_id = result["proposal_id"]
            msg = (
                f"🌑 VISION-PROPOSAL: {proposal_id}\n"
                f"Titel: {result['title']}\n"
                f"Zusammenfassung:\n{result['summary']}\n\n"
                f"Wollen wir das diskutieren, Details sehen, oder einen Plan bauen?"
            )
            buttons = [
                [
                    {"text": "💬 DISKUSSIEREN", "callback_data": f"discuss:{proposal_id}"},
                    {"text": "📄 DETAILS", "callback_data": f"details:{proposal_id}"},
                ],
                [
                    {"text": "📝 PLAN ONLY", "callback_data": f"plan:{proposal_id}"},
                    {"text": "✅ GO", "callback_data": f"go:{proposal_id}"},
                ],
            ]
            return self._send(chat_id, msg, buttons)

        if cmd == "/status":
            from hecate_bridge import snapshot
            data = snapshot()
            f = data.get("findings", {})
            return self._send(
                chat_id,
                f"🌑 HECATE Status\n🔴 {f.get('krit',0)}  🟠 {f.get('hoch',0)}  "
                f"🟡 {f.get('mittel',0)}  🔵 {f.get('info',0)}\n"
                f"Sensoren: {len(data.get('sensors', []))}"
            )

        if cmd == "/think":
            if not arg:
                return self._send(chat_id, "Bitte Thema angeben: /think <Thema>")
            self._typing(chat_id)
            answer = self.router.generate(TaskType.REASON, arg, context=self._system_context())
            return self._send(chat_id, f"🧠 {answer}")

        if cmd == "/proposals":
            open_props = self._open_proposals()
            if not open_props:
                return self._send(chat_id, "Keine offenen Proposals.")
            lines = ["📋 Offene Proposals:"]
            for p in open_props[:10]:
                lines.append(f"• {p['name']}")
            return self._send(chat_id, "\n".join(lines))



        # Unbekannter Slash → als Prompt behandeln
        return self.handle(chat_id, text=cmd + " " + arg)

    def _handle_callback(self, chat_id: str | int, data: str, cb_id: str) -> None:
        self._answer_cb(cb_id)
        action, _, proposal_id = data.partition(":")

        if action == "go":
            self.memory.set_status(proposal_id, "approved")
            self._send(chat_id, f"✅ {proposal_id} freigegeben. Ich baue den Plan und melde mich.")
            # TODO: Executor anwerfen
            return

        if action == "no":
            self.memory.set_status(proposal_id, "rejected")
            return self._send(chat_id, f"❌ {proposal_id} abgelehnt.")

        if action == "approve":
            ok = self._set_proposal_status(proposal_id, "approved")
            if not ok:
                return self._send(chat_id, f"❌ Proposal {proposal_id} nicht gefunden.")
            return self._send(chat_id, f"✅ {proposal_id} freigegeben. Naechster Loop setzt es um.")

        if action == "deny":
            ok = self._set_proposal_status(proposal_id, "rejected")
            if not ok:
                return self._send(chat_id, f"❌ Proposal {proposal_id} nicht gefunden.")
            return self._send(chat_id, f"❌ {proposal_id} abgelehnt.")

        if action == "skip":
            ok = self._set_proposal_status(proposal_id, "vorgeschlagen")
            if not ok:
                return self._send(chat_id, f"❌ Proposal {proposal_id} nicht gefunden.")
            return self._send(chat_id, f"⏭ {proposal_id} auf später verschoben.")

        if action == "approve-all":
            from hecate.proposal_notifier import mark_all
            changed = mark_all("approved")
            return self._send(chat_id, f"✅ {len(changed)} Proposals freigegeben.")

        if action == "deny-all":
            from hecate.proposal_notifier import mark_all
            changed = mark_all("rejected")
            return self._send(chat_id, f"❌ {len(changed)} Proposals abgelehnt.")

        if action == "snooze":
            from hecate.proposal_notifier import snooze
            changed = snooze()
            return self._send(chat_id, f"🔕 {len(changed)} Proposals auf später verschoben. Heute Ruhe.")

        if action == "details":
            path = Path("/root/projects/loop-master/proposals") / f"{proposal_id}.md"
            if path.exists():
                text = path.read_text(encoding="utf-8", errors="replace")[:3800]
                return self._send(chat_id, text)
            return self._send(chat_id, "Details nicht gefunden.")

        if action == "plan":
            self.memory.set_status(proposal_id, "plan_only")
            self._typing(chat_id)
            plan = self._build_plan(proposal_id)
            return self._send(chat_id, plan)

        if action == "discuss":
            self.memory.set_status(proposal_id, "open")
            self.memory.add_message(proposal_id, "hecate", "Worueber moechtest du diskutieren?")
            return self._send(chat_id, f"💬 {proposal_id} ist jetzt zur Diskussion offen. Schreib mir.")

    def _think_about(self, text: str) -> str:
        """Freitext-Antwort mit lokalem Reasoning + Diskussionskontext."""
        # Pruefen, ob der Text sich auf ein offenes Proposal bezieht
        open_props = self._open_proposals()
        active_proposal = None
        for p in open_props:
            if p["name"] in text or p["name"].replace(".md", "") in text:
                active_proposal = p["name"].replace(".md", "")
                break

        if active_proposal:
            context = self.memory.get_context(active_proposal)
            self.memory.add_message(active_proposal, "user", text)
            prompt = (
                f"Du diskutierst das Proposal {active_proposal} mit Maurice.\n"
                f"Bisheriger Kontext:\n{context}\n\n"
                f"Neue Nachricht von Maurice: {text}\n\n"
                f"Antworte knapp, technisch, stelle bei Unklarheit eine Gegenfrage. "
                f"Biete am Ende 3 Optionen an."
            )
            answer = self.router.generate(TaskType.REASON, prompt)
            self.memory.add_message(active_proposal, "hecate", answer)
            return answer

        # Allgemeine Frage
        prompt = (
            f"Du bist HECATE, der lokale Operator-Layer auf Maurices Hetzner-Server. "
            f"Antworte technisch, knapp, ehrlich. Wenn du etwas nicht weisst, sag es.\n\n"
            f"Maurice fragt: {text}\n\n"
            f"Antworte mit 3 Optionen, falls es um eine Entscheidung geht."
        )
        return self.router.generate(TaskType.REASON, prompt, context=self._system_context())

    def _build_plan(self, proposal_id: str) -> str:
        path = Path("/root/projects/loop-master/proposals") / f"{proposal_id}.md"
        if not path.exists():
            return "Plan: Proposal nicht gefunden."
        content = path.read_text(encoding="utf-8", errors="replace")[:3000]
        prompt = (
            f"Baue einen konkreten, sicheren Umsetzungsplan fuer dieses Proposal.\n"
            f"Keine automatischen Loeschungen. Keine Service-Restarts ohne GO.\n"
            f"Struktur: 1) Voraussetzungen 2) Schritte 3) Tests 4) Rollback 5) Risiken\n\n"
            f"Proposal:\n{content}\n\nPlan:"
        )
        return self.router.generate(TaskType.REASON, prompt)

    def _system_context(self) -> str:
        from hecate_bridge import snapshot
        data = snapshot()
        lines = [
            f"Findings: {data.get('findings', {})}",
            f"Sensoren: {len(data.get('sensors', []))}",
        ]
        return "\n".join(lines)

    def _open_proposals(self) -> list[dict]:
        proposals = Path("/root/projects/loop-master/proposals")
        out = []
        for p in sorted(proposals.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True):
            text = p.read_text(encoding="utf-8", errors="replace")
            status = "vorgeschlagen"
            m = re.search(r'status:\s*(\w+)', text)
            if m:
                status = m.group(1)
            if status in ("vorgeschlagen", "telegram_approval"):
                out.append({"name": p.name, "path": str(p), "status": status})
        return out

    def _set_proposal_status(self, proposal_id: str, status: str) -> bool:
        proposals = Path("/root/projects/loop-master/proposals")
        path = proposals / f"{proposal_id}.md"
        if not path.exists():
            # Versuche mit zusaetzlicher Nummerierung
            matches = list(proposals.glob(f"{proposal_id}*.md"))
            if not matches:
                return False
            path = matches[0]
        text = path.read_text(encoding="utf-8", errors="replace")
        new_text = re.sub(r'status:\s*\w+', f'status: {status}', text)
        if new_text == text:
            # Fuege status Zeile nach dem Frontmatter-Start ein
            new_text = "---\nstatus: " + status + "\n" + text.lstrip("-").lstrip()
        path.write_text(new_text, encoding="utf-8")
        return True

    def _help_text(self) -> str:
        return (
            "🌑 HECATE Operator\n\n"
            "Ich bin dein lokaler Assistent. Ich denke mit lokalen Modellen, "
            "speichere unseren Kontext und schicke dir nur echte Entscheidungen.\n\n"
            "/vision [Thema] — neue Vision/Proposal erzeugen\n"
            "/think <Frage> — tiefes Reasoning\n"
            "/status — HECATE Snapshot\n"
            "/proposals — offene Proposals\n"
            "/help — diese Hilfe\n\n"
            "Freier Text = Diskussion mit mir."
        )

    def run(self) -> None:
        if not TOKEN:
            sys.stderr.write("FEHLER: TELEGRAM_BOT_TOKEN fehlt\n")
            sys.exit(1)
        sys.stderr.write(f"TelegramOperator up. owner={OWNER_ID}\n")
        while True:
            try:
                resp = self._tg(
                    "getUpdates",
                    {
                        "offset": self.offset,
                        "timeout": 50,
                        "allowed_updates": json.dumps(["message", "callback_query"]),
                    },
                    timeout=70,
                )
            except Exception as exc:
                sys.stderr.write(f"poll error: {exc}\n")
                time.sleep(5)
                continue

            for upd in resp.get("result", []):
                self.offset = upd["update_id"] + 1
                self._save_state()

                cq = upd.get("callback_query")
                if cq:
                    uid = (cq.get("from") or {}).get("id")
                    if not self._authorized(uid):
                        continue
                    chat = ((cq.get("message") or {}).get("chat") or {}).get("id")
                    self._handle_callback(chat, cq.get("data", ""), cq.get("id", ""))
                    continue

                msg = upd.get("message") or upd.get("edited_message")
                if not msg:
                    continue
                uid = (msg.get("from") or {}).get("id")
                if not self._authorized(uid):
                    sys.stderr.write(f"denied uid={uid}\n")
                    continue

                text = msg.get("text", "")
                chat = (msg.get("chat") or {}).get("id")
                if not text:
                    self._send(chat, "(aktuell nur Text)")
                    continue

                try:
                    self.handle(chat, text)
                except Exception as exc:
                    self._send(chat, f"💥 Fehler: {exc}")
                    sys.stderr.write(f"handle error: {exc}\n")


if __name__ == "__main__":
    TelegramOperator().run()
