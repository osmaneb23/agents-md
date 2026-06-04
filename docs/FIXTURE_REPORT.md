# Fixture Report

This is a small first-run sanity report, not a benchmark and not proof that agent performance improves. It exists to show what `agents-md` emits on tiny repo shapes and to catch obvious regressions as detectors change.

Generated with `agents-md 0.2.1` from `tests/fixtures/repos/*` using:

```bash
agents-md explain --json
```

| Fixture | Shape | Lines | Quality | Commands | Conventions | Warnings | Dedup removed |
|---|---|---:|---:|---:|---:|---|---:|
| `python_cli` | Python CLI with `uv.lock`, `[project.scripts]`, pytest | 52 | 100 | 5 | 1 | none | 0 |
| `typescript_app` | Next.js/Vitest app with aliases, barrel export, env example, HTTP wrapper | 60 | 93 | 5 | 8 | `command-placeholders` | 0 |

Useful observations:

- The Python CLI fixture produces `uv run demo-cli`, not a self-reference to `agents-md`.
- The TypeScript fixture finds barrel imports, `Result<...>` error-as-value flow, centralized HTTP calls, and env vars.
- The TypeScript fixture still warns about placeholder single-test targets because it has a test runner but no concrete test file. That is intentional.
- Both outputs stay well below the 150-line budget.

Keep this report small. Add a row only when a fixture represents a repo shape that would catch a real detector regression.
