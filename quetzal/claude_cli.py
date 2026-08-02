"""Shared read-only `claude -p` invocation for answerers and judges."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass

from quetzal.config import AGENT_TIMEOUT_S, CLAUDE_ALLOWED_TOOLS, REPO_ROOT
from quetzal.core.repo_usage import RepoUsageCollector
from quetzal.models import RepoResources


@dataclass(frozen=True)
class ClaudeResult:
    data: dict
    repo_usage: RepoResources | None = None


def run_claude(
    prompt: str,
    model: str | None,
    label: str,
    track_repo_usage: bool = False,
) -> ClaudeResult:
    output_format = "stream-json" if track_repo_usage else "json"
    cmd = [
        "claude",
        "-p",
        prompt,
        "--output-format",
        output_format,
        "--allowedTools",
        *CLAUDE_ALLOWED_TOOLS,
    ]
    if track_repo_usage:
        cmd.append("--verbose")
    if model:
        cmd += ["--model", model]

    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=AGENT_TIMEOUT_S,
        stdin=subprocess.DEVNULL,
    )
    collector = RepoUsageCollector(REPO_ROOT) if track_repo_usage else None
    data = _parse_result(proc.stdout, collector)
    reported = str(data.get("result", "")).strip() if data else ""

    if data and data.get("is_error"):
        raise RuntimeError(f"{label} reported error: {reported[:400] or '(no detail)'}")
    if proc.returncode != 0:
        detail = reported or proc.stdout.strip() or proc.stderr.strip() or "(no output)"
        raise RuntimeError(f"{label} exited {proc.returncode}: {detail[:400]}")
    if not data:
        raise RuntimeError(f"{label} returned unparseable output: {proc.stdout.strip()[:400] or '(empty)'}")
    return ClaudeResult(data=data, repo_usage=collector.result() if collector else None)


def _parse_result(stdout: str, collector: RepoUsageCollector | None = None) -> dict | None:
    try:
        data = json.loads(stdout)
    except json.JSONDecodeError:
        data = None
    if isinstance(data, dict):
        if collector:
            collector.observe_event(data)
        return data

    result: dict | None = None
    for line in stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if collector:
            collector.observe_event(event)
        if isinstance(event, dict) and (event.get("type") == "result" or "result" in event):
            result = event
    return result
