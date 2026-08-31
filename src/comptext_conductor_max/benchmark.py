from __future__ import annotations

import hashlib
import json
import os
import random
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from .broker import ContextBroker
from .security import SecurityPolicy
from .tokens import estimate_tokens


@dataclass(frozen=True, slots=True)
class BenchmarkManifest:
    root: Path
    log_path: Path
    required_facts: tuple[str, ...]
    fixture_hash: str


@dataclass(frozen=True, slots=True)
class BenchmarkRun:
    mode: str
    raw_bytes: int
    returned_bytes: int
    raw_estimated_tokens: int
    returned_estimated_tokens: int
    required_facts_retained: int
    missing_required_facts: tuple[str, ...]
    tool_calls: int
    latency_ms: float
    reduction_ratio: float
    byte_reduction_ratio: float


@dataclass(frozen=True, slots=True)
class BenchmarkReport:
    fixture_hash: str
    raw_context_bytes: int
    raw_context_estimated_tokens: int
    token_metric: str
    required_facts: tuple[str, ...]
    runs: tuple[BenchmarkRun, ...]
    meets_target: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _git(root: Path, *args: str) -> None:
    env = os.environ.copy()
    env.update({
        "GIT_AUTHOR_DATE": "2026-08-07T10:00:00+00:00",
        "GIT_COMMITTER_DATE": "2026-08-07T10:00:00+00:00",
    })
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True, env=env)


def _fixture_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or ".git" in path.relative_to(root).parts or ".comptext" in path.relative_to(root).parts:
            continue
        rel = path.relative_to(root).as_posix().encode("utf-8")
        digest.update(len(rel).to_bytes(4, "big")); digest.update(rel)
        data = path.read_bytes()
        digest.update(len(data).to_bytes(8, "big")); digest.update(data)
    return digest.hexdigest()


def generate_fixture(root: Path, *, seed: int = 20260807) -> BenchmarkManifest:
    root.mkdir(parents=True, exist_ok=False)
    rng = random.Random(seed)
    (root / ".gitignore").write_text("build/\n.comptext/\n", encoding="utf-8")
    track = root / "conductor" / "tracks" / "demo"
    track.mkdir(parents=True)
    spec_facts = [
        "RENDERER=KNI",
        "STORAGE=IndexedDB",
        "COORDINATE_SYSTEM=legacy-preserved",
        "EXPECTED_COORDINATE=12",
    ]
    spec_noise = [f"requirement filler {i:04d} subsystem-{rng.randrange(1000):03d}" for i in range(700)]
    (track / "spec.md").write_text("# Demo specification\n" + "\n".join(spec_facts + spec_noise) + "\n", encoding="utf-8")
    plan_facts = [
        "- [ ] TASK_ID=MAP-003 legacy coordinate transformation",
        "- [ ] NEXT_STEP=texture-loading",
    ]
    plan_noise = [f"- [x] historical-step-{i:04d} completed" for i in range(650)]
    (track / "plan.md").write_text("# Demo plan\n" + "\n".join(plan_facts + plan_noise) + "\n", encoding="utf-8")
    (track / "metadata.json").write_text('{"name":"demo","status":"active"}\n', encoding="utf-8")

    src = root / "src"
    tests = root / "tests"
    src.mkdir(); tests.mkdir()
    (src / "map_loader.py").write_text(
        "RENDERER = 'KNI'\nEXPECTED_COORDINATE=11\n"
        "def legacy_coordinate_transform():\n    return EXPECTED_COORDINATE\n",
        encoding="utf-8",
    )
    (tests / "test_map_loader.py").write_text("def test_legacy():\n    assert 11 == 11\n", encoding="utf-8")
    for idx in range(48):
        lines = [
            f"def helper_{idx}_{line}(): return 'distractor-{seed}-{idx}-{line}-{rng.randrange(1_000_000)}'"
            for line in range(140)
        ]
        (src / f"module_{idx:02d}.py").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (root / "package-lock.json").write_text(
        "{\n" + ",\n".join(f'  "dep-{i}": "{rng.randrange(1_000_000)}"' for i in range(2200)) + "\n}\n",
        encoding="utf-8",
    )
    (root / "asset.bin").write_bytes(b"\x00BASE-BINARY" * 300)

    _git(root, "init", "-b", "main")
    _git(root, "config", "user.email", "benchmark@example.invalid")
    _git(root, "config", "user.name", "CompText Benchmark")
    _git(root, "add", ".")
    _git(root, "commit", "-m", "benchmark base")

    (src / "map_loader.py").write_text(
        "RENDERER = 'KNI'\nEXPECTED_COORDINATE=12\n"
        "def legacy_coordinate_transform():\n    return EXPECTED_COORDINATE\n",
        encoding="utf-8",
    )
    (tests / "test_map_loader.py").write_text(
        "def test_legacy():\n    expected = 12\n    actual = 0\n    assert actual == expected\n",
        encoding="utf-8",
    )
    for idx in range(12):
        path = src / f"module_{idx:02d}.py"
        with path.open("a", encoding="utf-8") as handle:
            for line in range(80):
                handle.write(f"CHANGED_{idx}_{line} = 'diff-noise-{seed}-{line}'\n")
    (root / "package-lock.json").write_text(
        "{\n" + ",\n".join(f'  "dep-{i}": "changed-{rng.randrange(1_000_000)}"' for i in range(2600)) + "\n}\n",
        encoding="utf-8",
    )
    (root / "asset.bin").write_bytes(b"\x00CHANGED-BINARY" * 400)

    log_path = root / "build" / "test.log"
    log_path.parent.mkdir()
    log_lines = [f"noise build line {i:05d} module={rng.randrange(48):02d}" for i in range(6500)]
    failure = [
        "FAILED_TEST=LegacyCoordinateTransform",
        "FAILED tests/test_map_loader.py::test_legacy - assert 0 == 12",
        "Expected: 12",
        "Actual: 0",
        "184 passed, 1 failed in 4.2s",
    ]
    log_path.write_text("\n".join(log_lines[:3200] + failure + log_lines[3200:]) + "\n", encoding="utf-8")

    required = (
        "RENDERER=KNI", "STORAGE=IndexedDB", "COORDINATE_SYSTEM=legacy-preserved",
        "TASK_ID=MAP-003", "NEXT_STEP=texture-loading", "EXPECTED_COORDINATE=12",
        "FAILED_TEST=LegacyCoordinateTransform", "Expected: 12", "Actual: 0", "src/map_loader.py",
    )
    return BenchmarkManifest(root=root, log_path=log_path, required_facts=required, fixture_hash=_fixture_hash(root))


