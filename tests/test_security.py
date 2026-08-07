from pathlib import Path

from comptext_conductor_max.security import SecurityPolicy


def test_secret_and_ignore_paths_are_blocked(tmp_path: Path):
    (tmp_path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (tmp_path / ".comptextignore").write_text("private/\n", encoding="utf-8")
    policy = SecurityPolicy.from_root(tmp_path)
    assert not policy.is_path_allowed(tmp_path / ".env")
    assert not policy.is_path_allowed(tmp_path / "ignored.txt")
    assert not policy.is_path_allowed(tmp_path / "private" / "notes.md")
    assert policy.is_path_allowed(tmp_path / "README.md")


def test_path_traversal_and_external_symlink_are_blocked(tmp_path: Path):
    outside = tmp_path.parent / "outside-secret.txt"
    outside.write_text("secret", encoding="utf-8")
    link = tmp_path / "link.txt"
    link.symlink_to(outside)
    policy = SecurityPolicy.from_root(tmp_path)
    assert not policy.is_path_allowed(tmp_path / ".." / outside.name)
    assert not policy.is_path_allowed(link)


def test_binary_and_secret_content_are_not_returned(tmp_path: Path):
    binary = tmp_path / "payload.bin"
    binary.write_bytes(b"abc\x00def")
    secret = tmp_path / "source.txt"
    secret.write_text("api_key = 'sk-example0123456789example'", encoding="utf-8")
    clean = tmp_path / "clean.py"
    clean.write_text("answer = 42\n", encoding="utf-8")
    policy = SecurityPolicy.from_root(tmp_path)
    assert policy.safe_text(binary, max_bytes=1024) is None
    assert policy.safe_text(secret, max_bytes=1024) is None
    assert policy.safe_text(clean, max_bytes=1024) == "answer = 42\n"
