from comptext_conductor_max.indexer import RepositoryIndexer


def test_conductor_project_context_kinds_are_distinct():
    assert RepositoryIndexer._kind("conductor/product.md") == "project_context"
    assert RepositoryIndexer._kind("conductor/tech-stack.md") == "project_context"
    assert RepositoryIndexer._kind("conductor/code_styleguides/python.md") == "styleguide"
    assert RepositoryIndexer._kind("conductor/tracks/demo/index.md") == "track_index"
