"""Step 3 — REPORT: aggregate accuracy and token usage per service.

Usage:
    quetzal report <session_id>
    quetzal report <session_id> --json

Writes results/<session_id>/report.json and prints a per-service table.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import click
from rich.console import Console
from tabulate import tabulate

from quetzal.config import RESULTS_DIR
from quetzal.core.storage import SessionStore
from quetzal.models import CaseResult

_console = Console()


@dataclass
class ServiceStats:
    service: str
    answered: int = 0
    errored: int = 0
    judged: int = 0
    correct: int = 0
    score_sum: int = 0
    total_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0
    tool_runs: int = 0
    cost_usd: float = 0.0
    cost_runs: int = 0
    failures: list[str] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return (self.correct / self.judged * 100) if self.judged else 0.0

    @property
    def avg_score(self) -> float:
        return (self.score_sum / self.judged) if self.judged else 0.0

    @property
    def avg_tokens(self) -> float:
        return (self.total_tokens / self.answered) if self.answered else 0.0


def _accumulate(stats: ServiceStats, result: CaseResult) -> None:
    if result.error or not result.answer_run:
        stats.errored += 1
        return
    stats.answered += 1
    run = result.answer_run
    usage = run.usage
    stats.total_tokens += usage.total_tokens
    stats.input_tokens += usage.input_tokens
    stats.output_tokens += usage.output_tokens
    if run.tool_calls is not None:
        stats.tool_calls += run.tool_calls
        stats.tool_runs += 1
    if run.cost_usd is not None:
        stats.cost_usd += run.cost_usd
        stats.cost_runs += 1
    if result.evaluation:
        stats.judged += 1
        stats.score_sum += result.evaluation.score
        if result.evaluation.correct:
            stats.correct += 1
        else:
            stats.failures.append(f"{result.case.id}: {result.evaluation.justification}")


def build_report(session_id: str) -> dict:
    """Aggregate a session into per-service and overall stats."""
    results = SessionStore(session_id).load_results()
    by_service: dict[str, ServiceStats] = {}
    for result in results:
        stats = by_service.setdefault(result.case.service, ServiceStats(service=result.case.service))
        _accumulate(stats, result)

    services = [
        {
            "service": s.service,
            "answered": s.answered,
            "errored": s.errored,
            "judged": s.judged,
            "correct": s.correct,
            "accuracy_pct": round(s.accuracy, 1),
            "avg_score": round(s.avg_score, 2),
            "avg_tokens": round(s.avg_tokens),
            "total_tokens": s.total_tokens,
            "avg_tool_calls": round(s.tool_calls / s.tool_runs, 1) if s.tool_runs else None,
            "total_cost_usd": round(s.cost_usd, 4) if s.cost_runs else None,
            "failures": s.failures,
        }
        for s in sorted(by_service.values(), key=lambda x: x.service)
    ]
    totals = _overall(by_service.values())
    return {"session_id": session_id, "services": services, "overall": totals}


def _overall(all_stats) -> dict:
    all_stats = list(all_stats)
    answered = sum(s.answered for s in all_stats)
    judged = sum(s.judged for s in all_stats)
    correct = sum(s.correct for s in all_stats)
    total_tokens = sum(s.total_tokens for s in all_stats)
    total_cost = sum(s.cost_usd for s in all_stats)
    cost_runs = sum(s.cost_runs for s in all_stats)
    return {
        "answered": answered,
        "judged": judged,
        "correct": correct,
        "accuracy_pct": round(correct / judged * 100, 1) if judged else 0.0,
        "avg_tokens": round(total_tokens / answered) if answered else 0,
        "total_tokens": total_tokens,
        "total_cost_usd": round(total_cost, 4) if cost_runs else None,
    }


def render_report(session_id: str, as_json: bool = False) -> None:
    """Aggregate a session, write report.json, and print it. Shared by the
    `report` command and by `run`'s default end-of-run summary."""
    try:
        exists = SessionStore(session_id).exists()
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if not exists:
        raise click.ClickException(f"Session '{session_id}' not found.")
    report = build_report(session_id)
    out_path = RESULTS_DIR / session_id / "report.json"
    out_path.write_text(json.dumps(report, indent=2))

    if as_json:
        _console.print_json(data=report)
        return

    rows = [
        [
            s["service"],
            f"{s['correct']}/{s['judged']}",
            f"{s['accuracy_pct']}%",
            s["avg_score"],
            f"{s['avg_tokens']:,}",
            f"{s['total_tokens']:,}",
            f"${s['total_cost_usd']}" if s["total_cost_usd"] is not None else "—",
            s["errored"] or "",
        ]
        for s in report["services"]
    ]
    headers = ["suite", "correct", "accuracy", "avg_score", "avg_tok", "total_tok", "cost", "err"]
    _console.print(tabulate(rows, headers=headers, tablefmt="github"))

    overall = report["overall"]
    cost = f", ${overall['total_cost_usd']} total" if overall.get("total_cost_usd") is not None else ""
    _console.print(
        f"\n[bold]Overall[/bold]: {overall['correct']}/{overall['judged']} correct "
        f"([green]{overall['accuracy_pct']}%[/green]), "
        f"avg {overall['avg_tokens']:,} tok/question, {overall['total_tokens']:,} tok total{cost}."
    )
    _console.print(f"Wrote {out_path}")


@click.command()
@click.argument("session_id")
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON instead of a table.")
def main(session_id: str, as_json: bool) -> None:
    """Aggregate and display a scored session."""
    render_report(session_id, as_json=as_json)


if __name__ == "__main__":
    main()
