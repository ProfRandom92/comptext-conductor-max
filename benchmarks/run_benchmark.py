import argparse
import tempfile
from pathlib import Path

from comptext_conductor_max.benchmark import generate_fixture, run_benchmark, write_report

parser = argparse.ArgumentParser()
parser.add_argument("--output", type=Path, default=Path("benchmarks/results/latest.json"))
parser.add_argument("--seed", type=int, default=20260807)
args = parser.parse_args()
with tempfile.TemporaryDirectory(prefix="ct-conductor-benchmark-") as tmp:
    manifest = generate_fixture(Path(tmp) / "repo", seed=args.seed)
    report = run_benchmark(manifest)
write_report(report, args.output)
print(args.output)
if not report.meets_target:
    raise SystemExit(1)
