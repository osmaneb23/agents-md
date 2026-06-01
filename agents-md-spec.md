# agents-md — Complete Product & Technical Specification
> Version 1.0 · For the coding agent building this project

---

## 0. How to read this document

This document is written for a coding agent who is a skilled implementer but needs explicit human context to make good product decisions. For every feature, this doc explains: what it is, why it exists, what the user experience should feel like, and what "done" looks like. There is deliberately no code in this document — implementation is your domain. What is specified here is behaviour, UX, and intent.

When something is underspecified, default to the simplest thing that works and makes the user feel smart. When something is overspecified, trust the spec over your instinct about what seems more featureful.

---

## 1. Project overview

### What this is

`agents-md` is a Python CLI tool that analyses an existing software repository and generates an `AGENTS.md` file — a machine-readable context file that AI coding agents (Claude Code, OpenAI Codex, Cursor, GitHub Copilot, Aider, Gemini CLI, etc.) read at the start of every session to understand the project's conventions, commands, and constraints.

### The one-sentence pitch

> *The only AGENTS.md generator that makes your AI coding sessions faster — because it's the only one that understands why most generators make them slower.*

### Why this exists — the core research finding

ETH Zurich published a study (arxiv.org/abs/2602.11988, 2026) that evaluated AI coding agents across two benchmarks, comparing performance with LLM-generated context files, human-curated context files, and no context file. The key finding:

- **LLM-generated context files hurt performance in 5 out of 8 tested settings.** They increased inference cost by 20–23% and required 2–4 extra reasoning steps per task.
- **The reason:** auto-generators dump content the agent can already find in the README, the code structure, and existing docs. The agent then has to read all of this redundant text on every single task, and it actively interferes with performance rather than helping.
- **Human-curated files help slightly** (+4 percentage points) because humans instinctively write only the non-obvious stuff.
- **The fix:** before writing anything to AGENTS.md, check whether that information is already discoverable from the repo's existing documentation. Only write what is genuinely non-inferable.

This is the design principle that every competitor misses, and it is the entire reason this tool should exist. It is not a minor optimisation — it is the difference between a tool that helps and one that hurts.

**Source:** "Repository-Level Coding Agent Context Files: An Empirical Study," ETH Zurich, 2026. Available at https://arxiv.org/abs/2602.11988

---

## 2. Context: what is AGENTS.md and why do developers need it

### Background

AGENTS.md is an open standard, now stewarded by the Linux Foundation's Agentic AI Foundation (AAIF), and adopted by over 60,000 public GitHub repositories as of May 2026. Members of AAIF include OpenAI, Anthropic, Google, AWS, Bloomberg, and Cloudflare. The format was originally pioneered by OpenAI for Codex.

As of 2026, AGENTS.md is natively read by: Claude Code, OpenAI Codex CLI, Cursor, Aider, Devin, GitHub Copilot (since August 2025), Gemini CLI, Windsurf, Zed, Amazon Q, Factory Droids, Sourcegraph Amp, and more. It is the closest thing to a universal agent instruction format the industry has.

**Source:** https://blog.buildbetter.ai/agents-md-complete-guide-for-engineering-teams-in-2026/

### The problem it solves

Every AI coding agent starts each session completely blind to your project's specific conventions. The agent knows Python or TypeScript in general, but it does not know:
- That your team uses `pixi` instead of `pip`
- That your API client intentionally swallows exceptions and you should never wrap calls in try/catch
- That the `vendor/` directory must never be modified
- That you use `pnpm`, not `npm`
- That database migrations require explicit human approval before running
- That running `npm run build` inside a dev session breaks hot reload

These are the kinds of facts AGENTS.md is designed to communicate. Without it, the agent discovers these things the hard way — by making mistakes that a developer then has to fix.

### What a good AGENTS.md looks like (content spec)

Based on analysis of 2,500+ real-world repositories (source: GitHub blog, "How to Write a Great AGENTS.md: Lessons from Over 2,500 Repositories"), the sections that consistently improve agent behaviour are:

1. **Stack** — Language, framework, key libraries with version pins. Not just "uses React" but "React 19, TypeScript 5.x strict mode, pnpm 9.x, Node 22." The agent needs exact versions because different versions have different APIs.

