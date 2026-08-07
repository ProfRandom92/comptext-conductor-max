# Code review record

Review date: 2026-08-07. Scope: complete `main...feature/context-broker-mcp` implementation diff plus post-review regression tests.

## Review status
A local source-diff review was completed against the project requirements. CodeRabbit CLI 0.7.2 was installed and a review was attempted, but the sandbox had no authenticated CodeRabbit session and the browser callback could not be completed within the execution environment. **No CodeRabbit result is claimed.** The separate isolated reviewer helper also returned no usable payload and is not counted as a review result.

## Findings fixed
1. **Checkpoint path traversal** — raw track names could have influenced checkpoint store paths. Fixed with strict track-slug validation, canonical containment defense, strict checkpoint-hash validation, and regression tests.
2. **Ambiguous compact handoff file list** — comma-delimited filenames were not reversible when a filename contained a comma. Fixed by URL-encoding a canonical JSON string-list and testing round-trip behavior.
3. **Untrusted MCP output parameters** — caller-provided search/result/hunk limits could be made arbitrarily large. Fixed with server-side clamps and a bounded hunk response.
4. **Large-log workflow still required raw text input** — added `ct_result(log_path=...)` with project-root, symlink, sensitive-path, size, and binary checks so large command output can remain local.
5. **Checkpoint responses exposed local absolute storage paths** — MCP save/list responses now expose hashes/state rather than absolute `.comptext` paths.
6. **Read counters were not wired to actual model-facing slices** — `partial_reads` now records selected repository slices; full-file model reads remain zero by design.

## Regression evidence
The review fixes are covered by dedicated tests for traversal rejection, comma-containing filenames, safe local log paths, MCP argument clamps, bounded hunks, non-disclosure of checkpoint paths, partial-read stats, and MAX hard-budget stress. The full post-review suite passed before final benchmark execution.

## Residual limitations
- Token counts use `estimated_tokens` unless an exact model tokenizer is configured.
- Antigravity host behavior determines whether the MCP working directory equals the active project; `CT_CONDUCTOR_ROOT`/`cwd` is the documented fallback.
- The v0.1 indexer locally processes up to its configured per-file text cap; unusually large single source files may require targeted normal reads.
- No CodeRabbit verdict is available until an authenticated CodeRabbit CLI/GitHub integration is present.
