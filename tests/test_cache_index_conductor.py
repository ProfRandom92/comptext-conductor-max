from pathlib import Path

from comptext_conductor_max.cache import ContentCache
from comptext_conductor_max.conductor import detect_conductor
from comptext_conductor_max.indexer import RepositoryIndexer
from comptext_conductor_max.security import SecurityPolicy


def _make_track(root: Path) -> None:
    track = root / "conductor" / "tracks" / "demo"
    track.mkdir(parents=True)
    (track / "spec.md").write_text("# Spec\nRENDERER=KNI\n", encoding="utf-8")
    (track / "plan.md").write_text("# Plan\n- [x] setup\n- [ ] MAP-003 load coordinates\n", encoding="utf-8")
    (track / "metadata.json").write_text('{"name":"demo"}', encoding="utf-8")


def test_cache_roundtrip_and_miss_hit_counters(tmp_path: Path):
    cache = ContentCache(tmp_path / ".comptext-cache")
    assert cache.get("missing") is None
    cache.put("abc", {"value": 42})
    assert cache.get("abc") == {"value": 42}
    status = cache.status()
    assert status.misses == 1
    assert status.hits == 1


def test_conductor_detector_reads_official_track_and_current_step(tmp_path: Path):
    _make_track(tmp_path)
    state = detect_conductor(tmp_path, "demo")
    assert state.track == "demo"
    assert state.spec_path.name == "spec.md"
    assert state.plan_path.name == "plan.md"
    assert state.metadata_path is not None
    assert state.current_step == "MAP-003 load coordinates"


def test_indexer_is_stable_and_invalidates_changed_file(tmp_path: Path):
    _make_track(tmp_path)
    src = tmp_path / "src"
    src.mkdir()
    code = src / "map_loader.py"
    code.write_text("def load_map():\n    return 12\n", encoding="utf-8")
    (tmp_path / "package-lock.json").write_text("generated-noise", encoding="utf-8")
    cache = ContentCache(tmp_path / ".ct-cache")
    indexer = RepositoryIndexer(tmp_path, SecurityPolicy.from_root(tmp_path), cache, window_lines=20)
    first = indexer.build()
    second = indexer.build()
    assert [s.model_dump() for s in first.slices] == [s.model_dump() for s in second.slices]
    assert all(s.path != "package-lock.json" for s in first.slices)
    first_hash = next(s.content_hash for s in first.slices if s.path == "src/map_loader.py")
    code.write_text("def load_map():\n    return 13\n", encoding="utf-8")
    third = indexer.build()
    third_hash = next(s.content_hash for s in third.slices if s.path == "src/map_loader.py")
    assert first_hash != third_hash
    assert cache.status().hits > 0
