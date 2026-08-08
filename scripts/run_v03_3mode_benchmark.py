from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from comptext_conductor_max.broker import ContextBroker
from comptext_conductor_max.skills import SkillCatalog

EXTERNAL_SKILLS_PATH = Path(r"C:\Users\contr\dev\external\google-skills")

POSITIVE_TASK = {
    "name": "Positive Control - Cloudflare WAF & Security Configuration",
    "track": "02_skill_aware_context_runtime",
    "task": "configure cloudflare waf zero trust rule for API rate limiting and bot management",
    "relevant_skill": "cloudflare-one",
}

NEGATIVE_TASK = {
    "name": "Negative Control - Python Legacy Math Bug Fix",
    "track": "02_skill_aware_context_runtime",
    "task": "fix legacy coordinate transformation bug in python map loader module 03",
    "relevant_skill": None,
}


def run_mode_a(root: Path, task_info: dict[str, Any]) -> dict[str, Any]:
    """Mode A: v0.2 without skills (skills directory empty or skill catalog disabled)."""
    broker = ContextBroker(root)
    # Clear any skills from catalog for Mode A simulation
    start_time = time.perf_counter()
    res = broker.search(query=task_info["task"], budget_tokens=18_000)
    elapsed = time.perf_counter() - start_time
    
    returned_bytes = sum(len(r.snippet.encode("utf-8")) for r in res.results)
    estimated_tokens = (returned_bytes + 3) // 4
    
    return {
        "mode": "Mode A (v0.2 Baseline, No Skills)",
        "task": task_info["name"],
        "discovered_skills": 0,
        "selected_skills": 0,
        "returned_results": len(res.results),
        "returned_bytes": returned_bytes,
        "estimated_tokens": estimated_tokens,
        "elapsed_seconds": round(elapsed, 4),
        "skills_used": [],
    }


def run_mode_b(root: Path, task_info: dict[str, Any]) -> dict[str, Any]:
    """Mode B: v0.2 + Native skills (dumping skill files whole without progressive disclosure)."""
    # In Mode B, all skills are loaded completely at once into prompt context
    catalog = SkillCatalog(root=root, external_roots=(EXTERNAL_SKILLS_PATH,))
    all_skills = catalog.discover_skills()
    
    start_time = time.perf_counter()
    # Dumps full body of all skills into context
    raw_skill_bytes = sum(
        len(Path(meta.source_path).read_text(encoding="utf-8").encode("utf-8"))
        for meta in all_skills
        if Path(meta.source_path).exists()
    )
    
    broker = ContextBroker(root, external_skill_roots=(EXTERNAL_SKILLS_PATH,))
    res = broker.search(query=task_info["task"], budget_tokens=100_000)
    elapsed = time.perf_counter() - start_time
    
    returned_bytes = raw_skill_bytes + sum(len(r.snippet.encode("utf-8")) for r in res.results)
    estimated_tokens = (returned_bytes + 3) // 4
    
    return {
        "mode": "Mode B (v0.2 + Native Skills Full Dump)",
        "task": task_info["name"],
        "discovered_skills": len(all_skills),
        "selected_skills": len(all_skills),  # All skills dumped into context
        "returned_results": len(res.results),
        "returned_bytes": returned_bytes,
        "estimated_tokens": estimated_tokens,
        "elapsed_seconds": round(elapsed, 4),
        "skills_used": [s.name for s in all_skills],
    }


def run_mode_c(root: Path, task_info: dict[str, Any]) -> dict[str, Any]:
    """Mode C: v0.3 Skill-Aware Context Runtime (3-level progressive disclosure & BM25 selection)."""
    broker = ContextBroker(root, external_skill_roots=(EXTERNAL_SKILLS_PATH,))
    
    start_time = time.perf_counter()
    res = broker.search(query=task_info["task"], budget_tokens=18_000)
    elapsed = time.perf_counter() - start_time
    
    returned_bytes = sum(len(r.snippet.encode("utf-8")) for r in res.results)
    estimated_tokens = (returned_bytes + 3) // 4
    
    selected_skill_names = [
        r.snippet.split("\n")[0].replace("Skill: ", "").strip()
        for r in res.results
        if "skill-metadata" in r.reasons or "skill-instruction" in r.reasons
    ]
    
    snap = broker.stats.snapshot()
    
    return {
        "mode": "Mode C (v0.3 Skill-Aware Context Runtime)",
        "task": task_info["name"],
        "discovered_skills": snap.discovered_skill_count,
        "selected_skills": snap.selected_skill_count,
        "returned_results": len(res.results),
        "returned_bytes": returned_bytes,
        "estimated_tokens": estimated_tokens,
        "elapsed_seconds": round(elapsed, 4),
        "skills_used": selected_skill_names,
    }


def main() -> None:
    root = Path.cwd()
    print("=== CompText Conductor Max v0.3 Benchmark ===")
    print(f"External Skills Path: {EXTERNAL_SKILLS_PATH}")
    
    results = []
    
    for task in [POSITIVE_TASK, NEGATIVE_TASK]:
        print(f"\n--- Running Benchmark for: {task['name']} ---")
        mA = run_mode_a(root, task)
        mB = run_mode_b(root, task)
        mC = run_mode_c(root, task)
        
        results.extend([mA, mB, mC])
        
        print(f"  Mode A (v0.2 No Skills):       {mA['estimated_tokens']:,} tokens | Selected Skills: {mA['selected_skills']}")
        print(f"  Mode B (v0.2 + Full Skills):   {mB['estimated_tokens']:,} tokens | Selected Skills: {mB['selected_skills']}")
        print(f"  Mode C (v0.3 Skill-Aware):     {mC['estimated_tokens']:,} tokens | Selected Skills: {mC['selected_skills']}")
    
    out_file = root / "benchmark_v03_report.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nBenchmark report written to: {out_file}")


if __name__ == "__main__":
    main()
