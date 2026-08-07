import json
from pathlib import Path

from typer.testing import CliRunner

from comptext_conductor_max.cli import app

runner = CliRunner()


def _repo(root: Path) -> None:
    track = root / "conductor" / "tracks" / "demo"
    track.mkdir(parents=True)
    (track / "spec.md").write_text("# Spec\nRENDERER=KNI\n", encoding="utf-8")
    (track / "plan.md").write_text("# Plan\n- [ ] MAP-003 legacy coordinate transform\n", encoding="utf-8")
    (track / "metadata.json").write_text('{"name":"demo"}', encoding="utf-8")
    (root / "src.py").write_text("def legacy_coordinate_transform():\n    return 12\n", encoding="utf-8")


def test_cli_doctor_index_context_stats_and_cache(tmp_path: Path):
    _repo(tmp_path)
    doctor = runner.invoke(app, ["doctor", "--root", str(tmp_path)])
    assert doctor.exit_code == 0
    assert "CompText Conductor Max" in doctor.stdout
    indexed = runner.invoke(app, ["index", str(tmp_path)])
    assert indexed.exit_code == 0
    assert "Indexed files" in indexed.stdout
    context = runner.invoke(app, ["context", "--root", str(tmp_path), "--track", "demo", "--task", "legacy coordinate"])
    assert context.exit_code == 0
    assert "RENDERER=KNI" in context.stdout
    stats = runner.invoke(app, ["stats", "--root", str(tmp_path)])
    assert stats.exit_code == 0
    assert "estimated_tokens" in stats.stdout
    cache = runner.invoke(app, ["cache", "status", "--root", str(tmp_path)])
    assert cache.exit_code == 0
    assert "entries" in cache.stdout.lower()


def test_antigravity_plugin_bundle_matches_current_schema():
    root = Path(__file__).resolve().parents[1]
    plugin = json.loads((root / "plugin.json").read_text(encoding="utf-8"))
    mcp = json.loads((root / "mcp_config.json").read_text(encoding="utf-8"))
    assert plugin["name"] == "comptext-conductor-max"
    assert set(plugin) == {"name", "description"}
    server = mcp["mcpServers"]["comptext-conductor-max"]
    assert server["command"] == "ct-conductor-mcp"
    assert server["args"] == []
    assert "url" not in server and "httpUrl" not in server
    assert (root / "rules" / "comptext-conductor-max.md").is_file()
    skill = (root / "skills" / "conductor-max" / "SKILL.md").read_text(encoding="utf-8")
    assert all(name in skill for name in ("SAFE", "BALANCED", "MAX", "ct_context", "ct_search", "ct_result"))
    assert len(skill) < 7000


def test_rule_prefers_broker_but_keeps_correctness_fallback():
    root = Path(__file__).resolve().parents[1]
    rule = (root / "rules" / "comptext-conductor-max.md").read_text(encoding="utf-8")
    assert "ct_diff" in rule and "ct_checkpoint" in rule
    assert "full" in rule.lower() and "correctness" in rule.lower()


def test_cli_benchmark_writes_measured_report(tmp_path: Path):
    output = tmp_path / "latest.json"
    result = runner.invoke(app, ["benchmark", "--output", str(output), "--seed", "29"])
    assert result.exit_code == 0
    assert output.is_file()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["meets_target"] is True
    assert report["token_metric"] == "estimated_tokens"
