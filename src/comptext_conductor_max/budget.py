from __future__ import annotations

from dataclasses import dataclass

from .tokens import TokenCount, estimate_tokens


@dataclass(frozen=True, slots=True)
class BudgetedText:
    text: str
    lines: int
    tokens: TokenCount
    truncated: bool


def fit_text(text: str, *, max_lines: int, max_tokens: int) -> BudgetedText | None:
    if max_lines <= 0 or max_tokens <= 0:
        return None
    source_lines = text.splitlines()
    if not source_lines and text:
        source_lines = [text]
    selected = source_lines[:max_lines]
    while selected:
        candidate = "\n".join(selected)
        count = estimate_tokens(candidate)
        if count.value <= max_tokens:
            return BudgetedText(candidate, len(selected), count, len(selected) < len(source_lines))
        selected.pop()
    return None
