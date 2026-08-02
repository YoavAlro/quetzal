"""Claude Code answerer (headless).

Runs `claude -p <prompt> --output-format json` in the repo with a read-only tool
allowlist, and reads the harness's own token usage and cost from the JSON result.

Assumptions:
    `claude` is on PATH and authenticated. Read-only is enforced via
    --allowedTools (no edit/bash tools); we never pass skip-permissions.
"""

from __future__ import annotations

import shutil
from typing import ClassVar

from quetzal.agents.base import AgentClient, build_prompt
from quetzal.claude_cli import run_claude
from quetzal.models import AnswerRun, TokenUsage


class ClaudeCodeAgent(AgentClient):
    name: ClassVar[str] = "claude-code"
    install_hint: ClassVar[str] = "Install Claude Code: https://docs.claude.com/claude-code"

    @classmethod
    def is_available(cls) -> bool:
        return shutil.which("claude") is not None

    def answer(self, question: str, service: str) -> AnswerRun:
        prompt = build_prompt(question, service)
        result = run_claude(prompt, self.model, "claude", self.track_repo_usage)
        data = result.data

        return AnswerRun(
            answer=data.get("result", ""),
            usage=_usage(data.get("usage", {})),
            model=self.model or _dominant_model(data.get("modelUsage", {})),
            agent=self.name,
            elapsed_s=round(data.get("duration_ms", 0) / 1000, 2),
            tool_calls=None,
            llm_calls=data.get("num_turns"),
            cost_usd=data.get("total_cost_usd"),
            repo_usage=result.repo_usage,
        )


def _usage(usage: dict) -> TokenUsage:
    inp = (
        usage.get("input_tokens", 0)
        + usage.get("cache_creation_input_tokens", 0)
        + usage.get("cache_read_input_tokens", 0)
    )
    out = usage.get("output_tokens", 0)
    return TokenUsage(
        input_tokens=inp,
        output_tokens=out,
        total_tokens=inp + out,
        cached_input_tokens=usage.get("cache_read_input_tokens", 0),
    )


def _dominant_model(model_usage: dict) -> str:
    """The model that did most of the work, by cost."""
    if not model_usage:
        return "default"
    return max(model_usage.items(), key=lambda kv: kv[1].get("costUSD", 0))[0]
