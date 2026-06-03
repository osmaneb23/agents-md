from __future__ import annotations

import json
from pathlib import Path

from agents_md.generator import has_managed_sections, render_document, render_sections, replace_managed_sections
from agents_md.scanner import scan_repo
from agents_md.dedup import read_markdown_facts


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


def test_boundaries_are_repo_neutral_for_generic_repos(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps(
            {
                "scripts": {
                    "test": "vitest run",
                    "db:migrate": "prisma migrate deploy",
                },
                "devDependencies": {"vitest": "^3.0.0"},
            }
        ),
        encoding="utf-8",
    )

    content = render_document(scan_repo(tmp_path), no_dedup=True)

    assert "Ask before running `npm run db:migrate`" in content
    assert "quality score thresholds" not in content
    assert "deduplication rules" not in content
    assert "managed-section marker formats" not in content
    assert "downloaded browser sidecar metadata" not in content
    assert "Never modify `vendor/`" in content


def test_replace_managed_sections_preserves_manual_text(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname = \"demo\"\nversion = \"0.1.0\"\n", encoding="utf-8")
    scan = scan_repo(tmp_path)
    original = render_document(scan, no_dedup=True) + "\nManual note.\n"
    sections = render_sections(scan, no_dedup=True)

    updated, changed = replace_managed_sections(original, sections)

    assert "Manual note." in updated
    assert changed == []


def test_detects_high_value_typescript_conventions(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"packageManager": "pnpm@10.0.0", "dependencies": {"typescript": "^5.0.0"}}),
        encoding="utf-8",
    )
    (tmp_path / "tsconfig.json").write_text(
        json.dumps({"compilerOptions": {"strict": True, "paths": {"@/*": ["src/*"]}}}),
        encoding="utf-8",
    )
    components = tmp_path / "src" / "components"
    components.mkdir(parents=True)
    (components / "Button.tsx").write_text("export function Button() { return null }\n", encoding="utf-8")
    (components / "index.ts").write_text("export { Button } from './Button'\n", encoding="utf-8")
    api = tmp_path / "src" / "api"
    api.mkdir()
    (api / "client.ts").write_text(
        """export async function request(path: string): Promise<Result<string, Error>> {
  try {
    return await fetch(path) as Result<string, Error>
  } catch (error) {
    return { ok: false, error }
  }
}
""",
        encoding="utf-8",
    )
    (tmp_path / ".env.example").write_text("API_BASE_URL=\nPUBLIC_SITE_URL=\n", encoding="utf-8")
    fixtures = tmp_path / "tests" / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "user.json").write_text("{}", encoding="utf-8")

    result = scan_repo(tmp_path)
    conventions = "\n".join(convention.text for convention in result.conventions)

    assert "named exports" in conventions
    assert "Barrel file detected" in conventions
    assert "@/components" in conventions
    assert "Result<...>" in conventions
    assert "HTTP calls appear centralized" in conventions
    assert "API_BASE_URL" in conventions
    assert "tests/fixtures" in conventions


def test_uv_run_command_uses_project_script(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "demo-cli"
version = "0.1.0"

[project.scripts]
demo-cli = "demo:main"
other = "demo:other"
""",
        encoding="utf-8",
    )

    result = scan_repo(tmp_path)
    commands = {command.category: command.command for command in result.commands}

    assert commands["install"] == "uv sync"
    assert commands["run"] == "uv run demo-cli"


def test_uv_without_project_script_omits_run_command(tmp_path: Path) -> None:
    (tmp_path / "uv.lock").write_text("", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(
        """[project]
name = "library"
version = "0.1.0"
""",
        encoding="utf-8",
    )

    result = scan_repo(tmp_path)
    commands = {command.category: command.command for command in result.commands}

    assert commands["install"] == "uv sync"
    assert "run" not in commands


def test_source_skip_dirs_are_repo_relative(tmp_path: Path) -> None:
    project = tmp_path / "build" / "myapp"
    src = project / "src"
    src.mkdir(parents=True)
    (project / "package.json").write_text(json.dumps({"dependencies": {"typescript": "^5.0.0"}}), encoding="utf-8")
    (src / "index.ts").write_text("export const value = 1\n", encoding="utf-8")

    result = scan_repo(project)
    conventions = "\n".join(convention.text for convention in result.conventions)

    assert "named exports" in conventions


def test_api_wrapper_detection_uses_repo_relative_path(tmp_path: Path) -> None:
    project = tmp_path / "services" / "myapp"
    src = project / "src"
    src.mkdir(parents=True)
    (project / "package.json").write_text(json.dumps({"dependencies": {"typescript": "^5.0.0"}}), encoding="utf-8")
    (src / "widget.ts").write_text("export const load = () => fetch('/status')\n", encoding="utf-8")

    result = scan_repo(project)
    conventions = "\n".join(convention.text for convention in result.conventions)

    assert "HTTP calls appear centralized" not in conventions


def test_api_wrapper_detection_handles_root_api_directory(tmp_path: Path) -> None:
    api = tmp_path / "api"
    api.mkdir()
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"typescript": "^5.0.0"}}), encoding="utf-8")
    (api / "index.ts").write_text("export const load = () => fetch('/status')\n", encoding="utf-8")

    result = scan_repo(tmp_path)
    conventions = "\n".join(convention.text for convention in result.conventions)

    assert "HTTP calls appear centralized" in conventions


def test_ignores_vendor_when_detecting_conventions(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(json.dumps({"dependencies": {"typescript": "^5.0.0"}}), encoding="utf-8")
    vendor = tmp_path / "vendor"
    vendor.mkdir()
    (vendor / "legacy.ts").write_text("export default function legacy() {}\n", encoding="utf-8")
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.ts").write_text("export const value = 1\n", encoding="utf-8")

    result = scan_repo(tmp_path)
    conventions = "\n".join(convention.text for convention in result.conventions)

    assert "named exports" in conventions
    assert "default exports" in conventions


def test_dedup_skips_claude_symlink_to_agents(tmp_path: Path) -> None:
    (tmp_path / "README.md").write_text("Independent docs.\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Generated by `agents-md`.\n", encoding="utf-8")
    (tmp_path / "CLAUDE.md").symlink_to("AGENTS.md")

    _, docs_read = read_markdown_facts(tmp_path)

    assert docs_read == ["README.md"]
