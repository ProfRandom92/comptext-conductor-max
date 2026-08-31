"""Authenticated AGY host benchmark; invalid evidence is never estimated."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from statistics import median
from typing import Any

from comptext_conductor_max import __version__

EXTERNAL_SKILLS_PATH = Path(r"C:\\Users\\contr\\dev\\external\\google-skills")
MIN_VALID_TRIALS = 3
TOKEN_FIELDS = (
    "input_tokens",
    "cache_read_tokens",
    "output_tokens",
    "thinking_tokens",
    "total_tokens",
)


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    for file in sorted(path.rglob("SKILL.md")):
        digest.update(file.relative_to(path).as_posix().encode())
        digest.update(file.read_bytes())
    return digest.hexdigest()


def invalid_trial(reason: str, elapsed: float = 0.0) -> dict[str, Any]:
    return {
        "status": "INVALID",
        "reason": reason,
        "elapsed_seconds": round(elapsed, 4),
        "duration_seconds": round(elapsed, 4),
        "timed_out": reason == "timeout",
        **{field: None for field in TOKEN_FIELDS},
    }


def run_host_probe(
    prompt: str, cwd: Path, *, env_overrides: dict[str, str] | None = None
) -> dict[str, Any]:
    env = os.environ.copy()
    env.update(env_overrides or {})
    started = time.perf_counter()
    try:
        proc = subprocess.run(
            ["agy", "-p", prompt, "--output-format", "stream-json"],
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return invalid_trial("timeout", 300.0)
    elapsed = time.perf_counter() - started
    if proc.returncode != 0:
        return invalid_trial(f"process_exit:{proc.returncode}", elapsed)
    terminal: dict[str, Any] | None = None
    for line in proc.stdout.splitlines():
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event") == "result" and isinstance(event.get("result"), dict):
            terminal = event["result"]
    if terminal is None:
        return invalid_trial("missing_terminal_result", elapsed)
    if terminal.get("status") != "SUCCESS":
        return invalid_trial(f"terminal_status:{terminal.get('status', 'missing')}", elapsed)
    usage = terminal.get("usage")
    if not isinstance(usage, dict) or any(
        not isinstance(usage.get(field), (int, float)) for field in TOKEN_FIELDS
    ):
        return invalid_trial("missing_or_invalid_usage", elapsed)
    return {
        "status": "VALID",
        "reason": None,
        "timed_out": False,
        **{field: usage[field] for field in TOKEN_FIELDS},
        "elapsed_seconds": round(elapsed, 4),
        "duration_seconds": round(float(terminal.get("duration_seconds", elapsed)), 4),
        "num_turns": terminal.get("num_turns", 1),
    }


def setup_mode_workspace(
    base_dir: Path, mode: str, skills_root: Path
) -> tuple[Path, dict[str, str]]:
    ws = base_dir / mode
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    for name in ("src", "conductor"):
        shutil.copytree(Path.cwd() / name, ws / name)
    shutil.copy(Path.cwd() / "pyproject.toml", ws / "pyproject.toml")
    # Both arms receive byte-identical skills. Only the access path changes.
    if mode == "mode_b_ws":
        shutil.copytree(skills_root, ws / ".agents" / "skills")
        return ws, {}
    exposed = ws / "ct_skills"
    shutil.copytree(skills_root, exposed)
    return ws, {"CT_SKILLS_ROOT": str(exposed)}


def run_trials_for_mode(
    mode: str, prompt: str, skills_root: Path, num_trials: int = MIN_VALID_TRIALS
) -> list[dict[str, Any]]:
    runs: list[dict[str, Any]] = []
    tmp_root = Path.cwd() / "benchmark_worktrees"
    tmp_root.mkdir(exist_ok=True)
    for trial in range(num_trials):
        ws, env = setup_mode_workspace(tmp_root / f"{mode}_{trial}", mode, skills_root)
        try:
            runs.append(run_host_probe(prompt, ws, env_overrides=env))
        finally:
            shutil.rmtree(ws, ignore_errors=True)
    return runs


def summarize_mode_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    valid = [run for run in runs if run["status"] == "VALID"]
    summary: dict[str, Any] = {
        "valid_trials": len(valid),
        "invalid_trials": len(runs) - len(valid),
        "runs": runs,
    }
    if len(valid) < MIN_VALID_TRIALS:
        return {
            **summary,
            "status": "BENCHMARK_INCONCLUSIVE",
            **{f"{field}_median": None for field in TOKEN_FIELDS},
        }
    return {
        **summary,
        "status": "MEASURED",
        **{f"{field}_median": median(run[field] for run in valid) for field in TOKEN_FIELDS},
        "elapsed_seconds_median": round(median(run["elapsed_seconds"] for run in valid), 4),
    }


def comparison(mode_b: dict[str, Any], mode_c: dict[str, Any]) -> dict[str, Any]:
    if mode_b["status"] != "MEASURED" or mode_c["status"] != "MEASURED":
        return {"status": "BENCHMARK_INCONCLUSIVE", "savings_verdict": "UNMEASURED"}
    result: dict[str, Any] = {"status": "MEASURED"}
    for label, field in (
        ("input", "input_tokens"),
        ("cache_read", "cache_read_tokens"),
        ("total", "total_tokens"),
    ):
        base, comptext = mode_b[f"{field}_median"], mode_c[f"{field}_median"]
        result[f"{label}_token_delta"] = comptext - base
        result[f"{label}_token_savings_pct"] = (
            round(((base - comptext) / base) * 100, 2) if base else None
        )
    result["savings_verdict"] = "MEASURED"
    return result


def provenance(skills_root: Path, positive: str, negative: str) -> dict[str, Any]:
    return {
        "skill_manifest_sha256": sha256_path(skills_root),
        "skill_count": len(list(skills_root.rglob("SKILL.md"))),
        "positive_prompt_sha256": hashlib.sha256(positive.encode()).hexdigest(),
        "negative_prompt_sha256": hashlib.sha256(negative.encode()).hexdigest(),
        "agy_version": subprocess.run(
            ["agy", "--version"], capture_output=True, text=True, check=False
        ).stdout.strip()
        or "unavailable",
        "model": os.environ.get("CT_AGY_MODEL", "unspecified"),
        "plugin_runtime_version": __version__,
        "repository_head": subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
        ).stdout.strip(),
        "trial_count": MIN_VALID_TRIALS,
    }


def main() -> None:
    root = Path.cwd()
    positive = (root / "benchmark-positive.txt").read_text(encoding="utf-8").strip()
    negative = (root / "benchmark-negative.txt").read_text(encoding="utf-8").strip()
    skills_root = EXTERNAL_SKILLS_PATH / "skills"
    if not skills_root.is_dir():
        raise SystemExit("BENCHMARK_INCONCLUSIVE: required shared skill corpus is unavailable")
    report: dict[str, Any] = {
        "benchmark_kind": "real_authenticated_agy_host",
        "provenance": provenance(skills_root, positive, negative),
        "tasks": {},
    }
    for name, prompt in (("positive_control", positive), ("negative_control", negative)):
        mode_b = summarize_mode_runs(run_trials_for_mode("mode_b_ws", prompt, skills_root))
        mode_c = summarize_mode_runs(run_trials_for_mode("mode_c_ws", prompt, skills_root))
        report["tasks"][name] = {
            "mode_b_native_skills": mode_b,
            "mode_c_comptext_routing": mode_c,
            "comparison": comparison(mode_b, mode_c),
        }
    (root / "real_antigravity_host_benchmark_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
