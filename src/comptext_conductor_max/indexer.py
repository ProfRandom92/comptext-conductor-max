from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .cache import ContentCache
from .models import IndexedSlice, RepositoryIndex
from .security import SecurityPolicy

_GENERATED_NAMES = {
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "uv.lock",
    "poetry.lock",
}
_PROJECT_CONTEXT_NAMES = {
    "product.md",
    "product-guidelines.md",
    "tech-stack.md",
    "workflow.md",
    "tracks.md",
}
_SYMBOL = re.compile(
    r"^\s*(?:def|class|async\s+def|function|interface|struct|enum|fn)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)",
    re.MULTILINE,
)


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
        if path.startswith("conductor/code_styleguides/") and path.endswith(".md"):
            return "styleguide"
        if path.startswith("conductor/tracks/"):
            if path.endswith("spec.md"):
                return "spec"
            if path.endswith("plan.md"):
                return "plan"
            if path.endswith("metadata.json"):
                return "metadata"
            if path.endswith("index.md"):
                return "track_index"
        if path.startswith("conductor/") and Path(path).name in _PROJECT_CONTEXT_NAMES:
            return "project_context"
        if "/test" in f"/{path}" or path.startswith("tests/"):
            return "test"
        return "source"

    def build(self) -> RepositoryIndex:
        slices: list[IndexedSlice] = []
        truncated_paths: list[str] = []
        files = 0
        for path in sorted(self.root.rglob("*"), key=lambda item: item.as_posix()):
            if not path.is_file() or path.is_symlink():
                continue
            rel = path.relative_to(self.root).as_posix()
            if path.name in _GENERATED_NAMES or any(
                part.startswith(".ct-cache") for part in path.relative_to(self.root).parts
            ):
                continue
            if not self.policy.is_path_allowed(path):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            is_truncated = stat.st_size > self.max_file_bytes
            stat_key = (
                f"index-stat:v1:{rel}:{stat.st_size}:{stat.st_mtime_ns}:"
                f"{self.window_lines}:{self.max_file_bytes}"
            )
            stat_cached = self.cache.get(stat_key)
            if isinstance(stat_cached, list):
                if is_truncated:
                    truncated_paths.append(rel)
                files += 1
                slices.extend(IndexedSlice.model_validate(item) for item in stat_cached)
                continue
            text = self.policy.safe_text(path, self.max_file_bytes)
            if text is None:
                continue
            if is_truncated:
                truncated_paths.append(rel)
            files += 1
            content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            content_key = f"index:v2:{rel}:{content_hash}:{self.window_lines}"
            content_cached = self.cache.get(content_key)
            if isinstance(content_cached, list):
                self.cache.put(stat_key, content_cached)
                slices.extend(IndexedSlice.model_validate(item) for item in content_cached)
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
            serialized = [item.model_dump(mode="json") for item in file_slices]
            self.cache.put(content_key, serialized)
            self.cache.put(stat_key, serialized)
            slices.extend(file_slices)
        return RepositoryIndex(
            root=str(self.root),
            slices=tuple(slices),
            file_count=files,
            truncated_paths=tuple(sorted(set(truncated_paths))),
        )
