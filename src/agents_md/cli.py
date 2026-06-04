from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .fingerprint import FINGERPRINT_RE, compare_fingerprints, encode_fingerprint, extract_fingerprint, fingerprint_repo
from .generator import has_managed_sections, line_count, render_document, render_sections, replace_managed_sections
from .llm import LlmError, detect_provider, missing_key_message, synthesize_with_llm
from .quality import apply_fix, format_human, format_json, lint_file, lint_text, placeholder_issues
from .scanner import scan_repo


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 0
    try:
        return args.handler(args)
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        return 130


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="agents-md", description="Generate and lint focused AGENTS.md files.")
    parser.add_argument("--version", action="version", version=f"agents-md {__version__}")
    sub = parser.add_subparsers(dest="command")

    init = sub.add_parser("init", help="Analyze the current repo and generate AGENTS.md.")
    init.add_argument("--no-llm", action="store_true", help="Generate from static extractors only.")
    init.add_argument("--provider", choices=["anthropic", "openai", "ollama", "gemini"], help="LLM provider for synthesis.")
    init.add_argument("--model", help="Override the provider default model.")
    init.add_argument("--output", default="AGENTS.md", help="Output filename.")
    init.add_argument("--no-symlink", action="store_true", help="Do not create CLAUDE.md symlink.")
    init.add_argument("--dry-run", action="store_true", help="Print generated content without writing files.")
    init.add_argument("--force", action="store_true", help="Overwrite existing output without prompting.")
    init.add_argument("--merge", action="store_true", help="Append managed sections to an existing hand-written file.")
    init.add_argument("--no-dedup", action="store_true", help="Skip README/docs deduplication.")
    init.add_argument("--verbose", action="store_true", help="Print scanner diagnostics.")
    init.set_defaults(handler=cmd_init)

    update = sub.add_parser("update", help="Refresh managed sections of an existing AGENTS.md.")
    update.add_argument("path", nargs="?", default="AGENTS.md")
    update.add_argument("--no-llm", action="store_true", help="Do not call an LLM.")
    update.add_argument(
        "--provider",
        choices=["anthropic", "openai", "ollama", "gemini"],
        help="Accepted for compatibility; update skips LLM synthesis to preserve manual content.",
    )
    update.add_argument("--model", help="Accepted for compatibility; update skips LLM synthesis.")
    update.add_argument("--no-dedup", action="store_true", help="Skip README/docs deduplication.")
    update.add_argument("--init-fingerprint", action="store_true", help="Add a fingerprint when updating managed sections.")
    update.set_defaults(handler=cmd_update)

    lint = sub.add_parser("lint", help="Score an AGENTS.md file.")
    lint.add_argument("path", nargs="?", default="AGENTS.md")
    lint.add_argument("--check", action="store_true", help="Exit non-zero if score is below threshold.")
    lint.add_argument("--threshold", type=int, default=60, help="Minimum score for --check.")
    lint.add_argument("--fix", action="store_true", help="Remove duplicate/style-rule lines after confirmation.")
    lint.add_argument("--yes", action="store_true", help="Confirm --fix without prompting.")
    lint.add_argument("--fail-on-placeholder", action="store_true", help="Exit non-zero if placeholder commands remain.")
    lint.add_argument("--json", action="store_true", help="Output JSON.")
    lint.set_defaults(handler=cmd_lint)

    diff = sub.add_parser("diff", help="Show repo changes since AGENTS.md was generated.")
    diff.add_argument("path", nargs="?", default="AGENTS.md")
    diff.set_defaults(handler=cmd_diff)

    return parser


