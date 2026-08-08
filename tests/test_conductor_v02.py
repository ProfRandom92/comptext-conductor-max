from pathlib import Path

from comptext_conductor_max.conductor import detect_conductor


def test_detects_project_and_track_context_paths(tmp_path: Path):
    conductor = tmp_path / "conductor"
    track = conductor / "tracks" / "demo"
    styles = conductor / "code_styleguides"
    track.mkdir(parents=True)
    styles.mkdir(parents=True)
    for name in (
        "product.md",
        "product-guidelines.md",
        "tech-stack.md",
        "workflow.md",
        "tracks.md",
    ):
        (conductor / name).write_text(f"# {name}\n", encoding="utf-8")
    (styles / "python.md").write_text("# Python\n", encoding="utf-8")
    (track / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (track / "plan.md").write_text("- [ ] STEP-1 implement\n", encoding="utf-8")
    (track / "metadata.json").write_text("{}", encoding="utf-8")
    (track / "index.md").write_text("# Track index\n", encoding="utf-8")

    state = detect_conductor(tmp_path, "demo")

    assert state.index_path == track / "index.md"
    assert [path.relative_to(tmp_path).as_posix() for path in state.project_context_paths] == [
        "conductor/product.md",
        "conductor/product-guidelines.md",
        "conductor/tech-stack.md",
        "conductor/workflow.md",
        "conductor/tracks.md",
        "conductor/code_styleguides/python.md",
    ]
    assert [path.name for path in state.track_context_paths] == [
        "spec.md",
        "plan.md",
        "metadata.json",
        "index.md",
    ]
