# agents-md

Generate short, useful `AGENTS.md` files for real repositories.

`agents-md` is a Python CLI that scans a repo, extracts the details an AI coding
agent is likely to need, removes content already discoverable in README/docs, and
writes a managed `AGENTS.md` with exact commands, testing notes, boundaries, and
security guidance.

The core opinion is simple: agent instructions should be brief. If a fact is
already in project docs or obvious from manifests, repeating it in `AGENTS.md`
usually adds cost without adding guidance.

## Install

```bash
pip install agents-md
```

For local development in this repo, install the package in editable mode with
the `dev` optional extra.

## Usage

Generate a file without any API key:

```bash
agents-md init --no-llm
```

Use LLM synthesis when a provider key is available:

```bash
ANTHROPIC_API_KEY=... agents-md init --provider anthropic
OPENAI_API_KEY=... agents-md init --provider openai
```

Lint an existing file:

```bash
agents-md lint AGENTS.md
agents-md lint --check --threshold 70
agents-md lint --json
```

Update only managed sections:

```bash
agents-md update --no-llm
```

Check whether important manifests changed since generation:

```bash
agents-md diff
```

## What It Detects

- Python, JavaScript/TypeScript, Go, and Rust stack signals
- Package managers, frameworks, linters, type checkers, and test runners
- Commands from `package.json`, `pyproject.toml`, `Makefile`, `Justfile`, and
  `Taskfile.yml`
- Single-test command patterns for pytest/unittest, Jest, Vitest, Go, and Cargo
- Managed marker sections for non-destructive updates
- Fingerprints for relevant manifest/config drift

## Design Constraints

- Core install has no runtime dependencies.
- LLM provider SDKs are optional extras.
- `--no-llm` must work offline and in CI.
- Generated AGENTS files should stay under 150 lines.
- `update` only rewrites sections inside `<!-- agents-md:start:* -->` markers.
- `lint --fix` writes a `.bak` backup before editing.

## GitHub Action

This repo includes a composite action at `.github/actions/agents-md-lint`:

```yaml
steps:
  - uses: actions/checkout@v6
  - uses: actions/setup-python@v6
    with:
      python-version: "3.13"
  - uses: ./.github/actions/agents-md-lint
    with:
      path: AGENTS.md
      threshold: "70"
```

## Development

Maintainer commands live in `AGENTS.md` so the agent-facing instructions stay
authoritative and easy to lint. The short version: install the dev extra in
editable mode, run the focused test while iterating, run the full suite before
handoff, and build the package before release work.

Before changing scoring weights, marker formats, or deduplication behavior,
open an issue or PR discussion. Those are product decisions, not incidental
implementation details.

## Sources

- AGENTS.md open format: https://github.com/agentsmd/agents.md
- OpenAI Responses API reference: https://developers.openai.com/api/reference/responses/overview
- Python packaging metadata: https://packaging.python.org/specifications/declaring-project-metadata/
