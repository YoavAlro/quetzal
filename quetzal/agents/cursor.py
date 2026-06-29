"""Cursor CLI answerer (headless, best-effort).

Runs `cursor-agent -p <prompt> --output-format json` in the repo and reads the
final result (and token usage if the version reports it).

Note:
    Cursor's headless JSON shape varies by version; this adapter parses
    defensively. Claude Code is the reference client.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from typing import ClassVar

from quetzal.agents.base import AgentClient, build_prompt
from quetzal.config import AGENT_TIMEOUT_S, REPO_ROOT
from quetzal.models import AnswerRun, TokenUsage


class CursorAgent(AgentClient):
    name: ClassVar[str] = "cursor"
    install_hint: ClassVar[str] = "Install Cursor CLI: curl https://cursor.com/install -fsS | bash"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("cursor-agent") is not None

    def answer(self, question: str, service: str) -> AnswerRun:
        prompt = build_prompt(question, service)
        cmd = ["cursor-agent", "-p", prompt, "--output-format", "json"]
        if self.model:
            cmd += ["--model", self.model]

        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=AGENT_TIMEOUT_S
        )
        if proc.returncode != 0:
            raise RuntimeError(f"cursor-agent exited {proc.returncode}: {proc.stderr.strip()[:400]}")

        data = _last_json_object(proc.stdout)
        answer = data.get("result") or data.get("response") or data.get("text") or ""
        if not answer:
            raise RuntimeError("cursor-agent produced no result")
        usage = data.get("usage", {}) or {}
        inp = usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
        out = usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
        return AnswerRun(
            answer=answer.strip(),
            usage=TokenUsage(input_tokens=inp, output_tokens=out, total_tokens=inp + out),
            model=self.model or data.get("model", "default"),
            agent=self.name,
            cost_usd=data.get("total_cost_usd"),
        )


def _last_json_object(stdout: str) -> dict:
    """Tolerate either a single JSON object or a JSONL stream (take the last object)."""
    text = stdout.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    for line in reversed(text.splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise RuntimeError("cursor-agent returned no parseable JSON")
