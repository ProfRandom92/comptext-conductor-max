# CompText Conductor Max Context Broker MCP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a production-oriented local Context Broker MCP + Antigravity/Conductor companion plugin that measurably reduces model-delivered context without losing benchmark-required facts.

**Architecture:** A deterministic Python 3.12+ core indexes safe repository/Conductor artifacts, ranks bounded slices, summarizes Git diffs and logs locally, persists hash-addressed checkpoints/caches, and exposes only six primary MCP tools. Antigravity integration remains a companion plugin using the current `plugin.json` + `mcp_config.json` packaging, while Conductor itself remains untouched.

**Tech Stack:** Python 3.12+, Pydantic v2, Typer, Rich, official MCP Python SDK v2/FastMCP, pathspec, pytest, pytest-asyncio, Ruff, MyPy.

## Global Constraints
- Private repository: `ProfRandom92/comptext-conductor-max`; default branch `main`.
- Productive changes occur on `feature/context-broker-mcp`; no force push and no direct feature development on `main`.
- No embeddings/vector database in v0.1.
- No external repository-content transmission or telemetry from broker code.
- Six primary MCP tools: `ct_context`, `ct_search`, `ct_diff`, `ct_result`, `ct_checkpoint`, `ct_stats`.
- SAFE/BALANCED/MAX hard limits: 30,000 / 18,000 / 10,000 tokens.
- Context correctness precedes maximal reduction; never invent benchmark values.
- Respect `.gitignore`, `.comptextignore`, secret patterns, binary detection, path boundaries, and symlink constraints.
- Benchmark target: at least 50% lower model-delivered context in BALANCED or MAX with all required benchmark facts retained.

---

### Task 1: Project skeleton, contracts, and configuration

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `.comptextignore`, `src/comptext_conductor_max/__init__.py`
- Create: `src/comptext_conductor_max/models.py`, `config.py`, `tokens.py`
- Test: `tests/test_config_tokens.py`

**Interfaces:**
- `ProfileName = Literal["safe", "balanced", "max"]`
- `BudgetProfile(name, hard_limit, priorities)`
- `TokenCount(count: int, exact: bool, method: str)`
- `count_tokens(text: str) -> TokenCount`

- [ ] Write failing tests asserting the three exact profile limits, deterministic config serialization, UTF-8 byte accounting, and explicit `exact=False` fallback token labeling.
- [ ] Run `pytest tests/test_config_tokens.py -q` and confirm failure before implementation.
- [ ] Implement Pydantic contracts/config plus tokenizer adapter that tries an installed supported tokenizer and otherwise uses a documented byte/character estimate; never label estimates as exact.
- [ ] Run the test file and Ruff on the new modules; require pass.
- [ ] Commit `feat: add core contracts and budget profiles`.

### Task 2: Security boundary and ignore semantics

**Files:**
- Create: `src/comptext_conductor_max/security.py`
- Test: `tests/test_security.py`
- Fixture: `tests/fixtures/security_repo/*`

**Interfaces:**
- `SecurityPolicy.from_root(root: Path) -> SecurityPolicy`
- `is_path_allowed(path: Path) -> bool`
- `safe_text(path: Path, max_bytes: int) -> str | None`
- `contains_secret(text: str) -> bool`

- [ ] Add failing tests for `.env`, `.env.*`, PEM/key/credentials/secrets exclusions, `.gitignore`, `.comptextignore`, `../` traversal, absolute outside-root paths, external symlinks, binary NUL data, and secret-shaped assignments.
- [ ] Run `pytest tests/test_security.py -q`; verify the expected failures.
- [ ] Implement canonical-path containment, pathspec-based ignore loading, deny patterns, no-follow indexing, conservative secret regexes, and binary detection before text decode.
- [ ] Re-run security tests plus `ruff check src tests`.
- [ ] Commit `feat: enforce local indexing security boundary`.

### Task 3: Hash cache and safe repository/Conductor index

**Files:**
- Create: `src/comptext_conductor_max/cache.py`, `indexer.py`, `conductor.py`
- Test: `tests/test_cache_indexer.py`, `tests/test_conductor.py`
- Fixtures: `tests/fixtures/conductor_repo/conductor/tracks/demo/{spec.md,plan.md,metadata.json}`

**Interfaces:**
- `ContentCache(root: Path)` with `get`, `put`, `invalidate`, `status`, `clear`
- `RepositoryIndexer(root, policy, cache).build() -> RepositoryIndex`
- `detect_conductor(root) -> ConductorState`
- `ConductorState.current_step(track: str) -> PlanStep | None`

- [ ] Write failing tests for lexical/stable file ordering, SHA-256 reuse, cache hit/miss accounting, single-file invalidation, generated/dependency exclusion, official track detection, fallback layout detection, and plan-step parsing.
- [ ] Run the two test files and record failure state.
- [ ] Implement versioned JSON cache records keyed by normalized content hash; index line windows and symbols without returning whole files; implement official track detector and read-only fallback.
- [ ] Re-run tests, Ruff, and MyPy for these modules.
- [ ] Commit `feat: add hash cache and conductor-aware index`.

