from __future__ import annotations

import hashlib
import json
import statistics
import time
from pathlib import Path
from typing import Any

from comptext_conductor_max.broker import ContextBroker
from comptext_conductor_max.skills import SkillCatalog

EXTERNAL_SKILLS_PATH = Path(r"C:\Users\contr\dev\external\google-skills")
COMMIT_SHA = "092e210b243601797a0fb939040be2b1288e6d39"

POSITIVE_TASK_FILE = Path("benchmark-positive.txt")
NEGATIVE_TASK_FILE = Path("benchmark-negative.txt")

POSITIVE_TASK_PROMPT = POSITIVE_TASK_FILE.read_text(encoding="utf-8").strip()
NEGATIVE_TASK_PROMPT = NEGATIVE_TASK_FILE.read_text(encoding="utf-8").strip()

POSITIVE_TASK_HASH = hashlib.sha256(POSITIVE_TASK_PROMPT.encode("utf-8")).hexdigest()
NEGATIVE_TASK_HASH = hashlib.sha256(NEGATIVE_TASK_PROMPT.encode("utf-8")).hexdigest()

# Ground Truth for Positive Control
GROUND_TRUTH_EXPECTED_SKILLS = {"google-cloud-waf-security", "google-cloud-waf-performance-optimization"}
GROUND_TRUTH_DISTRACTOR_SKILLS = {"firebase-basics", "gke-storage", "google-mobile-ads-banner"}

POSITIVE_TASK_INFO = {
    "name": "Positive Control - Google Cloud Architecture Review",
    "prompt": POSITIVE_TASK_PROMPT,
    "hash": POSITIVE_TASK_HASH,
    "expected_skills": GROUND_TRUTH_EXPECTED_SKILLS,
}

NEGATIVE_TASK_INFO = {
    "name": "Negative Control - CompText Stale Ref Bug Fix",
    "prompt": NEGATIVE_TASK_PROMPT,
    "hash": NEGATIVE_TASK_HASH,
    "expected_skills": set(),
}


def evaluate_run(mode_name: str, task_info: dict[str, Any], root: Path) -> dict[str, Any]:
    start_time = time.perf_counter()
    
    if mode_name == "Mode A (CompText v0.2 — no Agent Skills)":
        # Mode A: v0.2 broker without skills
        broker = ContextBroker(root)
        res = broker.search(query=task_info["prompt"], budget_tokens=18_000)
        returned_bytes = sum(len(r.snippet.encode("utf-8")) for r in res.results)
        selected_skills = []
        
    elif mode_name == "Mode B (CompText v0.2 + native Antigravity Agent Skills)":
        # Mode B: Native Antigravity progressive disclosure simulation
        # In Native Antigravity, only L1 metadata is added to system prompt context for 104 skills
        catalog = SkillCatalog(root=root, external_roots=(EXTERNAL_SKILLS_PATH,))
        all_skills = catalog.discover_skills()
        l1_metadata_bytes = sum(
            len(f"Skill: {s.name}\nDescription: {s.description}\n".encode())
            for s in all_skills
        )
        
        # Simulate agent searching repo with v0.2 broker
        broker = ContextBroker(root)
        res = broker.search(query=task_info["prompt"], budget_tokens=18_000)
        
        # Determine if native agent would activate relevant skills (L2 activation)
        activated_skills = []
        query_lower = task_info["prompt"].lower()
        for s in all_skills:
            if any(term in query_lower for term in s.name.split("-")):
                activated_skills.append(s.name)
                
        l2_activated_bytes = sum(
            len(Path(s.source_path).read_text(encoding="utf-8").encode("utf-8"))
            for s in all_skills if s.name in activated_skills
        )
        
        returned_bytes = l1_metadata_bytes + l2_activated_bytes + sum(len(r.snippet.encode("utf-8")) for r in res.results)
        selected_skills = activated_skills
        
    elif mode_name == "Mode C (CompText v0.3 + Skill-Aware Context Runtime)":
        # Mode C: CompText v0.3 Skill-Aware Runtime with BM25 selection and 3-level progressive disclosure
        broker = ContextBroker(root, external_skill_roots=(EXTERNAL_SKILLS_PATH,))
        res = broker.search(query=task_info["prompt"], budget_tokens=18_000)
        returned_bytes = sum(len(r.snippet.encode("utf-8")) for r in res.results)
        selected_skills = [
            r.snippet.split("\n")[0].replace("Skill: ", "").strip()
            for r in res.results
            if "skill-metadata" in r.reasons or "skill-instruction" in r.reasons
        ]
        
    elif mode_name == "Mode D (Naive full-body skill concatenation stress test)":
        # Mode D: Anti-pattern full dump of all 104 SKILL.md bodies
        catalog = SkillCatalog(root=root, external_roots=(EXTERNAL_SKILLS_PATH,))
        all_skills = catalog.discover_skills()
        full_dump_bytes = sum(
            len(Path(s.source_path).read_text(encoding="utf-8").encode("utf-8"))
            for s in all_skills
        )
        broker = ContextBroker(root)
        res = broker.search(query=task_info["prompt"], budget_tokens=100_000)
        returned_bytes = full_dump_bytes + sum(len(r.snippet.encode("utf-8")) for r in res.results)
        selected_skills = [s.name for s in all_skills]
        
    else:
        raise ValueError(f"Unknown mode: {mode_name}")
        
    elapsed = time.perf_counter() - start_time
    estimated_tokens = (returned_bytes + 3) // 4
    
    # Accuracy calculation against ground truth
    expected = task_info["expected_skills"]
    selected_set = set(selected_skills)
    
    if expected:
        tp = len(selected_set.intersection(expected))
        fp = len(selected_set - expected)
        fn = len(expected - selected_set)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    else:
        tp = 0
        fp = len(selected_set)
        fn = 0
        precision = 1.0 if fp == 0 else 0.0
        recall = 1.0
        
    return {
        "returned_bytes": returned_bytes,
        "estimated_tokens": estimated_tokens,
        "elapsed_seconds": elapsed,
        "selected_skills": selected_skills,
        "selected_skill_count": len(selected_skills),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
    }


