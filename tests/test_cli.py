from __future__ import annotations

from pathlib import Path

from agents_md.cli import main
from agents_md.fingerprint import compare_fingerprints, extract_fingerprint, fingerprint_repo


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


def test_init_dry_run_scores_without_writing_file(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.11"

[project.scripts]
demo = "demo:main"
""",
        encoding="utf-8",
    )

    code = main(["init", "--no-llm", "--dry-run", "--no-symlink"])

    captured = capsys.readouterr()
    assert code == 0
    assert not (tmp_path / "AGENTS.md").exists()
    assert "Would write" in captured.out
    assert "quality " in captured.out
    assert "not scored in dry-run" not in captured.out


def test_init_verbose_prints_warnings_without_generated_section(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "package.json").write_text(
        """{
  "scripts": {
    "test": "node --test"
  }
}
""",
        encoding="utf-8",
    )

    code = main(["init", "--no-llm", "--dry-run", "--no-symlink", "--verbose"])

    captured = capsys.readouterr()
    assert code == 0
    assert "Warnings:" in captured.err
    assert "js-package-manager-fallback" in captured.err
    assert "no-single-test" in captured.err
    assert "## Warnings" not in captured.out


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


def test_update_with_provider_key_skips_llm_and_preserves_manual_text(
    tmp_path: Path, monkeypatch, capsys
) -> None:
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
    assert main(["init", "--no-llm", "--force", "--no-symlink"]) == 0
    generated = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    manual_top = "# Manual Notes\n\nKeep this top note exactly.\n\n"
    manual_bottom = "\nKeep this bottom note exactly.\n"
    (tmp_path / "AGENTS.md").write_text(manual_top + generated + manual_bottom, encoding="utf-8")

    def fail_synthesis(*args, **kwargs):
        raise AssertionError("update mode must not call LLM synthesis")

    monkeypatch.setattr("agents_md.cli.synthesize_with_llm", fail_synthesis)
    capsys.readouterr()

    code = main(["update", "AGENTS.md"])

    captured = capsys.readouterr()
    updated = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert code == 0
    assert "LLM synthesis skipped in update mode to preserve manual content." in captured.err
    assert updated.startswith(manual_top)
    assert updated.endswith(manual_bottom)


def test_update_refreshes_existing_fingerprint(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text(
        """[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.11"
""",
        encoding="utf-8",
    )
    assert main(["init", "--no-llm", "--force", "--no-symlink"]) == 0

    pyproject.write_text(
        """[project]
name = "demo"
version = "0.1.1"
requires-python = ">=3.11"
""",
        encoding="utf-8",
    )

    code = main(["update", "AGENTS.md", "--no-llm"])

    refreshed = extract_fingerprint((tmp_path / "AGENTS.md").read_text(encoding="utf-8"))
    assert code == 0
    assert refreshed is not None
    assert compare_fingerprints(refreshed, fingerprint_repo(tmp_path))["changed"] == []


def test_diff_reports_readme_generation_input_change(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# Demo\n\nRun tests.\n", encoding="utf-8")
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
    (tmp_path / "README.md").write_text("# Demo\n\nRun `python -m pytest -q`.\n", encoding="utf-8")

    code = main(["diff", "AGENTS.md"])

    captured = capsys.readouterr()
    assert code == 0
    assert "changed: README.md" in captured.out
    assert "Recommendation: run `agents-md update` to sync managed sections." in captured.out


def test_diff_reports_no_generation_input_changes(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
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

    code = main(["diff", "AGENTS.md"])

    captured = capsys.readouterr()
    assert code == 0
    assert "No relevant generation input changes detected." in captured.out


def test_requested_provider_without_key_reports_specific_env_var(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.11"
""",
        encoding="utf-8",
    )

    code = main(["init", "--provider", "anthropic", "--force", "--no-symlink"])

    captured = capsys.readouterr()
    assert code == 2
    assert "ANTHROPIC_API_KEY is not set for provider anthropic" in captured.err
