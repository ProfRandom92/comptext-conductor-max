from comptext_conductor_max.models import IndexedSlice, RepositoryIndex
from comptext_conductor_max.refs import make_ref
from comptext_conductor_max.retrieval import Retriever


def test_retriever_expands_one_bounded_reference():
    item = IndexedSlice(
        path="src/map.py",
        start_line=1,
        end_line=3,
        text="one\ntwo\nthree",
        content_hash="a" * 64,
        kind="source",
    )
    index = RepositoryIndex(root="/repo", slices=(item,), file_count=1)
    ref = make_ref(item)
    response = Retriever().expand_ref(index, ref, max_lines=2, budget_tokens=100)
    assert len(response.results) == 1
    assert response.results[0].ref == ref
    assert response.results[0].snippet == "one\ntwo"
    assert response.results[0].reasons == ("reference",)
