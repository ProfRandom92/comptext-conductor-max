from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class StatsSnapshot:
    raw_bytes_considered: int = 0
    returned_bytes: int = 0
    raw_estimated_tokens: int = 0
    returned_estimated_tokens: int = 0
    full_file_reads: int = 0
    partial_reads: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    diff_bytes_avoided: int = 0
    log_bytes_avoided: int = 0
    retrieval_result_count: int = 0
    context_budget: int = 0

    @property
    def compression_ratio(self) -> float:
        return self.returned_bytes / self.raw_bytes_considered if self.raw_bytes_considered else 0.0

    @property
    def reduction_ratio(self) -> float:
        return 1.0 - self.compression_ratio if self.raw_bytes_considered else 0.0


class StatsLedger:
    def __init__(self, path: Path) -> None:
        self.path = path
        if path.is_file():
            try:
                self._data = StatsSnapshot(**json.loads(path.read_text(encoding="utf-8")))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                self._data = StatsSnapshot()
        else:
            self._data = StatsSnapshot()

    def _replace(self, **changes: int) -> None:
        data = asdict(self._data)
        data.update(changes)
        self._data = StatsSnapshot(**data)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(self._data), sort_keys=True, indent=2) + "\n", encoding="utf-8")

    def record_context(self, *, raw_bytes: int, returned_bytes: int, raw_tokens: int, returned_tokens: int, context_budget: int, retrieval_results: int) -> None:
        d = self._data
        self._replace(
            raw_bytes_considered=d.raw_bytes_considered + max(0, raw_bytes),
            returned_bytes=d.returned_bytes + max(0, returned_bytes),
            raw_estimated_tokens=d.raw_estimated_tokens + max(0, raw_tokens),
            returned_estimated_tokens=d.returned_estimated_tokens + max(0, returned_tokens),
            context_budget=max(0, context_budget),
            retrieval_result_count=d.retrieval_result_count + max(0, retrieval_results),
        )

    def record_cache(self, *, hit: bool) -> None:
        d = self._data
        self._replace(cache_hits=d.cache_hits + int(hit), cache_misses=d.cache_misses + int(not hit))

    def record_read(self, *, full: bool) -> None:
        d = self._data
        self._replace(full_file_reads=d.full_file_reads + int(full), partial_reads=d.partial_reads + int(not full))

    def record_diff(self, *, raw_bytes: int, returned_bytes: int) -> None:
        self._replace(diff_bytes_avoided=self._data.diff_bytes_avoided + max(0, raw_bytes - returned_bytes))

    def record_log(self, *, raw_bytes: int, returned_bytes: int) -> None:
        self._replace(log_bytes_avoided=self._data.log_bytes_avoided + max(0, raw_bytes - returned_bytes))

    def snapshot(self) -> StatsSnapshot:
        return self._data
