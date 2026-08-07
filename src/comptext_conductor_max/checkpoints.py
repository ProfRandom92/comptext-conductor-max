from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class Checkpoint(BaseModel):
    model_config = ConfigDict(frozen=True)
    version: int = 1
    track: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    step: str = Field(min_length=1)
    status: str = Field(min_length=1)
    decisions: dict[str, str] = Field(default_factory=dict)
    files_changed: tuple[str, ...] = ()
    tests_passed: int = Field(default=0, ge=0)
    tests_failed: int = Field(default=0, ge=0)
    next_step: str | None = None

    def canonical_json(self) -> str:
        return json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def digest(self) -> str:
        return hashlib.sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class StoredCheckpoint:
    checkpoint_hash: str
    json_path: Path
    markdown_path: Path


class CheckpointStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _track_dir(self, track: str) -> Path:
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", track) is None:
            raise ValueError("invalid checkpoint track")
        directory = (self.root / track).resolve()
        try:
            directory.relative_to(self.root)
        except ValueError as exc:
            raise ValueError("checkpoint track escapes store") from exc
        return directory

    def save(self, checkpoint: Checkpoint) -> StoredCheckpoint:
        digest = checkpoint.digest()
        directory = self._track_dir(checkpoint.track)
        directory.mkdir(parents=True, exist_ok=True)
        json_path = directory / f"{digest}.json"
        markdown_path = directory / f"{digest}.md"
        payload = checkpoint.canonical_json() + "\n"
        tmp = json_path.with_suffix(".json.tmp")
        tmp.write_text(payload, encoding="utf-8")
        tmp.replace(json_path)
        decisions = "\n".join(f"- {key}: {value}" for key, value in sorted(checkpoint.decisions.items())) or "- none"
        files = "\n".join(f"- {name}" for name in checkpoint.files_changed) or "- none"
        markdown = (
            f"# Checkpoint {checkpoint.track} / {checkpoint.step}\n\n"
            f"Status: {checkpoint.status}\n\n## Decisions\n{decisions}\n\n"
            f"## Files changed\n{files}\n\nTests: {checkpoint.tests_passed} passed / {checkpoint.tests_failed} failed\n\n"
            f"Next: {checkpoint.next_step or 'none'}\n\nHash: `{digest}`\n"
        )
        markdown_path.write_text(markdown, encoding="utf-8")
        return StoredCheckpoint(digest, json_path, markdown_path)

    def load(self, checkpoint_hash: str) -> Checkpoint:
        if re.fullmatch(r"[0-9a-f]{64}", checkpoint_hash) is None:
            raise ValueError("invalid checkpoint hash")
        matches = list(self.root.glob(f"*/{checkpoint_hash}.json"))
        if len(matches) != 1:
            raise KeyError(f"checkpoint not found: {checkpoint_hash}")
        return Checkpoint.model_validate_json(matches[0].read_text(encoding="utf-8"))

    def list(self, track: str | None = None) -> tuple[StoredCheckpoint, ...]:
        paths = sorted(self._track_dir(track).glob("*.json")) if track else sorted(self.root.glob("*/*.json"))
        return tuple(StoredCheckpoint(path.stem, path, path.with_suffix(".md")) for path in paths)