def run_trials(mode_name: str, task_info: dict[str, Any], root: Path, num_trials: int = 3) -> dict[str, Any]:
    trials = [evaluate_run(mode_name, task_info, root) for _ in range(num_trials)]
    
    tokens = [t["estimated_tokens"] for t in trials]
    bytes_list = [t["returned_bytes"] for t in trials]
    elapsed = [t["elapsed_seconds"] for t in trials]
    
    selected_counts = [t["selected_skill_count"] for t in trials]
    precisions = [t["precision"] for t in trials]
    recalls = [t["recall"] for t in trials]
    fps = [t["fp"] for t in trials]
    
    return {
        "mode": mode_name,
        "trials": trials,
        "summary": {
            "estimated_tokens_median": int(statistics.median(tokens)),
            "estimated_tokens_min": min(tokens),
            "estimated_tokens_max": max(tokens),
            "bytes_median": int(statistics.median(bytes_list)),
            "elapsed_seconds_median": round(statistics.median(elapsed), 4),
            "selected_skills_median": int(statistics.median(selected_counts)),
            "precision_median": statistics.median(precisions),
            "recall_median": statistics.median(recalls),
            "false_positives_median": int(statistics.median(fps)),
        }
    }


def main() -> None:
    root = Path.cwd()
    modes = [
        "Mode A (CompText v0.2 — no Agent Skills)",
        "Mode B (CompText v0.2 + native Antigravity Agent Skills)",
        "Mode C (CompText v0.3 + Skill-Aware Context Runtime)",
        "Mode D (Naive full-body skill concatenation stress test)",
    ]
    
    results = {"positive_control": [], "negative_control": []}
    
    print("=== Running Rigorous 3-Trial Benchmark for CompText v0.3 vs Native Agent Skills ===")
    
    for task_key, task_info in [("positive_control", POSITIVE_TASK_INFO), ("negative_control", NEGATIVE_TASK_INFO)]:
        print(f"\nTask: {task_info['name']}")
        print(f"Prompt SHA-256: {task_info['hash']}")
        
        for mode in modes:
            res = run_trials(mode, task_info, root, num_trials=3)
            results[task_key].append(res)
            s = res["summary"]
            print(f"  {mode[:45]:<45} | Tokens Median: {s['estimated_tokens_median']:>7,} | Selected Skills: {s['selected_skills_median']:>2} | Precision: {s['precision_median']:.2f}")

    out_file = root / "benchmark_v03_rigorous_report.json"
    out_file.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nRigorous benchmark report written to {out_file}")


if __name__ == "__main__":
    main()
