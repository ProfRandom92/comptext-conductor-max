# v0.3.1 stabilization

Stabilize the v0.3 skill-aware runtime without changing the six-tool public MCP surface.

## Scope

- make all published package/server/build versions `0.3.1` and verify them;
- make authenticated AGY A/B evidence fail closed and comparable;
- correct token savings semantics;
- preserve progressive disclosure while improving deterministic skill routing;
- cover the v0.3 branch line in CI.

## Non-goals

- no new MCP tools, embeddings, vector stores, remote retrieval, real AGY execution in CI,
  PR #1 changes, or merge.
