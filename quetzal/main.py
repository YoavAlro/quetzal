"""Unified CLI entry point.

Exposes one `quetzal` command with subcommands so consumers don't have to
remember the `python -m quetzal.<module>` form:

    quetzal init                          # scaffold config + keep-docs-fresh hook
    quetzal agents
    quetzal run    --suite <name> --agent claude-code
    quetzal score  <session-id> --judge claude-code
    quetzal report <session-id>
    quetzal docs-check                    # nudge when a new module has no docs
    quetzal ui

Each subcommand is the existing standalone command, re-exported here.
"""

from __future__ import annotations

import click

from quetzal.cli import main as run_command
from quetzal.docs_check import main as docs_check_command
from quetzal.init_cmd import main as init_command
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


cli.add_command(init_command, name="init")
cli.add_command(run_command, name="run")
cli.add_command(score_command, name="score")
cli.add_command(report_command, name="report")
cli.add_command(docs_check_command, name="docs-check")
cli.add_command(ui_command, name="ui")


if __name__ == "__main__":
    cli()
