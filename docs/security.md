# Security

## Boundary
The project is local-first: repository content is processed locally and the broker runtime has no telemetry or external-service upload path. The explicit LLM/MCP host remains responsible for whatever context it ultimately sends to its model provider.

## Path and content controls
`SecurityPolicy` resolves paths against a canonical root, rejects root escapes, skips symlinks during indexing, blocks common secret filenames, respects `.gitignore` and `.comptextignore`, rejects NUL/binary content, and applies conservative secret-content patterns. Common dependency/build/cache directories are excluded.

## Explicit local logs
`ct_result(log_path=...)` accepts an explicit file only after canonical root containment, symlink, sensitive-name, size, and binary checks. This explicit path may be ignored by Git (for example a build log); ignore status does not prevent local diagnostic reduction. Secret-shaped lines are filtered before return.

## Git subprocess
Git is invoked as an argv list with no shell interpolation and a timeout. Diff patch text is parsed locally. Generated/lock and binary patches are omitted from model-facing summaries by default.

## Limitations
Pattern-based secret detection can produce false positives and cannot prove a repository contains no secret. It is defense in depth. Run a dedicated secret/dependency/code scanner as part of repository security practice. Internal symlinks are currently skipped rather than followed, which favors safety over completeness.

## Security review checklist
- traversal and absolute outside-root paths rejected;
- `.env`, key/credential/secret filename patterns excluded;
- binary and secret-shaped content not returned;
- symlink escape test present;
- invalid MCP inputs return bounded errors;
- generated/binary diff bodies do not enter summary responses;
- no runtime telemetry/network client added.
