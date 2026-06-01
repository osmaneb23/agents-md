from __future__ import annotations

import ast
import json
import re
import tomllib
from pathlib import Path
from typing import Any

from .dedup import read_markdown_facts
from .types import CommandFact, ConventionFact, ScanResult, StackFact

SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
}

JS_FRAMEWORKS = {
    "next": "Next.js",
    "vite": "Vite",
    "astro": "Astro",
    "svelte": "Svelte",
    "react": "React",
    "vue": "Vue",
}

JS_TESTERS = ("vitest", "jest", "mocha", "playwright", "cypress")
PY_FRAMEWORKS = ("fastapi", "flask", "django", "starlette")
PY_LINTERS = ("ruff", "black", "flake8", "pylint")
PY_TYPECHECKERS = ("mypy", "pyright")
RISKY_COMMAND_RE = re.compile(r"\b(migrate|migration|alembic|prisma|db:|database|reset|seed)\b", re.I)


def scan_repo(root: Path, output_name: str = "AGENTS.md") -> ScanResult:
    root = root.resolve()
    result = ScanResult(root=root)
    markdown_facts, docs_read = read_markdown_facts(root, output_name)
    result.docs_read = docs_read
    _scan_general(root, result)
    _scan_javascript(root, result)
    _scan_python(root, result)
    _scan_go(root, result)
    _scan_rust(root, result)
    _scan_task_files(root, result)
    _scan_conventions(root, result)
    _dedupe_facts(result)
    # Keep markdown_facts reachable for verbose diagnostics without exposing it
    # as a public model field.
    setattr(result, "_markdown_facts", markdown_facts)
    return result


def _dedupe_facts(result: ScanResult) -> None:
    result.stack = list(dict.fromkeys(result.stack))
    result.commands = list(dict.fromkeys(result.commands))
    result.conventions = list(dict.fromkeys(result.conventions))


def _scan_general(root: Path, result: ScanResult) -> None:
    if (root / ".github" / "workflows").is_dir():
        result.stack.append(StackFact("ci", "GitHub Actions", source=".github/workflows"))
    if (root / ".gitlab-ci.yml").is_file():
        result.stack.append(StackFact("ci", "GitLab CI", source=".gitlab-ci.yml"))
    if (root / "Dockerfile").is_file() or (root / "docker-compose.yml").is_file():
        result.stack.append(StackFact("runtime", "Docker", source="Dockerfile/docker-compose.yml"))
    if any((root / name).exists() for name in ("pnpm-workspace.yaml", "nx.json", "turbo.json", "lerna.json")):
        result.monorepo = True
    package_json = _read_json(root / "package.json")
    if isinstance(package_json, dict) and "workspaces" in package_json:
        result.monorepo = True


def _scan_javascript(root: Path, result: ScanResult) -> None:
    package_json_path = root / "package.json"
    package_json = _read_json(package_json_path)
    if not isinstance(package_json, dict):
        return

    package_manager = _detect_js_package_manager(root, package_json)
    if package_manager:
        name, version = package_manager
        result.stack.append(StackFact("package-manager", name, version, source="package.json/lockfile"))

    dependencies = _merge_dependencies(package_json)
    for dep, label in JS_FRAMEWORKS.items():
        version = dependencies.get(dep)
        if version:
            result.stack.append(StackFact("framework", label, _clean_version(version), source="package.json"))
    for tester in JS_TESTERS:
        version = dependencies.get(tester)
        if version:
            result.stack.append(StackFact("test-runner", tester, _clean_version(version), source="package.json"))

    tsconfig = _read_json(root / "tsconfig.json")
    if isinstance(tsconfig, dict) or any(_iter_source_files(root, (".ts", ".tsx"), limit=1)):
        strict = None
        if isinstance(tsconfig, dict):
            compiler = tsconfig.get("compilerOptions", {})
            if isinstance(compiler, dict) and compiler.get("strict") is True:
                strict = "strict mode"
        result.stack.append(StackFact("language", "TypeScript", detail=strict, source="tsconfig.json"))

    runtime = "Bun" if _uses_bun(root, package_json) else "Node.js"
    result.stack.append(StackFact("runtime", runtime, source="package.json"))

    scripts = package_json.get("scripts", {})
    if isinstance(scripts, dict):
        for name, value in sorted(scripts.items()):
            if not isinstance(value, str) or name.startswith(("pre", "post")):
                continue
            category = _categorize_command(name, value)
            if not category:
                continue
            result.commands.append(
                CommandFact(
                    name=name,
                    command=_script_command(package_manager[0] if package_manager else "npm", name),
                    category=category,
                    source="package.json",
                    risky=bool(RISKY_COMMAND_RE.search(name) or RISKY_COMMAND_RE.search(value)),
                    note=value,
                )
            )
        single = _infer_js_single_test(package_manager[0] if package_manager else "npm", dependencies)
        if single:
            result.commands.append(single)


