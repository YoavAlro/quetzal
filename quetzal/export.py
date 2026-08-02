"""Write one shareable JSON bundle for a benchmark session."""

from __future__ import annotations

import json
from dataclasses import asdict

import click
from rich.console import Console

from quetzal.config import REPO_ROOT
from quetzal.core.gitinfo import git_state
from quetzal.core.storage import SessionStore
from quetzal.pricing import PriceBook
from quetzal.report import build_report

_console = Console()


def _case_dict(result, prices: PriceBook) -> dict:
    run = result.answer_run
    evaluation = result.evaluation
    cost = run.cost_usd if run else None
    estimated = False
    if run and cost is None:
        cost = prices.estimate(run.model, run.usage)
        estimated = cost is not None
    return {
        "case": asdict(result.case),
        "answer": run.answer if run else None,
        "usage": asdict(run.usage) if run else None,
        "model": run.model if run else None,
        "agent": run.agent if run else None,
        "cost_usd": round(cost, 6) if cost is not None else None,
        "cost_estimated": estimated,
        "elapsed_s": run.elapsed_s if run else None,
        "repo_usage": asdict(run.repo_usage) if run and run.repo_usage else None,
        "error": result.error,
        "evaluation": asdict(evaluation) if evaluation else None,
    }


@click.command()
@click.argument("session_id")
@click.option("--pricing", "pricing_path", default=None, help="JSON token-rate override.")
def main(session_id: str, pricing_path: str | None) -> None:
    """Write <results>/<session>/bundle.json with config, report, and cases."""
    try:
        store = SessionStore(session_id)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if not store.exists():
        raise click.ClickException(f"Session '{session_id}' not found.")
    try:
        prices = PriceBook.load(pricing_path)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    report = build_report(session_id, prices)
    config = store.load_config()
    commit, branch, dirty = config.git_commit, config.git_branch, config.git_dirty
    if not commit and not branch:
        live = git_state(REPO_ROOT)
        commit, branch, dirty = live.commit, live.branch, live.dirty
    bundle = {
        "schema_version": 1,
        "session_id": session_id,
        "config": asdict(config),
        "git": {"commit": commit, "branch": branch, "dirty": dirty},
        "report": report,
        "cases": [_case_dict(result, prices) for result in store.load_results()],
    }
    out_path = store.root / "bundle.json"
    out_path.write_text(json.dumps(bundle, indent=2, default=str))
    _console.print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
