import subprocess
from pathlib import Path

from comptext_conductor_max.cache import ContentCache
from comptext_conductor_max.gitops import GitDiffEngine
from comptext_conductor_max.indexer import RepositoryIndexer
from comptext_conductor_max.results import ResultAnalyzer
from comptext_conductor_max.retrieval import Retriever
from comptext_conductor_max.security import SecurityPolicy


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)


def test_secret_only_result_log_never_reappears_via_fallback():
    secret = "abcdefghijklmnopqrstuvwxyz123456"
    result = ResultAnalyzer().analyze(f"TOKEN={secret}\n", exit_code=1, max_lines=10)
    assert result.relevant_lines == ()
    assert secret not in "\n".join(result.relevant_lines)


def test_large_file_index_reports_truncation_explicitly(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "large.py").write_text("value = 1\n" + ("x" * 256), encoding="utf-8")
    policy = SecurityPolicy.from_root(tmp_path)
    cache = ContentCache(tmp_path / ".cache")
    index = RepositoryIndexer(
        tmp_path,
        policy,
        cache,
        max_file_bytes=32,
        window_lines=8,
    ).build()
    assert hasattr(index, "truncated_paths"), "oversized files must be surfaced explicitly"
    assert index.truncated_paths == ("src/large.py",)
    response = Retriever().search(index, "value", max_results=1, max_lines=8, budget_tokens=100)
    assert hasattr(response, "truncated_paths"), "search callers must see partial-index provenance"
    assert response.truncated_paths == ("src/large.py",)


def test_staged_changes_are_visible_in_default_diff_summary(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "test@example.invalid")
    _git(root, "config", "user.name", "Test")
    src = root / "src"
    src.mkdir()
    target = src / "app.py"
    target.write_text("value = 1\n", encoding="utf-8")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "base")

    target.write_text("value = 2\n", encoding="utf-8")
    _git(root, "add", "src/app.py")

    result = GitDiffEngine().summarize(root)
    assert result.files_changed == 1
    assert result.source_files == ("src/app.py",)
    assert result.hunks and result.hunks[0].path == "src/app.py"