def cmd_init(args: argparse.Namespace) -> int:
    root = Path.cwd()
    output = root / args.output
    existing = output.read_text(encoding="utf-8") if output.exists() else None
    if existing is not None and args.merge and has_managed_sections(existing):
        print(f"{output.name} already has managed sections. Run `agents-md update` instead.", file=sys.stderr)
        return 1
    if output.exists() and not args.force and not args.dry_run and not args.merge:
        if not _confirm(f"{output.name} already exists. Overwrite it?"):
            print("Aborted; existing file was not changed.", file=sys.stderr)
            return 1

    if args.merge and not args.no_llm:
        print("LLM synthesis skipped in --merge mode to preserve hand-written content.", file=sys.stderr)
        args.no_llm = True

    if not args.no_llm:
        provider = detect_provider(args.provider)
        if not provider:
            print(missing_key_message(args.provider), file=sys.stderr)
            if _confirm("Run once in --no-llm mode instead?"):
                args.no_llm = True
            else:
                return 2

    _progress("Scanning repo")
    scan = scan_repo(root, output_name=output.name)
    if args.verbose:
        _print_scan(scan)
    if not args.no_dedup:
        if scan.docs_read:
            _progress(f"Deduplicating against {', '.join(scan.docs_read)}")
        else:
            _progress("Deduplicating against existing docs")
    _progress("Rendering AGENTS.md")
    content = render_document(scan, no_dedup=args.no_dedup)
    if args.verbose:
        _print_dedup(scan)
    if existing is not None and args.merge:
        content = existing.rstrip() + "\n\n" + _managed_body(content)
    if not args.no_llm:
        provider = detect_provider(args.provider)
        if provider:
            _progress(f"Synthesizing with {provider}")
            try:
                content = synthesize_with_llm(content, provider=provider, model=args.model)
            except LlmError as exc:
                print(f"LLM synthesis failed: {exc}", file=sys.stderr)
                return 2
            if not has_managed_sections(content):
                print("LLM output omitted managed markers; refusing to write it.", file=sys.stderr)
                return 2

    if args.dry_run:
        print(content, end="")
        _summary(content, output, len(scan.dedup.removed), dry_run=True)
        return 0

    output.write_text(content, encoding="utf-8")
    if output.name == "AGENTS.md" and not args.no_symlink:
        _ensure_claude_symlink(root, output)
    _summary(content, output, len(scan.dedup.removed), dry_run=False)
    return 0


def cmd_update(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"{path} does not exist. Run `agents-md init` first.", file=sys.stderr)
        return 1
    existing = path.read_text(encoding="utf-8")
    if not has_managed_sections(existing):
        print("No managed sections found. Run `agents-md init --merge` to add managed sections without overwriting your file.")
        return 1

    scan = scan_repo(path.parent.resolve(), output_name=path.name)
    sections = render_sections(scan, no_dedup=args.no_dedup)
    updated, changed = replace_managed_sections(existing, sections)
    current_fingerprint = encode_fingerprint(fingerprint_repo(path.parent.resolve(), output_name=path.name))
    if "agents-md:fingerprint" in updated:
        refreshed = FINGERPRINT_RE.sub(current_fingerprint, updated)
        if refreshed != updated:
            updated = refreshed
            changed.append("fingerprint")
    elif args.init_fingerprint:
        updated = updated.rstrip() + "\n" + current_fingerprint + "\n"
        changed.append("fingerprint")

    if not args.no_llm:
        provider = detect_provider(args.provider)
        if provider:
            print("LLM synthesis skipped in update mode to preserve manual content.", file=sys.stderr)
        else:
            print(f"{missing_key_message(args.provider)} Proceeding with static update.", file=sys.stderr)
    path.write_text(updated, encoding="utf-8")
    if changed:
        print(f"Updated: {', '.join(changed)}.")
    else:
        print("No managed section changes detected.")
    print("Preserved: content outside managed markers.")
    return 0


