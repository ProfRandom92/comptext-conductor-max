# CompText Conductor Max — Context Broker Design

## Status
Approved by the user's autonomous build brief on 2026-08-07. This document records the implementation design chosen after inspecting the required CompText repositories and current Conductor/Antigravity/MCP documentation.

## Goal
Build a local-first companion plugin plus MCP server for Antigravity CLI and Google Conductor that reduces actual model-context transfer by performing deterministic repository, track, diff, log, and checkpoint processing before MCP responses are produced.

Core rule: **compute before context**. Context correctness always wins over maximal reduction.

## Research baseline

### Existing CompText projects
- `ProfRandom92/comptext-context`: reuse deterministic keyword retrieval, Top-K selection, stable context assembly, SHA-256/replay-trace concepts.
- `ProfRandom92/comptext-codex`: reuse only the ideas of compact handoffs, strict batch/notation parsing, and explicit optimization heuristics. Historical blanket savings claims are not evidence for this project.
- `ProfRandom92/comptext-mcp`: reuse the ideas of local deterministic MCP operations, lexical ordering, SHA-256 manifests, path policy, and secret exclusion. Do not copy unrelated Rust/OpenCode-specific behavior.
- `ProfRandom92/comptext-conductor-studio`: reference only for persistent agent/workflow/ledger concepts; do not modify it.

### Current external integration baseline
- Antigravity CLI plugins are namespaced bundles with `plugin.json` and optional `mcp_config.json`, `hooks.json`, `skills/`, `agents/`, and `rules/` under the staged plugin directory.
- Current Conductor is a separate agent plugin; its manifest is intentionally minimal. A track contains `spec.md`, `plan.md`, and `metadata.json`; project context also uses Conductor-managed Markdown files. The companion must detect these artifacts rather than fork Conductor.
- MCP Python SDK v2 is the current stable line. The implementation will target the official Python MCP SDK and its FastMCP server interface, using stdio as the primary local transport.
- `mksglu/context-mode` validates the architecture pattern of sandboxing/locally processing heavy tool output before returning a compact result.
- `HoangP8/tokless` is treated as an integration/reference aggregator, not as an implementation dependency.

## Chosen architecture

### Alternatives considered
1. **Prompt compressor only** — rejected: cheap to build but does not prevent raw repository/log/diff data from entering model context.
2. **Vector/embedding context service** — rejected for v0.1: adds model/network/dependency complexity and nondeterminism without proven benefit for the target workload.
3. **Deterministic local context broker (chosen)** — indexes safe text locally, ranks slices using reproducible lexical/symbol/Git/track signals, summarizes large diffs/logs locally, persists checkpoints and stats, and returns a bounded context pack.

### Component boundaries

`src/comptext_conductor_max/`:
- `config.py`: profiles and project configuration.
- `security.py`: ignore handling, secret-path policy, secret-content detection, binary/symlink/path-boundary checks.
- `tokens.py`: exact tokenizer adapter when available; explicit estimated-token fallback.
- `models.py`: Pydantic contracts shared by CLI/MCP/core.
- `cache.py`: content-hash cache with versioned records and invalidation.
- `indexer.py`: safe repository and Conductor-track indexing.
- `retrieval.py`: deterministic ranking and bounded code/spec slice selection.
- `conductor.py`: official/fallback track detection and current-plan-step extraction.
- `gitops.py`: Git-aware changed-file metadata, summary-first diffs, hunk retrieval.
- `results.py`: test/build/lint/compiler/security-log parsing and noise reduction.
- `checkpoints.py`: canonical human/machine-readable checkpoint storage and hashes.
- `handoff.py`: strict reversible CompText handoff codec; never the sole persisted form.
- `budget.py`: SAFE/BALANCED/MAX scoring and hard response budgets.
- `stats.py`: raw/returned bytes/tokens, reads, cache, diff/log avoidance, retrieval counts.
- `broker.py`: orchestrates context assembly.
- `mcp_server.py`: six primary MCP tools only.
- `cli.py`: local Typer interface.

### Six MCP tools
- `ct_context`: assemble minimal context for task/track/profile/budget.
- `ct_search`: bounded search over indexed safe slices.
- `ct_diff`: summary-first diff; optional hunk retrieval by stable hunk id.
- `ct_result`: locally parse a log file or supplied bounded text and return failures/diagnostics.
- `ct_checkpoint`: save/load/list versioned canonical checkpoints.
- `ct_stats`: return measured session/project reduction metrics.

No additional primary tool will be added unless required by the MCP SDK. Doctor/index/cache/benchmark remain CLI commands to avoid schema bloat.

## Retrieval model

