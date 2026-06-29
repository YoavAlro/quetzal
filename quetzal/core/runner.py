"""Run loop: answer a set of questions with an agent client and persist usage.

Intent:
    Drive the selected agent harness across the chosen questions and store one
    CaseResult per question. Scoring happens in a separate step so answers can
    be re-judged without re-spending answer tokens.
"""

from __future__ import annotations

from datetime import UTC, datetime

from rich.console import Console

from quetzal.agents.base import AgentClient
from quetzal.core.storage import SessionStore
from quetzal.models import CaseResult, QuestionCase, SessionConfig

_console = Console()


def run_cases(cases: list[QuestionCase], agent: AgentClient, session_id: str) -> str:
    """Answer every case with the agent harness and persist results."""
    store = SessionStore(session_id)
    store.reset()  # one run owns its session; never mix with leftover result files
    services = sorted({case.service for case in cases})
    store.save_config(
        SessionConfig(
            session_id=session_id,
            agent_client=agent.name,
            agent_model=agent.model or "default",
            services=services,
            started_at=datetime.now(UTC).isoformat(),
        )
    )

    _console.print(
        f"[bold]Running[/bold] {len(cases)} questions across {len(services)} suite(s) "
        f"with [cyan]{agent.name}[/cyan] ([cyan]{agent.model or 'default'}[/cyan])"
    )

    for index, case in enumerate(cases, 1):
        label = f"[{index}/{len(cases)}] {case.service}/{case.id}"
        try:
            run = agent.answer(case.question, case.service)
            result = CaseResult(case=case, answer_run=run)
            cost = f" ${run.cost_usd:.3f}" if run.cost_usd is not None else ""
            _console.print(f"{label}  {run.usage.total_tokens:>8,} tok{cost}  {run.elapsed_s}s")
        except Exception as exc:  # noqa: BLE001 - record failure, keep going
            result = CaseResult(case=case, error=f"{type(exc).__name__}: {exc}")
            _console.print(f"{label}  [red]error:[/red] {str(exc)[:160]}")
        store.save_result(result)

    _console.print(f"\n[green]Done.[/green] Session: [bold]{session_id}[/bold]")
    _console.print(f"Next: [cyan]quetzal score {session_id}[/cyan]")
    return session_id
