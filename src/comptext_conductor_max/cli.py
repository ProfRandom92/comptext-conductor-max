from __future__ import annotations

import json
import platform
import subprocess
import tempfile
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .antigravity import run_headless_probe
from .benchmark import generate_fixture, run_benchmark, write_report
from .broker import ContextBroker
from .config import ProfileName

app = typer.Typer(no_args_is_help=True, help="CompText Conductor Max local context broker")
cache_app = typer.Typer(no_args_is_help=True, help="Inspect or clear the local content cache")
app.add_typer(cache_app, name="cache")
console = Console(highlight=False, markup=False)

RootOption = Annotated[Path, typer.Option("--root")]
TrackOption = Annotated[str, typer.Option("--track")]
TaskOption = Annotated[str, typer.Option("--task")]
ProfileOption = Annotated[ProfileName, typer.Option("--profile")]
BudgetOption = Annotated[int | None, typer.Option("--budget")]
OutputOption = Annotated[Path, typer.Option("--output")]
SeedOption = Annotated[int, typer.Option("--seed")]
PathArgument = Annotated[Path, typer.Argument()]


@app.command()
def doctor(root: RootOption = Path(".")) -> None:
    """Check local runtime, repository, Conductor, and MCP prerequisites."""
    canonical = root.resolve()
    tracks = list((canonical / "conductor" / "tracks").glob("*/spec.md"))
    git_ok = subprocess.run(
        ["git", "--version"], capture_output=True, text=True, check=False
    ).returncode == 0
    table = Table(title="CompText Conductor Max")
    table.add_column("Check")
    table.add_column("Result")
    table.add_row("Python", platform.python_version())
    table.add_row("Root", str(canonical))
    table.add_row("Git", "ok" if git_ok else "unavailable")
    table.add_row("Conductor tracks", str(len(tracks)))
    table.add_row("MCP SDK", "2.x")
    console.print(table)


@app.command("index")
def index_command(path: PathArgument = Path(".")) -> None:
    """Build the safe local repository index."""
    broker = ContextBroker(path)
    result = broker.indexer.build()
    console.print(f"Indexed files: {result.file_count}; slices: {len(result.slices)}")


@app.command()
def context(
    track: TrackOption,
    task: TaskOption = "implement current plan step",
    profile: ProfileOption = "balanced",
    budget: BudgetOption = None,
    root: RootOption = Path("."),
) -> None:
    """Assemble bounded context for a Conductor implementation step."""
    result = ContextBroker(root).context(
        track=track, task=task, profile=profile, budget=budget
    )
    console.print(result.content)
    console.print(
        f"\n[{result.returned_tokens.metric}: {result.returned_tokens.value}; budget: {result.budget}; "
        f"budget_exceeded: {str(result.budget_exceeded).lower()}]"
    )


@app.command()
def stats(root: RootOption = Path(".")) -> None:
    """Print persisted measured context-reduction counters."""
    console.print_json(json.dumps(ContextBroker(root).stats_snapshot()))


@app.command("agy-probe")
def agy_probe(root: RootOption = Path(".")) -> None:
    """Probe Antigravity headless stream-json support and report host token usage."""
    result = run_headless_probe(root)
    payload: dict[str, object] = {
        "available": result.available,
        "usage_source": "antigravity_result_usage" if result.usage is not None else None,
        "usage": asdict(result.usage) if result.usage is not None else None,
        "error": result.error,
    }
    console.print_json(json.dumps(payload))
    if result.usage is None:
        raise typer.Exit(code=2)


@cache_app.command("status")
def cache_status(root: RootOption = Path(".")) -> None:
    broker = ContextBroker(root)
    status = broker.cache.status()
    console.print_json(
        json.dumps({"entries": status.entries, "hits": status.hits, "misses": status.misses})
    )


@cache_app.command("clear")
def cache_clear(root: RootOption = Path(".")) -> None:
    broker = ContextBroker(root)
    broker.cache.clear()
    console.print("Cache cleared")


@app.command()
def benchmark(
    output: OutputOption = Path("benchmarks/results/latest.json"),
    seed: SeedOption = 20260807,
) -> None:
    """Run the deterministic naive/SAFE/BALANCED/MAX context benchmark."""
    with tempfile.TemporaryDirectory(prefix="ct-conductor-benchmark-") as tmp:
        manifest = generate_fixture(Path(tmp) / "repo", seed=seed)
        report = run_benchmark(manifest)
    write_report(report, output)
    console.print(f"Benchmark report: {output}")
    for run in report.runs:
        console.print(
            f"{run.mode}: returned_estimated_tokens={run.returned_estimated_tokens}; "
            f"reduction={run.reduction_ratio:.4f}; missing={len(run.missing_required_facts)}"
        )
    if not report.meets_target:
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
