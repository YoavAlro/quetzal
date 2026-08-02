"""Run questions with an agent harness and persist one result per case."""

from __future__ import annotations

from datetime import UTC, datetime

from rich.console import Console

from quetzal.agents.base import AgentClient
from quetzal.config import REPO_ROOT
from quetzal.core.gitinfo import git_state
from quetzal.core.repo_usage import inventory_repo
from quetzal.core.storage import SessionStore
from quetzal.models import CaseResult, QuestionCase, SessionConfig

_console = Console()


def run_cases(
    cases: list[QuestionCase],
    agent: AgentClient,
    session_id: str,
    retry_errors: bool = False,
) -> str:
    """Answer all selected cases, or only failed/missing ones during a retry."""
    store = SessionStore(session_id)
    if retry_errors:
        cases = _pending_cases(store, cases, agent)
        if not cases:
            _console.print(f"Nothing to retry in [bold]{session_id}[/bold].")
            return session_id
    else:
        store.reset()
        git = git_state(REPO_ROOT)
        store.save_config(
            SessionConfig(
                session_id=session_id,
                agent_client=agent.name,
                agent_model=agent.model or "default",
                services=sorted({case.service for case in cases}),
                started_at=datetime.now(UTC).isoformat(),
                git_commit=git.commit,
                git_branch=git.branch,
                git_dirty=git.dirty,
                repo_inventory=inventory_repo(REPO_ROOT) if agent.track_repo_usage else None,
                extra={
                    key: value
                    for key, value in {
                        "agent_provider": agent.provider,
                        "reasoning_effort": agent.reasoning_effort,
                        "track_repo_usage": agent.track_repo_usage or None,
                    }.items()
                    if value is not None
                },
            )
        )

    services = sorted({case.service for case in cases})
    detail = f"with [cyan]{agent.name}[/cyan] ([cyan]{agent.model or 'default'}[/cyan])"
    if agent.provider:
        detail += f" provider=[cyan]{agent.provider}[/cyan]"
    if agent.reasoning_effort:
        detail += f" effort=[cyan]{agent.reasoning_effort}[/cyan]"
    if agent.track_repo_usage:
        detail += " [dim]repo-usage trace on[/dim]"
    _console.print(f"[bold]Running[/bold] {len(cases)} questions across {len(services)} suite(s) {detail}")

    for index, case in enumerate(cases, 1):
        label = f"[{index}/{len(cases)}] {case.service}/{case.id}"
        try:
            run = agent.answer(case.question, case.service)
            result = CaseResult(case=case, answer_run=run)
            cost = f" ${run.cost_usd:.3f}" if run.cost_usd is not None else ""
            context = ""
            if run.repo_usage and run.repo_usage.trace_available:
                context = (
                    f" ctx={len(run.repo_usage.markdown_files)}/"
                    f"{len(run.repo_usage.skill_files)}/{len(run.repo_usage.hook_files)}"
                )
            _console.print(f"{label}  {run.usage.total_tokens:>8,} tok{cost}  {run.elapsed_s}s{context}")
        except Exception as exc:  # noqa: BLE001 - persist failure and continue
            result = CaseResult(case=case, error=f"{type(exc).__name__}: {exc}")
            _console.print(f"{label}  [red]error:[/red] {str(exc)[:160]}")
        store.save_result(result)

    _console.print(f"\n[green]Done.[/green] Session: [bold]{session_id}[/bold]")
    return session_id


def _pending_cases(store: SessionStore, cases: list[QuestionCase], agent: AgentClient) -> list[QuestionCase]:
    if not store.exists():
        raise RuntimeError(f"Session '{store.session_id}' not found — run it without --retry-errors first.")
    config = store.load_config()
    ran_with = (
        config.agent_client,
        config.agent_model,
        config.extra.get("agent_provider"),
        bool(config.extra.get("track_repo_usage")),
    )
    retry_with = (agent.name, agent.model or "default", agent.provider, agent.track_repo_usage)
    if ran_with != retry_with:
        raise RuntimeError(
            f"Session '{store.session_id}' ran with {ran_with}; this retry uses {retry_with}. "
            "Match the original agent/model/provider/tracking settings or use a new --session."
        )
    answered = {
        (result.case.service, result.case.id)
        for result in store.load_results()
        if result.answer_run and not result.error
    }
    pending = [case for case in cases if (case.service, case.id) not in answered]
    _console.print(f"Retrying {len(pending)} unanswered case(s); keeping {len(answered)} existing answer(s).")
    return pending