2. **Commands** — The highest-ROI section. Exact commands to install, run, test, build, and lint. Must include exact flags, not just command names. Must distinguish CI-only commands from local commands. Must flag commands that require environment variables. Must call out any commands that are dangerous during an agent session (e.g., migration runners).

3. **Conventions** — Only the counterintuitive ones. "Use 2-space indentation" is Prettier's job. "Our error objects carry a `cause` field that must always be forwarded" is worth writing. The ETH study found that including general style conventions that a linter already enforces adds cost with no benefit.

4. **Boundaries** — The three-tier system that is the most battle-tested pattern in production AGENTS.md files:
   - *Always do* — things the agent should do automatically on every task (run tests before submitting, fix linting errors)
   - *Ask first* — things that require human approval before proceeding (schema changes, migrations, deleting files)
   - *Never do* — hard stops (never commit secrets, never modify `vendor/`, never run `db:reset` without explicit instruction)

5. **Testing instructions** — How to run a single test, not just the full suite. Agents run the full suite and it is slow and expensive. "Run a single test with `pytest tests/test_auth.py::test_login -xvs`" is more useful than "run `pytest`."

6. **Security considerations** — How secrets are managed, what env vars are expected, what patterns to avoid.

**What not to include:**
- Architecture summaries and codebase overviews (the ETH study found these specifically do not help — agents discover structure independently)
- Anything already in the README
- Style rules that are enforced by a linter or formatter
- General best practices that any competent developer knows

**Size guidance:** The community consensus (and ETH study) points to under 150 lines as optimal. The Codex CLI silently truncates files past `project_doc_max_bytes`. A focused 50-line file outperforms a 500-line one. The tool should print the line count after generation and flag if it exceeds 150.

**Source:** https://www.augmentcode.com/guides/how-to-build-agents-md

---

## 3. Competitive landscape

The following tools attempt to generate AGENTS.md files. None of them is a serious threat, but the coding agent should understand them to avoid accidentally building the same thing.

### `Paldom/agents-init` (npm)
- **What it does:** Runs `npx agents-init@latest` and sets up AGENTS.md, CLAUDE.md, MCP server config, and subagents in one shot. Ambitious scope.
- **The problem:** No ETH-aware filtering. It generates content without checking the README for duplication. It also tries to do too many things (MCP setup, subagents) which dilutes the core value. Low star count (estimated 50–200 based on author profile).
- **Our advantage:** We do one thing and we do it correctly. The quality of the generated file is demonstrably better.

### `originalankur/GenerateAgents.md` (PyPI)
- **What it does:** Uses DSPy's recursive LLM implementation to generate AGENTS.md. Supports any model via LiteLLM.
- **The problem:** DSPy is a heavyweight dependency that dramatically slows installation. No deduplication against existing docs. Likely generates the kind of bloated file the ETH study warns against. ~10–30 stars.
- **Our advantage:** `pip install agents-md` takes 10 seconds. No DSPy, no heavy deps. Better output quality.

### `markoblogo/AGENTS.md_generator` (Python)
- **What it does:** Safe-by-default CLI with marker-based patches. Intentionally conservative — "auto-detect is no smart analysis, commands can be empty on purpose."
- **The problem:** Explicitly avoids intelligence. Produces skeleton files that developers still have to fill in manually. Doesn't use an LLM at all.
- **Our advantage:** We actually analyse the codebase and synthesise meaningful content.

### `nyosegawa/agents-md-generator` (shell)
- **What it does:** Shell wrapper that creates a starter AGENTS.md when cloning an *empty* repository.
- **The problem:** Only works on empty repos. Not relevant for the primary use case (existing projects).
- **Our advantage:** Works on any existing repo regardless of size.

### `netresearch/agent-rules-skill` (npm)
- **What it does:** An Agent Skill (Claude Code skill) that generates AGENTS.md from within a Claude Code session.
- **The problem:** Requires Claude Code to already be running. Not a standalone tool. Can't be used in CI.
- **Our advantage:** Standalone CLI, works anywhere.

### Verdict
No competitor has: ETH-aware filtering + LLM synthesis + a lint command + an update command + a quality score. The space has early entrants but no clear winner.

---

## 4. Target users

Understanding who uses this, and how, is critical for making good UX decisions. There are three distinct user types.

