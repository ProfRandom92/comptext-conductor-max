from pathlib import Path

from comptext_conductor_max.benchmark import generate_fixture, run_benchmark
from comptext_conductor_max.broker import ContextBroker


def test_fixture_generation_is_content_deterministic(tmp_path: Path):
    first = generate_fixture(tmp_path / "first", seed=17)
    second = generate_fixture(tmp_path / "second", seed=17)
    assert first.fixture_hash == second.fixture_hash
    assert first.required_facts == second.required_facts


def test_benchmark_compares_naive_safe_balanced_max_and_meets_target(tmp_path: Path):
    manifest = generate_fixture(tmp_path / "repo", seed=23)
    report = run_benchmark(manifest)
    assert [run.mode for run in report.runs] == ["naive", "safe", "balanced", "max"]
    assert report.raw_context_bytes > 0
    assert report.token_metric == "estimated_tokens"
    assert all(run.raw_bytes == report.raw_context_bytes for run in report.runs)
    assert all(run.missing_required_facts == () for run in report.runs)
    assert any(run.reduction_ratio >= 0.50 for run in report.runs if run.mode in {"balanced", "max"})
    assert report.meets_target is True


def test_diff_broker_summary_does_not_return_raw_hunk_text(tmp_path: Path):
    manifest = generate_fixture(tmp_path / "repo", seed=5)
    payload = ContextBroker(manifest.root).diff()
    assert payload["hunks"]
    assert all("hunk_id" in item and "path" in item for item in payload["hunks"] )
    assert all("text" not in item for item in payload["hunks"] )
