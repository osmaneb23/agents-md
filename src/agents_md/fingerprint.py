from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

FINGERPRINT_RE = re.compile(r"<!-- agents-md:fingerprint (?P<payload>\{.*?\}) -->")

KEY_NAMES = {
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
}


def iter_key_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for name in sorted(KEY_NAMES):
        path = root / name
        if path.is_file():
            files.append(path)
    workflows = root / ".github" / "workflows"
    if workflows.is_dir():
        files.extend(sorted(p for p in workflows.rglob("*") if p.is_file()))
    return files


def fingerprint_repo(root: Path) -> dict[str, Any]:
    entries: dict[str, str] = {}
    for path in iter_key_files(root):
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
