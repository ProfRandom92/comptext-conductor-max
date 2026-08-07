# CompText Conductor Max

Local-first Context Broker MCP companion for Google Conductor and Antigravity CLI. The design rule is simple: **compute before context**.

## Problem
Large agentic coding sessions waste model context on whole repositories, repeated specifications, complete diffs, generated files, and thousands of build-log lines. Prompt shortening alone does not solve this because the raw tool output has already entered the model context.

CompText Conductor Max performs deterministic work locally first: safe indexing, ranking, slice selection, Git-diff classification, log reduction, checkpointing, caching, and accounting. The MCP returns only the information selected for the current task.

## Architecture

```text
Antigravity CLI -> Conductor -> companion plugin -> Context Broker MCP
                                           |-> Track index
                                           |-> Repository index
                                           |-> Git diff engine
                                           |-> Result/log reducer
                                           |-> Checkpoints + hash cache
                                           `-> Context Budget Engine
```

Conductor is not forked. Its track files are detected and read without modification. The broker is local-first and the default MCP transport is stdio.

See `docs/architecture.md` for component boundaries and data flow.

## How it reduces context
The primary gain comes from selection and local computation, not from compact prose:

- repository files are indexed into bounded slices instead of returned wholesale;
- deterministic lexical/symbol/Git/Conductor signals rank candidate slices;
- `ct_diff` returns a summary and stable hunk IDs before any hunk text;
- `ct_result` extracts failures, diagnostics, test counts, and relevant files from large logs;
- checkpoints replace repeated chat-history replay for agent handoffs;
- SHA-256 keyed cache entries avoid reprocessing unchanged content;
- generated files, binaries, ignored paths, and likely secrets are excluded by default;
- hard context budgets apply after ranking and report critical omissions rather than silently guessing.

If bounded retrieval is insufficient for correctness, the rules explicitly permit targeted or full reads of the necessary file/range.

## Installation
Requires Python 3.12+ and Git.

```bash
python -m pip install .
ct-conductor doctor --root /path/to/project
```

For development:

```bash
python -m pip install -e '.[dev]'
```

The install exposes `ct-conductor` and `ct-conductor-mcp` on `PATH`.

## Antigravity setup
The companion bundle follows the current Antigravity plugin shape used during the 2026-08-07 research pass:

```text
plugin.json
mcp_config.json
rules/comptext-conductor-max.md
skills/conductor-max/SKILL.md
```

`mcp_config.json` registers a local stdio server named `comptext-conductor-max` and starts `ct-conductor-mcp`. Stage the bundle through Antigravity's plugin mechanism so these files live under the plugin directory and ensure the console script is on `PATH`.

The server uses the process working directory as project root unless `CT_CONDUCTOR_ROOT` is set. If the host launches MCP servers outside the active workspace, set that environment variable or configure an appropriate `cwd` in the local MCP configuration.

No hook is required in v0.1; avoiding a permanent hook keeps instruction overhead small.

## Conductor setup
Preferred track layout:

```text
conductor/
  tracks/
    <track>/
      spec.md
      plan.md
      metadata.json
