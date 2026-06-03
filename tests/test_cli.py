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


def test_init_merge_preserves_hand_written_file(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.11"
""",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("# Existing Notes\n\nKeep this hand-written paragraph.\n", encoding="utf-8")

    code = main(["init", "--no-llm", "--merge", "--no-symlink"])

    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert code == 0
    assert "Keep this hand-written paragraph." in content
    assert "<!-- agents-md:start:stack -->" in content


def test_init_merge_skips_llm_synthesis(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.11"
""",
        encoding="utf-8",
    )
    (tmp_path / "AGENTS.md").write_text("# Existing Notes\n\nKeep this exact text.\n", encoding="utf-8")

    code = main(["init", "--merge", "--no-symlink"])

    captured = capsys.readouterr()
    content = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert code == 0
    assert "LLM synthesis skipped in --merge mode" in captured.err
    assert "Keep this exact text." in content


def test_update_without_llm_key_reports_static_fallback(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    for name in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.11"
""",
        encoding="utf-8",
    )
    assert main(["init", "--no-llm", "--force", "--no-symlink"]) == 0
    capsys.readouterr()

    code = main(["update", "AGENTS.md"])

    captured = capsys.readouterr()
    assert code == 0
    assert "Proceeding with static update." in captured.err
