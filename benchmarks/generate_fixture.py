import argparse
from pathlib import Path

from comptext_conductor_max.benchmark import generate_fixture

parser = argparse.ArgumentParser()
parser.add_argument("path", type=Path)
parser.add_argument("--seed", type=int, default=20260807)
args = parser.parse_args()
manifest = generate_fixture(args.path, seed=args.seed)
print(manifest.fixture_hash)
