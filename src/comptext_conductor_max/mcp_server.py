from __future__ import annotations

import os
from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from mcp.server import MCPServer

from .broker import ContextBroker
from .checkpoints import Checkpoint
from .config import ProfileName


def create_server(root: Path | None = None) -> MCPServer:
    broker = ContextBroker(root or Path(os.environ.get("CT_CONDUCTOR_ROOT", Path.cwd())))
    server = MCPServer(
        "CompText Conductor Max",
        description="Local-first context broker: compute before context.",
        instructions=(
            "Prefer bounded broker tools for repository context, diffs, and logs; "
            "expand only when correctness requires it."
        ),
        version="0.3.0",
    )

    @server.tool(
        name="ct_context",
        description="Assemble bounded context for a Conductor track and current task.",
        structured_output=True,
    )
    def ct_context(
        track: str,
        task: str,
        profile: ProfileName = "balanced",
        budget: int | None = None,
    ) -> dict[str, Any]:
        result = broker.context(track=track, task=task, profile=profile, budget=budget)
        return {
            "track": result.track,
            "current_step": result.current_step,
            "content": result.content,
            "returned_tokens": asdict(result.returned_tokens),
            "budget": result.budget,
            "budget_exceeded": result.budget_exceeded,
            "omitted_critical": list(result.omitted_critical),
        }

    @server.tool(
        name="ct_search",
        description=(
            "Search safe indexed repository slices with hard limits, or expand one stable "
            "ctref returned by an earlier search. Provide exactly one of query or ref."
        ),
        structured_output=True,
    )
    def ct_search(
        query: str | None = None,
        ref: str | None = None,
        max_results: int = 5,
        max_lines: int = 180,
        budget: int = 18_000,
    ) -> dict[str, Any]:
        response = broker.search(
            query,
            ref=ref,
            max_results=max_results,
            max_lines=max_lines,
            budget_tokens=budget,
        )
        return {
            "results": [
                {**asdict(item), "token_count": asdict(item.token_count)}
                for item in response.results
            ],
            "returned_lines": response.returned_lines,
            "returned_tokens": asdict(response.returned_tokens),
            "budget_exceeded": response.budget_exceeded,
            "omitted_critical": list(response.omitted_critical),
        }

    @server.tool(
        name="ct_diff",
        description="Return a Git diff summary first, or one stable hunk by id.",
        structured_output=True,
    )
    def ct_diff(hunk_id: str | None = None, max_lines: int = 400) -> dict[str, Any]:
        try:
            return broker.diff(hunk_id, max_lines=max_lines)
        except (RuntimeError, KeyError) as exc:
            return {"available": False, "error": str(exc)}

    @server.tool(
        name="ct_result",
        description=(
            "Reduce build/test/lint/compiler output locally while retaining failures and diagnostics."
        ),
        structured_output=True,
    )
    def ct_result(
        log: str | None = None,
        log_path: str | None = None,
        exit_code: int | None = None,
        max_lines: int = 120,
    ) -> dict[str, Any]:
        return broker.result(log, log_path=log_path, exit_code=exit_code, max_lines=max_lines)

    @server.tool(
        name="ct_checkpoint",
        description="Save, load, or list versioned deterministic Conductor work checkpoints.",
        structured_output=True,
    )
    def ct_checkpoint(
        action: Literal["save", "load", "list"],
        track: str | None = None,
        step: str | None = None,
        status: str = "complete",
        decisions: dict[str, str] | None = None,
        files_changed: list[str] | None = None,
        tests_passed: int = 0,
        tests_failed: int = 0,
        next_step: str | None = None,
        checkpoint_hash: str | None = None,
    ) -> dict[str, Any]:
        if action == "save":
            if not track or not step:
                raise ValueError("track and step are required for save")
            return broker.checkpoint_save(
                Checkpoint(
                    track=track,
                    step=step,
                    status=status,
                    decisions=decisions or {},
                    files_changed=tuple(files_changed or ()),
                    tests_passed=tests_passed,
                    tests_failed=tests_failed,
                    next_step=next_step,
                )
            )
        if action == "load":
            if not checkpoint_hash:
                raise ValueError("checkpoint_hash is required for load")
            return broker.checkpoints.load(checkpoint_hash).model_dump(mode="json")
        return {
            "checkpoints": [
                {"checkpoint_hash": item.checkpoint_hash}
                for item in broker.checkpoints.list(track)[:100]
            ]
        }

    @server.tool(
        name="ct_stats",
        description="Return measured context, cache, read, diff, and log reduction counters.",
        structured_output=True,
    )
    def ct_stats() -> dict[str, Any]:
        return broker.stats_snapshot()

    return server


def main() -> None:
    create_server().run(transport="stdio")


if __name__ == "__main__":
    main()
