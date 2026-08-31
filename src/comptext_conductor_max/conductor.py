from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

_UNCHECKED = re.compile(r"^\s*[-*]\s*\[ \]\s*(.+?)\s*$")
_TRACK_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_PROJECT_CONTEXT_FILES = (
    "product.md",
    "product-guidelines.md",
    "tech-stack.md",
    "workflow.md",
    "tracks.md",
)


@dataclass(frozen=True, slots=True)
class ConductorState:
    track: str
    directory: Path
    spec_path: Path
    plan_path: Path
    metadata_path: Path | None
    index_path: Path | None
    project_context_paths: tuple[Path, ...]
    track_context_paths: tuple[Path, ...]
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


def _project_context(conductor_root: Path) -> tuple[Path, ...]:
    paths: list[Path] = []
    for name in _PROJECT_CONTEXT_FILES:
        path = conductor_root / name
        if path.is_file():
            paths.append(path)
    style_root = conductor_root / "code_styleguides"
    if style_root.is_dir():
        paths.extend(sorted(path for path in style_root.rglob("*.md") if path.is_file()))
    return tuple(paths)


def detect_conductor(root: Path, track: str) -> ConductorState:
    if _TRACK_NAME.fullmatch(track) is None:
        raise ValueError("invalid Conductor track name")
    canonical = root.resolve()
    conductor_root = canonical / "conductor"
    preferred = conductor_root / "tracks" / track
    candidates = [preferred]
    if not preferred.is_dir() and conductor_root.is_dir():
        candidates.extend(
            path.parent
            for path in conductor_root.glob("**/spec.md")
            if path.parent.name == track
        )
    for directory in candidates:
        spec = directory / "spec.md"
        plan = directory / "plan.md"
        if spec.is_file() and plan.is_file():
            metadata = directory / "metadata.json"
            index = directory / "index.md"
            metadata_path = metadata if metadata.is_file() else None
            index_path = index if index.is_file() else None
            track_context = [spec, plan]
            if metadata_path is not None:
                track_context.append(metadata_path)
            if index_path is not None:
                track_context.append(index_path)
            return ConductorState(
                track=track,
                directory=directory,
                spec_path=spec,
                plan_path=plan,
                metadata_path=metadata_path,
                index_path=index_path,
                project_context_paths=_project_context(conductor_root),
                track_context_paths=tuple(track_context),
                current_step=_current_step(plan),
            )
    raise FileNotFoundError(f"Conductor track not found: {track}")