def _scan_python(root: Path, result: ScanResult) -> None:
    pyproject_path = root / "pyproject.toml"
    pyproject = _read_toml(pyproject_path)
    has_python = bool(pyproject) or any(_iter_source_files(root, (".py",), limit=1))
    if not has_python:
        return

    result.stack.append(StackFact("language", "Python", source="pyproject.toml" if pyproject else "source files"))
    manager = _detect_python_package_manager(root, bool(pyproject))
    if manager:
        result.stack.append(StackFact("package-manager", manager, source="lock/config files"))

    project = pyproject.get("project", {}) if isinstance(pyproject, dict) else {}
    if isinstance(project, dict):
        if project.get("name"):
            result.stack.append(
                StackFact("package", str(project["name"]), str(project.get("version", "")) or None, source="pyproject.toml")
            )
        if project.get("requires-python"):
            result.stack.append(StackFact("runtime", "Python", str(project["requires-python"]), source="pyproject.toml"))

    deps = _python_dependencies(pyproject)
    for framework in PY_FRAMEWORKS:
        if framework in deps:
            result.stack.append(StackFact("framework", framework, deps[framework], source="pyproject.toml"))
    for linter in PY_LINTERS:
        if linter in deps or _tool_config_exists(pyproject, linter):
            result.stack.append(StackFact("linter", linter, deps.get(linter), source="pyproject.toml"))
    for checker in PY_TYPECHECKERS:
        if checker in deps or _tool_config_exists(pyproject, checker):
            result.stack.append(StackFact("type-checker", checker, deps.get(checker), source="pyproject.toml"))

    result.commands.extend(_python_default_commands(root, pyproject, manager))
    result.commands.extend(_python_task_commands(pyproject))


def _scan_go(root: Path, result: ScanResult) -> None:
    go_mod = root / "go.mod"
    if not go_mod.is_file():
        return
    text = go_mod.read_text(encoding="utf-8", errors="ignore")
    result.stack.append(StackFact("language", "Go", source="go.mod"))
    for framework in ("gin", "echo", "fiber", "chi"):
        if framework in text.lower():
            result.stack.append(StackFact("framework", framework, source="go.mod"))
    result.commands.append(CommandFact("test", "go test ./...", "test", "go.mod"))
    result.commands.append(CommandFact("single-test", "go test ./... -run <TestName>", "single-test", "go.mod"))


def _scan_rust(root: Path, result: ScanResult) -> None:
    cargo = root / "Cargo.toml"
    if not cargo.is_file():
        return
    result.stack.append(StackFact("language", "Rust", source="Cargo.toml"))
    result.commands.append(CommandFact("build", "cargo build", "build", "Cargo.toml"))
    result.commands.append(CommandFact("test", "cargo test", "test", "Cargo.toml"))
    result.commands.append(CommandFact("single-test", "cargo test <test_name>", "single-test", "Cargo.toml"))
    if (root / "tests").is_dir():
        result.conventions.append(ConventionFact("Rust integration tests live in `tests/`.", "tests/"))


