"""Aggregate accuracy, telemetry, cost, timing, and observed repo context."""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import click
from rich.console import Console
from tabulate import tabulate

from quetzal.config import RESULTS_DIR
from quetzal.core.storage import SessionStore
from quetzal.models import CaseResult, RepoResources
from quetzal.pricing import DEFAULT_PRICING_PATH, PriceBook

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
    cached_input_tokens: int = 0
    tool_calls: int = 0
    tool_runs: int = 0
    cost_usd: float = 0.0
    cost_runs: int = 0
    estimated_cost_runs: int = 0
    elapsed_s: float = 0.0
    timed_runs: int = 0
    trace_runs: int = 0
    markdown_files: set[str] = field(default_factory=set)
    skill_files: set[str] = field(default_factory=set)
    hook_files: set[str] = field(default_factory=set)
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

    @property
    def avg_elapsed_s(self) -> float:
        return (self.elapsed_s / self.timed_runs) if self.timed_runs else 0.0


def _accumulate(stats: ServiceStats, result: CaseResult, prices: PriceBook) -> None:
    if result.error or not result.answer_run:
        stats.errored += 1
        return
    stats.answered += 1
    run = result.answer_run
    usage = run.usage
    stats.total_tokens += usage.total_tokens
    stats.input_tokens += usage.input_tokens
    stats.output_tokens += usage.output_tokens
    stats.cached_input_tokens += usage.cached_input_tokens
    if run.tool_calls is not None:
        stats.tool_calls += run.tool_calls
        stats.tool_runs += 1
    if run.elapsed_s:
        stats.elapsed_s += run.elapsed_s
        stats.timed_runs += 1
    cost = run.cost_usd
    estimated = False
    if cost is None:
        cost = prices.estimate(run.model, usage)
        estimated = cost is not None
    if cost is not None:
        stats.cost_usd += cost
        stats.cost_runs += 1
        stats.estimated_cost_runs += int(estimated)
    if run.repo_usage and run.repo_usage.trace_available:
        stats.trace_runs += 1
        stats.markdown_files.update(run.repo_usage.markdown_files)
        stats.skill_files.update(run.repo_usage.skill_files)
        stats.hook_files.update(run.repo_usage.hook_files)
    if result.evaluation:
        stats.judged += 1
        stats.score_sum += result.evaluation.score
        if result.evaluation.correct:
            stats.correct += 1
        else:
            stats.failures.append(f"{result.case.id}: {result.evaluation.justification}")


def _observed(stats: ServiceStats) -> dict:
    return {
        "trace_runs": stats.trace_runs,
        "markdown_files": len(stats.markdown_files),
        "custom_skills": len(stats.skill_files),
        "hooks": len(stats.hook_files),
        "markdown_paths": sorted(stats.markdown_files),
        "skill_paths": sorted(stats.skill_files),
        "hook_paths": sorted(stats.hook_files),
    }


def _inventory(resources: RepoResources | None) -> dict | None:
    if resources is None:
        return None
    return {
        "markdown_files": len(resources.markdown_files),
        "custom_skills": len(resources.skill_files),
        "hooks": len(resources.hook_files),
        "markdown_paths": list(resources.markdown_files),
        "skill_paths": list(resources.skill_files),
        "hook_paths": list(resources.hook_files),
    }


def build_report(session_id: str, prices: PriceBook | None = None) -> dict:
    prices = prices if prices is not None else PriceBook.load()
    store = SessionStore(session_id)
    results = store.load_results()
    by_service: dict[str, ServiceStats] = {}
    for result in results:
        stats = by_service.setdefault(result.case.service, ServiceStats(service=result.case.service))
        _accumulate(stats, result, prices)

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
            "cached_input_tokens": s.cached_input_tokens,
            "avg_elapsed_s": round(s.avg_elapsed_s, 1) if s.timed_runs else None,
            "total_elapsed_s": round(s.elapsed_s, 1) if s.timed_runs else None,
            "avg_tool_calls": round(s.tool_calls / s.tool_runs, 1) if s.tool_runs else None,
            "total_cost_usd": round(s.cost_usd, 4) if s.cost_runs else None,
            "cost_estimated": bool(s.estimated_cost_runs),
            "observed_repo_usage": _observed(s),
            "failures": s.failures,
        }
        for s in sorted(by_service.values(), key=lambda item: item.service)
    ]
    config = store.load_config()
    overall = _overall(by_service.values())
    return {
        "session_id": session_id,
        "services": services,
        "overall": overall,
        "repo_context": {
            "inventory": _inventory(config.repo_inventory),
            "observed_usage": overall["observed_repo_usage"],
            "observation_note": (
                "Observed usage counts unique repo assets referenced by structured harness tool events; "
                "CLIs may omit internal reads or hook execution."
            ),
        },
    }


