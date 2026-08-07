from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from .budget import fit_text
from .models import IndexedSlice, RepositoryIndex
from .tokens import TokenCount, estimate_tokens

_TOKEN = re.compile(r"[a-z0-9]+")


def _tokens(text: str) -> set[str]:
    return set(_TOKEN.findall(text.lower().replace("_", " ").replace("-", " ")))


@dataclass(frozen=True, slots=True)
class SearchResult:
    path: str
    start_line: int
    end_line: int
    snippet: str
    score: int
    reasons: tuple[str, ...]
    token_count: TokenCount


@dataclass(frozen=True, slots=True)
class SearchResponse:
    results: tuple[SearchResult, ...]
    returned_lines: int
    returned_tokens: TokenCount
    budget_exceeded: bool
    omitted_critical: tuple[str, ...]


class Retriever:
    @staticmethod
    def _score(
        item: IndexedSlice,
        query_tokens: set[str],
        *,
        changed_files: set[str],
        failure_files: set[str],
        critical_paths: set[str],
    ) -> tuple[int, tuple[str, ...]]:
        haystack = _tokens(item.text)
        path_tokens = _tokens(str(PurePosixPath(item.path)))
        symbol_tokens = _tokens(" ".join(item.symbols))
        overlap = len(query_tokens & haystack)
        path_overlap = len(query_tokens & path_tokens)
        symbol_overlap = len(query_tokens & symbol_tokens)
        score = overlap * 10 + path_overlap * 12 + symbol_overlap * 14
        reasons: list[str] = []
        if overlap:
            reasons.append(f"query-overlap:{overlap}")
        if path_overlap:
            reasons.append(f"path-overlap:{path_overlap}")
        if symbol_overlap:
            reasons.append(f"symbol-overlap:{symbol_overlap}")
        if item.kind in {"spec", "plan"}:
            score += 8
            reasons.append(f"conductor-{item.kind}")
        if item.kind == "source":
            score += 2
        if item.path in changed_files:
            score += 25
            reasons.append("changed-file")
        if item.path in failure_files:
            score += 40
            reasons.append("failing-test")
        if item.path in critical_paths and (overlap or path_overlap or symbol_overlap or item.start_line == 1):
            score += 100
            reasons.append("critical")
        return score, tuple(reasons)

    def search(
        self,
        index: RepositoryIndex,
        query: str,
        *,
        max_results: int = 5,
        max_lines: int = 180,
        budget_tokens: int = 18_000,
        changed_files: set[str] | None = None,
        failure_files: set[str] | None = None,
        critical_paths: set[str] | None = None,
    ) -> SearchResponse:
        changed = changed_files or set()
        failures = failure_files or set()
        critical = critical_paths or set()
        query_tokens = _tokens(query)
        ranked: list[tuple[int, IndexedSlice, tuple[str, ...]]] = []
        for item in index.slices:
            score, reasons = self._score(
                item, query_tokens, changed_files=changed, failure_files=failures, critical_paths=critical
            )
            if score > 2 or "critical" in reasons:
                ranked.append((score, item, reasons))
        ranked.sort(key=lambda row: (-row[0], row[1].path, row[1].start_line))

        selected: list[SearchResult] = []
        lines_used = 0
        tokens_used = 0
        omitted_critical: list[str] = []
        for score, item, reasons in ranked:
            if len(selected) >= max(0, max_results):
                if "critical" in reasons:
                    omitted_critical.append(item.path)
                continue
            remaining_lines = max_lines - lines_used
            remaining_tokens = budget_tokens - tokens_used
            fitted = fit_text(item.text, max_lines=remaining_lines, max_tokens=remaining_tokens)
            if fitted is None:
                if "critical" in reasons:
                    omitted_critical.append(item.path)
                continue
            selected.append(
                SearchResult(
                    path=item.path,
                    start_line=item.start_line,
                    end_line=item.start_line + fitted.lines - 1,
                    snippet=fitted.text,
                    score=score,
                    reasons=reasons,
                    token_count=fitted.tokens,
                )
            )
            lines_used += fitted.lines
            tokens_used += fitted.tokens.value
        total = estimate_tokens("\n".join(item.snippet for item in selected))
        return SearchResponse(
            results=tuple(selected),
            returned_lines=lines_used,
            returned_tokens=TokenCount(tokens_used if selected else total.value, False, "estimated_tokens"),
            budget_exceeded=bool(omitted_critical),
            omitted_critical=tuple(sorted(set(omitted_critical))),
        )