### Task 4: Deterministic retrieval and Context Budget Engine

**Files:**
- Create: `src/comptext_conductor_max/retrieval.py`, `budget.py`
- Test: `tests/test_retrieval_budget.py`

**Interfaces:**
- `search(index, query, max_results, max_lines) -> SearchResponse`
- `score_candidate(candidate, RetrievalQuery) -> ScoredSlice`
- `select_with_budget(candidates, profile, hard_limit) -> BudgetSelection`

- [ ] Add failing tests proving relevant file/symbol selection, irrelevant exclusion, Top-K, stable tie-breaking, max-line bounds, changed-file/failing-test boosts, and strict SAFE/BALANCED/MAX hard limits.
- [ ] Add a test where all critical facts cannot fit and assert structured `budget_exceeded` instead of silent omission.
- [ ] Run the focused tests to failure.
- [ ] Implement integer scoring with explainable reasons and deterministic greedy selection ordered by priority, score, path, line.
- [ ] Run focused tests + full suite + static checks.
- [ ] Commit `feat: add deterministic retrieval and context budgets`.

### Task 5: Git diff summary-first engine

**Files:**
- Create: `src/comptext_conductor_max/gitops.py`
- Test: `tests/test_gitops.py`

**Interfaces:**
- `summarize_diff(root, base=None, head=None) -> DiffSummary`
- `get_hunk(root, hunk_id: str) -> DiffHunk`

- [ ] Build a temporary Git fixture and failing tests for changed-file counts, additions/deletions, test/source classification, generated/lockfile omission, binary omission, stable hunk IDs, and targeted hunk retrieval.
- [ ] Run `pytest tests/test_gitops.py -q` and verify failure.
- [ ] Implement subprocess calls as argv lists with `shell=False`, bounded output, parse unified diff locally, cache diff hash, and never return full generated/lock/binary patches by default.
- [ ] Re-run tests and security static checks.
- [ ] Commit `feat: summarize git diffs before context`.

### Task 6: Build/test/log result reducer

**Files:**
- Create: `src/comptext_conductor_max/results.py`
- Test: `tests/test_results.py`
- Fixtures: `tests/fixtures/logs/{pytest-large.log,compiler-large.log,lint-large.log}`

**Interfaces:**
- `analyze_result(text_or_path, exit_code=None, max_lines=...) -> ResultSummary`

- [ ] Add failing tests that preserve exit code, pytest failed test identity, expected/actual assertions, compiler file/line diagnostics, linter errors, and relevant surrounding lines while discarding thousands of noise lines.
- [ ] Assert secret-like log lines are redacted/excluded and oversized outputs remain bounded.
- [ ] Run focused tests to failure.
- [ ] Implement deterministic parser stages, diagnostics normalization, file-hint extraction, local raw-log hash/reference, and stats for avoided bytes.
- [ ] Re-run focused/full tests and checks.
- [ ] Commit `feat: reduce build and test output locally`.

### Task 7: Checkpoints, reversible handoff compression, and stats

**Files:**
- Create: `src/comptext_conductor_max/checkpoints.py`, `handoff.py`, `stats.py`
- Test: `tests/test_checkpoints_handoff_stats.py`

**Interfaces:**
- `CheckpointStore.save(checkpoint) -> StoredCheckpoint`
- `CheckpointStore.load(hash_or_name) -> Checkpoint`
- `encode_handoff(checkpoint) -> str`; `decode_handoff(text) -> Handoff`
- `StatsLedger.record(event)`; `StatsLedger.snapshot() -> StatsSnapshot`

- [ ] Add failing tests for canonical JSON SHA-256 stability, readable Markdown sidecar, save/load, changed checkpoint hash, strict grammar rejection, encode/decode round trip, and exact raw/returned/cache/read/diff/log counters.
- [ ] Run focused tests to failure.
- [ ] Implement canonical serialization (`sort_keys`, stable separators), atomic writes, version field, strict regex/parser for the compact handoff, and append-only local stats ledger.
- [ ] Re-run tests + Ruff + MyPy.
- [ ] Commit `feat: add checkpoints handoffs and measured stats`.

### Task 8: Broker orchestration and six MCP tools

**Files:**
- Create: `src/comptext_conductor_max/broker.py`, `mcp_server.py`
- Test: `tests/test_broker.py`, `tests/test_mcp.py`

**Interfaces:**
- `ContextBroker.context(track, task, budget, profile) -> ContextResponse`
- `ContextBroker.search(...)`, `.diff(...)`, `.result(...)`, `.checkpoint(...)`, `.stats()`
- MCP exposes exactly `ct_context`, `ct_search`, `ct_diff`, `ct_result`, `ct_checkpoint`, `ct_stats`.

