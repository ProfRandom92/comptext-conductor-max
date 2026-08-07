import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_required_documentation_exists():
    required = [
        ROOT / "README.md",
        ROOT / "AGENTS.md",
        ROOT / "LICENSE",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "context-budget.md",
        ROOT / "docs" / "benchmark.md",
        ROOT / "docs" / "security.md",
        ROOT / "docs" / "conductor-integration.md",
        ROOT / "docs" / "research.md",
    ]
    assert all(path.is_file() for path in required)


def test_readme_has_required_sections_and_measured_benchmark_values():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for heading in (
        "## Problem", "## Architecture", "## How it reduces context", "## Installation",
        "## Antigravity setup", "## Conductor setup", "## MCP tools", "## Profiles",
        "## Benchmarks", "## Security", "## Troubleshooting", "## Development", "## License",
    ):
        assert heading in readme
    report = json.loads((ROOT / "benchmarks/results/latest.json").read_text(encoding="utf-8"))
    balanced = next(run for run in report["runs"] if run["mode"] == "balanced")
    assert f"{report['raw_context_estimated_tokens']:,}" in readme
    assert f"{balanced['returned_estimated_tokens']:,}" in readme
    assert f"{balanced['reduction_ratio'] * 100:.2f}%" in readme
    assert report["fixture_hash"] in readme
    assert "synthetic" in readme.lower()
    assert "estimated_tokens" in readme


def test_docs_do_not_restate_old_unverified_94_percent_claim():
    docs = "\n".join(path.read_text(encoding="utf-8") for path in [ROOT / "README.md", *sorted((ROOT / "docs").glob("*.md")), ROOT / "AGENTS.md"] if path.is_file())
    assert "94%" not in docs
    assert "94 %" not in docs


def test_agents_completion_rules_prioritize_correctness_and_measurement():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "Context correctness" in agents
    assert "invent" in agents.lower() and "benchmark" in agents.lower()
    assert "pytest -q" in agents
    assert "ruff check ." in agents
    assert "mypy src" in agents


def test_research_doc_records_reference_licenses_and_no_code_copying():
    research = (ROOT / "docs/research.md").read_text(encoding="utf-8")
    assert "Apache-2.0" in research
    assert "Elastic License 2.0" in research
    assert "MIT" in research
    assert "no source code" in research.lower()
