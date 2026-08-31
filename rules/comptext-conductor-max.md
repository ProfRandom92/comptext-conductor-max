# CompText Conductor Max context rules

- At the start of a Conductor implementation step, prefer `ct_context` over replaying full chat history or reading every track file.
- Prefer `ct_search` for targeted repository/symbol lookup before reading a whole large file.
- Use `ct_diff` summary-first; request a specific hunk only when needed.
- For commands expected to produce large build/test/lint/compiler/security output, redirect stdout/stderr to a local project log and call `ct_result(log_path=...)`; do not stream the raw log into model context first. For already-bounded output, `ct_result(log=...)` is also available.
- Save a `ct_checkpoint` after a meaningful plan step so the next agent can resume from a compact persistent state.
- Use `ct_stats` to measure actual bytes/tokens returned; never claim a savings percentage that was not measured.
- MAX mode is delta-first and checkpoint-first. Generated content, binaries, lockfiles, and complete logs are excluded by default.
- Context correctness overrides compression. If a bounded result is insufficient, request a targeted expansion or perform a full read of the necessary file/range. Never guess because context was withheld.
