"""Codex CLI answerer with read-only isolation and JSONL telemetry."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import ClassVar

from quetzal.agents.base import AgentClient, build_prompt
from quetzal.config import AGENT_TIMEOUT_S, DEFAULT_CODEX_PROVIDER, REPO_ROOT
from quetzal.core.repo_usage import RepoUsageCollector
from quetzal.models import AnswerRun, RepoResources, TokenUsage

_MODEL_REFRESH_ERROR = "failed to refresh available models"
_MODEL_REFRESH_ATTEMPTS = 3
_MODEL_REFRESH_BACKOFF_S = (5, 20)
_NO_MCP_SERVERS = ("--config", "mcp_servers={}")


class CodexAgent(AgentClient):
    name: ClassVar[str] = "codex"
    install_hint: ClassVar[str] = "Install Codex CLI: npm i -g @openai/codex"

    def __init__(
        self,
        model: str | None = None,
        provider: str | None = None,
        reasoning_effort: str | None = None,
        track_repo_usage: bool = False,
    ):
        super().__init__(
            model=model,
            provider=provider or DEFAULT_CODEX_PROVIDER,
            reasoning_effort=reasoning_effort,
            track_repo_usage=track_repo_usage,
        )

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("codex") is not None

    def answer(self, question: str, service: str) -> AnswerRun:
        cmd = [
            "codex",
            "exec",
            "--json",
            "--ephemeral",
            "--sandbox",
            "read-only",
            "--disable",
            "plugins",
            "--disable",
            "apps",
        ]
        if self.provider == "openai":
            cmd.append("--ignore-user-config")
        else:
            cmd.extend(_NO_MCP_SERVERS)
        cmd += ["--config", f"model_provider={json.dumps(self.provider)}"]
        if self.reasoning_effort:
            cmd += ["--config", f"model_reasoning_effort={json.dumps(self.reasoning_effort)}"]
        if self.model:
            cmd += ["--model", self.model]
        cmd.append(build_prompt(question, service))

        started = time.monotonic()
        proc = _run_codex(cmd)
        elapsed = time.monotonic() - started
        if proc.returncode != 0:
            detail = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"codex exited {proc.returncode}: {detail[:400]}")

        parsed = _parse_events(proc.stdout, track_repo_usage=self.track_repo_usage)
        if not parsed.answer:
            raise RuntimeError("codex produced no final message")
        return AnswerRun(
            answer=parsed.answer,
            usage=parsed.usage,
            model=self.model or "default",
            agent=self.name,
            elapsed_s=round(elapsed, 2),
            repo_usage=parsed.repo_usage,
        )


@dataclass(frozen=True)
class _ParsedEvents:
    answer: str
    usage: TokenUsage
    repo_usage: RepoResources | None = None


def _run_codex(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    for attempt in range(_MODEL_REFRESH_ATTEMPTS):
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=AGENT_TIMEOUT_S,
            stdin=subprocess.DEVNULL,
        )
        if proc.returncode == 0 or _MODEL_REFRESH_ERROR not in proc.stderr or attempt == _MODEL_REFRESH_ATTEMPTS - 1:
            return proc
        time.sleep(_MODEL_REFRESH_BACKOFF_S[min(attempt, len(_MODEL_REFRESH_BACKOFF_S) - 1)])
    raise AssertionError("unreachable")


def _parse_events(stdout: str, track_repo_usage: bool = False) -> _ParsedEvents:
    answer = ""
    inp = out = cached = 0
    collector = RepoUsageCollector(REPO_ROOT) if track_repo_usage else None
    for line in stdout.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if collector:
            collector.observe_event(event)
        msg = event.get("msg", event)
        kind = msg.get("type", "")
        if kind == "item.completed":
            item = msg.get("item", {})
            if item.get("type") == "agent_message" and item.get("text"):
                answer = item["text"]
        elif kind in ("agent_message", "agent_message_delta", "message") and msg.get("message"):
            answer = msg["message"] if kind != "agent_message_delta" else answer + msg["message"]
        elif kind == "turn.completed" and msg.get("usage"):
            usage = msg["usage"]
            inp = usage.get("input_tokens", 0) or 0
            out = usage.get("output_tokens", 0) or 0
            cached = usage.get("cached_input_tokens", 0) or 0
        elif "token" in kind.lower() or "usage" in kind.lower():
            usage = msg.get("info", msg)
            inp += usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0
            out += usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0
            cached += usage.get("cached_input_tokens", 0) or 0
    return _ParsedEvents(
        answer=answer.strip(),
        usage=TokenUsage(
            input_tokens=inp,
            output_tokens=out,
            total_tokens=inp + out,
            cached_input_tokens=min(cached, inp),
        ),
        repo_usage=collector.result() if collector else None,
    )
