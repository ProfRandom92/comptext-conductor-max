import subprocess
from pathlib import Path

from comptext_conductor_max.gitops import GitDiffEngine


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def _repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    (root / "src").mkdir()
    (root / "tests").mkdir()
    (root / "src/app.py").write_text("value = 1\n", encoding="utf-8")
    (root / "tests/test_app.py").write_text("assert 1 == 1\n", encoding="utf-8")
    (root / "package-lock.json").write_text('{"v":1}\n', encoding="utf-8")
    (root / "asset.png").write_bytes(b"\x89PNG\x00base")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")
    (root / "src/app.py").write_text("value = 2\nnew_value = 3\n", encoding="utf-8")
    (root / "tests/test_app.py").write_text("assert 2 == 2\n", encoding="utf-8")
    (root / "package-lock.json").write_text('{"v":2,"noise":true}\n', encoding="utf-8")
    (root / "asset.png").write_bytes(b"\x89PNG\x00changed-binary")
    return root


def test_diff_is_summary_first_and_omits_generated_and_binary_hunks(tmp_path: Path):
    result = GitDiffEngine().summarize(_repo(tmp_path))
    assert result.files_changed == 4
    assert result.additions > 0
    assert result.deletions > 0
    assert "package-lock.json" in result.generated_omitted
    assert "asset.png" in result.binary_omitted
    assert {h.path for h in result.hunks} == {"src/app.py", "tests/test_app.py"}


def test_hunk_ids_are_stable_and_individual_hunk_can_be_retrieved(tmp_path: Path):
    root = _repo(tmp_path)
    engine = GitDiffEngine()
    first = engine.summarize(root)
    second = engine.summarize(root)
    assert [h.hunk_id for h in first.hunks] == [h.hunk_id for h in second.hunks]
    hunk = engine.get_hunk(root, first.hunks[0].hunk_id)
    assert hunk.hunk_id == first.hunks[0].hunk_id
    assert hunk.text.startswith("@@")
