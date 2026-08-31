---
name: conductor-max
description: Use CompText Conductor Max to minimize redundant context while implementing Conductor tracks.
---

# Conductor Max

Use the local Context Broker when a Conductor task involves a medium/large repository, long plan/spec, large diff, build/test output, or agent handoff. The broker computes locally before returning bounded MCP context.

## Workflow
1. Start a new implementation step with `ct_context(track, task, profile)`.
2. Use `ct_search` for a symbol, behavior, file, or small adjacent slice.
3. Use `ct_diff` before asking for a complete diff; fetch an individual hunk only if the summary says it matters.
4. For expected large test/build/lint/compiler/security output, redirect the command to a local log file and call `ct_result(log_path=...)` so raw output never enters model context. Use `ct_result(log=...)` only for already-bounded text.
5. After a meaningful completed step, save `ct_checkpoint`.
6. Check `ct_stats` when evaluating context reduction.

## Profiles
- **SAFE** — 30,000-token hard limit; broadest adjacent context and easiest fallback expansion.
- **BALANCED** — 18,000-token hard limit; prioritizes current task, spec/plan, changed code, failures, then adjacency.
- **MAX** — 10,000-token hard limit; delta-first, checkpoint-first, no full logs/generated files by default.

Token counts are reported as `estimated_tokens` unless an exact model-specific tokenizer is configured. Do not describe estimates as exact.

## Checkpoints and handoffs
The canonical checkpoint is versioned JSON with a SHA-256 hash and human-readable Markdown sidecar. Compact handoffs are strictly reversible convenience messages; they are never the only persisted state.

## Debugging / fallback
If `budget_exceeded` or `omitted_critical` is returned, expand the specific missing file/range/hunk. If Git is unavailable, repository/Conductor retrieval still works while `ct_diff` reports unavailable. If broker retrieval cannot establish correctness, use a normal targeted or full read of the required source. Correctness always wins over token reduction.

## Security
The broker stays local, respects `.gitignore` and `.comptextignore`, blocks common secret paths/content, path traversal, unsafe symlinks, and binary text reads. Do not disable these protections merely to gain more context.
