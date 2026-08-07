from pathlib import Path

import pytest

from comptext_conductor_max.checkpoints import Checkpoint, CheckpointStore
from comptext_conductor_max.handoff import decode_handoff, encode_handoff
from comptext_conductor_max.stats import StatsLedger


def _checkpoint() -> Checkpoint:
    return Checkpoint(
        track="p3d-web-port",
        step="3.2",
        status="complete",
        decisions={"renderer": "KNI", "coordinate_system": "legacy-preserved"},
        files_changed=("MapLoader.cs", "MapLoaderTests.cs"),
        tests_passed=185,
        tests_failed=0,
        next_step="implement texture loading",
    )


def test_checkpoint_hash_is_deterministic_and_save_load_has_markdown_sidecar(tmp_path: Path):
    store = CheckpointStore(tmp_path)
    first = store.save(_checkpoint())
    second = store.save(_checkpoint())
    assert first.checkpoint_hash == second.checkpoint_hash
    assert first.json_path.is_file()
    assert first.markdown_path.is_file()
    loaded = store.load(first.checkpoint_hash)
    assert loaded == _checkpoint()
    assert "renderer: KNI" in first.markdown_path.read_text(encoding="utf-8")


def test_handoff_roundtrip_is_strict_and_debuggable():
    encoded = encode_handoff(_checkpoint())
    assert encoded.startswith("H1;")
    decoded = decode_handoff(encoded)
    assert decoded.track == "p3d-web-port"
    assert decoded.step == "3.2"
    assert decoded.tests_passed == 185
    assert decoded.next_step == "implement texture loading"
    with pytest.raises(ValueError):
        decode_handoff(encoded + ";UNKNOWN=x")


def test_stats_records_measured_context_and_avoidance(tmp_path: Path):
    ledger = StatsLedger(tmp_path / "stats.json")
    ledger.record_context(raw_bytes=4000, returned_bytes=1000, raw_tokens=1000, returned_tokens=250, context_budget=10_000, retrieval_results=5)
    ledger.record_cache(hit=True)
    ledger.record_cache(hit=False)
    ledger.record_diff(raw_bytes=2000, returned_bytes=500)
    ledger.record_log(raw_bytes=6000, returned_bytes=600)
    snap = ledger.snapshot()
    assert snap.raw_bytes_considered == 4000
    assert snap.returned_bytes == 1000
    assert snap.raw_estimated_tokens == 1000
    assert snap.returned_estimated_tokens == 250
    assert snap.cache_hits == 1 and snap.cache_misses == 1
    assert snap.diff_bytes_avoided == 1500
    assert snap.log_bytes_avoided == 5400
    assert snap.reduction_ratio == 0.75
    reloaded = StatsLedger(tmp_path / "stats.json").snapshot()
    assert reloaded == snap


def test_checkpoint_track_cannot_escape_store(tmp_path: Path):
    with pytest.raises(ValueError):
        Checkpoint(track="../escape", step="1", status="complete")
    with pytest.raises(ValueError):
        Checkpoint(track="nested/escape", step="1", status="complete")
    assert not (tmp_path.parent / "escape").exists()


def test_handoff_roundtrip_handles_commas_in_file_names():
    checkpoint = _checkpoint().model_copy(update={"files_changed": ("src/a,b.py", "src/c.py")})
    assert decode_handoff(encode_handoff(checkpoint)).files_changed == checkpoint.files_changed
