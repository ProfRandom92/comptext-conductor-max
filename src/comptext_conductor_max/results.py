from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .security import SecurityPolicy

_IMPORTANT = re.compile(r"(?:FAILED|FAILURE|ERROR|error:|exception|traceback|assert|expected:|actual:|\d+ passed|\d+ failed|warning:)", re.IGNORECASE)
_FILE = re.compile(r"(?P<path>[A-Za-z0-9_./\-]+\.(?:py|ts|tsx|js|jsx|cs|rs|go|java|kt|cpp|c|h))(?::\d+(?::\d+)?)?")
_PASSED = re.compile(r"(\d+)\s+passed")
_FAILED = re.compile(r"(\d+)\s+failed")
_EXPECTED = re.compile(r"expected:\s*(.+)$", re.IGNORECASE)
_ACTUAL = re.compile(r"actual:\s*(.+)$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class ResultSummary:
    exit_code: int | None
    passed: int | None
    failed: int | None
    expected: str | None
    actual: str | None
    likely_files: tuple[str, ...]
    relevant_lines: tuple[str, ...]
    raw_sha256: str
    raw_bytes: int
    returned_bytes: int

    @property
    def avoided_bytes(self) -> int:
        return max(0, self.raw_bytes - self.returned_bytes)


class ResultAnalyzer:
    def analyze(self, value: str | Path, *, exit_code: int | None = None, max_lines: int = 120) -> ResultSummary:
        if isinstance(value, Path):
            raw = value.read_text(encoding="utf-8", errors="replace")
        else:
            raw = value
        raw_bytes = len(raw.encode("utf-8"))
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        relevant: list[str] = []
        files: set[str] = set()
        passed: int | None = None
        failed: int | None = None
        expected: str | None = None
        actual: str | None = None
        for line in raw.splitlines():
            if SecurityPolicy.contains_secret(line):
                continue
            for match in _FILE.finditer(line):
                files.add(match.group("path").replace("\\", "/"))
            if passed_match := _PASSED.search(line):
                passed = int(passed_match.group(1))
            if failed_match := _FAILED.search(line):
                failed = int(failed_match.group(1))
            if expected_match := _EXPECTED.search(line):
                expected = expected_match.group(1).strip()
            if actual_match := _ACTUAL.search(line):
                actual = actual_match.group(1).strip()
            if _IMPORTANT.search(line):
                relevant.append(line)
        if not relevant and raw:
            relevant = raw.splitlines()[-max_lines:]
        relevant = relevant[: max(0, max_lines)]
        returned = "\n".join(relevant)
        return ResultSummary(
            exit_code=exit_code,
            passed=passed,
            failed=failed,
            expected=expected,
            actual=actual,
            likely_files=tuple(sorted(files)),
            relevant_lines=tuple(relevant),
            raw_sha256=digest,
            raw_bytes=raw_bytes,
            returned_bytes=len(returned.encode("utf-8")),
        )
