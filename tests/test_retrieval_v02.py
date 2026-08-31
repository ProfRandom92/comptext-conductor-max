from comptext_conductor_max.models import IndexedSlice, RepositoryIndex
from comptext_conductor_max.retrieval import Retriever


def test_preferred_project_context_gets_explainable_boost():
    index = RepositoryIndex(
        root="/repo",
        file_count=2,
        slices=(
            IndexedSlice(
                path="docs/other.md",
                start_line=1,
                end_line=1,
                text="python architecture rules",
                content_hash="a",
                kind="source",
            ),
            IndexedSlice(
                path="conductor/tech-stack.md",
                start_line=1,
                end_line=1,
                text="python architecture rules",
                content_hash="b",
                kind="project_context",
            ),
        ),
    )
    response = Retriever().search(
        index,
        "python architecture",
        max_results=2,
        preferred_paths={"conductor/tech-stack.md"},
    )
    assert response.results[0].path == "conductor/tech-stack.md"
    assert "preferred-context" in response.results[0].reasons
