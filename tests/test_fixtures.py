from __future__ import annotations

from pathlib import Path

from agents_md.generator import line_count, render_document
from agents_md.scanner import scan_repo


FIXTURES = Path(__file__).parent / "fixtures" / "repos"


def _render_fixture(name: str) -> str:
    return render_document(scan_repo(FIXTURES / name), no_dedup=True)


def test_python_cli_fixture_output_has_project_run_command() -> None:
    content = _render_fixture("python_cli")

    assert "uv run demo-cli" in content
    assert "uv run agents-md" not in content
    assert "python -m pytest tests/test_demo.py::test_demo -xvs" in content
    assert "No high-confidence" not in content
    assert line_count(content) < 80


def test_typescript_fixture_output_has_high_value_conventions() -> None:
    content = _render_fixture("typescript_app")

    assert "Package Manager: pnpm 10.0.0" in content
    assert "Framework: Next.js 15.3.0" in content
    assert "test: `pnpm test`" in content
    assert "Barrel file detected" in content
    assert "@/components" in content
    assert "`Result<...>` return types appear" in content
    assert "HTTP calls appear centralized" in content
    assert "API_BASE_URL" in content
    assert line_count(content) < 90
