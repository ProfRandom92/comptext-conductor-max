from pathlib import Path

from comptext_conductor_max.results import ResultAnalyzer


def test_large_test_log_keeps_failure_and_discards_noise(tmp_path: Path):
    log = tmp_path / "pytest.log"
    noise = [f"noise line {i}" for i in range(5000)]
    core = [
        "FAILED tests/test_map_loader.py::test_legacy_coordinates - assert 0 == 12",
        "Expected: 12",
        "Actual: 0",
        "184 passed, 1 failed in 2.4s",
    ]
    log.write_text("\n".join(noise[:2500] + core + noise[2500:]), encoding="utf-8")
    result = ResultAnalyzer().analyze(log, exit_code=1, max_lines=30)
    assert result.exit_code == 1
    assert result.passed == 184
    assert result.failed == 1
    assert any("test_legacy_coordinates" in line for line in result.relevant_lines)
    assert "tests/test_map_loader.py" in result.likely_files
    assert len(result.relevant_lines) <= 30
    assert result.avoided_bytes > 0


def test_compiler_diagnostic_and_expected_actual_are_preserved():
    text = "build start\nsrc/core.py:41:5: error: coordinate mismatch\nExpected: 12\nActual: 0\nbuild failed"
    result = ResultAnalyzer().analyze(text, exit_code=1, max_lines=10)
    assert "src/core.py" in result.likely_files
    assert result.expected == "12"
    assert result.actual == "0"
    assert any("coordinate mismatch" in line for line in result.relevant_lines)


def test_secret_shaped_log_lines_are_redacted():
    text = "start\nTOKEN=abcdefghijklmnopqrstuvwxyz123456\nERROR safe failure\n"
    result = ResultAnalyzer().analyze(text, exit_code=1, max_lines=10)
    joined = "\n".join(result.relevant_lines)
    assert "abcdefghijklmnopqrstuvwxyz123456" not in joined
    assert "safe failure" in joined
