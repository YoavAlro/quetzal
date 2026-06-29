"""Codex CLI answerer (headless, best-effort).

Runs `codex exec --json <prompt>` in the repo (read-only sandbox) and parses the
JSONL event stream for the final message and token usage.

Note:
    Codex's exec JSON event shapes vary by version. This adapter parses
    defensively: it takes the last agent message as the answer and sums any
    token-usage events it recognizes. Verified shapes may need a tweak per
    Codex release; Claude Code is the reference client.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import ClassVar

from quetzal.agents.base import AgentClient, build_prompt
from quetzal.config import AGENT_TIMEOUT_S, REPO_ROOT
from quetzal.models import AnswerRun, TokenUsage


class CodexAgent(AgentClient):
    name: ClassVar[str] = "codex"
    install_hint: ClassVar[str] = "Install Codex CLI: npm i -g @openai/codex"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("codex") is not None

    def answer(self, question: str, service: str) -> AnswerRun:
        prompt = build_prompt(question, service)
        cmd = ["codex", "exec", "--json", "--sandbox", "read-only"]
        if self.model:
            cmd += ["-m", self.model]
        cmd.append(prompt)

        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=AGENT_TIMEOUT_S
        )
        if proc.returncode != 0:
            raise RuntimeError(f"codex exited {proc.returncode}: {proc.stderr.strip()[:400]}")

        answer, usage = _parse_events(proc.stdout)
        if not answer:
            raise RuntimeError("codex produced no final message")
        return AnswerRun(
            answer=answer,
            usage=usage,
            model=self.model or "default",
            agent=self.name,
        )


def _parse_events(stdout: str) -> tuple[str, TokenUsage]:
    answer = ""
    inp = out = 0
    for line in stdout.splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        msg = event.get("msg", event)
        kind = msg.get("type", "")
        if kind in ("agent_message", "agent_message_delta", "message") and msg.get("message"):
            answer = msg["message"] if kind != "agent_message_delta" else answer + msg["message"]
        elif "token" in kind.lower() or "usage" in kind.lower():
            usage = msg.get("info", msg)
            inp += usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
            out += usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
    return answer.strip(), TokenUsage(input_tokens=inp, output_tokens=out, total_tokens=inp + out)
