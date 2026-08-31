from pathlib import Path

from comptext_conductor_max.cache import ContentCache
from comptext_conductor_max.indexer import RepositoryIndexer
from comptext_conductor_max.security import SecurityPolicy


class CountingPolicy(SecurityPolicy):
    def __init__(self, base: SecurityPolicy):
        super().__init__(base.root, base.ignore_spec)
        self.reads = 0

    def safe_text(self, path: Path, max_bytes: int) -> str | None:
        self.reads += 1
        return super().safe_text(path, max_bytes)


def test_warm_index_skips_content_reads_for_unchanged_files(tmp_path: Path):
    (tmp_path / "source.py").write_text("def answer():\n    return 42\n", encoding="utf-8")
    policy = CountingPolicy(SecurityPolicy.from_root(tmp_path))
    indexer = RepositoryIndexer(tmp_path, policy, ContentCache(tmp_path / ".ct-cache"))

    indexer.build()
    first_reads = policy.reads
    indexer.build()

    assert first_reads >= 1
    assert policy.reads == first_reads
