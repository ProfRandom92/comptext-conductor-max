from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .cache import ContentCache
from .checkpoints import Checkpoint, CheckpointStore
from .conductor import detect_conductor
from .config import ProfileName, Settings, budget_profile
from .gitops import GitDiffEngine
from .indexer import RepositoryIndexer
from .results import ResultAnalyzer
from .retrieval import Retriever, SearchResponse
from .security import SecurityPolicy
from .skills import SkillCatalog
from .state import ProjectStateStore
from .stats import StatsLedger
from .tokens import TokenCount, estimate_tokens


@dataclass(frozen=True, slots=True)
class BrokerContext:
    track: str
    current_step: str | None
    task: str
    content: str
    returned_tokens: TokenCount
    budget: int
    budget_exceeded: bool
    omitted_critical: tuple[str, ...]
    truncated_paths: tuple[str, ...] = ()


class ContextBroker:
    def __init__(self, root: Path, external_skill_roots: tuple[Path, ...] = ()) -> None:
        self.root = root.resolve()
        self.settings = Settings(root=self.root)
        self.policy = SecurityPolicy.from_root(self.root)
        state = self.root / ".comptext"
        self.cache = ContentCache(state / "cache")
        self.checkpoints = CheckpointStore(state / "checkpoints")
        self.project_state = ProjectStateStore(state / "project-state.json")
        self.stats = StatsLedger(state / "stats.json")
        self.indexer = RepositoryIndexer(self.root, self.policy, self.cache)
        self.skills = SkillCatalog(root=self.root, external_roots=external_skill_roots)
        self.retriever = Retriever()
        self.git = GitDiffEngine()
        self.results = ResultAnalyzer()

    def _record_cache_delta(self, before_hits: int, before_misses: int) -> None:
        after = self.cache.status()
        for _ in range(max(0, after.hits - before_hits)):
            self.stats.record_cache(hit=True)
        for _ in range(max(0, after.misses - before_misses)):
            self.stats.record_cache(hit=False)

    def _record_search_stats(
        self,
        response: SearchResponse,
        *,
        raw_bytes: int,
        budget_tokens: int,
    ) -> None:
        for _ in response.results:
            self.stats.record_read(full=False)
        returned_text = "\n".join(item.snippet for item in response.results)
        self.stats.record_context(
            raw_bytes=raw_bytes,
            returned_bytes=len(returned_text.encode("utf-8")),
            raw_tokens=(raw_bytes + 3) // 4,
            returned_tokens=estimate_tokens(returned_text).value,
            context_budget=budget_tokens,
            retrieval_results=len(response.results),
        )

    def _index_and_search(
        self,
        query: str,
        *,
        max_results: int,
        max_lines: int,
        budget_tokens: int,
        changed_files: set[str] | None = None,
        failure_files: set[str] | None = None,
        critical_paths: set[str] | None = None,
        preferred_paths: set[str] | None = None,
    ) -> SearchResponse:
        before = self.cache.status()
        repo_index = self.indexer.build()
        skill_index = self.skills.build_skill_index(query)
        all_slices = repo_index.slices + skill_index.slices
        from .models import RepositoryIndex

        index = RepositoryIndex(
            root=repo_index.root,
            slices=all_slices,
            file_count=repo_index.file_count + skill_index.file_count,
            truncated_paths=tuple(
                sorted(set(repo_index.truncated_paths + skill_index.truncated_paths))
            ),
        )
        self._record_cache_delta(before.hits, before.misses)
        response = self.retriever.search(
            index,
            query,
            max_results=max_results,
            max_lines=max_lines,
            budget_tokens=budget_tokens,
            changed_files=changed_files,
            failure_files=failure_files,
            critical_paths=critical_paths,
            preferred_paths=preferred_paths,
        )
        raw_bytes = sum(len(item.text.encode("utf-8")) for item in index.slices)
        self._record_search_stats(response, raw_bytes=raw_bytes, budget_tokens=budget_tokens)

        # Skill telemetry tracking
        discovered = self.skills.discover_skills()
        selected_skills = [
            r for r in response.results if any(reason.startswith("skill-") for reason in r.reasons)
        ]
        meta_bytes = sum(
            len(item.text.encode("utf-8")) for item in index.slices if item.kind == "skill_metadata"
        )
        returned_meta = sum(
            len(r.snippet.encode("utf-8"))
            for r in response.results
            if "skill-metadata" in r.reasons
        )
        returned_instr = sum(
            len(r.snippet.encode("utf-8"))
            for r in response.results
            if "skill-instruction" in r.reasons
        )
        returned_res = sum(
            len(r.snippet.encode("utf-8"))
            for r in response.results
            if "skill-resource" in r.reasons
        )
        self.stats.record_skills(
            discovered=len(discovered),
            candidates=len(discovered),
            selected=len(selected_skills),
            metadata_considered=meta_bytes,
            metadata_returned=returned_meta,
            instruction_returned=returned_instr,
            resource_returned=returned_res,
        )
        return response

    def search(
        self,
        query: str | None = None,
        *,
        ref: str | None = None,
        max_results: int = 5,
        max_lines: int = 180,
        budget_tokens: int = 18_000,
    ) -> SearchResponse:
        if (query is None) == (ref is None):
            raise ValueError("provide exactly one of query or ref")
        bounded_results = min(20, max(1, max_results))
        bounded_lines = min(1_000, max(1, max_lines))
        bounded_budget = min(30_000, max(1, budget_tokens))
        if ref is not None:
            before = self.cache.status()
            repo_index = self.indexer.build()
            skill_index = self.skills.build_skill_index()
            all_slices = repo_index.slices + skill_index.slices
            from .models import RepositoryIndex

            index = RepositoryIndex(
                root=repo_index.root,
                slices=all_slices,
                file_count=repo_index.file_count + skill_index.file_count,
                truncated_paths=tuple(
                    sorted(set(repo_index.truncated_paths + skill_index.truncated_paths))
                ),
            )
            self._record_cache_delta(before.hits, before.misses)
            response = self.retriever.expand_ref(
                index,
                ref,
                max_lines=bounded_lines,
                budget_tokens=bounded_budget,
            )
            raw_bytes = sum(len(item.text.encode("utf-8")) for item in index.slices)
            self._record_search_stats(
                response,
                raw_bytes=raw_bytes,
                budget_tokens=bounded_budget,
            )
            return response
        return self._index_and_search(
            query or "",
            max_results=bounded_results,
            max_lines=bounded_lines,
            budget_tokens=bounded_budget,
        )

    def context(
        self,
        *,
        track: str,
        task: str,
        profile: ProfileName = "balanced",
        budget: int | None = None,
    ) -> BrokerContext:
        state = detect_conductor(self.root, track)
        hard_limit = budget_profile(self.settings, profile).hard_limit
        if budget is not None:
            hard_limit = min(hard_limit, max(1, budget))
        changed: set[str] = set()
        runtime_state = self.project_state.snapshot()
        failures = {
            path
            for path in runtime_state.latest_result_files
            if self.policy.is_path_allowed(self.root / path)
        }
        try:
            diff = self.git.summarize(self.root)
            changed.update(diff.source_files)
            changed.update(diff.test_files)
            self.stats.record_diff(raw_bytes=diff.raw_bytes, returned_bytes=0)
        except RuntimeError:
            pass
        query_parts = [track, state.current_step or "", task]
        critical = {
            state.spec_path.relative_to(self.root).as_posix(),
            state.plan_path.relative_to(self.root).as_posix(),
        }
        preferred = {path.relative_to(self.root).as_posix() for path in state.project_context_paths}
        for path in (state.metadata_path, state.index_path):
            if path is not None:
                preferred.add(path.relative_to(self.root).as_posix())
        checkpoint_hash = runtime_state.latest_checkpoints.get(track)
        if checkpoint_hash is not None:
            try:
                checkpoint = self.checkpoints.load(checkpoint_hash)
                query_parts.extend((checkpoint.step, checkpoint.next_step or ""))
                preferred.update(
                    path
                    for path in checkpoint.files_changed
                    if self.policy.is_path_allowed(self.root / path)
                )
            except (KeyError, OSError, ValueError):
                pass
        query = " ".join(part for part in query_parts if part)
        response = self._index_and_search(
            query,
            max_results=12,
            max_lines=320,
            budget_tokens=max(1, hard_limit - self.settings.safety_margin),
            changed_files=changed,
            failure_files=failures,
            critical_paths=critical,
            preferred_paths=preferred,
        )
        blocks = [
            f"## {item.path}:{item.start_line}-{item.end_line}\n{item.snippet}"
            for item in response.results
        ]
        content = "\n\n".join(blocks)
        count = estimate_tokens(content)
        return BrokerContext(
            track=track,
            current_step=state.current_step,
            task=task,
            content=content,
            returned_tokens=count,
            budget=hard_limit,
            budget_exceeded=response.budget_exceeded or count.value > hard_limit,
            omitted_critical=response.omitted_critical,
            truncated_paths=response.truncated_paths,
        )

    def diff(self, hunk_id: str | None = None, *, max_lines: int = 400) -> dict[str, Any]:
        if hunk_id:
            hunk = self.git.get_hunk(self.root, hunk_id)
            limit = min(1_000, max(1, max_lines))
            lines = hunk.text.splitlines()
            selected = lines[:limit]
            return {
                "hunk_id": hunk.hunk_id,
                "path": hunk.path,
                "text": "\n".join(selected) + ("\n" if selected else ""),
                "truncated": len(lines) > limit,
                "total_lines": len(lines),
            }
        summary = self.git.summarize(self.root)
        payload: dict[str, Any] = {
            "files_changed": summary.files_changed,
            "additions": summary.additions,
            "deletions": summary.deletions,
            "source_files": list(summary.source_files),
            "test_files": list(summary.test_files),
            "generated_omitted": list(summary.generated_omitted),
            "binary_omitted": list(summary.binary_omitted),
            "hunks": [{"hunk_id": hunk.hunk_id, "path": hunk.path} for hunk in summary.hunks],
            "raw_bytes": summary.raw_bytes,
        }
        import json

        returned_bytes = len(json.dumps(payload, sort_keys=True).encode("utf-8"))
        payload["returned_bytes"] = returned_bytes
        payload["avoided_bytes"] = max(0, summary.raw_bytes - returned_bytes)
        self.stats.record_diff(raw_bytes=summary.raw_bytes, returned_bytes=returned_bytes)
        return payload

    def result(
        self,
        log: str | None = None,
        *,
        log_path: str | None = None,
        exit_code: int | None = None,
        max_lines: int = 120,
    ) -> dict[str, Any]:
        if (log is None) == (log_path is None):
            raise ValueError("provide exactly one of log or log_path")
        source: str | Path
        if log_path is not None:
            source = self.policy.resolve_explicit_file(Path(log_path))
        else:
            source = log or ""
        bounded_lines = min(500, max(1, max_lines))
        summary = self.results.analyze(source, exit_code=exit_code, max_lines=bounded_lines)
        self.stats.record_log(raw_bytes=summary.raw_bytes, returned_bytes=summary.returned_bytes)
        self.project_state.record_result(
            summary.raw_sha256,
            summary.likely_files,
            summary.exit_code,
        )
        return asdict(summary)

    def checkpoint_save(self, checkpoint: Checkpoint) -> dict[str, Any]:
        stored = self.checkpoints.save(checkpoint)
        self.project_state.record_checkpoint(checkpoint.track, stored.checkpoint_hash)
        return {
            "checkpoint_hash": stored.checkpoint_hash,
            "track": checkpoint.track,
            "step": checkpoint.step,
            "version": checkpoint.version,
        }

    def stats_snapshot(self) -> dict[str, Any]:
        snap = self.stats.snapshot()
        data = asdict(snap)
        data["compression_ratio"] = snap.compression_ratio
        data["reduction_ratio"] = snap.reduction_ratio
        data["token_metric"] = "estimated_tokens"
        return data
