from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TokenCount:
    value: int
    exact: bool
    metric: str


def estimate_tokens(text: str) -> TokenCount:
    # No model-specific tokenizer is assumed. The explicit estimate avoids false precision.
    encoded = text.encode("utf-8")
    return TokenCount(value=max(1, math.ceil(len(encoded) / 4)) if text else 0, exact=False, metric="estimated_tokens")
