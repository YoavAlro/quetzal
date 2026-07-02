"""Step 1 — RUN: answer questions with an agent harness and store token usage.

The answerer is a real coding-agent CLI (Claude Code by default; Codex, Cursor),
run headless against the repo so the benchmark measures the actual harness — its
system prompt, tools, and planning loop — not a raw-API reimplementation.

By default `run` also judges the answers and prints the report, so one command
covers the whole pipeline; use --no-score / --no-report to stop earlier.

Usage:
    quetzal run --suite <name>                    # answer + judge + report
    quetzal run --all --agent claude-code
    quetzal run --suite <name> --agent codex --limit 3
    quetzal run --suite <name> --no-score         # just answer (judge later)
    quetzal run --agents          # show which CLIs are installed
"""

from __future__ import annotations

from datetime import datetime

import click
from dotenv import load_dotenv

from quetzal.agents import available_agents, build_agent, list_agents
from quetzal.config import DEFAULT_AGENT, DEFAULT_AGENT_MODEL
from quetzal.datasets import all_cases, get_cases, list_services
from quetzal.judge.registry import list_judges

load_dotenv()  # provider credentials for the API baseline (.env at repo or cwd)


@click.command()
@click.option("--suite", "-s", "service", type=click.Choice(list_services()), help="Run one suite.")
@click.option("--all", "run_all", is_flag=True, help="Run every service suite.")
@click.option("--agent", "-a", type=click.Choice(list_agents()), default=DEFAULT_AGENT, help="Answerer harness.")
@click.option("--model", "-m", default=DEFAULT_AGENT_MODEL, help="Model for the agent (CLI default if unset).")
@click.option("--limit", "-n", type=click.IntRange(min=1), default=None, help="Cap how many questions to run.")
@click.option("--session", default=None, help="Session id to write to; ANY existing results for this id are replaced.")
@click.option("--score/--no-score", "do_score", default=True, help="Judge the answers after answering (default: on).")
@click.option(
    "--judge", "-J", type=click.Choice(list_judges()), default="claude-code", help="Judge backend (with --score)."
)
@click.option("--judge-model", "-j", default=None, help="Judge model (default: the backend's own default).")
@click.option(
    "--report/--no-report", "do_report", default=True, help="Print the aggregated report at the end (default: on)."
)
@click.option("--agents", "show_agents", is_flag=True, help="List agents and whether they are installed, then exit.")
def main(
    service: str | None,
    run_all: bool,
    agent: str,
    model: str | None,
    limit: int | None,
    session: str | None,
    do_score: bool,
    judge: str,
    judge_model: str | None,
    do_report: bool,
    show_agents: bool,
) -> None:
    """Answer the selected questions, then (by default) judge them and report."""
    if show_agents:
        for name, ok in available_agents().items():
            click.echo(f"  {'✓' if ok else '✗'} {name}")
        return

    if not service and not run_all:
        raise click.UsageError("Pass --service <name> or --all (or --agents to list harnesses).")

    cases = all_cases() if run_all else get_cases(service)
    if limit is not None:
        cases = cases[:limit]
    if not cases:
        raise click.UsageError("No questions selected.")

    try:
        client = build_agent(agent, model)
    except RuntimeError as exc:
        raise click.ClickException(str(exc)) from exc

    session_id = session or f"quetzal-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    from quetzal.core.storage import SessionStore

    try:
        SessionStore(session_id)  # validate the id before any run/reset touches disk
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    from quetzal.core.runner import run_cases

    run_cases(cases, client, session_id)

    if do_score:
        from quetzal.score import score_session

        score_session(session_id, judge=judge, judge_model=judge_model)
    if do_report:
        from quetzal.report import render_report

        render_report(session_id)
    if not do_score:
        click.echo(f"Next: quetzal score {session_id}")


if __name__ == "__main__":
    main()
