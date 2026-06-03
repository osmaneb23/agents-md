from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .dedup import normalize_fact


@dataclass
class Issue:
    line: int
    message: str
    kind: str


@dataclass
class QualityResult:
    score: int
    verdict: str
    breakdown: list[str] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
    line_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "verdict": self.verdict,
            "line_count": self.line_count,
            "breakdown": self.breakdown,
            "issues": [issue.__dict__ for issue in self.issues],
        }


STYLE_RULE_RE = re.compile(
    r"\b(indentation|indent|trailing comma|quote style|single quotes|double quotes|semicolons?|line length|prettier)\b",
    re.I,
)
COMMAND_RE = re.compile(r"`([^`]+)`")


def lint_file(path: Path) -> QualityResult:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    lower = text.lower()
    score = 0
    breakdown: list[str] = []
    issues: list[Issue] = []

    command_lines = _section_lines(lines, "commands")
    command_count = sum(1 for line in command_lines if COMMAND_RE.search(line))
    if command_lines and command_count >= 2:
        score += 10
        breakdown.append("Commands section: +10")
    else:
        breakdown.append("Commands section: +0")
        issues.append(Issue(_heading_line(lines, "commands"), "Commands section needs at least two exact commands.", "commands"))

    flag_count = sum(1 for cmd in _commands(text) if re.search(r"\s-{1,2}[A-Za-z]", cmd))
    flag_points = 15 if flag_count >= 2 else 8 if flag_count == 1 else 0
    score += flag_points
    breakdown.append(f"Commands with exact flags: +{flag_points}")
    if flag_points < 15:
        issues.append(Issue(1, "Add exact command flags where they matter, especially for test targeting.", "command-flags"))

    if _has_single_test(text):
        score += 10
        breakdown.append("Single-test command: +10")
    else:
        breakdown.append("Single-test command: +0")
        issues.append(Issue(1, "Testing section should show how to run one file or one test.", "single-test"))

    boundaries_ok = all(token in lower for token in ("always", "ask first")) and "never" in lower
    if boundaries_ok:
        score += 20
        breakdown.append("Three-tier boundaries: +20")
    else:
        breakdown.append("Three-tier boundaries: +0")
        issues.append(Issue(_heading_line(lines, "boundaries"), "Boundaries need Always Do, Ask First, and Never Do tiers.", "boundaries"))

    if _section_lines(lines, "testing"):
        score += 10
        breakdown.append("Testing section: +10")
    else:
        breakdown.append("Testing section: +0")
        issues.append(Issue(1, "Add a dedicated testing section.", "testing"))

    line_points = _line_points(len(lines))
    score += line_points
    breakdown.append(f"Under 150 lines: +{line_points}")
    if line_points < 15:
        issues.append(Issue(1, f"File has {len(lines)} lines; keep AGENTS.md focused and under 150 lines.", "length"))

    duplicate_issues = _readme_duplication_issues(path, lines)
    if duplicate_issues:
        penalty = min(15 + (len(duplicate_issues) - 1) * 5, 45)
        score -= penalty
        breakdown.append(f"README duplication: -{penalty}")
        issues.extend(duplicate_issues)
    else:
        score += 15
        breakdown.append("No README duplication detected: +15")

    style_issues = _style_issues(lines)
    if style_issues:
        penalty = min(len(style_issues) * 5, 20)
        score -= penalty
        breakdown.append(f"Linter-owned style rules: -{penalty}")
        issues.extend(style_issues)
    else:
        score += 5
        breakdown.append("No linter-owned rules: +5")

    score = max(0, min(100, score))
    return QualityResult(score=score, verdict=_verdict(score), breakdown=breakdown, issues=issues, line_count=len(lines))


def format_human(result: QualityResult) -> str:
    parts = [f"Score: {result.score}/100", result.verdict, "", "Breakdown:"]
    parts.extend(f"- {item}" for item in result.breakdown)
    if result.issues:
        parts.extend(["", "Issues:"])
        for issue in result.issues:
            line = f"Line {issue.line}" if issue.line > 0 else "File"
            parts.append(f"- {line}: {issue.message}")
    return "\n".join(parts) + "\n"


