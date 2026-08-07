# Research and provenance

Research snapshot: 2026-08-07. External repositories were inspected for architecture and integration behavior; **no source code was copied** into CompText Conductor Max.

| Reference | Use | License observed |
| --- | --- | --- |
| `gemini-cli-extensions/conductor` | Current plugin/track structure and compatibility target | Apache-2.0 |
| `mksglu/context-mode` | Local/sandbox processing of heavy tool output as an architecture reference | Elastic License 2.0 |
| `HoangP8/tokless` | Multi-agent/context-tool integration reference | MIT |

The Elastic-licensed `context-mode` project is deliberately treated only as an architectural research reference.

Existing CompText projects were also inspected before implementation: `comptext-context` for deterministic Top-K/context assembly/replay ideas; `comptext-codex` for compact handoff concepts; `comptext-mcp` for local deterministic MCP/security patterns; and `comptext-conductor-studio` for Conductor workflow concepts. None is used as benchmark evidence for this project.

The current Antigravity research pass found a plugin bundle built around `plugin.json`, optional `mcp_config.json`, hooks, skills, agents, and rules. This project needs no hook or extra agent in v0.1. The current MCP implementation targets the official Python SDK 2.x and is tested against the installed `mcp==2.0.0`.
