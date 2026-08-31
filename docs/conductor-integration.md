# Conductor and Antigravity integration

## Conductor
The preferred layout observed in the current Conductor project is `conductor/tracks/<track>/spec.md`, `plan.md`, and `metadata.json`. CompText Conductor Max reads these files and derives the first unchecked plan item as the active step. It never updates them. A fallback detector accepts equivalent spec/plan pairs under `conductor/` and reports the detected state.

## Antigravity
The current companion package uses `plugin.json`, `mcp_config.json`, `rules/`, and `skills/`. `mcp_config.json` registers `ct-conductor-mcp` as a local stdio MCP server. No hook is required in v0.1.

The rules guide the host toward `ct_context` at a new plan step, `ct_search` instead of broad file reads, `ct_diff` before raw diff retrieval, and `ct_checkpoint` after meaningful progress. For commands expected to emit large output, they instruct the agent to redirect output to a local project file and use `ct_result(log_path=...)` before any raw log reaches model context. They explicitly permit targeted/full reads where correctness requires more information.

## Project-root resolution
The MCP server defaults to its process working directory. `CT_CONDUCTOR_ROOT` overrides that root. Hosts that do not launch the MCP server in the active workspace must configure either this environment value or an MCP `cwd` for the current project. This is intentionally not hard-coded into the reusable plugin bundle.
