from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class AntigravityUsage:
    conversation_id: str
    status: str
    duration_seconds: float
    num_turns: int
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cache_read_tokens: int
    total_tokens: int


@dataclass(frozen=True, slots=True)
class AntigravityRun:
    available: bool
    usage: AntigravityUsage | None
    error: str | None = None


def _nonnegative_int(value: object, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"invalid Antigravity usage field: {field}")
    return value


def parse_stream_json(stream: str) -> AntigravityUsage:
    terminal: dict[str, object] | None = None
    for raw_line in stream.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("invalid Antigravity stream-json line") from exc
        if not isinstance(event, dict):
            raise ValueError("invalid Antigravity stream-json event")
        if event.get("event") == "result":
            payload = event.get("result")
            if not isinstance(payload, dict):
                raise ValueError("invalid Antigravity result payload")
            terminal = payload
    if terminal is None:
        raise ValueError("Antigravity stream has no terminal result event")
    usage = terminal.get("usage")
    if not isinstance(usage, dict):
        raise ValueError("Antigravity result has no usage object")
    conversation_id = terminal.get("conversation_id")
    status = terminal.get("status")
    duration = terminal.get("duration_seconds", 0.0)
    turns = terminal.get("num_turns", 0)
    if not isinstance(conversation_id, str) or not conversation_id:
        raise ValueError("invalid Antigravity conversation_id")
    if not isinstance(status, str) or not status:
        raise ValueError("invalid Antigravity status")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
        raise ValueError("invalid Antigravity duration_seconds")
    return AntigravityUsage(
        conversation_id=conversation_id,
        status=status,
        duration_seconds=float(duration),
        num_turns=_nonnegative_int(turns, "num_turns"),
        input_tokens=_nonnegative_int(usage.get("input_tokens"), "input_tokens"),
        output_tokens=_nonnegative_int(usage.get("output_tokens"), "output_tokens"),
        thinking_tokens=_nonnegative_int(usage.get("thinking_tokens"), "thinking_tokens"),
        cache_read_tokens=_nonnegative_int(usage.get("cache_read_tokens"), "cache_read_tokens"),
        total_tokens=_nonnegative_int(usage.get("total_tokens"), "total_tokens"),
    )


def run_headless_probe(root: Path, *, timeout_seconds: int = 120) -> AntigravityRun:
    executable = shutil.which("agy")
    if executable is None:
        return AntigravityRun(available=False, usage=None, error="agy executable not found")
    try:
        completed = subprocess.run(
            [
                executable,
                "-p",
                "Return exactly CT_AGY_PROBE_OK and do not use tools.",
                "--output-format",
                "stream-json",
            ],
            cwd=root.resolve(),
            capture_output=True,
            text=True,
            check=False,
            timeout=max(1, timeout_seconds),
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return AntigravityRun(available=True, usage=None, error=str(exc))
    if completed.returncode != 0:
        message = completed.stderr.strip() or f"agy exited with code {completed.returncode}"
        return AntigravityRun(available=True, usage=None, error=message[:2000])
    try:
        usage = parse_stream_json(completed.stdout)
    except ValueError as exc:
        return AntigravityRun(available=True, usage=None, error=str(exc))
    return AntigravityRun(available=True, usage=usage)
