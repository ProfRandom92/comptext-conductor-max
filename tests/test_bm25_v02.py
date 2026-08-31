from comptext_conductor_max.models import IndexedSlice, RepositoryIndex
from comptext_conductor_max.retrieval import Retriever


def test_term_frequency_can_outweigh_alphabetical_tie_break():
    index = RepositoryIndex(
        root="/repo",
        file_count=2,
        slices=(
            IndexedSlice(
                path="a_single.py",
                start_line=1,
                end_line=1,
                text="renderer coordinate helper",
                content_hash="a",
                kind="source",
            ),
            IndexedSlice(
                path="z_dense.py",
                start_line=1,
                end_line=1,
                text="renderer renderer renderer coordinate coordinate implementation",
                content_hash="b",
                kind="source",
            ),
        ),
    )
    response = Retriever().search(index, "renderer coordinate", max_results=2)
    assert response.results[0].path == "z_dense.py"
    assert any(reason.startswith("bm25:") for reason in response.results[0].reasons)
