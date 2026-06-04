from __future__ import annotations

from pathlib import Path

from agents_md.fingerprint import compare_fingerprints, fingerprint_repo


def test_fingerprint_includes_docs_and_env_examples_but_excludes_output_aliases(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"demo\"\nversion = \"0.1.0\"\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# Demo\n\nRun `python -m pytest`.\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("DATABASE_URL=\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "guide.md").write_text("Use the shared API client.\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("generated output\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").symlink_to("AGENTS.md")

    files = fingerprint_repo(tmp_path)["files"]

    assert "README.md" in files
    assert ".env.example" in files
    assert "docs/guide.md" in files
    assert "pyproject.toml" in files
    assert "AGENTS.md" not in files
    assert "CLAUDE.md" not in files


def test_fingerprint_diff_reports_markdown_and_env_example_changes(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("# Demo\n\nRun tests.\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("DATABASE_URL=\n", encoding="utf-8")

    old = fingerprint_repo(tmp_path)
    (tmp_path / "README.md").write_text("# Demo\n\nRun `python -m pytest -q`.\n", encoding="utf-8")
    (tmp_path / ".env.example").write_text("DATABASE_URL=\nAPI_BASE_URL=\n", encoding="utf-8")

    diff = compare_fingerprints(old, fingerprint_repo(tmp_path))

    assert "README.md" in diff["changed"]
    assert ".env.example" in diff["changed"]
