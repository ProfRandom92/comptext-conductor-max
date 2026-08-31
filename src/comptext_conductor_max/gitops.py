from __future__ import annotations

import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

_GENERATED = {"package-lock.json", "pnpm-lock.yaml", "yarn.lock", "uv.lock", "poetry.lock"}
_DIFF_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")


@dataclass(frozen=True, slots=True)
class DiffHunk:
    hunk_id: str
    path: str
    text: str


@dataclass(frozen=True, slots=True)
class DiffSummary:
    files_changed: int
    additions: int
    deletions: int
    source_files: tuple[str, ...]
    test_files: tuple[str, ...]
    generated_omitted: tuple[str, ...]
    binary_omitted: tuple[str, ...]
    hunks: tuple[DiffHunk, ...]
    raw_bytes: int
    returned_bytes: int

    @property
    def avoided_bytes(self) -> int:
        return max(0, self.raw_bytes - self.returned_bytes)


class GitDiffEngine:
    @staticmethod
    def _run(root: Path, *args: str) -> str:
        try:
            proc = subprocess.run(
                ["git", *args],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=20,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise RuntimeError(f"git unavailable: {exc}") from exc
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr.strip() or "git command failed")
        return proc.stdout

    @staticmethod
    def _is_test(path: str) -> bool:
        return path.startswith("tests/") or "/tests/" in f"/{path}" or Path(path).name.startswith("test_")

    def summarize(self, root: Path, *, base: str | None = None, head: str | None = None) -> DiffSummary:
        range_args: list[str] = []
        if base and head:
            range_args = [f"{base}..{head}"]
        elif base:
            range_args = [base]
        else:
            try:
                self._run(root, "rev-parse", "--verify", "HEAD")
            except RuntimeError:
                range_args = []
            else:
                # Compare the full working tree to HEAD so both staged and
                # unstaged tracked changes are represented in one coherent diff.
                range_args = ["HEAD"]
        numstat = self._run(root, "diff", "--no-ext-diff", "--numstat", *range_args)
        patch = self._run(root, "diff", "--no-ext-diff", "--unified=3", *range_args)
        additions = 0
        deletions = 0
        changed: list[str] = []
        generated: list[str] = []
        binary: list[str] = []
        source: list[str] = []
        tests: list[str] = []
        for line in numstat.splitlines():
            parts = line.split("\t", 2)
            if len(parts) != 3:
                continue
            added, deleted, path = parts
            changed.append(path)
            if added == "-" or deleted == "-":
                binary.append(path)
                continue
            additions += int(added)
            deletions += int(deleted)
            if Path(path).name in _GENERATED:
                generated.append(path)
            elif self._is_test(path):
                tests.append(path)
            else:
                source.append(path)

        ignored = set(generated) | set(binary)
        hunks: list[DiffHunk] = []
        current_path: str | None = None
        current_lines: list[str] = []

        def flush() -> None:
            nonlocal current_lines
            if current_path is None or not current_lines or current_path in ignored:
                current_lines = []
                return
            text = "\n".join(current_lines) + "\n"
            digest = hashlib.sha256(f"{current_path}\0{text}".encode()).hexdigest()[:16]
            hunks.append(DiffHunk(digest, current_path, text))
            current_lines = []

        for line in patch.splitlines():
            header = _DIFF_HEADER.match(line)
            if header:
                flush()
                current_path = header.group(2)
                continue
            if line.startswith("@@"):
                flush()
                current_lines = [line]
                continue
            if current_lines:
                current_lines.append(line)
        flush()
        returned_bytes = sum(len(h.text.encode("utf-8")) for h in hunks)
        return DiffSummary(
            files_changed=len(changed),
            additions=additions,
            deletions=deletions,
            source_files=tuple(sorted(source)),
            test_files=tuple(sorted(tests)),
            generated_omitted=tuple(sorted(generated)),
            binary_omitted=tuple(sorted(binary)),
            hunks=tuple(hunks),
            raw_bytes=len(patch.encode("utf-8")),
            returned_bytes=returned_bytes,
        )

    def get_hunk(self, root: Path, hunk_id: str, *, base: str | None = None, head: str | None = None) -> DiffHunk:
        for hunk in self.summarize(root, base=base, head=head).hunks:
            if hunk.hunk_id == hunk_id:
                return hunk
        raise KeyError(f"Unknown hunk id: {hunk_id}")
