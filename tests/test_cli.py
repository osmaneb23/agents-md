from __future__ import annotations

from pathlib import Path

from agents_md.cli import main


def test_init_no_llm_writes_agents(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.11"
""",
        encoding="utf-8",
    )

    code = main(["init", "--no-llm", "--force", "--no-symlink"])

    assert code == 0
    assert (tmp_path / "AGENTS.md").is_file()
    assert "## Stack" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")


def test_lint_check_threshold(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text("# AGENTS.md\n\nToo short.\n", encoding="utf-8")

    code = main(["lint", str(agents), "--check", "--threshold", "90"])

    assert code == 1
