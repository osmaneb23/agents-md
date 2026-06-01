from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class StackFact:
    kind: str
    name: str
    version: str | None = None
    detail: str | None = None
    source: str | None = None

    def label(self) -> str:
        value = self.name
        if self.version:
            value = f"{value} {self.version}"
        if self.detail:
            value = f"{value} ({self.detail})"
        return value


@dataclass(frozen=True)
class CommandFact:
    name: str
    command: str
    category: str
    source: str
    risky: bool = False
    note: str | None = None


@dataclass(frozen=True)
class ConventionFact:
    text: str
    source: str


@dataclass
class DedupLog:
    removed: list[str] = field(default_factory=list)

    def add(self, line: str, reason: str) -> None:
        self.removed.append(f"{line} ({reason})")


@dataclass
class ScanResult:
    root: Path
    stack: list[StackFact] = field(default_factory=list)
    commands: list[CommandFact] = field(default_factory=list)
    conventions: list[ConventionFact] = field(default_factory=list)
    monorepo: bool = False
    docs_read: list[str] = field(default_factory=list)
    dedup: DedupLog = field(default_factory=DedupLog)
