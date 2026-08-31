from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class IndexedSlice(BaseModel):
    model_config = ConfigDict(frozen=True)
    path: str
    start_line: int
    end_line: int
    text: str
    content_hash: str
    kind: str
    symbols: tuple[str, ...] = ()


class RepositoryIndex(BaseModel):
    model_config = ConfigDict(frozen=True)
    root: str
    slices: tuple[IndexedSlice, ...]
    file_count: int
    truncated_paths: tuple[str, ...] = ()
