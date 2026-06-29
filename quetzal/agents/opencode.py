"""opencode answerer (headless, best-effort).

Runs `opencode run <prompt>` in the repo and captures the assistant's reply.

Note:
    opencode's non-interactive `run` prints the answer to stdout but does not
    expose token usage there, so tokens are recorded as 0 (accuracy + latency
    are still measured). Flags vary by version; Claude Code is the reference
    client with full token + cost telemetry.
"""

from __future__ import annotations

import shutil
import subprocess
import time
from typing import ClassVar

from quetzal.agents.base import AgentClient, build_prompt
from quetzal.config import AGENT_TIMEOUT_S, REPO_ROOT
from quetzal.models import AnswerRun, TokenUsage


class OpenCodeAgent(AgentClient):
    name: ClassVar[str] = "opencode"
    install_hint: ClassVar[str] = "Install opencode: https://opencode.ai (npm i -g opencode-ai)"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("opencode") is not None

    def answer(self, question: str, service: str) -> AnswerRun:
        prompt = build_prompt(question, service)
        cmd = ["opencode", "run"]
        if self.model:
            cmd += ["--model", self.model]
        cmd.append(prompt)

        started = time.monotonic()
        proc = subprocess.run(
            cmd, cwd=REPO_ROOT, capture_output=True, text=True, timeout=AGENT_TIMEOUT_S
        )
        elapsed = time.monotonic() - started
        if proc.returncode != 0:
            raise RuntimeError(f"opencode exited {proc.returncode}: {proc.stderr.strip()[:400]}")

        answer = proc.stdout.strip()
        if not answer:
            raise RuntimeError("opencode produced no output")
        return AnswerRun(
            answer=answer,
            usage=TokenUsage(),  # not exposed by `opencode run`
            model=self.model or "default",
            agent=self.name,
            elapsed_s=round(elapsed, 2),
        )
