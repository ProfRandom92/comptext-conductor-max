# AGENTS.md

## Mission
Build and maintain a local-first context broker for Conductor/Antigravity that reduces redundant model context by computing before context.

## Architecture
Keep repository/Conductor indexing, Git diff analysis, result reduction, checkpointing, caching, budgets, and statistics in `src/comptext_conductor_max/`. Expose exactly six primary MCP tools: `ct_context`, `ct_search`, `ct_diff`, `ct_result`, `ct_checkpoint`, `ct_stats`. Conductor is a read-only upstream integration.

## Security rules
Never index or return known secret paths, ignored content, binary data, traversal targets, or unsafe symlinks. Do not introduce telemetry or external repository-content transmission. Use subprocess argument vectors rather than shell command construction.

## Context rules
**Context correctness** takes priority over maximum compression. Never silently omit a critical fact. Return an explicit omission/budget signal and allow targeted/full fallback reads when required. Do not add embeddings or a vector database without measured benefit.

## Test commands
```bash
pytest -q
ruff check .
mypy src
python -m build
ct-conductor benchmark --output benchmarks/results/latest.json --seed 20260807
```

## Completion standard
Do not invent or extrapolate benchmark savings. Only publish values from a freshly executed report and label estimates as `estimated_tokens`. Before declaring completion, run tests, lint, type checks, package build, MCP client smoke, Conductor fixture workflow, Antigravity config validation, security/code review, and the benchmark on the final code.
