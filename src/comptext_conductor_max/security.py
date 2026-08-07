from __future__ import annotations

import fnmatch
import re
from pathlib import Path

from pathspec import PathSpec

_SECRET_GLOBS = (".env", ".env.*", "*.pem", "*.key", "id_rsa", "id_rsa.*", "id_ed25519", "id_ed25519.*", "credentials*", "secrets*")
_DENY_DIRS = {".git", ".venv", "venv", "node_modules", "dist", "build", "__pycache__", ".comptext"}
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_./+=-]{16,}", re.IGNORECASE),
    re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|sk-[A-Za-z0-9_-]{20,})\b"),
)


class SecurityPolicy:
    def __init__(self, root: Path, ignore_spec: PathSpec) -> None:
        self.root = root.resolve()
        self.ignore_spec = ignore_spec

    @classmethod
    def from_root(cls, root: Path) -> SecurityPolicy:
        canonical = root.resolve()
        lines: list[str] = []
        for name in (".gitignore", ".comptextignore"):
            path = canonical / name
            if path.is_file():
                lines.extend(path.read_text(encoding="utf-8", errors="replace").splitlines())
        return cls(canonical, PathSpec.from_lines("gitwildmatch", lines))

    def _relative(self, path: Path) -> Path | None:
        try:
            candidate = path if path.is_absolute() else self.root / path
            if candidate.is_symlink():
                return None
            resolved = candidate.resolve(strict=False)
            return resolved.relative_to(self.root)
        except (OSError, ValueError):
            return None

    def is_path_allowed(self, path: Path) -> bool:
        relative = self._relative(path)
        if relative is None:
            return False
        if any(part in _DENY_DIRS for part in relative.parts):
            return False
        if any(fnmatch.fnmatch(relative.name, pattern) for pattern in _SECRET_GLOBS):
            return False
        return not self.ignore_spec.match_file(relative.as_posix())

    def resolve_explicit_file(self, path: Path, *, max_bytes: int = 50_000_000) -> Path:
        candidate = path if path.is_absolute() else self.root / path
        if candidate.is_symlink():
            raise ValueError("symlink log paths are not allowed")
        resolved = candidate.resolve(strict=True)
        try:
            relative = resolved.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("path escapes project root") from exc
        if ".git" in relative.parts or any(fnmatch.fnmatch(relative.name, pattern) for pattern in _SECRET_GLOBS):
            raise ValueError("sensitive path is not allowed")
        if not resolved.is_file():
            raise ValueError("path is not a file")
        if resolved.stat().st_size > max_bytes:
            raise ValueError("explicit file exceeds local processing limit")
        with resolved.open("rb") as handle:
            if b"\x00" in handle.read(8192):
                raise ValueError("binary file is not a supported log")
        return resolved

    @staticmethod
    def contains_secret(text: str) -> bool:
        return any(pattern.search(text) is not None for pattern in _SECRET_PATTERNS)

    def safe_text(self, path: Path, max_bytes: int) -> str | None:
        if max_bytes <= 0 or not self.is_path_allowed(path):
            return None
        candidate = path if path.is_absolute() else self.root / path
        try:
            raw = candidate.read_bytes()[:max_bytes]
        except OSError:
            return None
        if b"\x00" in raw:
            return None
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError:
            return None
        return None if self.contains_secret(text) else text
