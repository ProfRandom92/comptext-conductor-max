# Track Plan: Skill-Aware Context Runtime (v0.3)

## Phase 1: Skill Discovery & Progressive Disclosure Engine (TDD)
- [x] Task 1.1: Discover skills from workspace `.agents/skills/` and configured external paths.
- [x] Task 1.2: Parse YAML frontmatter (`name`, `description`) safely for L1 metadata.
- [x] Task 1.3: Implement deterministic ranking and L1/L2/L3 progressive disclosure.
- [x] Task 1.4: Implement negative selection (0 skills selected for irrelevant tasks).

## Phase 2: Retrieval Integration & Security Boundary (TDD)
- [x] Task 2.1: Integrate skill slices (`skill_metadata`, `skill_instruction`, `skill_resource`) into `ContextBroker` and `ct_search`.
- [x] Task 2.2: Implement `ctref:v1` reversible references for skill content with hash invalidation.
- [x] Task 2.3: Implement untrusted content security boundary and prompt injection regression fixture (`malicious-demo`).
- [x] Task 2.4: Update `ct_stats` to expose skill-selection telemetry.

## Phase 3: Verification & Benchmark A/B/C
- [x] Task 3.1: Quality gate checks (`pytest`, `ruff`, `mypy`, `build`, `bandit`, `pip-audit`).
- [x] Task 3.2: Controlled 3-mode benchmark (Modes A, B, C across Positive & Negative tasks).
- [x] Task 3.3: Final Validation Report.
