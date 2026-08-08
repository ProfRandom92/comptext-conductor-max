from pathlib import Path

from comptext_conductor_max.state import ProjectStateStore


def test_project_state_persists_result_and_checkpoint(tmp_path: Path):
    path = tmp_path / ".comptext" / "project-state.json"
    store = ProjectStateStore(path)
    store.record_result(
        "a" * 64,
        ("src/map_loader.py", "tests/test_map_loader.py"),
        1,
    )
    store.record_checkpoint("demo", "b" * 64)

    loaded = ProjectStateStore(path).snapshot()
    assert loaded.latest_result_sha256 == "a" * 64
    assert loaded.latest_result_files == (
        "src/map_loader.py",
        "tests/test_map_loader.py",
    )
    assert loaded.latest_result_exit_code == 1
    assert loaded.latest_checkpoints == {"demo": "b" * 64}
