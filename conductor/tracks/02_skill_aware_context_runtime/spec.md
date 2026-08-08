# Track Spec: Skill-Aware Context Runtime (v0.3)

## Problem
Adding Agent Skills (such as `google/skills`) to AI context can introduce context bloat if entire skill bodies are injected indiscriminately.

## Solution & Architecture
Implement a Skill-Aware Context Runtime with Progressive Disclosure:
1. **L1 — Skill Metadata**: Local discovery & indexing of `name` and `description` from YAML frontmatter in `SKILL.md`.
2. **L2 — Skill Instructions**: Bounded instruction loading triggered only when relevance threshold is met or task explicitly requires it.
3. **L3 — Skill Resources**: Files in `references/`, `resources/`, `examples/`, `scripts/` accessed strictly on-demand.
4. **Deterministic Ranking & Zero-Skill Selection**: Integrated into CompText BM25 ranking. Skill-irrelevant tasks select 0 skills.
5. **Reversible References**: Stable `ctref:v1:<hash>` references for skill slices.
6. **Security & Prompt Injection Boundary**: External skills treated as untrusted data; prompt injection fixtures remain inert.
7. **Public API Compatibility**: Preserve exact 6 public MCP tools (`ct_context`, `ct_search`, `ct_diff`, `ct_result`, `ct_checkpoint`, `ct_stats`).
