# Architecture

## Design principle
CompText Conductor Max implements **compute before context**: expensive or voluminous repository/tool data is processed in the local Python process before an MCP response is serialized.

## Data flow
1. `SecurityPolicy` establishes the canonical project boundary, ignore rules, secret filters, binary rules, and symlink policy.
2. `RepositoryIndexer` walks safe files in stable lexical order, hashes content, extracts bounded line windows/symbol hints, and reuses `ContentCache` entries.
3. `conductor.py` detects the current read-only track and first unchecked plan step.
4. `Retriever` combines query, symbol/path overlap, Conductor kind, changed-file, failing-test, and critical signals into integer scores with deterministic tie-breaking.
5. `budget.py` admits slices only inside the selected hard budget. Critical omissions are surfaced.
6. `GitDiffEngine` parses Git output locally, classifies source/test/generated/binary changes, and emits stable hunk IDs. Raw hunk text is returned only for a requested hunk.
7. `ResultAnalyzer` extracts failures/diagnostics/test counts/files from large logs and tracks avoided bytes. `ct_result(log_path=...)` resolves an explicit local file inside the project boundary, allowing command output to be processed without first entering model context.
8. `CheckpointStore`, `handoff.py`, and `StatsLedger` persist reproducible state and measurements.
9. `ContextBroker` composes these units; `mcp_server.py` exposes only the six primary tools.

## Determinism
Retrieval uses integer scoring and stable `(-score, path, line)` ordering. Checkpoints and cache identities use SHA-256 over canonicalized content. Compact handoffs have a fixed field grammar and are never the only persisted form.

## Failure semantics
Stale content is keyed by content hash and is recomputed when the hash changes. A budget that cannot accommodate a critical slice produces `budget_exceeded`/`omitted_critical`. Git unavailability disables diff operations without disabling repository/track retrieval.

## Non-goals for v0.1
No Conductor fork, hosted LLM layer, vector database, embedding service, telemetry service, or automatic modification of Conductor track files.
