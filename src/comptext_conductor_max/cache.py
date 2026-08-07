from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class CacheStatus:
    hits: int
    misses: int
    entries: int


class ContentCache:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _digest(key: str) -> str:
        return hashlib.sha256(key.encode("utf-8")).hexdigest()

    def _path(self, key: str) -> Path:
        return self.root / f"{self._digest(key)}.json"

    def get(self, key: str) -> Any | None:
        path = self._path(key)
        if not path.is_file():
            self._misses += 1
            return None
        self._hits += 1
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._misses += 1
            self._hits -= 1
            return None

    def put(self, key: str, value: Any) -> None:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        path = self._path(key)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(encoded, encoding="utf-8")
        tmp.replace(path)

    def invalidate(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)

    def clear(self) -> None:
        if self.root.exists():
            shutil.rmtree(self.root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._hits = 0
        self._misses = 0

    def status(self) -> CacheStatus:
        return CacheStatus(self._hits, self._misses, len(list(self.root.glob("*.json"))))