- [ ] Add failing broker tests covering current track/plan/spec/decisions/changed files/failures/checkpoints and ensuring responses do not contain full unrelated files.
- [ ] Add MCP SDK client tests for initialize, `tools/list`, each `tools/call`, invalid arguments, path-policy errors, and serialized response hard budget.
- [ ] Run focused tests and confirm red state.
- [ ] Implement orchestration and FastMCP stdio server with concise schemas/descriptions; keep index/doctor/cache/benchmark out of the MCP schema.
- [ ] Re-run focused/full tests and inspect `tools/list` schema size.
- [ ] Commit `feat: expose six context broker MCP tools`.

### Task 9: Local CLI and Antigravity companion bundle

**Files:**
- Create: `src/comptext_conductor_max/cli.py`
- Create: `plugin.json`, `mcp_config.json`, `rules/comptext-conductor-max.md`, `skills/conductor-max/SKILL.md`
- Test: `tests/test_cli_plugin.py`

**Interfaces:**
- Console scripts: `ct-conductor`, `ct-conductor-mcp`
- Commands: `doctor`, `index`, `context`, `stats`, `cache status`, `cache clear`, `benchmark`.

- [ ] Add failing CLI smoke tests and JSON validation tests for `plugin.json`/`mcp_config.json`; assert the plugin bundle uses current Antigravity filenames and the skill/rule remain compact.
- [ ] Run focused tests to failure.
- [ ] Implement Typer commands and plugin files. Rules must prefer `ct_*` for large reads/logs/diffs but explicitly allow targeted/full reads when correctness requires them.
- [ ] Run CLI smoke tests, `ct-conductor doctor`, and full checks.
- [ ] Commit `feat: add antigravity companion plugin and cli`.

### Task 10: Reproducible benchmark and evidence

**Files:**
- Create: `benchmarks/generate_fixture.py`, `benchmarks/run_benchmark.py`
- Create: `benchmarks/README.md`, `benchmarks/results/.gitkeep`
- Test: `tests/test_benchmark.py`

**Interfaces:**
- `generate_fixture(path, seed=...) -> BenchmarkManifest`
- `run_benchmark(path) -> BenchmarkReport`

- [ ] Add failing benchmark tests for deterministic fixture hashes, known required facts, four workflows, byte/token metrics, fact-retention checks, missing-fact reporting, and reduction calculation from measured values only.
- [ ] Run focused tests to failure.
- [ ] Implement generator with large source/spec/plan/diff/log corpus and a manifest of required facts; implement naive/SAFE/BALANCED/MAX runners using the real broker.
- [ ] Execute `ct-conductor benchmark`; write the actual report to `benchmarks/results/latest.json`. Fail the command if no BALANCED/MAX run achieves >=50% reduction with zero missing facts.
- [ ] Re-run benchmark once to confirm deterministic facts and stable fixture hash; latency may vary and must be reported as observed.
- [ ] Commit `test: add reproducible context reduction benchmark`.

### Task 11: Documentation and integration guide

**Files:**
- Replace: `README.md`
- Create: `docs/architecture.md`, `docs/context-budget.md`, `docs/benchmark.md`, `docs/security.md`, `docs/conductor-integration.md`, `AGENTS.md`, `LICENSE`

**Interfaces:** documentation must match actual commands/schema/results.

- [ ] Write README sections Problem, Architecture, How it reduces context, Installation, Antigravity setup, Conductor setup, MCP tools, Profiles, Benchmarks, Security, Troubleshooting, Development, License.
- [ ] Document only measured `latest.json` benchmark values; label exact versus estimated token counts accurately.
- [ ] Add architecture/security/budget/Conductor docs and compact AGENTS.md completion rules.
- [ ] Run Markdown/link/path checks available locally and grep for forbidden unsupported savings claims (`94%`, `98%`) outside clearly attributed research notes.
- [ ] Commit `docs: document conductor max and measured benchmark`.

### Task 12: Quality gate, reviews, PR, and finish decision

**Files:** only fixes required by review/verification.

**Interfaces:** final branch must satisfy Definition of Done before any merge decision.

- [ ] Run `pytest -q`, `ruff check .`, `mypy src`, packaging build/import checks, and CLI doctor.
- [ ] Start/initialize the MCP through the SDK client smoke test and verify exactly six tools plus invalid-call handling.
- [ ] Simulate the `conductor/tracks/demo` workflow through `ct_context`, checkpoint, diff, result, and stats.
- [ ] Validate Antigravity `plugin.json` and `mcp_config.json` against current documented packaging assumptions and record any host-level limitation that cannot be exercised in this environment.
- [ ] Run the reproducible benchmark on the final code and update evidence if code changes affected results.
- [ ] Invoke code review and security review skills/tools; fix validated findings and re-run affected gates.
- [ ] Compare `main...feature/context-broker-mcp`, confirm no unrelated/generated/secret files, and create a pull request rather than force-pushing or developing on main.
- [ ] Apply `verification-before-completion`; report repository URL, branch, final commit, tests/lint/security/benchmark, integrations, limitations, and recommended next step. Do not merge unless the finishing workflow and user intent permit it.