def _overall(all_stats) -> dict:
    stats = list(all_stats)
    answered = sum(item.answered for item in stats)
    judged = sum(item.judged for item in stats)
    correct = sum(item.correct for item in stats)
    total_tokens = sum(item.total_tokens for item in stats)
    total_cost = sum(item.cost_usd for item in stats)
    cost_runs = sum(item.cost_runs for item in stats)
    total_elapsed = sum(item.elapsed_s for item in stats)
    timed_runs = sum(item.timed_runs for item in stats)
    combined = ServiceStats(service="overall")
    combined.trace_runs = sum(item.trace_runs for item in stats)
    for item in stats:
        combined.markdown_files.update(item.markdown_files)
        combined.skill_files.update(item.skill_files)
        combined.hook_files.update(item.hook_files)
    return {
        "answered": answered,
        "judged": judged,
        "correct": correct,
        "accuracy_pct": round(correct / judged * 100, 1) if judged else 0.0,
        "avg_tokens": round(total_tokens / answered) if answered else 0,
        "total_tokens": total_tokens,
        "cached_input_tokens": sum(item.cached_input_tokens for item in stats),
        "avg_elapsed_s": round(total_elapsed / timed_runs, 1) if timed_runs else None,
        "total_elapsed_s": round(total_elapsed, 1) if timed_runs else None,
        "total_cost_usd": round(total_cost, 4) if cost_runs else None,
        "cost_estimated": any(item.estimated_cost_runs for item in stats),
        "observed_repo_usage": _observed(combined),
    }


def _cost_cell(cost: float | None, estimated: bool) -> str:
    return "—" if cost is None else f"{'~' if estimated else ''}${cost}"


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    if seconds < 60:
        return f"{seconds:.1f}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60):02d}s"
    return f"{int(seconds // 3600)}h {int(seconds % 3600 // 60):02d}m"


def render_report(session_id: str, as_json: bool = False, pricing_path: str | None = None) -> None:
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
    out_path = RESULTS_DIR / session_id / "report.json"
    out_path.write_text(json.dumps(report, indent=2))
    if as_json:
        _console.print_json(data=report)
        return

    rows = []
    for suite in report["services"]:
        observed = suite["observed_repo_usage"]
        context = "—"
        if observed["trace_runs"]:
            context = f"{observed['markdown_files']}/{observed['custom_skills']}/{observed['hooks']}"
        rows.append(
            [
                suite["service"],
                f"{suite['correct']}/{suite['judged']}",
                f"{suite['accuracy_pct']}%",
                suite["avg_score"],
                f"{suite['avg_tokens']:,}",
                _duration(suite["avg_elapsed_s"]),
                _cost_cell(suite["total_cost_usd"], suite["cost_estimated"]),
                context,
                suite["errored"] or "",
            ]
        )
    headers = ["suite", "correct", "accuracy", "score", "avg_tok", "avg_time", "cost", "md/sk/hook", "err"]
    _console.print(tabulate(rows, headers=headers, tablefmt="github"))

    overall = report["overall"]
    cost = ""
    if overall["total_cost_usd"] is not None:
        cost = f", {_cost_cell(overall['total_cost_usd'], overall['cost_estimated'])} total"
    timing = ""
    if overall["avg_elapsed_s"] is not None:
        timing = f", avg {_duration(overall['avg_elapsed_s'])}/question"
    _console.print(
        f"\n[bold]Overall[/bold]: {overall['correct']}/{overall['judged']} correct "
        f"([green]{overall['accuracy_pct']}%[/green]), avg {overall['avg_tokens']:,} tok/question{cost}{timing}."
    )
    inventory = report["repo_context"]["inventory"]
    observed = report["repo_context"]["observed_usage"]
    if inventory:
        _console.print(
            "[bold]Repo context[/bold]: "
            f"inventory {inventory['markdown_files']} md / "
            f"{inventory['custom_skills']} skills / {inventory['hooks']} hooks; "
            f"observed {observed['markdown_files']} / {observed['custom_skills']} / {observed['hooks']} "
            f"across {observed['trace_runs']} traced answer(s)."
        )
    if overall["cost_estimated"]:
        _console.print(f"[dim]~ = API-equivalent estimate from {prices.source}, not a billed amount.[/dim]")
    elif overall["total_cost_usd"] is None:
        _console.print(f"[dim]No cost telemetry or matching rate in {DEFAULT_PRICING_PATH.name}.[/dim]")
    _console.print(f"Wrote {out_path}")


@click.command()
@click.argument("session_id")
@click.option("--json", "as_json", is_flag=True, help="Print raw JSON instead of a table.")
@click.option("--pricing", "pricing_path", default=None, help="JSON token-rate override.")
def main(session_id: str, as_json: bool, pricing_path: str | None) -> None:
    """Aggregate and display a scored session."""
    render_report(session_id, as_json=as_json, pricing_path=pricing_path)


if __name__ == "__main__":
    main()