Each candidate slice receives an integer score derived from deterministic signals:
- exact task/plan identifier match
- query token overlap
- symbol/file-name match
- current track/spec/plan membership
- changed-file status
- failing-test file hint
- adjacency to a selected symbol/hunk
- checkpoint recency relevance

Tie-breakers are stable: score descending, path ascending, line start ascending. No embedding service is required.

Slices carry source path, line range, content hash, source kind, score reasons, and token cost. The budget engine selects critical material first, then greedily fills the remaining hard limit while reserving a small safety margin for response framing.

## Profiles
- SAFE: hard limit 30,000 tokens; broader adjacent context and fallback expansion.
- BALANCED: hard limit 18,000 tokens; current task/spec/diff/failures prioritized.
- MAX: hard limit 10,000 tokens; delta-first, checkpoint-first, no full files/logs unless targeted fallback proves necessary.

A caller-supplied lower budget overrides a profile. A higher budget may not exceed a configured global safety ceiling unless explicitly changed in project config.

## Security
- Resolve all paths against a canonical project root; reject traversal and escapes.
- Do not follow symlinks outside the project root. Internal symlinks are skipped by default during indexing.
- Respect `.gitignore` and `.comptextignore`.
- Always exclude `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa`, `id_ed25519`, `credentials*`, `secrets*`, VCS metadata, caches, build output, and common dependency directories.
- Detect likely secrets in content using conservative patterns (private-key blocks, common API/token assignments, GitHub/OpenAI-like token shapes). A matching slice is not indexed or returned.
- Binary files are identified before decoding and skipped.
- No telemetry and no external network calls in broker/runtime code.

## Caching
Index/cache keys use SHA-256 over normalized content plus schema/indexer version. Derived entries store dependencies; a changed file hash invalidates only affected slices/results. Track state, diffs, logs, and checkpoints have independent hashes.

## Checkpoints and handoffs
A checkpoint persists canonical JSON plus readable Markdown. The checkpoint hash is SHA-256 over canonical JSON excluding the hash field itself. Handoff compression may emit forms such as `H:MAP3.2;S:DONE;...`, but the parser uses a fixed grammar and the canonical checkpoint remains the source of truth.

## Antigravity companion packaging
Root plugin bundle:
- `plugin.json`
- `mcp_config.json`
- `rules/comptext-conductor-max.md`
- `skills/conductor-max/SKILL.md`

No hook is required for v0.1. Avoiding hooks keeps behavior explicit and avoids permanent context/system-instruction overhead. The MCP config starts the local `ct-conductor-mcp` stdio command.

## Conductor compatibility
Preferred detection:
- `conductor/tracks/<track>/spec.md`
- `conductor/tracks/<track>/plan.md`
- `conductor/tracks/<track>/metadata.json`
- project-level Conductor Markdown/index artifacts when present.

Fallback detection accepts equivalent `spec.md` / `plan.md` pairs beneath a `conductor/` tree and reports the detected layout. Conductor files are read-only unless a user explicitly asks another tool to modify them; this project never silently edits them.

## Benchmark design
Generate a deterministic synthetic repository containing many source files, one large spec, one large plan, a large Git diff, a large test log, and a known set of required facts. Run four workflows:
- naive full-context
- SAFE
- BALANCED
- MAX

Measure raw bytes, returned bytes, actual tokens when tokenizer support is installed otherwise `estimated_tokens`, required-fact retention, missing facts, tool operations, local latency, and context reduction. Passing target: BALANCED or MAX returns at least 50% less context while retaining every required benchmark fact. Results are generated by the benchmark command and checked into `benchmarks/results/latest.json` and docs only after an actual run.

## Error/fallback behavior
- If an index is stale, rebuild affected files before serving results.
- If a budget cannot hold all critical facts, return an explicit `budget_exceeded` signal with omitted critical item metadata rather than silently dropping it.
- If retrieval confidence is insufficient, expose targeted expansion hints (specific file/range/hunk) rather than a full repository dump.
- If Git is unavailable, repository/track retrieval still works but `ct_diff` returns a structured unavailable error.
- If exact tokenization is unavailable, all token metrics are labeled `estimated_tokens`.

## Testing strategy
TDD at module boundaries, including retrieval, budgets, diff summaries/hunks, log failure retention, checkpoint hashes, cache invalidation, security/path/symlinkbinary behavior, MCP initialize/list/call, hard output budgets, Conductor fixtures, CLI smoke tests, and deterministic benchmark assertions.

## Completion gate
No success claim until tests, Ruff, MyPy, local MCP smoke/SDK client test, Conductor fixture workflow, Antigravity config validation, security tests/review, code review, and the real benchmark have run on the final feature commit.
