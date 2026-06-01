from __future__ import annotations

import json
from pathlib import Path

from agents_md.generator import has_managed_sections, render_document, render_sections, replace_managed_sections
from agents_md.scanner import scan_repo


def test_scans_package_json_commands(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "packageManager": "pnpm@10.0.0",
                "scripts": {"dev": "vite --host 0.0.0.0", "test": "vitest run", "lint": "eslint ."},
                "devDependencies": {"vite": "^7.0.0", "vitest": "^3.0.0", "typescript": "^5.0.0"},
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "tsconfig.json").write_text(json.dumps({"compilerOptions": {"strict": True}}), encoding="utf-8")

    result = scan_repo(tmp_path)

    commands = {command.category: command.command for command in result.commands}
    assert commands["run"] == "pnpm dev"
    assert commands["test"] == "pnpm test"
    assert "single-test" in commands
    assert any(fact.name == "Vite" for fact in result.stack)


def test_rendered_document_has_managed_sections(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "demo"
version = "0.1.0"
requires-python = ">=3.11"

[project.optional-dependencies]
dev = ["pytest>=9.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
""",
        encoding="utf-8",
    )
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_demo.py").write_text("def test_demo():\n    assert True\n", encoding="utf-8")

    content = render_document(scan_repo(tmp_path), no_dedup=True)

    assert has_managed_sections(content)
    assert "<!-- agents-md:fingerprint " in content
    assert "python -m pytest" in content


def test_replace_managed_sections_preserves_manual_text(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"demo\"\nversion = \"0.1.0\"\n", encoding="utf-8")
    scan = scan_repo(tmp_path)
    original = render_document(scan, no_dedup=True) + "\nManual note.\n"
    sections = render_sections(scan, no_dedup=True)

    updated, changed = replace_managed_sections(original, sections)

    assert "Manual note." in updated
    assert changed == []
