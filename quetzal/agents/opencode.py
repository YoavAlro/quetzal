"""OpenCode answerer using its read-only plan agent and JSONL telemetry."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from typing import ClassVar

from quetzal.agents.base import AgentClient, build_prompt
from quetzal.config import AGENT_TIMEOUT_S, REPO_ROOT
from quetzal.core.repo_usage import RepoUsageCollector
from quetzal.models import AnswerRun, RepoResources, TokenUsage


class OpenCodeAgent(AgentClient):
    name: ClassVar[str] = "opencode"
    install_hint: ClassVar[str] = "Install OpenCode: https://opencode.ai (npm i -g opencode-ai)"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("opencode") is not None

    def answer(self, question: str, service: str) -> AnswerRun:
        cmd = ["opencode", "run", "--format", "json", "--agent", "plan", "--pure"]
        if self.model:
            cmd += ["--model", self.model]
        cmd.append(build_prompt(question, service))

        started = time.monotonic()
        proc = subprocess.run(
            cmd,
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=AGENT_TIMEOUT_S,
            stdin=subprocess.DEVNULL,
        )
        elapsed = time.monotonic() - started
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout).strip()
            raise RuntimeError(f"opencode exited {proc.returncode}: {detail[:400]}")

        parsed = _parse_events(proc.stdout, self.track_repo_usage)
        if parsed.error:
            raise RuntimeError(f"opencode reported error: {parsed.error[:400]}")
        if not parsed.answer:
            raise RuntimeError("opencode produced no assistant text")
        return AnswerRun(
            answer=parsed.answer.strip(),
            usage=parsed.usage,
            model=self.model or parsed.model or "default",
            agent=self.name,
            elapsed_s=round(elapsed, 2),
            cost_usd=parsed.cost or None,
            repo_usage=parsed.repo_usage,
        )


@dataclass
class _ParsedEvents:
    answer: str = ""
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost: float = 0.0
    model: str = ""
    error: str = ""
    step_usage: TokenUsage = field(default_factory=TokenUsage)
    step_cost: float = 0.0
    has_message_total: bool = False
    repo_usage: RepoResources | None = None


def _record_usage(parsed: _ParsedEvents, payload: dict) -> None:
    usage = _usage(payload["tokens"])
    cost = float(payload.get("cost") or 0.0)
    if payload.get("role") == "assistant":
        parsed.has_message_total = True
        parsed.usage = usage
        parsed.cost = cost
        return
    parsed.step_usage = parsed.step_usage + usage
    parsed.step_cost += cost
    if not parsed.has_message_total:
        parsed.usage = parsed.step_usage
        parsed.cost = parsed.step_cost


def _parse_events(stdout: str, track_repo_usage: bool = False) -> _ParsedEvents:
    parsed = _ParsedEvents()
    texts: list[str] = []
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
        if event.get("error"):
            parsed.error = _error_message(event["error"])
        for payload in _payloads(event):
            if payload.get("type") == "text" and payload.get("text") and not payload.get("synthetic"):
                texts.append(payload["text"])
            if isinstance(payload.get("tokens"), dict):
                _record_usage(parsed, payload)
            parsed.model = payload.get("modelID") or parsed.model
    parsed.answer = max(texts, key=len) if texts else ""
    parsed.repo_usage = collector.result() if collector else None
    return parsed


def _payloads(event: dict) -> list[dict]:
    props = event.get("properties") or {}
    candidates = (event.get("part"), props.get("part"), props.get("info"), event)
    return [candidate for candidate in candidates if isinstance(candidate, dict)]


def _usage(tokens: dict) -> TokenUsage:
    cache = tokens.get("cache") or {}
    cached = int(cache.get("read") or 0)
    inp = int(tokens.get("input") or 0) + cached + int(cache.get("write") or 0)
    out = int(tokens.get("output") or 0) + int(tokens.get("reasoning") or 0)
    return TokenUsage(
        input_tokens=inp,
        output_tokens=out,
        total_tokens=inp + out,
        cached_input_tokens=cached,
    )


def _error_message(error: dict) -> str:
    data = error.get("data") or {}
    return str(data.get("message") or error.get("name") or error)
