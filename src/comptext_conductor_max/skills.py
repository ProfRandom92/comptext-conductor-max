from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml  # type: ignore[import-untyped]

from .models import IndexedSlice, RepositoryIndex


@dataclass(frozen=True, slots=True)
class SkillMetadata:
    name: str
    description: str
    source_path: str
    content_hash: str
    is_trusted: bool = False
    body_text: str | None = None


@dataclass(frozen=True, slots=True)
class SkillPackage:
    metadata: SkillMetadata
    instruction_text: str
    resources: dict[str, str]
    content_hash: str


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", re.DOTALL)


def parse_skill_frontmatter(skill_md_path: Path, is_trusted: bool = False) -> SkillMetadata | None:
    if not skill_md_path.exists() or not skill_md_path.is_file():
        return None
    try:
        content = skill_md_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    match = _FRONTMATTER_RE.match(content)
    if not match:
        return None

    frontmatter_text = match.group(1)
    try:
        data = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError:
        return None

    if not isinstance(data, dict):
        return None

    name = data.get("name")
    description = data.get("description")

    if not isinstance(name, str) or not isinstance(description, str):
        return None

    name = name.strip()
    description = description.strip()

    if not name or not description:
        return None

    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    return SkillMetadata(
        name=name,
        description=description,
        source_path=str(skill_md_path.resolve()),
        content_hash=content_hash,
        is_trusted=is_trusted,
        # L1 discovery must remain metadata-only. Instructions are loaded only after routing.
        body_text=None,
    )


class SkillCatalog:
    def __init__(self, root: Path | None = None, external_roots: tuple[Path, ...] = ()) -> None:
        self.root = root or Path.cwd()
        env_external = os.environ.get("CT_SKILLS_ROOT")
        ext_list = list(external_roots)
        if env_external and Path(env_external).exists():
            ext_list.append(Path(env_external))
        self.external_roots = tuple(ext_list)
        self._cache: dict[str, SkillMetadata] = {}

    def discover_skills(self) -> tuple[SkillMetadata, ...]:
        discovered: list[SkillMetadata] = []
        seen_names: set[str] = set()

        # 1. Project local skills (.agents/skills) -> Trusted
        workspace_skills = self.root / ".agents" / "skills"
        if workspace_skills.exists() and workspace_skills.is_dir():
            for skill_md in workspace_skills.glob("**/SKILL.md"):
                meta = parse_skill_frontmatter(skill_md, is_trusted=True)
                if meta and meta.name not in seen_names:
                    discovered.append(meta)
                    seen_names.add(meta.name)
                    self._cache[meta.name] = meta

        # 2. External skills roots -> Untrusted data boundary
        for ext_root in self.external_roots:
            if ext_root.exists() and ext_root.is_dir():
                for skill_md in ext_root.glob("**/SKILL.md"):
                    meta = parse_skill_frontmatter(skill_md, is_trusted=False)
                    if meta and meta.name not in seen_names:
                        discovered.append(meta)
                        seen_names.add(meta.name)
                        self._cache[meta.name] = meta

        return tuple(discovered)

    def is_trusted(self, skill_name: str) -> bool:
        meta = self._cache.get(skill_name)
        if meta:
            return meta.is_trusted
        return False

    def rank_skills(
        self,
        query_or_task: str,
        candidates: tuple[SkillMetadata, ...] | None = None,
        threshold: int = 25,
    ) -> tuple[SkillMetadata, ...]:
        pool = candidates if candidates is not None else self.discover_skills()
        if not pool or not query_or_task.strip():
            return ()

        query_tokens = set(re.findall(r"[a-z0-9]+", query_or_task.lower()))
        if not query_tokens:
            return ()

        scored: list[tuple[int, SkillMetadata]] = []
        for meta in pool:
            score = 0
            name_tokens = set(re.findall(r"[a-z0-9]+", meta.name.lower()))
            desc_tokens = set(re.findall(r"[a-z0-9]+", meta.description.lower()))

            name_overlap = len(query_tokens & name_tokens)
            desc_overlap = len(query_tokens & desc_tokens)

            # High weight for skill name and description matches
            score += name_overlap * 30
            score += desc_overlap * 15

            # Stage 2 is intentionally bounded to L1-promising candidates only. It lets
            # instruction terminology disambiguate a metadata match without putting every
            # SKILL.md body in the generic retrieval pool.
            if 0 < score < threshold:
                body = self.get_skill_instruction(meta.name) or ""
                body_overlap = len(query_tokens & set(re.findall(r"[a-z0-9]+", body.lower())))
                score += body_overlap * 8
            if score >= threshold:
                scored.append((score, meta))

        scored.sort(key=lambda item: (-item[0], item[1].name))
        return tuple(meta for score, meta in scored)

    def get_skill_instruction(self, skill_name: str) -> str | None:
        meta = self._cache.get(skill_name)
        if not meta:
            self.discover_skills()
            meta = self._cache.get(skill_name)
        if not meta:
            return None
        try:
            content = Path(meta.source_path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return None
        match = _FRONTMATTER_RE.match(content)
        return match.group(2).strip() if match else None

    def get_skill_resource(self, skill_name: str, resource_rel_path: str) -> str | None:
        meta = self._cache.get(skill_name)
        if not meta:
            self.discover_skills()
            meta = self._cache.get(skill_name)
        if not meta:
            return None

        resolved_skill_dir = Path(meta.source_path).parent.resolve()
        try:
            target_file = (resolved_skill_dir / resource_rel_path).resolve(strict=False)
        except (OSError, ValueError):
            return None

        # Prevent path traversal outside resolved_skill_dir
        if not target_file.is_relative_to(resolved_skill_dir) or target_file == resolved_skill_dir:
            return None

        if target_file.is_symlink():
            return None

        if target_file.exists() and target_file.is_file():
            try:
                return target_file.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                return None
        return None

    def build_skill_index(self, query_or_task: str | None = None) -> RepositoryIndex:
        skills = self.discover_skills()
        selected = {item.name for item in self.rank_skills(query_or_task or "", skills)}
        slices: list[IndexedSlice] = []
        for meta in skills:
            # L1 Metadata slice
            meta_text = f"Skill: {meta.name}\nDescription: {meta.description}"
            m_hash = hashlib.sha256(meta_text.encode("utf-8")).hexdigest()
            slices.append(
                IndexedSlice(
                    path=meta.source_path,
                    start_line=1,
                    end_line=5,
                    text=meta_text,
                    content_hash=m_hash,
                    kind="skill_metadata",
                    symbols=(meta.name,),
                )
            )

            # L2 instructions are admitted only after bounded routing selection.
            if meta.name in selected:
                instruction = self.get_skill_instruction(meta.name)
                if not instruction:
                    continue
                i_hash = hashlib.sha256(instruction.encode("utf-8")).hexdigest()
                slices.append(
                    IndexedSlice(
                        path=meta.source_path,
                        start_line=6,
                        end_line=6 + len(instruction.splitlines()),
                        text=instruction,
                        content_hash=i_hash,
                        kind="skill_instruction",
                        symbols=(meta.name,),
                    )
                )

        return RepositoryIndex(
            root=str(self.root),
            slices=tuple(slices),
            file_count=len(skills),
        )
