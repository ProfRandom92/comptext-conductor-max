import importlib.util
import subprocess
import sys
from importlib.metadata import version
from pathlib import Path

from comptext_conductor_max import __version__
from comptext_conductor_max.mcp_server import create_server
from comptext_conductor_max.skills import SkillCatalog

ROOT = Path(__file__).parents[1]


def _skill(root: Path, name: str, description: str, body: str) -> None:
    path = root / name
    path.mkdir()
    (path / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n{body}\n", encoding="utf-8"
    )


def test_version_consistency_and_mcp_version() -> None:
    assert __version__ == "0.3.1"
    assert version("comptext-conductor-max") == __version__
    assert create_server().version == __version__


def test_real_benchmark_invalid_trials_and_sign_semantics() -> None:
    spec = importlib.util.spec_from_file_location(
        "real_benchmark", ROOT / "scripts" / "run_real_antigravity_host_benchmark.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    invalid = module.summarize_mode_runs([module.invalid_trial("timeout")] * 3)
    assert invalid["status"] == "BENCHMARK_INCONCLUSIVE"
    assert invalid["total_tokens_median"] is None
    measured_b = {
        "status": "MEASURED",
        "input_tokens_median": 100,
        "cache_read_tokens_median": 40,
        "total_tokens_median": 200,
    }
    measured_c = {
        "status": "MEASURED",
        "input_tokens_median": 80,
        "cache_read_tokens_median": 50,
        "total_tokens_median": 240,
    }
    result = module.comparison(measured_b, measured_c)
    assert result["input_token_delta"] == -20
    assert result["input_token_savings_pct"] == 20.0
    assert result["total_token_delta"] == 40
    assert result["total_token_savings_pct"] == -20.0


def test_routing_golden_corpus(tmp_path: Path) -> None:
    _skill(
        tmp_path,
        "deploy-api",
        "Deploy a web API service",
        "Use blue-green rollout and canary checks.",
    )
    _skill(
        tmp_path,
        "database-migration",
        "Safely migrate relational database schemas",
        "Use backward-compatible SQL migrations and rollback plans.",
    )
    _skill(
        tmp_path,
        "trace-observability",
        "Telemetry guidance for service health",
        "OpenTelemetry spans bodymarker trace request latency and propagation.",
    )
    catalog = SkillCatalog(external_roots=(tmp_path,))
    skills = catalog.discover_skills()
    assert [s.name for s in catalog.rank_skills("use deploy-api", skills)] == ["deploy-api"]
    assert {
        s.name for s in catalog.rank_skills("deploy API and migrate database schema", skills)
    } == {"deploy-api", "database-migration"}
    body_query = "telemetry OpenTelemetry spans bodymarker"
    metadata_score = 15  # one metadata token match: telemetry
    assert 0 < metadata_score < 25
    assert [s.name for s in catalog.rank_skills(body_query, skills)] == ["trace-observability"]
    control_root = tmp_path / "no-body-evidence"
    control_root.mkdir()
    _skill(
        control_root,
        "trace-observability-control",
        "Telemetry guidance for service health",
        "Run unrelated canary checks.",
    )
    control = SkillCatalog(external_roots=(control_root,))
    assert control.rank_skills(body_query, control.discover_skills()) == ()
    assert catalog.rank_skills("write a poem about mountain sunrise", skills) == ()
    assert catalog.rank_skills("repair a bicycle chain", skills) == ()
    index = catalog.build_skill_index(body_query)
    assert [item.kind for item in index.slices].count("skill_instruction") == 1


def test_built_artifacts_report_v031(tmp_path: Path) -> None:
    subprocess.run(
        [sys.executable, "-m", "build", "--outdir", str(tmp_path)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    artifacts = [str(path) for path in tmp_path.iterdir()]
    assert any("0.3.1" in artifact and artifact.endswith(".whl") for artifact in artifacts)
    assert any("0.3.1" in artifact and artifact.endswith(".tar.gz") for artifact in artifacts)