def cmd_lint(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        if args.check:
            return 1
        print(f"{path} does not exist.", file=sys.stderr)
        return 1
    result = lint_file(path)
    placeholders = placeholder_issues(path.read_text(encoding="utf-8")) if args.fail_on_placeholder else []
    if args.fix:
        if not result.issues:
            print("No auto-fixable issues detected.")
            return 1 if placeholders else 0
        if not args.yes and not _confirm(f"Create {path.name}.bak and remove auto-fixable lines?"):
            print("Aborted; file was not changed.", file=sys.stderr)
            return 1
        backup = apply_fix(path, result)
        print(f"Fixed {path}; backup written to {backup}.")
        if placeholders:
            print("Placeholder issues remain after --fix; replace them manually.", file=sys.stderr)
            return 1
        return 0
    if placeholders:
        result.issues.extend(placeholders)
    if args.check:
        for issue in placeholders:
            print(f"Line {issue.line}: {issue.message}", file=sys.stderr)
        return 0 if result.score >= args.threshold and not placeholders else 1
    print(format_json(result) if args.json else format_human(result), end="")
    return 1 if placeholders else 0


def cmd_diff(args: argparse.Namespace) -> int:
    path = Path(args.path)
    if not path.is_file():
        print(f"{path} does not exist.", file=sys.stderr)
        return 1
    old = extract_fingerprint(path.read_text(encoding="utf-8"))
    if not old:
        print("No fingerprint found. Run `agents-md init` or `agents-md update --init-fingerprint`.")
        return 1
    current = fingerprint_repo(path.parent.resolve(), output_name=path.name)
    diff = compare_fingerprints(old, current)
    for label in ("added", "removed", "changed"):
        values = diff[label]
        if values:
            print(f"{label}: {', '.join(values)}")
    if not diff["added"] and not diff["removed"] and not diff["changed"]:
        print("No relevant generation input changes detected.")
    else:
        print("Recommendation: run `agents-md update` to sync managed sections.")
    return 0


def _confirm(message: str) -> bool:
    if not sys.stdin.isatty():
        return False
    answer = input(f"{message} [y/N] ").strip().lower()
    return answer in {"y", "yes"}


def _progress(message: str) -> None:
    print(f"{message}...", file=sys.stderr)


def _summary(content: str, output: Path, removed: int, *, dry_run: bool) -> None:
    result = lint_text(content, root=output.parent) if dry_run else lint_file(output)
    action = "Would write" if dry_run else "Wrote"
    print(f"{action} {output}: {line_count(content)} lines, quality {result.score}/100, dedup removed {removed} item(s).")


def _ensure_claude_symlink(root: Path, output: Path) -> None:
    link = root / "CLAUDE.md"
    if link.exists() or link.is_symlink():
        if link.is_symlink() and link.resolve() == output.resolve():
            return
        print("CLAUDE.md exists and was left unchanged.", file=sys.stderr)
        return
    try:
        link.symlink_to(output.name)
    except OSError as exc:
        print(f"Could not create CLAUDE.md symlink: {exc}", file=sys.stderr)


def _print_scan(scan) -> None:
    print("Detected stack:", file=sys.stderr)
    for fact in scan.stack:
        print(f"  - {fact.kind}: {fact.label()} ({fact.source})", file=sys.stderr)
    print("Detected commands:", file=sys.stderr)
    for command in scan.commands:
        print(f"  - {command.category}: {command.command} ({command.source})", file=sys.stderr)
    if scan.docs_read:
        print(f"Docs read for dedup: {', '.join(scan.docs_read)}", file=sys.stderr)
    if scan.warnings:
        print("Warnings:", file=sys.stderr)
        for warning in scan.warnings:
            source = f" ({warning.source})" if warning.source else ""
            print(f"  - {warning.code}: {warning.message}{source}", file=sys.stderr)


def _print_dedup(scan) -> None:
    if scan.dedup.removed:
        print("Dedup removed:", file=sys.stderr)
        for item in scan.dedup.removed:
            print(f"  - {item}", file=sys.stderr)
    else:
        print("Dedup removed 0 item(s).", file=sys.stderr)


def _managed_body(content: str) -> str:
    marker = "<!-- agents-md:start:"
    start = content.find(marker)
    return content[start:] if start >= 0 else content
