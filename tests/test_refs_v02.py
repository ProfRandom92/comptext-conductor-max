import pytest

from comptext_conductor_max.models import IndexedSlice, RepositoryIndex
from comptext_conductor_max.refs import make_ref, resolve_ref


def test_slice_ref_round_trip_and_stale_detection():
    item = IndexedSlice(
        path="src/map.py",
        start_line=10,
        end_line=20,
        text="def load():\n    return 12",
        content_hash="a" * 64,
        kind="source",
    )
    index = RepositoryIndex(root="/repo", slices=(item,), file_count=1)
    ref = make_ref(item)
    assert ref.startswith("ctref:v1:")
    assert resolve_ref(index, ref) == item

    changed = item.model_copy(update={"content_hash": "b" * 64})
    with pytest.raises(KeyError):
        resolve_ref(RepositoryIndex(root="/repo", slices=(changed,), file_count=1), ref)