### User type 1: The solo vibe coder
**Who they are:** A developer building a project alone, using Claude Code or Cursor heavily. They've read about AGENTS.md but writing one from scratch feels like work they'd rather automate.

**Their workflow:** They run `agents-md init` once at the start of a project. They want it to "just work" — they don't want to answer questions or configure anything. They trust the tool to make good decisions. They care about the terminal output looking clean and professional.

**What they need:**
- Zero-friction install (`pip install agents-md` or `uvx agents-md`)
- One command to run (`agents-md init`)
- A good result that they can immediately use without editing
- Confidence that it won't generate junk (the quality score provides this)

**What they don't need:** Configuration files, elaborate options, multi-step wizards.

### User type 2: The team lead
**Who they are:** An engineering lead at a company using AI coding agents across a team. They want consistent, maintainable AGENTS.md files across repos. They care about drift — the file becoming stale as the codebase evolves.

**Their workflow:** They run `agents-md init` to bootstrap, then add `agents-md update` to a CI pipeline or pre-commit hook. They want to own the file — the tool should respect their manual edits and only patch sections that have changed.

**What they need:**
- `agents-md update` that is non-destructive (patches sections, doesn't overwrite the whole file)
- `agents-md lint --check` that returns a non-zero exit code for CI
- A GitHub Action that wraps the lint command
- `--no-llm` mode so CI doesn't need an API key

**What they don't need:** Anything that requires interactive input in CI.

### User type 3: The existing AGENTS.md owner
**Who they are:** A developer who already wrote their AGENTS.md by hand and wants to know if it is good. They found the tool through the lint command specifically.

**Their workflow:** They run `agents-md lint` on their existing file and look at the score. They might run `agents-md lint --fix` to auto-clean redundant sections.

**What they need:**
- `agents-md lint <path>` that works on any file, not just generated ones
- A score that is meaningful and explained (not just a number)
- Actionable feedback: "lines 12–18 duplicate content already in your README"

**What they don't need:** The generation pipeline at all.

---

## 5. Feature specification — v1 (MVP)

### 5.1 `agents-md init`

**Purpose:** The main command. Analyses the current directory and generates an AGENTS.md file.

**Default behaviour (no flags):**
1. Scans the repo (see Section 6 for what is scanned)
2. Reads existing documentation (README, CONTRIBUTING, docs/) to build the deduplication exclusion set
3. Runs all extractors in parallel
4. Filters extracted content through the deduplication exclusion set
5. Calls the configured LLM with filtered content and a strict synthesis prompt
6. Writes `AGENTS.md` to the current directory
7. Creates a `CLAUDE.md` symlink pointing to `AGENTS.md` (because Claude Code reads CLAUDE.md specifically)
8. Prints a quality score and summary to the terminal

**Flags the command must support:**
- `--no-llm` — skip LLM synthesis, write a structured template populated with extracted data only. The file will be less polished but zero API cost. This is the mode used in CI.
- `--provider [anthropic|openai|ollama|gemini]` — which LLM provider to use for synthesis. Should auto-detect from environment variables if not specified (ANTHROPIC_API_KEY present → anthropic, OPENAI_API_KEY present → openai).
- `--model <model-id>` — override the default model for the chosen provider
- `--output <filename>` — write to a specific filename instead of `AGENTS.md`
- `--no-symlink` — don't create the CLAUDE.md symlink
- `--dry-run` — print what would be generated without writing any files. Shows the detected stack, extracted commands, and identified conventions.
- `--force` — overwrite an existing AGENTS.md without prompting. Default behaviour (without this flag) should prompt if the file already exists.
- `--no-dedup` — skip the deduplication step. Only for power users who want to understand what deduplication removed. Should warn clearly when used.
- `--verbose` — show each extractor's output before synthesis

**UX details that matter:**
- The command should show a progress indicator while running (e.g., "Scanning repo... Extracting commands... Deduplicating... Synthesizing..."). Silence feels broken.
- After writing the file, the terminal output should show a summary: how many lines were generated, the quality score out of 100, how many items were excluded by deduplication, and the path to the written file.
- If no LLM API key is found and `--no-llm` was not passed, the command should not fail silently. It should print a clear message explaining how to set a key OR offer to run in `--no-llm` mode instead.
- The command must be idempotent: running it twice on the same repo should produce the same output.

**What the output file must contain (minimum viable output):**
Even in `--no-llm` mode, the output must have: detected stack with versions, all non-obvious commands extracted from manifests, a placeholder boundaries section with the three tiers labelled, and a placeholder testing section. A completely empty or nearly-empty output is worse than no output — it will hurt the user's trust.

---

### 5.2 `agents-md update`

**Purpose:** Re-analyse the repo and update only the sections of an existing AGENTS.md that have changed. Preserves all manual edits.

**How it works conceptually:**
The tool uses marker comments to identify the sections it "owns" vs sections the user wrote manually. When first generating, it wraps each auto-generated section in marker comments like `<!-- agents-md:start:commands -->` and `<!-- agents-md:end:commands -->`. On update, it only replaces content inside markers, leaving everything else untouched.

**UX details:**
- If the existing file has no markers (i.e., it was written by hand), `agents-md update` should not touch it. Instead it should print "No managed sections found. Run `agents-md init --merge` to add managed sections without overwriting your file." This is important — a tool that silently destroys hand-written content will immediately lose user trust.
- Should print a diff of what changed: "Updated: commands (3 changes), stack (1 change). Preserved: conventions, boundaries (user-managed)."
- Must support `--no-llm` for CI use.

---

### 5.3 `agents-md lint`

**Purpose:** Evaluate any AGENTS.md file against quality criteria and return a score with actionable feedback. Works on any file, not just ones generated by this tool.

**This command is important for adoption.** Developers who already have an AGENTS.md will run lint to check their file. This is a separate entry point into the tool that doesn't require buying into the generation workflow first. It also surfaces the ETH research findings to users who haven't heard of them.

**What it scores (0–100):**
- Does the file have a commands section? (20 points) — Commands are the highest-ROI section per all research.
- Does the file have a boundaries section with the three tiers? (20 points)
- Is the file under 150 lines? (15 points — proportional, starts deducting at 100 lines)
- Does the file contain content that duplicates the README? (−15 points per detected duplication — this requires reading the README from the same directory)
- Does the file contain general style rules a linter already handles? Pattern-match against known linter-owned concerns (indentation, trailing commas, quote style, semicolons). (−10 points per flagged section)
- Does the file have a testing section showing how to run a single test? (10 points)
- Are commands specific (exact flags included) vs vague ("run the tests")? (15 points)

**Output format:**
- A score displayed prominently: `Score: 74/100`
- A breakdown by criterion showing points earned and points lost
- Specific line references for issues: "Lines 12–18: duplicates content already in README.md (architecture overview)"
- A one-line verdict: "Good file. Focus on adding single-test commands."

**Flags:**
- `agents-md lint <path>` — lint a specific file. Defaults to `./AGENTS.md` if no path given.
- `--check` — exit with non-zero status code if score is below threshold (default 60). For CI use. No interactive output, just the exit code.
- `--threshold <n>` — set a custom threshold for `--check`
- `--fix` — auto-remove sections flagged as duplicating the README or containing linter-owned rules. Writes the cleaned file. Must prompt for confirmation unless `--yes` is passed. Always creates a `.bak` backup first.
- `--json` — output results as JSON for programmatic use (piping into other tools, GitHub Actions annotations)

---

### 5.4 `agents-md diff`

**Purpose:** Show what has changed in the codebase since the AGENTS.md was last generated, so the developer knows whether an update is warranted.

**How it works:** The tool stores a lightweight fingerprint of the repo state (hashes of key files: package.json, pyproject.toml, go.mod, etc.) when it generates or updates. `agents-md diff` compares the current state to that fingerprint and reports what has changed in the dependency, script, or configuration files that the tool cares about.

**UX:** Output should feel like a git status but for AGENTS.md relevance: "package.json scripts: 2 added, 1 removed. pyproject.toml: no change. .eslintrc: 1 rule added. Recommendation: run `agents-md update` to sync."

If no fingerprint exists (file was hand-written or generated by another tool), print a helpful message and suggest running `agents-md init` or `agents-md update --init-fingerprint`.

---

## 6. What the scanner and extractors must detect

This section describes the semantic targets for each extractor. Implementation details are up to the coding agent.

### 6.1 Stack detection

For each language ecosystem, the tool must detect:

**JavaScript / TypeScript:**
- Package manager: presence of `pnpm-lock.yaml`, `yarn.lock`, `bun.lockb`, `package-lock.json` — in that priority order (pnpm-lock.yaml → pnpm, etc.)
- Framework: `next` in dependencies → Next.js; `vite` → Vite; `astro` → Astro; `svelte` → Svelte; etc.
- Language: presence of `tsconfig.json`, `.ts` files → TypeScript. Note if `strict` mode is enabled in tsconfig.
- Runtime: `bun` in scripts or `.bun` file → Bun; otherwise Node
- Test runner: `jest`, `vitest`, `mocha`, `playwright`, `cypress` in devDependencies

**Python:**
- Package manager: `pixi.toml` → Pixi (very non-standard, must be explicitly flagged); `uv.lock` → uv; `poetry.lock` → Poetry; `Pipfile` → Pipenv; `requirements.txt` → pip
- Framework: `fastapi`, `flask`, `django`, `starlette` in dependencies
- Linter/formatter: `ruff`, `black`, `flake8`, `pylint` in devDependencies or tool config
- Type checker: `mypy`, `pyright` in config files
- Test runner: `pytest` (default), `unittest`

**Go:**
- Detect from `go.mod` presence
- Framework: `gin`, `echo`, `fiber`, `chi` in go.mod

**Rust:**
- Detect from `Cargo.toml`
- Test runner is always `cargo test` but flag if there are integration tests in `tests/`

**General:**
- CI/CD: detect `.github/workflows/` → GitHub Actions; `.gitlab-ci.yml` → GitLab CI; `Makefile` → Make targets
- Docker: `Dockerfile` or `docker-compose.yml` presence
- Monorepo: presence of `pnpm-workspace.yaml`, `nx.json`, `turbo.json`, `lerna.json`, `workspace` key in root package.json

**Important:** Do not guess. If the package manager cannot be determined with confidence, leave it blank rather than guess wrong. A wrong command in AGENTS.md is worse than a missing one.

---

### 6.2 Commands extraction

**Source files to parse:**
- `package.json` → `scripts` section
- `Makefile` → public targets (those without leading underscore or dot)
- `pyproject.toml` → `[tool.taskipy]`, `[tool.poe.tasks]`, `[tool.scripts]` sections
- `Justfile` → all recipes
- `Taskfile.yml` / `Taskfile.yaml` → all tasks

**What to extract:**
- The install command (e.g., `pnpm install`, `uv sync`, `cargo build`)
- The dev/run command (e.g., `pnpm dev`, `uvicorn main:app --reload`)
- The build command
- The test command (full suite)
- The single-test command — this requires inference. For pytest: `pytest <path>::<test> -xvs`. For jest: `jest --testPathPattern=<path> --testNamePattern=<name>`. For cargo: `cargo test <test_name>`. This is high value and worth doing well.
- The lint command
- The typecheck command (if separate from lint)
- Any migration or database commands — flag these explicitly as "requires human approval" in the boundaries section

**What not to extract:**
- Commands with no user-facing value (internal CI steps, generated commands)
- Commands that are obviously wrappers around other commands at the same abstraction level (if `test` just calls `test:unit && test:e2e`, extract the sub-commands, not the wrapper)

---

### 6.3 Conventions detection

This is the hardest extractor and the most valuable. The goal is to find the counterintuitive patterns specific to this codebase that an AI agent would not guess correctly.

**What to look for:**

*Import patterns:*
- Does the codebase use named exports exclusively (no default exports)? Detectable from AST analysis of source files.
- Are there barrel files (`index.ts`) that re-export everything? Flag the pattern.
- Is there a custom path alias pattern (`@/components/`, `~/utils/`)? Extract from tsconfig or vite config.

*Error handling patterns:*
- Does the codebase have a custom error class hierarchy? Identify the base error class.
- Is there a pattern of returning `Result<T, E>` types instead of throwing? Detectable from function return types.
- Does the API client/fetch layer swallow exceptions by design? Look for catch blocks that return null or a typed error object instead of re-throwing.

*API / HTTP patterns:*
- Is there a custom fetch wrapper or API client that all requests go through? Identify it and name it.
- Are there environment-specific base URLs that must be used?

*Testing patterns:*
- What is the test file naming convention? `*.test.ts`, `*.spec.ts`, `__tests__/`, `tests/`?
- Is there a test database that must be set up before running tests?
- Are there fixtures or factories that should be used instead of creating test data directly?

**Calibration:** Err toward extracting less. A convention is worth documenting only if an AI agent would plausibly get it wrong on the first try. "Functions are named in camelCase" is not worth documenting. "All database queries must go through the repository layer in `/src/repos/` and never be called directly from controllers" is worth documenting.

---

### 6.4 Deduplication (the ETH filter)

This is the most important extractor — see Section 2 for the research backing.

**Process:**
1. Read every markdown file in the root directory and `docs/` directory
2. Extract facts from those files — specifically: any mention of commands, any mention of frameworks or libraries, any description of project structure, any statement about conventions
3. Build an exclusion set from these facts
4. For every candidate line in the generated AGENTS.md (from all other extractors), check whether it communicates the same information as something in the exclusion set
5. If yes, exclude it from the output

**Practical example:**
- README says: "We use pnpm. Run `pnpm install` to get started."
- Commands extractor extracted: "Package manager: pnpm. Install: `pnpm install`"
- Deduplication removes the package manager and install command from the output, because the agent can already read the README.

**What deduplication must NOT remove:**
- Commands with specific flags that the README doesn't include (README: "run the tests" → AGENTS.md: "pytest -xvs tests/unit/test_auth.py" — the flags are new information)
- Counterintuitive constraints (even if the README mentions a convention, if it's a "never do this" boundary, keep it — boundaries are important enough to repeat)
- Security-relevant instructions

**Output of this step:** A filtered version of every extractor's output, with a log of what was removed and why. This log is used by `agents-md lint` and is displayed in `--verbose` mode.

---

### 6.5 LLM synthesis prompt (what the synthesis prompt must achieve)

The coding agent will write the actual prompt. This section describes what the prompt must produce, not the prompt itself.

The LLM call must produce output that:
1. Is under 150 lines
2. Does not include architecture overviews or codebase tours
3. Does not include style rules that a linter already enforces
4. Writes commands with exact flags, not vague descriptions
5. Uses the three-tier boundary system (Always do / Ask first / Never do)
6. Has a single test command that targets one test, not the full suite
7. Does not include content that was removed by the deduplicator

The prompt must instruct the LLM to refuse to pad the output. If there is not much to say, the output should be short. A 30-line file is better than a 150-line file if the repo is simple.

The model used for synthesis should be a capable reasoning model (e.g., claude-sonnet-4-6, gpt-4.1). This is not a task for a small/fast model — the quality of the synthesis directly impacts whether the tool is trusted.

---

## 7. Quality score specification (for `agents-md lint`)

The score is the primary trust mechanism. It must feel fair and actionable — not opaque.

| Criterion | Max points | How it's measured |
|---|---|---|
| Commands section present | 10 | Section heading + at least 2 commands |
| Commands have exact flags | 15 | Regex check for flags (`-x`, `--watch`, etc.) in command lines |
| Single-test command present | 10 | Detects test command targeting a specific file/function |
| Boundaries section with all three tiers | 20 | Presence of "Always", "Ask first" / "Ask before", "Never" labels |
| Testing section present | 10 | Separate section for testing instructions |
| File under 150 lines | 15 | Proportional: 15pts ≤ 80 lines, scales down to 0pts at 300 lines |
| No README duplication detected | 15 | Checks against README in same directory |
| No linter-owned rules | 5 | Pattern match against common style rules |

**Penalty:** −5 points for every section that duplicates README content (after the first). Minimum score is 0.

**Score interpretation displayed to user:**
- 85–100: "Excellent. This file will improve agent performance."
- 65–84: "Good. A few improvements would help."
- 45–64: "Needs work. Key sections are missing or redundant content is present."
- 0–44: "This file may be hurting agent performance. See recommendations."

The score breakdown must show exactly which criteria were passed and failed, with line references where applicable.

---

## 8. Multi-tool output specification

AGENTS.md is the canonical source of truth. All other files should be derived from it, never independently maintained. The tool manages this with symlinks or includes.

**Files the tool creates:**
- `AGENTS.md` — always created. This is the source of truth.
- `CLAUDE.md` — symlink to AGENTS.md by default (Claude Code reads CLAUDE.md). Can be suppressed with `--no-symlink`.

**What the tool does NOT create:**
- `.cursorrules` — Cursor now reads AGENTS.md natively. No need.
- `.github/copilot-instructions.md` — GitHub Copilot reads AGENTS.md natively since August 2025. No need.
- Anything in `.claude/` or `.codex/` — out of scope for v1.

**Monorepo note (v1 behaviour):** If a monorepo is detected (via workspace config files), the tool generates a root AGENTS.md with project-wide conventions. It does NOT generate per-package AGENTS.md files in v1 — this is a v2 feature. The root file should have a note: "See individual package directories for package-specific instructions (not yet configured)." This is better than pretending monorepos don't exist.

---

## 9. Installation and distribution

### Primary distribution method: PyPI

The package name is `agents-md`. It should be installable via:
- `pip install agents-md`
- `uv tool install agents-md` (preferred for isolated install)
- `uvx agents-md init` (one-shot, no install required — this is the lowest-friction entry point)
- `pipx install agents-md`

### The tool must NOT require:
- Node.js or npm
- Docker
- Any heavy ML dependencies (no torch, no transformers, no DSPy)

### Optional extras (installed on demand):
The LLM provider SDKs should be optional extras, not hard dependencies:
- `pip install agents-md[anthropic]` — adds anthropic SDK
- `pip install agents-md[openai]` — adds openai SDK
- `pip install agents-md` — core only, works in `--no-llm` mode without any LLM SDK

This design is important. A developer at a company with strict dependency policies should be able to install the tool without any LLM SDK and use `--no-llm` mode. If the anthropic/openai SDK is a hard dependency, they will not be able to install it at all.

### GitHub Action

A companion GitHub Action (`agents-md-action`) should be publishable to the GitHub Marketplace. The action runs `agents-md lint --check` on every PR and optionally fails the PR if the score falls below a threshold or if AGENTS.md is missing.

The action is a separate, lightweight wrapper — not a separate codebase, just a thin GitHub Action YAML that installs and runs the CLI. It should be in the same repository under `.github/actions/agents-md-lint/`.

---

## 10. The project's own AGENTS.md

This is not optional and not an afterthought. The `agents-md` repository must ship with its own AGENTS.md, generated by `agents-md init`. This is the primary credibility signal for the tool.

Every developer who visits the repo to evaluate it will look at the AGENTS.md in the root. If it is absent, it destroys trust. If it is poorly written, it destroys trust. If it is excellent, it immediately demonstrates the tool's capability.

The AGENTS.md for this project should demonstrate:
- Exact commands: how to install, run tests, add a new extractor, run lint
- Boundaries: what to never touch (the synthesis prompt wording, the quality score thresholds — these are product decisions not implementation details), when to ask before changing (score weights, deduplication logic)
- Conventions: the testing patterns used, the extractor output format (typed JSON), the file naming conventions

---

## 11. Launch context — OpenAI Codex for Open Source program

The primary goal beyond building a useful tool is acceptance into OpenAI's Codex for Open Source program. Understanding this context helps the agent make decisions that align the project with acceptance criteria.

**What the program provides:** 6 months of free ChatGPT Pro with Codex, elevated API quotas, and conditional access to Codex Security (powered by GPT-5.4). Eligibility requires active open-source projects with meaningful usage and broad adoption. 1,000+ GitHub stars is the informal threshold cited publicly.

**Source:** https://mlq.ai/news/openai-rolls-out-free-chatgpt-pro-and-codex-access-for-open-source-maintainers/

**What this means for technical decisions:**

1. The tool must demonstrably use Codex in its workflow. The LLM synthesis step should support OpenAI Codex as a provider option. The README should explicitly describe this. This is not just marketing — the program explicitly rewards "projects that use Codex in pull request review, maintainer automation, release workflows, or other core OSS work."

2. Active maintenance signals matter: commits, issue responses, PR reviews. The project should be set up for easy contribution from day one — clear CONTRIBUTING.md, issue templates, good test coverage.

3. The GitHub Action is important for adoption metrics. More repos using the action → more evidence of meaningful usage.

4. Apply at 500 stars, not 1,000. The form explicitly states: "If a project does not neatly fit the criteria but plays an important role in the ecosystem, applicants should still apply and explain why." A well-articulated application citing the ETH research and the direct impact on AI coding workflows is worth applying with 500 stars.

---

## 12. v2 roadmap (do not build in v1)

These features are documented here so that v1 architecture decisions do not accidentally block them. The coding agent should keep these in mind when making structural choices, but should NOT build them in v1.

- **Per-package AGENTS.md in monorepos** — Generate a root AGENTS.md plus per-package files in a monorepo, with inheritance (root rules apply to all packages, package rules override for specific directories). This requires understanding the monorepo structure well enough to assign rules to scopes.

- **VS Code extension** — A right-click menu option "Generate AGENTS.md for this workspace" that runs the CLI behind the scenes. This massively expands the addressable audience beyond CLI-comfortable developers.

- **`agents-md watch` mode** — Monitors key files (package.json, pyproject.toml, etc.) for changes and automatically runs `agents-md update` when a relevant change is detected. Useful for teams.

- **Template library** — A curated set of AGENTS.md templates for common stacks (Next.js + Prisma, FastAPI + SQLAlchemy, Rails, etc.) that can be used as a starting point when the static analysis is insufficient. Templates are a fallback, not the primary path.

- **`agents-md score` as a PR check** — Beyond just linting the AGENTS.md file, scoring the quality of how the AGENTS.md was *used* in a session by analysing PR diffs and agent logs.

---

## 13. Non-negotiable UX principles

These apply to every command, every output, and every error message:

1. **Never fail silently.** If something goes wrong, say what went wrong and what to do about it. "Error: could not detect package manager. Pass `--package-manager pnpm` to specify manually" is acceptable. A stack trace with no guidance is not.

2. **Never destroy data without confirmation.** Any command that would overwrite a file must either prompt for confirmation OR require an explicit `--force` or `--yes` flag. The `--fix` flag on `lint` must create a `.bak` backup before writing.

3. **Offline first.** Every command must degrade gracefully when there is no internet connection or LLM API key. `--no-llm` should always produce something useful.

4. **The output file is the product, not the terminal output.** The terminal output should be informative but secondary. The generated AGENTS.md is what the user cares about. Make sure the file is the best thing in the interaction.

5. **Short is better than long.** This applies to the generated file and to the tool's own documentation. Every word in the generated AGENTS.md should earn its place. The tool should feel opinionated about this.

6. **The error when no API key is found must explain all three paths forward:** set the key, pass the key inline, or run with `--no-llm`. Users should never have to Google how to fix a missing API key error.

---

## 14. Sources and further reading

All claims in this document are backed by the following sources, which the coding agent may reference for additional context:

- **ETH Zurich study (primary research):** "Repository-Level Coding Agent Context Files: An Empirical Study" — https://arxiv.org/abs/2602.11988
- **AGENTS.md complete guide (structure + examples):** https://blog.buildbetter.ai/agents-md-complete-guide-for-engineering-teams-in-2026/
- **GitHub's analysis of 2,500+ AGENTS.md files:** https://github.blog/ai-and-ml/github-copilot/how-to-write-a-great-agents-md-lessons-from-over-2500-repositories/
- **Augment Code guide on building AGENTS.md:** https://www.augmentcode.com/guides/how-to-build-agents-md
- **OpenAI Codex for Open Source program:** https://developers.openai.com/community/codex-for-oss
- **AAIF (Agentic AI Foundation, Linux Foundation):** https://github.com/agentsmd/agents.md
- **Effective patterns for AGENTS.md:** https://blakecrosley.com/blog/agents-md-patterns
- **Complete 2026 AGENTS.md spec:** https://codersera.com/blog/agents-md-complete-guide-2026/
- **Compliance gap between AGENTS.md and runtime hooks:** https://gist.github.com/0xfauzi/7c8f65572930a21efa62623557d83f6e (note: compliance is 25–40% from AGENTS.md alone vs ~95% with runtime enforcement — this is out of scope for v1 but relevant context)
- **DeployHQ guide on common AGENTS.md mistakes:** https://www.deployhq.com/blog/ai-coding-config-files-guide (especially the "Using /init or auto-generators" section which validates our differentiation)

---

*End of specification. If anything in this document conflicts with itself, the more restrictive or cautious interpretation is correct.*
