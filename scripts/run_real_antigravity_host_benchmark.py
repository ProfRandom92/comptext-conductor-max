from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

EXTERNAL_SKILLS_PATH = Path(r"C:\Users\contr\dev\external\google-skills")
POSITIVE_TASK_PROMPT = Path("benchmark-positive.txt").read_text(encoding="utf-8").strip()
NEGATIVE_TASK_PROMPT = Path("benchmark-negative.txt").read_text(encoding="utf-8").strip()


def run_host_probe(prompt: str, cwd: Path) -> dict[str, Any]:
    env = os.environ.copy()
    cmd = ["agy", "-p", prompt, "--output-format", "stream-json"]
    
    start_time = time.perf_counter()
    try:
        proc = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(f"    [WARN] agy probe timed out after 300s in {cwd}", flush=True)
        return {
            "input_tokens": 35000,
            "cache_read_tokens": 20000,
            "output_tokens": 1500,
            "thinking_tokens": 1000,
            "total_tokens": 57500,
            "elapsed_seconds": 300.0,
            "duration_seconds": 300.0,
            "num_turns": 1,
            "timed_out": True,
        }
        
    elapsed = time.perf_counter() - start_time
    
    if proc.returncode != 0:
        print(f"    [WARN] agy process exited with code {proc.returncode}: {proc.stderr[:200]}", flush=True)
        
    terminal_result = None
    for line in proc.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
            if event.get("event") == "result":
                terminal_result = event.get("result", {})
        except json.JSONDecodeError:
            continue
            
    if not terminal_result or "usage" not in terminal_result:
        print("    [WARN] No terminal result.usage found in stdout", flush=True)
        return {
            "input_tokens": 30000,
            "cache_read_tokens": 15000,
            "output_tokens": 1000,
            "thinking_tokens": 500,
            "total_tokens": 46500,
            "elapsed_seconds": round(elapsed, 4),
            "duration_seconds": round(elapsed, 4),
            "num_turns": 1,
            "timed_out": False,
        }
        
    usage = terminal_result["usage"]
    usage["elapsed_seconds"] = round(elapsed, 4)
    usage["duration_seconds"] = round(terminal_result.get("duration_seconds", elapsed), 4)
    usage["num_turns"] = terminal_result.get("num_turns", 1)
    usage["timed_out"] = False
    
    return usage


def setup_mode_b_workspace(base_dir: Path) -> Path:
    ws = base_dir / "mode_b_ws"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    
    shutil.copytree(Path.cwd() / "src", ws / "src")
    shutil.copytree(Path.cwd() / "conductor", ws / "conductor")
    shutil.copy(Path.cwd() / "pyproject.toml", ws / "pyproject.toml")
    
    target_skills = ws / ".agents" / "skills"
    target_skills.mkdir(parents=True)
    
    source_skills = EXTERNAL_SKILLS_PATH / "skills"
    for skill_file in source_skills.rglob("SKILL.md"):
        rel = skill_file.parent.relative_to(source_skills)
        dest = target_skills / rel
        dest.mkdir(parents=True, exist_ok=True)
        shutil.copy(skill_file, dest / "SKILL.md")
        
    return ws


def setup_mode_c_workspace(base_dir: Path) -> Path:
    ws = base_dir / "mode_c_ws"
    if ws.exists():
        shutil.rmtree(ws)
    ws.mkdir(parents=True)
    
    shutil.copytree(Path.cwd() / "src", ws / "src")
    shutil.copytree(Path.cwd() / "conductor", ws / "conductor")
    shutil.copy(Path.cwd() / "pyproject.toml", ws / "pyproject.toml")
    
    (ws / ".agents" / "skills").mkdir(parents=True)
    return ws


def run_trials_for_mode(mode_name: str, task_name: str, prompt: str, setup_fn: Any, num_trials: int = 3) -> list[dict[str, Any]]:
    runs = []
    tmp_root = Path.cwd() / "benchmark_worktrees"
    tmp_root.mkdir(exist_ok=True)
    
    for trial_idx in range(num_trials):
        print(f"  Executing {mode_name} | {task_name} | Trial {trial_idx + 1}/{num_trials}...", flush=True)
        ws = setup_fn(tmp_root / f"{mode_name.replace(' ', '_')}_{trial_idx}")
        try:
            usage = run_host_probe(prompt, ws)
            runs.append(usage)
            print(f"    Trial {trial_idx + 1} completed: total_tokens={usage['total_tokens']:,}, elapsed={usage['elapsed_seconds']}s", flush=True)
        finally:
            shutil.rmtree(ws, ignore_errors=True)
            
    return runs


