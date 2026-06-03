# agents-md

**Generate `AGENTS.md` files that make AI coding sessions faster — not slower.**

[![CI](https://github.com/osmaneb23/agents-md/actions/workflows/ci.yml/badge.svg)](https://github.com/osmaneb23/agents-md/actions)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](pyproject.toml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

![agents-md terminal demo](docs/demo.svg)

The demo shows a JS/TS-style repo; simpler repos intentionally generate shorter files.

---

## The problem with most AGENTS.md generators

An ETH Zurich study ([arxiv.org/abs/2602.11988](https://arxiv.org/abs/2602.11988)) evaluated AI coding agents with and without context files across eight real-world benchmarks. The finding:

> Auto-generated context files **reduced task success rates by ~3%** and **increased inference costs by 20–23%** in 5 out of 8 tested scenarios.

The reason is straightforward: most generators blindly dump content the agent can already read — architecture overviews, things already in your README, style rules your linter already enforces. The agent has to re-read all of it on every task, and it interferes rather than helping.

`agents-md` is built around this finding. Before writing anything, it reads your existing docs and filters out everything already discoverable. What's left — exact commands with real flags, counterintuitive conventions, hard boundaries — is what the file should contain.

---

## What it looks like

```
$ agents-md init --no-llm

Scanning repo...
Deduplicating against README.md, CONTRIBUTING.md...
Rendering AGENTS.md...

Wrote AGENTS.md: 54 lines, quality 91/100, dedup removed 6 item(s).
```

The generated file:

```markdown
# AGENTS.md

<!-- agents-md:start:stack -->
## Stack
- CI: GitHub Actions
- Framework: Next.js 15.3
- Language: TypeScript (strict mode)
- Package Manager: pnpm 10.0.0
- Runtime: Node.js
- Test Runner: vitest 3.0.0
<!-- agents-md:end:stack -->

<!-- agents-md:start:commands -->
## Commands
- install: `pnpm install` from package.json.
- run: `pnpm dev` from package.json.
- build: `pnpm build` from package.json.
- test: `pnpm test` from package.json.
- lint: `pnpm lint` from package.json.
<!-- agents-md:end:commands -->

<!-- agents-md:start:testing -->
## Testing
- Full suite: `pnpm test`
- Single test: `pnpm vitest run src/auth/login.test.ts -t "should reject expired tokens"`
- Prefer the narrowest relevant test while iterating, then run the broader check before release changes.
<!-- agents-md:end:testing -->

<!-- agents-md:start:boundaries -->
## Boundaries
### Always Do
- Run the narrowest relevant test before handing off a code change.
### Ask First
- Ask before running `pnpm db:migrate` because it appears to touch migrations or data.
- Ask before deleting files, rewriting public history, or changing release/package metadata.
### Never Do
- Never commit secrets, tokens, or `.env` files.
- Never overwrite a hand-written AGENTS.md without `--force` or an explicit confirmation.
<!-- agents-md:end:boundaries -->
```

The managed `<!-- agents-md:start/end -->` markers let `agents-md update` refresh individual sections without touching anything you wrote by hand.

---

## Install

```bash
# Until the first PyPI release, install directly from GitHub:
python -m pip install "git+https://github.com/osmaneb23/agents-md.git"

# Once the first PyPI release is published:
pip install agents-md
uv tool install agents-md
pipx install agents-md
```

No Node.js. No Docker. No heavy ML dependencies. The core package has **zero runtime dependencies**.

LLM provider SDKs are optional extras — the tool works fully offline without them. From a source checkout:

```bash
python -m pip install -e .[anthropic]   # adds Anthropic SDK
python -m pip install -e .[openai]      # adds OpenAI SDK
python -m pip install -e .[gemini]      # adds Google Gemini SDK
```

---

## Usage

### Generate

```bash
# Offline — pure static analysis, no API key needed:
agents-md init --no-llm

# With LLM synthesis (auto-detects provider from env):
ANTHROPIC_API_KEY=... agents-md init
OPENAI_API_KEY=...   agents-md init
GEMINI_API_KEY=...   agents-md init

# Explicit provider and model:
agents-md init --provider anthropic --model <model-id>

# Preview without writing:
agents-md init --no-llm --dry-run --verbose
```

### Lint any AGENTS.md (including hand-written ones)

```bash
agents-md lint                         # score ./AGENTS.md
agents-md lint path/to/AGENTS.md       # score a specific file
agents-md lint --check --threshold 70  # CI: exit non-zero if score < 70
agents-md lint --fix                   # auto-remove duplicate/style lines
agents-md lint --json                  # machine-readable output
```

### Keep it up to date

```bash
agents-md update        # refresh managed sections, preserve manual notes
agents-md diff          # show which manifests changed since last generation
```

---

## How deduplication works

This is the step every other generator skips.

When you run `agents-md init`, the tool reads every Markdown file in your repo root and `docs/` directory before touching the output. It builds a set of already-documented facts — every command, framework mention, convention, and structural note it finds. Then, for every candidate line the extractors produced, it checks: *is this information already in the docs the agent can independently read?* If yes, the line is excluded.

```
README says:  "We use pnpm. Run `pnpm install` to get started."
Extractor:    install: pnpm install

→ Dedup removes it. The agent can read the README.

README says:  "Run the tests before pushing."
Extractor:    single test: pytest tests/test_auth.py::test_login -xvs

→ Dedup keeps it. The README mentions tests vaguely;
  the exact single-test command with flags is new information.
```

Boundaries and security instructions are always kept, even when they overlap with the README — they're important enough to repeat.

Run `--verbose` to see exactly what was removed and why.

---

## Quality scoring (`agents-md lint`)

Every generated (and hand-written) file gets a score out of 100. The score is broken down by criterion so you know exactly what to fix.

| Criterion | Points |
|---|---|
| Commands section with ≥ 2 exact commands | 10 |
| Commands include real flags (`-x`, `--watch`, etc.) | 15 |
| Single-test command targeting one file/function | 10 |
| Three-tier boundaries (Always / Ask First / Never) | 20 |
| Dedicated testing section | 10 |
| File under 150 lines | 15 |
| No README duplication detected | 15 |
| No linter-owned style rules | 5 |

**Score interpretation:**
- **85–100** — Excellent. This file will improve agent performance.
- **65–84** — Good. A few improvements would help.
- **45–64** — Needs work. Key sections are missing or redundant.
- **0–44** — This file may be hurting agent performance.

The lint command works on any AGENTS.md — including ones you wrote by hand before finding this tool.

---

## GitHub Action

Add to `.github/workflows/ci.yml` to fail PRs when the file drops below a quality threshold:

```yaml
- uses: actions/checkout@v6
- uses: actions/setup-python@v6
  with:
    python-version: "3.13"
- uses: osmaneb23/agents-md/.github/actions/agents-md-lint@main
  with:
    path: AGENTS.md
    threshold: "70"
```

Pin the action to a release tag once the first release is cut. The composite action installs from its own checked-out source, so it works even before the first PyPI package exists.

---

## What gets detected

`agents-md` reads the following files when scanning a repo:

**Commands** — `package.json` scripts, `Makefile` targets, `pyproject.toml` task runners (taskipy, poe), `Justfile` recipes, `Taskfile.yml` tasks. It infers single-test commands for pytest, unittest, Jest, Vitest, Mocha, Cargo, and Go.

**Stack** — Package manager (detected from lock files, not guessed), framework (from dependencies), language (TypeScript strict mode detected from tsconfig), runtime, test runner, linter, type checker, CI.

**Conventions** — `src/` layout, test file naming patterns, TypeScript path aliases, named-export-only modules, barrel files, `Result<...>` error-as-value returns, centralized API/fetch wrappers, catch blocks that intentionally return fallback values, `.env.example` variables, test fixtures/factories, and custom error class hierarchies. Only things a reasonable agent would get wrong on first attempt.

**Fingerprint** — A SHA-256 hash of key manifests stored in the file. `agents-md diff` uses this to tell you which files changed since the last generation and whether an update is warranted.

Supported ecosystems: **Python**, **JavaScript/TypeScript**, **Go**, **Rust**. The `--no-llm` mode works on all of them with no API key.

---

## Why not the alternatives?

| Tool | What it does | The gap |
|---|---|---|
| `agents-init` (npm) | Sets up AGENTS.md + MCP config + subagents in one shot | No deduplication filter — generates the kind of bloated file the ETH study warns against. Broader scope dilutes the core value. |
| `GenerateAgents.md` (PyPI) | DSPy-based generation, any model via LiteLLM | DSPy is a heavyweight dependency. `pip install` pulls in the full stack. Same ETH problem. |
| `AGENTS.md_generator` (Python) | Safe-by-default skeleton with marker patches | Intentionally avoids intelligence — "commands can be empty on purpose." You still fill it in manually. |
| Writing by hand | Full control | Takes time, drifts with the codebase, no quality feedback. |

`agents-md` does one thing: generate the **shortest file that actually helps**. The `lint` command tells you whether any AGENTS.md — generated or hand-written — achieves that.

---

## Design constraints (what this will never do)

- **No heavy deps.** The core package installs in seconds with zero runtime dependencies. LLM SDKs are opt-in extras.
- **No silent destruction.** `update` only touches sections inside managed markers. `lint --fix` creates a `.bak` before writing. `init` prompts before overwriting.
- **No guessing.** If the package manager cannot be determined with confidence from lock files, it's left blank. A wrong command is worse than a missing one.
- **No padding.** The LLM synthesis prompt instructs the model to refuse to pad output. A 30-line file is better than a 150-line file if the repo is simple.
- **No Node.js required.** This is a Python tool, installable anywhere Python runs.

---

## Development

Maintainer commands live in [AGENTS.md](AGENTS.md) so the agent-facing instruction file stays authoritative and easy to lint. In short: install the dev extra from a checkout, run the focused test while iterating, run the full suite before handoff, and build the package before release work.

Before changing scoring weights, deduplication rules, or managed marker formats, open an issue or PR discussion. These are product decisions that affect user trust, not implementation details.

Releases are published through PyPI Trusted Publishing from `.github/workflows/publish.yml`. Configure a pending publisher for project `agents-md`, repository `osmaneb23/agents-md`, workflow `publish.yml`, environment `pypi`, then publish a GitHub release.

See [CONTRIBUTING.md](CONTRIBUTING.md) for pull request expectations.

---

## Sources

- ETH Zurich study: ["Repository-Level Coding Agent Context Files: An Empirical Study"](https://arxiv.org/abs/2602.11988)
- AGENTS.md open format: [github.com/agentsmd/agents.md](https://github.com/agentsmd/agents.md)
- GitHub analysis of 2,500+ AGENTS.md files: [github.blog](https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/)
- Augment Code guide: [augmentcode.com/guides/how-to-build-agents-md](https://www.augmentcode.com/guides/how-to-build-agents-md)
- Python packaging metadata: [packaging.python.org](https://packaging.python.org/specifications/declaring-project-metadata/)