def _full_diff(root: Path) -> str:
    proc = subprocess.run(
        ["git", "diff", "--no-ext-diff", "--unified=3"],
        cwd=root, check=True, capture_output=True, text=True,
    )
    return proc.stdout


def _naive_payload(manifest: BenchmarkManifest) -> str:
    policy = SecurityPolicy.from_root(manifest.root)
    parts: list[str] = []
    for path in sorted(manifest.root.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or ".git" in path.relative_to(manifest.root).parts:
            continue
        text = policy.safe_text(path, 5_000_000)
        if text is not None:
            parts.append(f"## {path.relative_to(manifest.root).as_posix()}\n{text}")
    parts.append("## FULL GIT DIFF\n" + _full_diff(manifest.root))
    parts.append("## FULL TEST LOG\n" + manifest.log_path.read_text(encoding="utf-8"))
    return "\n\n".join(parts)


def _facts(payload: str, required: tuple[str, ...]) -> tuple[int, tuple[str, ...]]:
    missing = tuple(fact for fact in required if fact not in payload)
    return len(required) - len(missing), missing


def run_benchmark(manifest: BenchmarkManifest) -> BenchmarkReport:
    naive = _naive_payload(manifest)
    raw_bytes = len(naive.encode("utf-8"))
    raw_tokens = estimate_tokens(naive).value
    retained, missing = _facts(naive, manifest.required_facts)
    runs: list[BenchmarkRun] = [
        BenchmarkRun(
            mode="naive", raw_bytes=raw_bytes, returned_bytes=raw_bytes,
            raw_estimated_tokens=raw_tokens, returned_estimated_tokens=raw_tokens,
            required_facts_retained=retained, missing_required_facts=missing, tool_calls=3,
            latency_ms=0.0, reduction_ratio=0.0, byte_reduction_ratio=0.0,
        )
    ]
    log_text = manifest.log_path.read_text(encoding="utf-8")
    for mode in ("safe", "balanced", "max"):
        started = time.perf_counter()
        broker = ContextBroker(manifest.root)
        context = broker.context(
            track="demo",
            task="implement TASK_ID=MAP-003 legacy coordinate transformation and diagnose LegacyCoordinateTransform",
            profile=mode,
        )
        diff = broker.diff()
        result = broker.result(log_text, exit_code=1, max_lines=80)
        payload = context.content + "\n\n" + json.dumps(diff, sort_keys=True) + "\n\n" + json.dumps(result, sort_keys=True)
        elapsed = (time.perf_counter() - started) * 1000.0
        returned_bytes = len(payload.encode("utf-8"))
        returned_tokens = estimate_tokens(payload).value
        retained, missing = _facts(payload, manifest.required_facts)
        token_reduction = max(0.0, 1.0 - (returned_tokens / raw_tokens if raw_tokens else 0.0))
        byte_reduction = max(0.0, 1.0 - (returned_bytes / raw_bytes if raw_bytes else 0.0))
        runs.append(
            BenchmarkRun(
                mode=mode, raw_bytes=raw_bytes, returned_bytes=returned_bytes,
                raw_estimated_tokens=raw_tokens, returned_estimated_tokens=returned_tokens,
                required_facts_retained=retained, missing_required_facts=missing, tool_calls=3,
                latency_ms=round(elapsed, 3), reduction_ratio=token_reduction, byte_reduction_ratio=byte_reduction,
            )
        )
    target_runs = [run for run in runs if run.mode in {"balanced", "max"}]
    meets = any(run.reduction_ratio >= 0.50 and not run.missing_required_facts for run in target_runs)
    return BenchmarkReport(
        fixture_hash=manifest.fixture_hash, raw_context_bytes=raw_bytes,
        raw_context_estimated_tokens=raw_tokens, token_metric="estimated_tokens",
        required_facts=manifest.required_facts, runs=tuple(runs), meets_target=meets,
    )


def write_report(report: BenchmarkReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report.as_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
