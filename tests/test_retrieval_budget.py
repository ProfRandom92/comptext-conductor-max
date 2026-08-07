from comptext_conductor_max.models import IndexedSlice, RepositoryIndex
from comptext_conductor_max.retrieval import Retriever


def _index() -> RepositoryIndex:
    return RepositoryIndex(
        root="/repo",
        file_count=3,
        slices=(
            IndexedSlice(path="src/map_loader.py", start_line=1, end_line=3, text="def legacy_coordinate_transform():\n    return 12", content_hash="a", kind="source", symbols=("legacy_coordinate_transform",)),
            IndexedSlice(path="tests/test_map_loader.py", start_line=1, end_line=3, text="def test_legacy_coordinate_transform():\n    assert value == 12", content_hash="b", kind="test", symbols=("test_legacy_coordinate_transform",)),
            IndexedSlice(path="docs/unrelated.md", start_line=1, end_line=3, text="marketing colors and typography", content_hash="c", kind="source"),
        ),
    )


def test_search_ranks_relevant_slices_and_top_k_is_stable():
    retriever = Retriever()
    first = retriever.search(_index(), "legacy coordinate transformation", max_results=2, max_lines=20)
    second = retriever.search(_index(), "legacy coordinate transformation", max_results=2, max_lines=20)
    assert [item.path for item in first.results] == [item.path for item in second.results]
    assert first.results[0].path == "src/map_loader.py"
    assert "docs/unrelated.md" not in [item.path for item in first.results]
    assert len(first.results) == 2


def test_search_respects_line_and_token_budget():
    response = Retriever().search(_index(), "legacy coordinate", max_results=5, max_lines=2, budget_tokens=30)
    assert response.returned_lines <= 2
    assert response.returned_tokens.value <= 30
    assert response.returned_tokens.metric == "estimated_tokens"


def test_changed_and_failing_file_boosts_are_explainable():
    response = Retriever().search(
        _index(),
        "legacy coordinate",
        max_results=3,
        max_lines=20,
        changed_files={"tests/test_map_loader.py"},
        failure_files={"tests/test_map_loader.py"},
    )
    test_result = next(item for item in response.results if item.path == "tests/test_map_loader.py")
    assert "changed-file" in test_result.reasons
    assert "failing-test" in test_result.reasons


def test_critical_slice_does_not_silently_disappear_when_budget_is_too_small():
    response = Retriever().search(
        _index(),
        "legacy coordinate",
        max_results=2,
        max_lines=20,
        budget_tokens=1,
        critical_paths={"src/map_loader.py"},
    )
    assert response.budget_exceeded is True
    assert "src/map_loader.py" in response.omitted_critical
