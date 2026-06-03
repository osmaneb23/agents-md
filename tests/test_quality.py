from __future__ import annotations

from pathlib import Path

from agents_md.quality import lint_file


def test_scores_core_sections(tmp_path: Path) -> None:
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        """# AGENTS.md

## Commands
- install: `python -m pip install -e .[dev]`
- test: `python -m pytest -x`

## Testing
- Single test: `python -m pytest tests/test_quality.py::test_scores_core_sections -xvs`

## Boundaries
### Always Do
- Run focused tests.
### Ask First
- Ask before changing scoring weights.
### Never Do
- Never commit secrets.
""",
        encoding="utf-8",
    )

    result = lint_file(agents)

    assert result.score >= 85
    assert not [issue for issue in result.issues if issue.kind == "boundaries"]


def test_flags_readme_duplication(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("Run `python -m pytest` before committing.\n", encoding="utf-8")
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        """# AGENTS.md

## Commands
- test: `python -m pytest`
- lint: `ruff check .`

## Testing
- Single test: `python -m pytest tests/test_quality.py::test_scores_core_sections -xvs`

## Boundaries
### Always Do
- Run tests.
### Ask First
- Ask before migrations.
### Never Do
- Never commit secrets.
""",
        encoding="utf-8",
    )

    result = lint_file(agents)

    assert any(issue.kind == "readme-duplication" for issue in result.issues)


def test_flags_readme_duplication_with_lowercase_readme(tmp_path: Path) -> None:
    (tmp_path / "readme.md").write_text("Run `python -m pytest` before committing.\n", encoding="utf-8")
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        """# AGENTS.md

## Commands
- test: `python -m pytest`
- lint: `ruff check .`

## Testing
- Single test: `python -m pytest tests/test_quality.py::test_scores_core_sections -xvs`

## Boundaries
### Always Do
- Run tests.
### Ask First
- Ask before migrations.
### Never Do
- Never commit secrets.
""",
        encoding="utf-8",
    )

    result = lint_file(agents)

    assert any(issue.kind == "readme-duplication" for issue in result.issues)


def test_does_not_flag_ask_before_boundary_duplication(tmp_path: Path) -> None:
    repeated = "Ask before deleting files, rewriting public history, or changing release metadata."
    (tmp_path / "README.md").write_text(repeated + "\n", encoding="utf-8")
    agents = tmp_path / "AGENTS.md"
    agents.write_text(
        f"""# AGENTS.md

## Commands
- install: `python -m pip install -e .[dev]`
- test: `python -m pytest -x`

## Testing
- Single test: `python -m pytest tests/test_quality.py::test_scores_core_sections -xvs`

## Boundaries
### Always Do
- Run focused tests.
### Ask First
- {repeated}
### Never Do
- Never commit secrets.
""",
        encoding="utf-8",
    )

    result = lint_file(agents)

    assert not any(issue.kind == "readme-duplication" for issue in result.issues)
