"""Typed records passed between the run, score, and report steps.

Intent:
    Named dataclasses (never tuples) so each pipeline step has a stable,
    self-describing contract and the JSON on disk is round-trippable.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields
from typing import Any


@dataclass(frozen=True)
class QuestionCase:
    """One benchmark question scoped to a single suite."""

    id: str
    service: str
    question: str
    ground_truth: str
    difficulty: str = "medium"
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0

    def __add__(self, other: TokenUsage) -> TokenUsage:
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            total_tokens=self.total_tokens + other.total_tokens,
            cached_input_tokens=self.cached_input_tokens + other.cached_input_tokens,
        )


@dataclass(frozen=True)
class RepoResources:
    """Repository context assets, stored as repo-relative paths."""

    markdown_files: tuple[str, ...] = ()
    skill_files: tuple[str, ...] = ()
    hook_files: tuple[str, ...] = ()
    trace_available: bool = False


@dataclass
class AnswerRun:
    """What the answerer agent produced for one question.

    Token/turn fields are optional because different agent CLIs report
    different telemetry; whatever the harness gives us is recorded as-is.
    """

    answer: str
    usage: TokenUsage
    model: str
    agent: str = ""
    elapsed_s: float = 0.0
    tool_calls: int | None = None
    llm_calls: int | None = None
    cost_usd: float | None = None
    repo_usage: RepoResources | None = None


@dataclass
class Evaluation:
    """The judge's verdict for one answer."""

    correct: bool
    score: int
    justification: str
    judge_model: str
    evaluated_at: str


@dataclass
class CaseResult:
    """The full record for one question across the pipeline."""

    case: QuestionCase
    answer_run: AnswerRun | None = None
    evaluation: Evaluation | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CaseResult:
        # Tolerate keys from older schemas (e.g. a removed "reviewed" field) so
        # results written by a previous version still load.
        known = {f.name for f in fields(QuestionCase)}
        case_data = {k: v for k, v in data["case"].items() if k in known}
        case_data["tags"] = tuple(case_data.get("tags", ()))
        case = QuestionCase(**case_data)
        answer_run = None
        if data.get("answer_run"):
            run = dict(data["answer_run"])
            run["usage"] = TokenUsage(**run["usage"])
            if run.get("repo_usage"):
                run["repo_usage"] = _resources(run["repo_usage"])
            answer_run = AnswerRun(**run)
        evaluation = Evaluation(**data["evaluation"]) if data.get("evaluation") else None
        return cls(case=case, answer_run=answer_run, evaluation=evaluation, error=data.get("error"))


@dataclass
class SessionConfig:
    """Identifies one benchmark run."""

    session_id: str
    agent_model: str
    services: list[str]
    started_at: str
    agent_client: str = "claude-code"
    judge_model: str | None = None
    git_commit: str | None = None
    git_branch: str | None = None
    git_dirty: bool = False
    repo_inventory: RepoResources | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionConfig:
        values = dict(data)
        if values.get("repo_inventory"):
            values["repo_inventory"] = _resources(values["repo_inventory"])
        return cls(**values)


def _resources(data: dict[str, Any]) -> RepoResources:
    return RepoResources(
        markdown_files=tuple(data.get("markdown_files", ())),
        skill_files=tuple(data.get("skill_files", ())),
        hook_files=tuple(data.get("hook_files", ())),
        trace_available=bool(data.get("trace_available", False)),
    )
