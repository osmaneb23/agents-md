from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .dedup import iter_markdown_docs

FINGERPRINT_RE = re.compile(r"<!-- agents-md:fingerprint (?P<payload>\{.*?\}) -->")

KEY_NAMES = {
    ".env.example",
    ".env.sample",
    "package.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "bun.lockb",
    "package-lock.json",
    "pyproject.toml",
    "uv.lock",
    "poetry.lock",
    "pixi.toml",
    "requirements.txt",
    "Pipfile",
    "go.mod",
    "go.sum",
    "Cargo.toml",
    "Cargo.lock",
    "Makefile",
    "MANIFEST.in",
    "Justfile",
    "Taskfile.yml",
    "Taskfile.yaml",
    "tsconfig.json",
    "pnpm-workspace.yaml",
    "nx.json",
    "turbo.json",
    "lerna.json",
    "example.env",
}


def iter_key_files(root: Path, output_name: str = "AGENTS.md") -> list[Path]:
    files: list[Path] = []
    seen: set[str] = set()

    def add(path: Path) -> None:
        rel = path.relative_to(root).as_posix()
        if rel in seen:
            return
        seen.add(rel)
        files.append(path)

    for path in iter_markdown_docs(root, output_name):
        add(path)
    for name in sorted(KEY_NAMES):
        path = root / name
        if path.is_file():
            add(path)
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        for path in sorted(p for p in workflows.rglob("*") if p.is_file()):
            add(path)
    return sorted(files, key=lambda path: path.relative_to(root).as_posix())


def fingerprint_repo(root: Path, output_name: str = "AGENTS.md") -> dict[str, Any]:
    entries: dict[str, str] = {}
    for path in iter_key_files(root, output_name):
        rel = path.relative_to(root).as_posix()
        entries[rel] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"version": 1, "files": entries}


def encode_fingerprint(fingerprint: dict[str, Any]) -> str:
    payload = json.dumps(fingerprint, sort_keys=True, separators=(",", ":"))
    return f"<!-- agents-md:fingerprint {payload} -->"


def extract_fingerprint(text: str) -> dict[str, Any] | None:
    match = FINGERPRINT_RE.search(text)
    if not match:
        return None
    try:
        payload = json.loads(match.group("payload"))
    except json.JSONDecodeError:
        return None
    if isinstance(payload, dict) and isinstance(payload.get("files"), dict):
        return payload
    return None


def compare_fingerprints(old: dict[str, Any], new: dict[str, Any]) -> dict[str, list[str]]:
    old_files = old.get("files", {})
    new_files = new.get("files", {})
    old_keys = set(old_files)
    new_keys = set(new_files)
    return {
        "added": sorted(new_keys - old_keys),
        "removed": sorted(old_keys - new_keys),
        "changed": sorted(k for k in old_keys & new_keys if old_files[k] != new_files[k]),
        "unchanged": sorted(k for k in old_keys & new_keys if old_files[k] == new_files[k]),
    }
