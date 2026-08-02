"""Cursor CLI answerer with ask-mode read-only enforcement."""

from __future__ import annotations

import json
import shutil
import subprocess
import time
from dataclasses import dataclass
from typing import Any, ClassVar

from quetzal.agents.base import AgentClient, build_prompt
from quetzal.config import AGENT_TIMEOUT_S, REPO_ROOT
from quetzal.core.repo_usage import RepoUsageCollector
from quetzal.models import AnswerRun, RepoResources, TokenUsage


class CursorAgent(AgentClient):
    name: ClassVar[str] = "cursor"
    install_hint: ClassVar[str] = "Install Cursor CLI: curl https://cursor.com/install -fsS | bash"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("cursor-agent") is not None

    def answer(self, question: str, service: str) -> AnswerRun:
        output_format = "stream-json" if self.track_repo_usage else "json"
        cmd = [
            "cursor-agent",
            "-p",
            build_prompt(question, service),
            "--output-format",
            output_format,
            "--mode",
            "ask",
            "--sandbox",
            "enabled",
            "--trust",
        ]
        if self.model:
            cmd += ["--model", self.model]

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
            detail = proc.stderr.strip() or proc.stdout.strip()
            raise RuntimeError(f"cursor-agent exited {proc.returncode}: {detail[:400]}")

        parsed = _parse_output(proc.stdout, self.track_repo_usage)
        if parsed.error:
            raise RuntimeError(f"cursor-agent reported error: {parsed.error[:400]}")
        if not parsed.answer:
            raise RuntimeError("cursor-agent produced no result")
        return AnswerRun(
            answer=parsed.answer.strip(),
            usage=_usage(parsed.data.get("usage") or {}),
            model=self.model or parsed.data.get("model", "default"),
            agent=self.name,
            elapsed_s=round(elapsed, 2),
            cost_usd=parsed.data.get("total_cost_usd"),
            repo_usage=parsed.repo_usage,
        )


@dataclass(frozen=True)
class _CursorOutput:
    answer: str
    data: dict[str, Any]
    error: str = ""
    repo_usage: RepoResources | None = None


def _parse_output(stdout: str, track_repo_usage: bool = False) -> _CursorOutput:
    collector = RepoUsageCollector(REPO_ROOT) if track_repo_usage else None
    events = _json_objects(stdout)
    if not events:
        raise RuntimeError("cursor-agent returned no parseable JSON")
    texts: list[str] = []
    final: dict[str, Any] = events[-1]
    error = ""
    for event in events:
        if collector:
            collector.observe_event(event)
        if event.get("is_error") or event.get("type") == "error":
            error = str(event.get("error") or event.get("result") or event)
        candidate = event.get("result") or event.get("response") or event.get("text")
        if isinstance(candidate, str) and candidate.strip():
            texts.append(candidate)
        message = event.get("message")
        if isinstance(message, dict):
            texts.extend(_message_texts(message))
        if event.get("type") == "result" or isinstance(event.get("usage"), dict):
            final = event
    return _CursorOutput(
        answer=max(texts, key=len) if texts else "",
        data=final,
        error=error,
        repo_usage=collector.result() if collector else None,
    )


def _message_texts(message: dict[str, Any]) -> list[str]:
    content = message.get("content", [])
    if isinstance(content, str):
        return [content]
    return [part["text"] for part in content if isinstance(part, dict) and isinstance(part.get("text"), str)]


def _json_objects(stdout: str) -> list[dict[str, Any]]:
    text = stdout.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        return [data]
    events: list[dict[str, Any]] = []
    for line in text.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            events.append(event)
    return events


def _usage(usage: dict) -> TokenUsage:
    def pick(*names: str) -> int:
        for name in names:
            value = usage.get(name)
            if value:
                return int(value)
        return 0

    cached = pick("cacheReadTokens", "cache_read_tokens", "cache_read_input_tokens")
    inp = pick("inputTokens", "input_tokens", "prompt_tokens")
    inp += cached + pick("cacheWriteTokens", "cache_write_tokens", "cache_creation_input_tokens")
    out = pick("outputTokens", "output_tokens", "completion_tokens")
    return TokenUsage(
        input_tokens=inp,
        output_tokens=out,
        total_tokens=inp + out,
        cached_input_tokens=cached,
    )