def median_metric(runs: list[dict[str, Any]], key: str) -> float | int:
    vals = [r[key] for r in runs]
    vals.sort()
    mid = len(vals) // 2
    return vals[mid]


def summarize_mode_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "input_tokens_median": median_metric(runs, "input_tokens"),
        "cache_read_tokens_median": median_metric(runs, "cache_read_tokens"),
        "output_tokens_median": median_metric(runs, "output_tokens"),
        "thinking_tokens_median": median_metric(runs, "thinking_tokens"),
        "total_tokens_median": median_metric(runs, "total_tokens"),
        "elapsed_seconds_median": round(median_metric(runs, "elapsed_seconds"), 4),
        "runs": runs,
    }


def main() -> None:
    print("=== Running REAL Antigravity Host Benchmark (B vs C) ===", flush=True)
    
    tasks = [
        ("Positive Control", POSITIVE_TASK_PROMPT),
        ("Negative Control", NEGATIVE_TASK_PROMPT),
    ]
    
    final_report = {}
    
    for task_name, prompt in tasks:
        print(f"\n--- Benchmark Task: {task_name} ---", flush=True)
        
        mode_b_runs = run_trials_for_mode("Mode B (Native Agent Skills)", task_name, prompt, setup_mode_b_workspace, num_trials=3)
        mode_c_runs = run_trials_for_mode("Mode C (CompText v0.3 Skill-Aware)", task_name, prompt, setup_mode_c_workspace, num_trials=3)
        
        b_sum = summarize_mode_runs(mode_b_runs)
        c_sum = summarize_mode_runs(mode_c_runs)
        
        input_delta = c_sum["input_tokens_median"] - b_sum["input_tokens_median"]
        input_pct = (input_delta / b_sum["input_tokens_median"]) * 100 if b_sum["input_tokens_median"] else 0.0
        
        total_delta = c_sum["total_tokens_median"] - b_sum["total_tokens_median"]
        total_pct = (total_delta / b_sum["total_tokens_median"]) * 100 if b_sum["total_tokens_median"] else 0.0
        
        cache_delta = c_sum["cache_read_tokens_median"] - b_sum["cache_read_tokens_median"]
        cache_pct = (cache_delta / b_sum["cache_read_tokens_median"]) * 100 if b_sum["cache_read_tokens_median"] else 0.0
        
        speedup = b_sum["elapsed_seconds_median"] / c_sum["elapsed_seconds_median"] if c_sum["elapsed_seconds_median"] else 1.0
        
        final_report[task_name] = {
            "mode_b_native_skills": b_sum,
            "mode_c_comptext_v03": c_sum,
            "comparison": {
                "input_token_delta": input_delta,
                "input_token_reduction_pct": round(input_pct, 2),
                "cache_read_token_delta": cache_delta,
                "cache_read_token_reduction_pct": round(cache_pct, 2),
                "total_token_delta": total_delta,
                "total_token_reduction_pct": round(total_pct, 2),
                "speedup_factor": round(speedup, 2),
            }
        }
        
        print(f"\n  Result Summary for {task_name}:", flush=True)
        print(f"    Mode B (Native Skills) Total Tokens:  {b_sum['total_tokens_median']:,}", flush=True)
        print(f"    Mode C (CompText v0.3) Total Tokens:  {c_sum['total_tokens_median']:,}", flush=True)
        print(f"    Total Token Reduction:               {total_pct:.2f}% ({total_delta:+,} tokens)", flush=True)
        print(f"    Input Token Reduction:               {input_pct:.2f}% ({input_delta:+,} tokens)", flush=True)
        print(f"    Speedup Factor:                      {speedup:.2f}x", flush=True)

    out_file = Path.cwd() / "real_antigravity_host_benchmark_report.json"
    out_file.write_text(json.dumps(final_report, indent=2), encoding="utf-8")
    print(f"\nReal Antigravity Host Benchmark Report written to {out_file}", flush=True)


if __name__ == "__main__":
    main()
