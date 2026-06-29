"""Agent-client contract and the shared question prompt.

Intent:
    Every answerer (Claude Code, Codex, Cursor, ...) implements the same small
    interface so the runner is agnostic to which harness produced the answer.
    The prompt is identical across clients — each client supplies its own system
    prompt and tools, which is exactly what we want to compare.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar

from quetzal.datasets import service_hint
from quetzal.models import AnswerRun

_PROMPT = """You are answering a question about the `{service}` area of a codebase.

Relevant code lives under:
{roots}

Explore the repository (read-only) to ground your answer in what the code and docs
actually say — a README in that area is usually the fastest route. Answer concisely
and specifically, citing the file path(s) for any concrete claim. If the repository
does not contain the answer, say so rather than guessing. Do not modify anything.

Question: {question}"""


def build_prompt(question: str, service: str) -> str:
    """The single user prompt handed to whichever agent harness is under test."""
    return _PROMPT.format(service=service, roots=service_hint(service), question=question)


class AgentClient(ABC):
    """One answerer harness (a coding-agent CLI run headless)."""

    name: ClassVar[str]
    install_hint: ClassVar[str] = ""

    def __init__(self, model: str | None = None):
        self.model = model

    @classmethod
    @abstractmethod
    def is_available(cls) -> bool:
        """True if this client can run in the current environment."""

    @abstractmethod
    def answer(self, question: str, service: str) -> AnswerRun:
        """Answer one suite-scoped question and report token usage."""
