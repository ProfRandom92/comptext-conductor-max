from __future__ import annotations

import hashlib
import json
import re

from .models import IndexedSlice, RepositoryIndex

_REF = re.compile(r"^ctref:v1:[0-9a-f]{64}$")


def make_ref(item: IndexedSlice) -> str:
    payload = json.dumps(
        {
            "content_hash": item.content_hash,
            "end_line": item.end_line,
            "path": item.path,
            "start_line": item.start_line,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return "ctref:v1:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


class StaleRefError(KeyError):
    pass


def resolve_ref(index: RepositoryIndex, ref: str) -> IndexedSlice:
    if _REF.fullmatch(ref) is None:
        raise ValueError("invalid context ref")
    for item in index.slices:
        if make_ref(item) == ref:
            return item
    raise StaleRefError("context ref is stale or not found")