def format_json(result: QualityResult) -> str:
    return json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"


def apply_fix(path: Path, result: QualityResult) -> Path:
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    remove_lines = {issue.line for issue in result.issues if issue.kind in {"readme-duplication", "style-rule"} and issue.line > 0}
    lines = path.read_text(encoding="utf-8").splitlines()
    kept = [line for index, line in enumerate(lines, start=1) if index not in remove_lines]
    path.write_text("\n".join(kept).rstrip() + "\n", encoding="utf-8")
    return backup


def _commands(text: str) -> list[str]:
    return COMMAND_RE.findall(text)


def _section_lines(lines: list[str], heading: str) -> list[str]:
    start = None
    heading_re = re.compile(rf"^##+\s+.*{re.escape(heading)}", re.I)
    for index, line in enumerate(lines):
        if heading_re.search(line):
            start = index + 1
            break
    if start is None:
        return []
    section: list[str] = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        section.append(line)
    return section


def _heading_line(lines: list[str], heading: str) -> int:
    heading_re = re.compile(rf"^##+\s+.*{re.escape(heading)}", re.I)
    for index, line in enumerate(lines, start=1):
        if heading_re.search(line):
            return index
    return 1


def _has_single_test(text: str) -> bool:
    patterns = (
        r"pytest .*::",
        r"pytest .*-k ",
        r"unittest .*test_",
        r"jest .*--testNamePattern",
        r"vitest .* -t ",
        r"cargo test \S+",
        r"go test .* -run ",
    )
    return any(re.search(pattern, text, re.I) for pattern in patterns)


def _line_points(count: int) -> int:
    if count <= 80:
        return 15
    if count >= 300:
        return 0
    if count <= 150:
        return max(8, round(15 - ((count - 80) / 70) * 7))
    return max(0, round(8 - ((count - 150) / 150) * 8))


def _readme_duplication_issues(path: Path, lines: list[str]) -> list[Issue]:
    readme = _find_readme(path.parent)
    if not readme:
        return []
    readme_text = readme.read_text(encoding="utf-8", errors="ignore")
    readme_facts = set()
    for raw in readme_text.splitlines():
        normalized = normalize_fact(raw.strip(" -#>\t"))
        if normalized:
            readme_facts.add(normalized)
        for command in COMMAND_RE.findall(raw):
            if _is_command_snippet(command):
                readme_facts.add(normalize_fact(command))
    facts = readme_facts
    issues: list[Issue] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--") or stripped.startswith("#"):
            continue
        if stripped.startswith("Generated by `agents-md`."):
            continue
        normalized = normalize_fact(stripped)
        command_dupe = any(
            normalize_fact(command) in facts for command in COMMAND_RE.findall(stripped) if _is_command_snippet(command)
        )
        important_boundary = any(token in normalized for token in ("never", "ask first", "ask before"))
        if (normalized in facts or command_dupe) and not important_boundary:
            issues.append(Issue(index, "Duplicates content already present in README/docs.", "readme-duplication"))
    return issues[:8]


def _find_readme(root: Path) -> Path | None:
    for name in ("README.md", "readme.md", "Readme.md"):
        path = root / name
        if path.is_file():
            return path
    return None


def _is_command_snippet(text: str) -> bool:
    stripped = text.strip()
    if " " not in stripped:
        return False
    return stripped.startswith(
        ("agents-md ", "python ", "pytest ", "uv ", "pip ", "pipx ", "npm ", "pnpm ", "yarn ", "bun ", "cargo ", "go ")
    )


def _style_issues(lines: list[str]) -> list[Issue]:
    issues: list[Issue] = []
    for index, line in enumerate(lines, start=1):
        if STYLE_RULE_RE.search(line):
            issues.append(Issue(index, "This looks like a formatter/linter-owned style rule.", "style-rule"))
    return issues[:8]


def _verdict(score: int) -> str:
    if score >= 85:
        return "Excellent. This file will improve agent performance."
    if score >= 65:
        return "Good. A few improvements would help."
    if score >= 45:
        return "Needs work. Key sections are missing or redundant content is present."
    return "This file may be hurting agent performance. See recommendations."
