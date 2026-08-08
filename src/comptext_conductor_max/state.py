from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TRACK = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True, slots=True)
class ProjectState:
    version: int = 1
    latest_result_sha256: str | None = None
    latest_result_files: tuple[str, ...] = ()
    latest_result_exit_code: int | None = None
    latest_checkpoints: dict[str, str] = field(default_factory=dict)


class ProjectStateStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._state = self._load()

    def _load(self) -> ProjectState:
        if not self.path.is_file():
            return ProjectState()
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            checkpoints = {
                str(track): str(digest)
                for track, digest in dict(data.get("latest_checkpoints", {})).items()
                if _TRACK.fullmatch(str(track)) and _SHA256.fullmatch(str(digest))
            }
            result_sha = data.get("latest_result_sha256")
            if result_sha is not None and _SHA256.fullmatch(str(result_sha)) is None:
                result_sha = None
            files = tuple(
                sorted(
                    {
                        str(path).replace("\\", "/")
                        for path in data.get("latest_result_files", [])
                        if isinstance(path, str) and path and not path.startswith("/") and ".." not in Path(path).parts
                    }
                )
            )
            exit_code = data.get("latest_result_exit_code")
            if exit_code is not None and not isinstance(exit_code, int):
                exit_code = None
            return ProjectState(
                version=1,
                latest_result_sha256=str(result_sha) if result_sha is not None else None,
                latest_result_files=files,
                latest_result_exit_code=exit_code,
                latest_checkpoints=checkpoints,
            )
        except (OSError, TypeError, ValueError, json.JSONDecodeError):
            return ProjectState()

    def _write(self, state: ProjectState) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(state), sort_keys=True, indent=2) + "\n"
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(self.path)
        self._state = state

    def record_result(
        self,
        raw_sha256: str,
        likely_files: tuple[str, ...],
        exit_code: int | None,
    ) -> None:
        if _SHA256.fullmatch(raw_sha256) is None:
            raise ValueError("invalid result SHA-256")
        safe_files = tuple(
            sorted(
                {
                    path.replace("\\", "/")
                    for path in likely_files
                    if path and not path.startswith("/") and ".." not in Path(path).parts
                }
            )
        )
        self._write(
            ProjectState(
                latest_result_sha256=raw_sha256,
                latest_result_files=safe_files,
                latest_result_exit_code=exit_code,
                latest_checkpoints=dict(self._state.latest_checkpoints),
            )
        )

    def record_checkpoint(self, track: str, checkpoint_hash: str) -> None:
        if _TRACK.fullmatch(track) is None:
            raise ValueError("invalid track")
        if _SHA256.fullmatch(checkpoint_hash) is None:
            raise ValueError("invalid checkpoint SHA-256")
        checkpoints = dict(self._state.latest_checkpoints)
        checkpoints[track] = checkpoint_hash
        self._write(
            ProjectState(
                latest_result_sha256=self._state.latest_result_sha256,
                latest_result_files=self._state.latest_result_files,
                latest_result_exit_code=self._state.latest_result_exit_code,
                latest_checkpoints=checkpoints,
            )
        )

    def snapshot(self) -> ProjectState:
        return self._state
