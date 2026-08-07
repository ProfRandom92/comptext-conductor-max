from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_UNCHECKED = re.compile(r"^\s*[-*]\s*\[ \]\s*(.+?)\s*$")


@dataclass(frozen=True, slots=True)
class ConductorState:
    track: str
    directory: Path
    spec_path: Path
    plan_path: Path
    metadata_path: Path | None
    current_step: str | None


def _current_step(plan: Path) -> str | None:
    try:
        lines = plan.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None
    for line in lines:
        match = _UNCHECKED.match(line)
        if match:
            return match.group(1)
    return None


def detect_conductor(root: Path, track: str) -> ConductorState:
    canonical = root.resolve()
    preferred = canonical / "conductor" / "tracks" / track
    candidates = [preferred]
    if not preferred.is_dir():
        candidates.extend(
            path.parent for path in (canonical / "conductor").glob("**/spec.md") if path.parent.name == track
        )
    for directory in candidates:
        spec = directory / "spec.md"
        plan = directory / "plan.md"
        if spec.is_file() and plan.is_file():
            metadata = directory / "metadata.json"
            return ConductorState(
                track=track,
                directory=directory,
                spec_path=spec,
                plan_path=plan,
                metadata_path=metadata if metadata.is_file() else None,
                current_step=_current_step(plan),
            )
    raise FileNotFoundError(f"Conductor track not found: {track}")