def _scan_task_files(root: Path, result: ScanResult) -> None:
    makefile = root / "Makefile"
    if makefile.is_file():
        for target in _parse_make_targets(makefile):
            category = _categorize_command(target, target)
            if category:
                result.commands.append(
                    CommandFact(target, f"make {target}", category, "Makefile", risky=bool(RISKY_COMMAND_RE.search(target)))
                )

    justfile = root / "Justfile"
    if justfile.is_file():
        for recipe in _parse_just_recipes(justfile):
            category = _categorize_command(recipe, recipe)
            if category:
                result.commands.append(CommandFact(recipe, f"just {recipe}", category, "Justfile"))

    for name in ("Taskfile.yml", "Taskfile.yaml"):
        taskfile = root / name
        if taskfile.is_file():
            for task in _parse_taskfile_tasks(taskfile):
                category = _categorize_command(task, task)
                if category:
                    result.commands.append(CommandFact(task, f"task {task}", category, name))


def _scan_conventions(root: Path, result: ScanResult) -> None:
    src = root / "src"
    if src.is_dir():
        result.conventions.append(ConventionFact("Package code uses a `src/` layout; import through the installed package path.", "src/"))
    tests = root / "tests"
    if tests.is_dir():
        patterns = sorted({p.name for p in tests.rglob("test_*.py") if p.is_file()})
        if patterns:
            result.conventions.append(ConventionFact("Python tests live under `tests/` as `test_*.py` files.", "tests/"))
    tsconfig = _read_json(root / "tsconfig.json")
    if isinstance(tsconfig, dict):
        paths = tsconfig.get("compilerOptions", {}).get("paths", {})
        if isinstance(paths, dict) and paths:
            aliases = ", ".join(sorted(paths)[:4])
            result.conventions.append(ConventionFact(f"TypeScript path aliases are configured in tsconfig: {aliases}.", "tsconfig.json"))

    for py_file in _iter_source_files(root, (".py",), limit=80):
        for class_name in _python_error_classes(py_file):
            result.conventions.append(ConventionFact(f"Custom Python error class detected: `{class_name}`.", py_file.relative_to(root).as_posix()))
            return


def _detect_js_package_manager(root: Path, package_json: dict[str, Any]) -> tuple[str, str | None] | None:
    for filename, manager in (
        ("pnpm-lock.yaml", "pnpm"),
        ("yarn.lock", "yarn"),
        ("bun.lockb", "bun"),
        ("package-lock.json", "npm"),
    ):
        if (root / filename).is_file():
            return manager, _package_manager_version(package_json, manager)
    package_manager = package_json.get("packageManager")
    if isinstance(package_manager, str) and "@" in package_manager:
        name, version = package_manager.split("@", 1)
        return name, version
    return None


def _detect_python_package_manager(root: Path, has_pyproject: bool) -> str | None:
    for filename, manager in (
        ("pixi.toml", "Pixi"),
        ("uv.lock", "uv"),
        ("poetry.lock", "Poetry"),
        ("Pipfile", "Pipenv"),
        ("requirements.txt", "pip"),
    ):
        if (root / filename).is_file():
            return manager
    return "pip" if has_pyproject else None


def _package_manager_version(package_json: dict[str, Any], manager: str) -> str | None:
    package_manager = package_json.get("packageManager")
    if isinstance(package_manager, str) and package_manager.startswith(f"{manager}@"):
        return package_manager.split("@", 1)[1]
    return None


