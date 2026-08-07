import subprocess
from pathlib import Path

import pytest
from mcp import Client

from comptext_conductor_max.broker import ContextBroker
from comptext_conductor_max.mcp_server import create_server


def _repo(root: Path) -> None:
    track = root / "conductor" / "tracks" / "demo"
    track.mkdir(parents=True)
    (track / "spec.md").write_text("# Spec\nRENDERER=KNI\ncoordinate semantics must stay legacy\n", encoding="utf-8")
    (track / "plan.md").write_text("# Plan\n- [ ] MAP-003 legacy coordinate transformation\n", encoding="utf-8")
    (track / "metadata.json").write_text('{"name":"demo"}', encoding="utf-8")
    src = root / "src"
    src.mkdir()
    (src / "map_loader.py").write_text("def legacy_coordinate_transform():\n    return 12\n", encoding="utf-8")
    (root / "unrelated.txt").write_text(("unrelated typography colors\n" * 500), encoding="utf-8")


def _init_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "main"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-m", "base"], cwd=root, check=True, capture_output=True)


def test_context_broker_returns_minimal_track_context_with_budget(tmp_path: Path):
    _repo(tmp_path)
    result = ContextBroker(tmp_path).context(track="demo", task="legacy coordinate transformation", profile="max")
    assert result.track == "demo"
    assert result.current_step == "MAP-003 legacy coordinate transformation"
    assert "RENDERER=KNI" in result.content
    assert "legacy_coordinate_transform" in result.content
    assert "unrelated typography" not in result.content
    assert result.returned_tokens.value <= 10_000
    assert result.returned_tokens.metric == "estimated_tokens"


@pytest.mark.asyncio
async def test_mcp_initializes_lists_exactly_six_tools_and_calls_search(tmp_path: Path):
    _repo(tmp_path)
    server = create_server(tmp_path)
    async with Client(server) as client:
        listed = await client.list_tools()
        assert {tool.name for tool in listed.tools} == {
            "ct_context", "ct_search", "ct_diff", "ct_result", "ct_checkpoint", "ct_stats"
        }
        called = await client.call_tool("ct_search", {"query": "legacy coordinate", "max_results": 3, "max_lines": 30})
        assert called.is_error is False
        assert called.structured_content is not None
        assert called.structured_content["results"][0]["path"] == "src/map_loader.py"


@pytest.mark.asyncio
async def test_mcp_rejects_invalid_arguments_without_unbounded_output(tmp_path: Path):
    _repo(tmp_path)
    async with Client(create_server(tmp_path)) as client:
        called = await client.call_tool("ct_search", {})
        assert called.is_error is True
        assert sum(len(getattr(item, "text", "")) for item in called.content) < 10_000


@pytest.mark.asyncio
async def test_result_can_reduce_a_local_log_path_and_reject_escape(tmp_path: Path):
    _repo(tmp_path)
    log = tmp_path / "test-output.log"
    log.write_text(("noise\n" * 2000) + "FAILED_TEST=LegacyCoordinateTransform\nExpected: 12\nActual: 0\n", encoding="utf-8")
    async with Client(create_server(tmp_path)) as client:
        called = await client.call_tool("ct_result", {"log_path": "test-output.log", "exit_code": 1, "max_lines": 20})
        assert called.is_error is False
        assert called.structured_content is not None
        assert "LegacyCoordinateTransform" in "\n".join(called.structured_content["relevant_lines"])
        escaped = await client.call_tool("ct_result", {"log_path": "../outside.log"})
        assert escaped.is_error is True


@pytest.mark.asyncio
async def test_checkpoint_mcp_does_not_expose_absolute_store_paths(tmp_path: Path):
    _repo(tmp_path)
    async with Client(create_server(tmp_path)) as client:
        saved = await client.call_tool("ct_checkpoint", {"action": "save", "track": "demo", "step": "MAP-003"})
        assert saved.is_error is False
        payload = saved.structured_content or {}
        serialized = str(payload)
        assert str(tmp_path) not in serialized
        assert "checkpoint_hash" in payload


@pytest.mark.asyncio
async def test_search_clamps_untrusted_output_limit_arguments(tmp_path: Path):
    _repo(tmp_path)
    for i in range(80):
        (tmp_path / f"legacy_{i:03d}.txt").write_text(("legacy coordinate transformation relevant\n" * 300), encoding="utf-8")
    async with Client(create_server(tmp_path)) as client:
        called = await client.call_tool("ct_search", {"query": "legacy coordinate transformation", "max_results": 1000000, "max_lines": 1000000, "budget": 1000000})
        assert called.is_error is False
        payload = called.structured_content or {}
        assert len(payload["results"]) <= 20
        assert payload["returned_tokens"]["value"] <= 30000


@pytest.mark.asyncio
async def test_diff_hunk_retrieval_is_bounded(tmp_path: Path):
    _repo(tmp_path)
    _init_git_repo(tmp_path)
    target = tmp_path / "src" / "map_loader.py"
    target.write_text("\n".join(f"value_{i} = {i}" for i in range(2000)) + "\n", encoding="utf-8")
    async with Client(create_server(tmp_path)) as client:
        summary = await client.call_tool("ct_diff", {})
        hunk_id = (summary.structured_content or {})["hunks"][0]["hunk_id"]
        hunk = await client.call_tool("ct_diff", {"hunk_id": hunk_id, "max_lines": 50})
        payload = hunk.structured_content or {}
        assert len(payload["text"].splitlines()) <= 50
        assert payload["truncated"] is True


@pytest.mark.asyncio
async def test_stats_count_model_facing_partial_repository_reads(tmp_path: Path):
    _repo(tmp_path)
    async with Client(create_server(tmp_path)) as client:
        searched = await client.call_tool("ct_search", {"query": "legacy coordinate", "max_results": 3})
        assert searched.is_error is False
        stats = await client.call_tool("ct_stats", {})
        payload = stats.structured_content or {}
        assert payload["partial_reads"] >= 1
        assert payload["full_file_reads"] == 0


def test_context_profile_hard_limit_includes_response_headers(tmp_path: Path):
    _repo(tmp_path)
    nested = tmp_path
    for i in range(4):
        nested = nested / (chr(97 + i) * 180)
        nested.mkdir()
    long_file = nested / ("legacy_coordinate_" + ("x" * 150) + ".py")
    long_file.write_text(("legacy coordinate transformation " * 20 + "\n") * 400, encoding="utf-8")
    result = ContextBroker(tmp_path).context(track="demo", task="legacy coordinate transformation", profile="max")
    assert result.returned_tokens.value <= 10_000