```

The broker detects this structure, extracts the first unchecked plan item as the current step, and uses relevant specification/plan slices as high-priority context. A conservative fallback looks for equivalent `spec.md` / `plan.md` pairs beneath `conductor/`. Conductor files remain read-only.

Example:

```bash
ct-conductor context --root . --track demo --task "implement current plan step" --profile balanced
```

## MCP tools
| Tool | Purpose |
| --- | --- |
| `ct_context` | Assemble bounded task/track context from current plan/spec, source, Git changes, and local state. |
| `ct_search` | Search safe indexed repository slices with result, line, and token limits. |
| `ct_diff` | Return summary-first Git diff metadata or one requested stable hunk. |
| `ct_result` | Reduce test/build/compiler/lint/security output from bounded text or a safe local `log_path` while retaining actionable diagnostics. |
| `ct_checkpoint` | Save/load/list versioned canonical checkpoints with SHA-256 identity. |
| `ct_stats` | Report measured bytes/tokens, cache activity, retrieval counts, and avoided diff/log bytes. |

Exactly these six primary tools are exposed to keep MCP schema overhead bounded. Index/cache/benchmark/doctor operations remain CLI concerns.

## Profiles
| Profile | Hard limit | Intent |
| --- | ---: | --- |
| SAFE | 30,000 tokens | Broader adjacent context and easier expansion. |
| BALANCED | 18,000 tokens | Current task/spec/plan/changes/failures first. |
| MAX | 10,000 tokens | Delta-first and checkpoint-first; aggressive context reduction. |

A caller may request a smaller budget. A larger call-time value does not raise the selected profile's hard limit. Token values are labeled `estimated_tokens` unless a model-specific exact tokenizer is available.

## Benchmarks
The committed benchmark is **synthetic and reproducible**, not a universal savings claim. Seed `20260807` generated fixture hash `60e3a95992e3dd4786f8e858991bf8ca3cedff8831ae05ca93c42b2937c38421`. The final measured run considered **986,077 bytes / 246,520 `estimated_tokens`** in the naive full-context workflow. BALANCED returned **13,910 bytes / 3,478 `estimated_tokens`**, a measured **98.59%** token reduction with **0 missing required facts** in that fixture.

SAFE and MAX produced the same returned size in this fixture because all task-relevant facts fit comfortably below the smallest profile limit; the benchmark does not claim that the profiles are equivalent on larger relevant working sets.

Run it yourself:

```bash
ct-conductor benchmark --output benchmarks/results/latest.json --seed 20260807
```

The gate requires BALANCED or MAX to reduce delivered context by at least 50% while retaining every manifest-required fact. See `docs/benchmark.md` and the committed JSON report for exact measurements.

## Security
Default behavior is local-only. The broker:

- resolves paths against a canonical project root and blocks escapes;
- skips symlinks during indexing and rejects external symlink reads;
- respects `.gitignore` and `.comptextignore`;
- excludes common secret filenames and directories;
- rejects binary/NUL-containing data before decoding;
- applies conservative secret-content patterns before returning text;
- invokes Git with argument vectors, `shell=False`, bounded output paths, and timeouts;
- has no telemetry path and no broker runtime network call.

Secret detection is defense in depth, not a replacement for dedicated repository secret scanning. See `docs/security.md` and the final evidence in `docs/security-review.md`.

## Troubleshooting
**`ct_diff` reports unavailable:** confirm the project is a Git worktree and `git` is on `PATH`. Other retrieval remains usable without Git.

**`budget_exceeded` / `omitted_critical`:** increase the budget within the profile ceiling or fetch the named target explicitly. Do not infer the missing fact.

**Large command output:** redirect the command to a local project log (for example `pytest -q > test-output.log 2>&1`) and call `ct_result(log_path="test-output.log")`. This preserves the compute-before-context benefit because the raw log does not need to be streamed into the model first.

**MCP starts in the wrong directory:** set `CT_CONDUCTOR_ROOT` to the active project root or configure MCP `cwd` for that workspace.

**A file is missing from search:** check `.gitignore`, `.comptextignore`, secret/binary classification, and whether it is generated content. Use normal reads only after confirming the omission is intentional and safe.

## Development
Primary checks:

```bash
pytest -q
ruff check .
mypy src
python -m build
ct-conductor benchmark --output benchmarks/results/latest.json --seed 20260807
```

The implementation plan and design record are under `docs/superpowers/`; final review evidence is in `docs/code-review.md` and `docs/security-review.md`. The quality standard is evidence before success claims: tests, static checks, MCP client smoke, integration fixtures, security review, and a fresh benchmark must all run on the final feature commit.

## License
CompText Conductor Max is released under the MIT License. External projects listed in `docs/research.md` were used as documentation/architecture references only; their licenses remain their own.