def _merge_dependencies(package_json: dict[str, Any]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for key in ("dependencies", "devDependencies", "peerDependencies"):
        deps = package_json.get(key, {})
        if isinstance(deps, dict):
            merged.update({str(k): str(v) for k, v in deps.items()})
    return merged


def _uses_bun(root: Path, package_json: dict[str, Any]) -> bool:
    if (root / "bun.lockb").is_file():
        return True
    scripts = package_json.get("scripts", {})
    return isinstance(scripts, dict) and any("bun " in str(value) for value in scripts.values())


def _script_command(manager: str, name: str) -> str:
    if manager == "npm":
        return f"npm {name}" if name in {"test", "start"} else f"npm run {name}"
    if manager == "bun":
        return f"bun run {name}"
    return f"{manager} {name}"


def _infer_js_single_test(manager: str, dependencies: dict[str, str]) -> CommandFact | None:
    runner = None
    for candidate in ("vitest", "jest", "mocha"):
        if candidate in dependencies:
            runner = candidate
            break
    if not runner:
        return None
    prefix = "npx" if manager == "npm" else manager
    if runner == "jest":
        command = f"{prefix} jest --testPathPattern=<path> --testNamePattern=<name>"
    elif runner == "vitest":
        command = f"{prefix} vitest run <path> -t \"<name>\""
    else:
        command = f"{prefix} mocha <path> --grep \"<name>\""
    return CommandFact("single-test", command, "single-test", "package.json")


def _python_default_commands(root: Path, pyproject: dict[str, Any], manager: str | None) -> list[CommandFact]:
    commands: list[CommandFact] = []
    extras = pyproject.get("project", {}).get("optional-dependencies", {}) if isinstance(pyproject, dict) else {}
    has_dev = isinstance(extras, dict) and "dev" in extras
    if manager == "uv":
        commands.append(CommandFact("install", "uv sync", "install", "uv.lock"))
        commands.append(CommandFact("run", "uv run agents-md --help", "run", "pyproject.toml"))
    elif manager == "Poetry":
        commands.append(CommandFact("install", "poetry install", "install", "poetry.lock"))
    elif manager == "Pixi":
        commands.append(CommandFact("install", "pixi install", "install", "pixi.toml"))
    elif manager == "pip":
        suffix = ".[dev]" if has_dev else "."
        commands.append(CommandFact("install", f"python -m pip install -e {suffix}", "install", "pyproject.toml"))

    if (root / "tests").is_dir() or _tool_config_exists(pyproject, "pytest"):
        if _tool_config_exists(pyproject, "pytest"):
            commands.append(CommandFact("test", "python -m pytest", "test", "pyproject.toml"))
            commands.append(CommandFact("single-test", _infer_python_single_test(root, "pytest"), "single-test", "pyproject.toml"))
        else:
            commands.append(CommandFact("test", "python -m unittest discover -s tests -p 'test_*.py'", "test", "tests/"))
            commands.append(
                CommandFact(
                    "single-test",
                    _infer_python_single_test(root, "unittest"),
                    "single-test",
                    "tests/",
                )
            )
    if _tool_config_exists(pyproject, "ruff") or "ruff" in _python_dependencies(pyproject):
        commands.append(CommandFact("lint", "ruff check .", "lint", "pyproject.toml"))
    if _tool_config_exists(pyproject, "mypy") or "mypy" in _python_dependencies(pyproject):
        commands.append(CommandFact("typecheck", "mypy src tests", "typecheck", "pyproject.toml"))
    if has_dev:
        commands.append(CommandFact("build", "python -m build", "build", "pyproject.toml"))
    return commands


def _python_task_commands(pyproject: dict[str, Any]) -> list[CommandFact]:
    commands: list[CommandFact] = []
    tool = pyproject.get("tool", {}) if isinstance(pyproject, dict) else {}
    for table_name in ("taskipy", "poe"):
        table = tool.get(table_name, {})
        tasks = table.get("tasks", {}) if isinstance(table, dict) else {}
        if isinstance(tasks, dict):
            for name, value in sorted(tasks.items()):
                command_text = value.get("cmd") if isinstance(value, dict) else value
                if not isinstance(command_text, str):
                    continue
                category = _categorize_command(name, command_text)
                if category:
                    runner = "task" if table_name == "taskipy" else "poe"
                    commands.append(
                        CommandFact(name, f"{runner} {name}", category, f"pyproject.toml [tool.{table_name}.tasks]")
                    )
    custom = tool.get("scripts", {})
    if isinstance(custom, dict):
        for name in sorted(custom):
            category = _categorize_command(name, str(custom[name]))
            if category:
                commands.append(CommandFact(name, f"python -m {name}", category, "pyproject.toml [tool.scripts]"))
    return commands


def _python_dependencies(pyproject: dict[str, Any]) -> dict[str, str | None]:
    deps: dict[str, str | None] = {}
    project = pyproject.get("project", {}) if isinstance(pyproject, dict) else {}
    raw_lists: list[Any] = []
    if isinstance(project, dict):
        raw_lists.append(project.get("dependencies", []))
        optional = project.get("optional-dependencies", {})
        if isinstance(optional, dict):
            raw_lists.extend(optional.values())
    for raw_list in raw_lists:
        if not isinstance(raw_list, list):
            continue
        for item in raw_list:
            if not isinstance(item, str):
                continue
            match = re.match(r"([A-Za-z0-9_.-]+)\s*([<>=!~].*)?", item)
            if match:
                deps[match.group(1).lower().replace("_", "-")] = match.group(2)
    return deps


def _tool_config_exists(pyproject: dict[str, Any], name: str) -> bool:
    tool = pyproject.get("tool", {}) if isinstance(pyproject, dict) else {}
    if name == "pytest":
        return isinstance(tool, dict) and ("pytest" in tool or "pytest.ini_options" in tool)
    return isinstance(tool, dict) and name in tool


def _categorize_command(name: str, command: str) -> str | None:
    value = f"{name} {command}".lower()
    if RISKY_COMMAND_RE.search(value):
        return "migration"
    if any(token in value for token in ("install", "sync")):
        return "install"
    if any(token in value for token in ("dev", "serve", "start", "runserver", "uvicorn")):
        return "run"
    if "build" in value:
        return "build"
    if "typecheck" in value or "tsc" in value or "mypy" in value or "pyright" in value:
        return "typecheck"
    if "lint" in value or "ruff" in value or "eslint" in value:
        return "lint"
    if "test" in value or "pytest" in value or "unittest" in value:
        return "test"
    return None


def _read_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return {}


def _clean_version(version: str | None) -> str | None:
    if not version:
        return None
    return version.strip().lstrip("^~")


def _iter_source_files(root: Path, suffixes: tuple[str, ...], limit: int) -> list[Path]:
    files: list[Path] = []
    for path in root.rglob("*"):
        if len(files) >= limit:
            break
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file() and path.suffix in suffixes:
            files.append(path)
    return files


def _parse_make_targets(path: Path) -> list[str]:
    targets: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_.-]*):(?!=)", line)
        if match and not match.group(1).startswith(("_", ".")):
            targets.append(match.group(1))
    return sorted(set(targets))


