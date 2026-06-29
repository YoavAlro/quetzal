"""Unified CLI entry point.

Exposes one `service-docs-qa` command with subcommands so consumers don't have
to remember the `python -m quetzal.<module>` form:

    service-docs-qa agents
    service-docs-qa run    --service sync_service --agent claude-code
    service-docs-qa score  <session-id> --judge claude-code
    service-docs-qa report <session-id>
    service-docs-qa ui

Each subcommand is the existing standalone command, re-exported here.
"""

from __future__ import annotations

import click

from quetzal.cli import main as run_command
from quetzal.report import main as report_command
from quetzal.score import main as score_command
from quetzal.ui.__main__ import main as ui_command


@click.group(
    help="Codebase documentation-QA eval harness: answer repo questions with a real "
    "coding-agent harness, judge the answers, and report accuracy + token cost per service."
)
@click.version_option(package_name="quetzal", message="%(version)s")
def cli() -> None:
    pass


@cli.command(name="agents")
def agents_command() -> None:
    """List answerer agents and whether each CLI is installed."""
    from quetzal.agents import available_agents

    for name, ok in available_agents().items():
        click.echo(f"  {'✓' if ok else '✗'} {name}")


cli.add_command(run_command, name="run")
cli.add_command(score_command, name="score")
cli.add_command(report_command, name="report")
cli.add_command(ui_command, name="ui")


if __name__ == "__main__":
    cli()
