from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .cache import ContentCache
from .models import IndexedSlice, RepositoryIndex
from .security import SecurityPolicy

_GENERATED_NAMES = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "poetry.lock"}
_SYMBOL = re.compile(r"^\s*(?:def|class|async\s+def|function|interface|struct|enum|fn)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)


class RepositoryIndexer:
    def __init__(
        self,
        root: Path,
        policy: SecurityPolicy,
        cache: ContentCache,
        *,
        window_lines: int = 80,
        max_file_bytes: int = 1_000_000,
    ) -> None:
        self.root = root.resolve()
        self.policy = policy
        self.cache = cache
        self.window_lines = max(1, window_lines)
        self.max_file_bytes = max_file_bytes

    @staticmethod
    def _kind(path: str) -> str:
        if "/conductor/tracks/" in f"/{path}" or path.startswith("conductor/"):
            if path.endswith("spec.md"):
                return "spec"
            if path.endswith("plan.md"):
                return "plan"
            if path.endswith("metadata.json"):
                return "metadata"
        if "/test" in f"/{path}" or path.startswith("tests/"):
            return "test"
        return "source"

    def build(self) -> RepositoryIndex:
        slices: list[IndexedSlice] = []
        files = 0
        for path in sorted(self.root.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(self.root).as_posix()
            if path.name in _GENERATED_NAMES or any(part.startswith(".ct-cache") for part in path.relative_to(self.root).parts):
                continue
            if not self.policy.is_path_allowed(path):
                continue
            text = self.policy.safe_text(path, self.max_file_bytes)
            if text is None:
                continue
            files += 1
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            key = f"index:v1:{rel}:{content_hash}:{self.window_lines}"
            cached = self.cache.get(key)
            if isinstance(cached, list):
                slices.extend(IndexedSlice.model_validate(item) for item in cached)
                continue
            lines = text.splitlines()
            file_slices: list[IndexedSlice] = []
            for offset in range(0, max(1, len(lines)), self.window_lines):
                chunk_lines = lines[offset : offset + self.window_lines]
                chunk = "\n".join(chunk_lines)
                if text.endswith("\n") and offset + self.window_lines >= len(lines):
                    chunk += "\n"
                symbols = tuple(dict.fromkeys(_SYMBOL.findall(chunk)))
                file_slices.append(
                    IndexedSlice(
                        path=rel,
                        start_line=offset + 1,
                        end_line=max(offset + 1, offset + len(chunk_lines)),
                        text=chunk,
                        content_hash=content_hash,
                        kind=self._kind(rel),
                        symbols=symbols,
                    )
                )
            self.cache.put(key, [item.model_dump(mode="json") for item in file_slices])
            slices.extend(file_slices)
        return RepositoryIndex(root=str(self.root), slices=tuple(slices), file_count=files)
