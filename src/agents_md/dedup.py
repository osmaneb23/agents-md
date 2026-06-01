from __future__ import annotations

import re
from pathlib import Path

from .types import DedupLog

CODE_RE = re.compile(r"`([^`]+)`")


def normalize_fact(text: str) -> str:
    text = text.lower()
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"[^a-z0-9_./:-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def read_markdown_facts(root: Path, output_name: str = "AGENTS.md") -> tuple[set[str], list[str]]:
    paths: list[Path] = []
    for path in root.glob("*.md"):
        if path.name == output_name:
            continue
        paths.append(path)
    docs = root / "docs"
    if docs.is_dir():
        paths.extend(sorted(docs.rglob("*.md")))

    facts: set[str] = set()
    docs_read: list[str] = []
    for path in sorted(paths):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        docs_read.append(path.relative_to(root).as_posix())
        for raw in text.splitlines():
            line = raw.strip(" -#>\t")
            if len(line) < 12:
                continue
            normalized = normalize_fact(line)
            if normalized:
                facts.add(normalized)
            for code in CODE_RE.findall(raw):
                if " " in code or code.startswith(("npm", "pnpm", "python", "pytest", "uv", "cargo", "go ")):
                    facts.add(normalize_fact(code))
    return facts, docs_read


def should_keep_important_line(line: str) -> bool:
    lower = line.lower()
    return any(token in lower for token in ("never", "ask first", "secret", "security", "migration", "database"))


def deduplicate_lines(lines: list[str], facts: set[str], log: DedupLog) -> list[str]:
    filtered: list[str] = []
    seen: set[str] = set()
    for line in lines:
        normalized = normalize_fact(line)
        if normalized and normalized in seen:
            log.add(line, "duplicate generated line")
            continue
        seen.add(normalized)
        if normalized and normalized in facts and not should_keep_important_line(line):
            log.add(line, "already discoverable in markdown docs")
            continue
        filtered.append(line)
    return filtered
