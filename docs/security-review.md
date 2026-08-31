# Security review record

Review date: 2026-08-07. Scope: broker/runtime source, MCP input boundaries, path handling, local log processing, subprocess use, runtime dependency graph, and security regression tests.

## Automated evidence
- **Bandit:** 0 High, 0 Medium, 14 Low findings over 1,411 LOC.
- Low findings were reviewed: subprocess import/calls use fixed `git` argv with `shell=False` and timeouts; the benchmark's `random.Random` is intentionally deterministic and non-cryptographic; two password findings are false positives on the literal metric name `estimated_tokens`.
- **pip-audit:** a clean isolated venv containing this package and its resolved runtime dependencies reported **no known vulnerabilities** after upgrading the venv bootstrap `pip`; the unpublished local package itself is correctly skipped as not present on PyPI.
- Security regression tests cover `.env`/secret paths, ignored paths, traversal, external symlinks, binary data, secret-shaped content, checkpoint-store traversal, explicit log-path escape, and bounded MCP errors.

## Security properties verified
- Canonical root containment on repository and explicit-log paths.
- Secret filename/content filters and `.gitignore` / `.comptextignore` for indexing.
- Symlink and binary protections.
- Checkpoint track and hash validation before filesystem access.
- Generated/lock and binary diff bodies omitted from model-facing summaries.
- Git subprocess invocations are argument-vector based; no shell interpolation.
- Broker runtime has no telemetry or repository-upload client.
- Explicit local logs can be reduced without entering model context as raw output.

## Scanner interpretation
Bandit's non-zero process exit is caused solely by Low findings; it is not reported as a zero-finding scan. The accepted Low items are intentional/false-positive patterns with compensating tests and constrained inputs.
