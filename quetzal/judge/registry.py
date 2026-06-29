"""Judge registry.

Maps a --judge name to its grader, imported lazily so picking the Claude Code
judge never pulls another backend's dependencies.
"""

from __future__ import annotations

import importlib
from typing import Protocol

from quetzal.judge.prompt import JudgeVerdict

# name -> "module:ClassName"
_REGISTRY: dict[str, str] = {
    "claude-code": "quetzal.judge.claude_judge:ClaudeCodeJudge",
}


class Judge(Protocol):
    model_id: str

    def judge(self, question: str, ground_truth: str, answer: str, service: str) -> JudgeVerdict: ...


def list_judges() -> list[str]:
    return list(_REGISTRY)


def build_judge(name: str, model: str | None = None) -> Judge:
    if name not in _REGISTRY:
        raise ValueError(f"Unknown judge '{name}'. Options: {', '.join(_REGISTRY)}")
    module_path, class_name = _REGISTRY[name].split(":")
    judge_cls = getattr(importlib.import_module(module_path), class_name)
    return judge_cls(model)