def _parse_just_recipes(path: Path) -> list[str]:
    recipes: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = re.match(r"^([A-Za-z0-9][A-Za-z0-9_-]*)\s*(?:.*?)?:", line)
        if match and not match.group(1).startswith("_"):
            recipes.append(match.group(1))
    return sorted(set(recipes))


def _parse_taskfile_tasks(path: Path) -> list[str]:
    tasks: list[str] = []
    in_tasks = False
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if re.match(r"^tasks:\s*$", line):
            in_tasks = True
            continue
        if in_tasks:
            match = re.match(r"^\s{2}([A-Za-z0-9_-]+):\s*$", line)
            if match:
                tasks.append(match.group(1))
            elif line and not line.startswith(" "):
                in_tasks = False
    return sorted(set(tasks))


def _infer_python_single_test(root: Path, runner: str) -> str:
    tests = root / "tests"
    if tests.is_dir():
        for path in sorted(tests.rglob("test_*.py")):
            target = _first_python_test_target(path, root)
            if target:
                if runner == "pytest":
                    return f"python -m pytest {target} -xvs"
                module_target = target.replace("/", ".").replace(".py::", ".")
                module_target = module_target.replace(".py", "")
                return f"python -m unittest {module_target} -v"
    if runner == "pytest":
        return "python -m pytest tests/test_example.py::test_name -xvs"
    return "python -m unittest tests.test_example.TestExample.test_name -v"


def _first_python_test_target(path: Path, root: Path) -> str | None:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return None
    rel = path.relative_to(root).as_posix()
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            return f"{rel}::{node.name}"
        if isinstance(node, ast.ClassDef) and node.name.startswith(("Test", "Quality")):
            for child in node.body:
                if isinstance(child, ast.FunctionDef) and child.name.startswith("test_"):
                    return f"{rel}::{node.name}.{child.name}"
    return None


def _python_error_classes(path: Path) -> list[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return []
    classes: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name.endswith("Error"):
            for base in node.bases:
                if isinstance(base, ast.Name) and base.id in {"Exception", "RuntimeError", "ValueError"}:
                    classes.append(node.name)
    return classes
