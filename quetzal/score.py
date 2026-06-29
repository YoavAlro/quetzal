"""Step 2 — SCORE: judge stored answers against ground truth.

Usage:
    quetzal score <session_id>
    quetzal score <session_id> --judge-model gpt-5.2
    quetzal score <session_id> --force
    quetzal score --list
"""

from __future__ import annotations

from datetime import UTC, datetime

import click
from dotenv import load_dotenv
from rich.console import Console

from quetzal.core.storage import SessionStore
from quetzal.judge.registry import build_judge, list_judges
from quetzal.models import Evaluation

load_dotenv()
_console = Console()


@click.command()
@click.argument("session_id", required=False)
@click.option("--judge", "-J", type=click.Choice(list_judges()), default="claude-code", help="Judge backend.")
@click.option("--judge-model", "-j", default=None, help="Judge model (default: the backend's own default).")
@click.option("--force", "-f", is_flag=True, help="Re-judge cases that already have a verdict.")
@click.option("--list", "list_only", is_flag=True, help="List available sessions and exit.")
def main(session_id: str | None, judge: str, judge_model: str | None, force: bool, list_only: bool) -> None:
    """Grade every answered case in a session and store the verdicts."""
    if list_only or not session_id:
        sessions = SessionStore.list_sessions()
        _console.print("Available sessions:" if sessions else "No sessions found.")
        for name in sessions:
            _console.print(f"  {name}")
        return

    try:
        store = SessionStore(session_id)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if not store.exists():
        raise click.ClickException(f"Session '{session_id}' not found. Run --list to see available sessions.")
    results = store.load_results()

    grader = build_judge(judge, judge_model)
    _console.print(f"Judging [bold]{session_id}[/bold] with [cyan]{grader.model_id}[/cyan]")

    # Record the judge on the session so the UI/history show it (not just per-case).
    config = store.load_config()
    config.judge_model = grader.model_id
    store.save_config(config)

    judged = 0
    failed = 0
    for result in results:
        if result.error or not result.answer_run:
            continue
        if result.evaluation and not force:
            continue
        try:
            verdict = grader.judge(
                question=result.case.question,
                ground_truth=result.case.ground_truth,
                answer=result.answer_run.answer,
                service=result.case.service,
            )
        except Exception as exc:  # noqa: BLE001 - one judge failure shouldn't abort the whole session
            failed += 1
            _console.print(f"  [red]judge error[/red] {result.case.service}/{result.case.id}: {str(exc)[:160]}")
            continue
        result.evaluation = Evaluation(
            correct=verdict.correct,
            score=verdict.score,
            justification=verdict.justification,
            judge_model=grader.model_id,
            evaluated_at=datetime.now(UTC).isoformat(),
        )
        store.save_result(result)
        judged += 1
        mark = "[green]✓[/green]" if verdict.correct else "[red]✗[/red]"
        _console.print(f"  {mark} {result.case.service}/{result.case.id}  score={verdict.score}")

    suffix = f" ({failed} judge error(s) skipped — re-run score to retry)" if failed else ""
    _console.print(f"\nJudged {judged} case(s).{suffix}")
    _console.print(f"Next: [cyan]quetzal report {session_id}[/cyan]")


if __name__ == "__main__":
    main()
