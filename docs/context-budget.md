# Context Budget Engine

Profiles provide hard output ceilings: SAFE 30,000, BALANCED 18,000, MAX 10,000 tokens. A lower call-specific budget may tighten the ceiling. Current token accounting uses the explicit `estimated_tokens` fallback unless an exact model tokenizer is configured.

## Ranking signals
The deterministic ranker considers query-token overlap, path overlap, symbol overlap, Conductor spec/plan membership, changed-file status, failing-test status, and critical current-track material. Stable ties use path and starting line.

## Priority intent
Current task and plan step are critical; relevant spec decisions, changed code, and failures are high; adjacent code is medium; historical/unrelated context is low. MAX is delta-first and checkpoint-first. Generated files and complete logs remain out of context unless a correctness-driven targeted fallback requires otherwise.

## Correctness behavior
The engine must not manufacture confidence from an undersized context. If critical content does not fit, it returns explicit omission metadata. The caller should fetch the specific file/range/hunk or choose a broader profile.
