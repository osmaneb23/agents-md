# Release Checklist

Use this checklist for every public release. Keep releases boring: one version, one tag, one PyPI upload, then verify the install path users actually run.

## Before the Release

1. Decide the next version.
2. Update `pyproject.toml`.
3. Update `src/agents_md/__init__.py`.
4. Update `.github/actions/agents-md-lint/action.yml` so the default `version` input matches the package version.
5. Update README examples that mention the release tag or package version.
6. Update relevant status notes in `docs/LEAN_IMPROVEMENT_IDEAS.md`.
7. Run `PYTHONPATH=src python -m agents_md update --no-llm`.

## Local Verification

Run these from the repository root:

```bash
PYTHONPATH=src uv run --no-project --with pytest python -m pytest
python -m compileall -q src
PYTHONPATH=src python -m agents_md lint AGENTS.md --check --threshold 70 --fail-on-placeholder --max-lines 150 --max-bytes 32000
PYTHONPATH=src python -m agents_md diff
git diff --check
uv run --no-project --with build python -m build
uv run --no-project --with twine python -m twine check dist/agent_context_md-*.tar.gz dist/agent_context_md-*.whl
```

Then install the wheel that was just built:

```bash
rm -rf /tmp/agents-md-wheel-check
python -m pip install --target /tmp/agents-md-wheel-check dist/agent_context_md-<version>-py3-none-any.whl
PYTHONPATH=/tmp/agents-md-wheel-check /tmp/agents-md-wheel-check/bin/agents-md --version
```

## Publish

1. Commit the release changes.
2. Push `main`.
3. Wait for CI to pass on the release commit.
4. Create a GitHub release tag such as `v0.2.2`.
5. Let `.github/workflows/publish.yml` publish through PyPI Trusted Publishing.
6. Confirm the Publish workflow completed successfully.

The publish workflow intentionally keeps publishing isolated: build artifacts are created in one job, then the PyPI job only downloads those artifacts and publishes them with `id-token: write`.

## After Publish

Verify PyPI and the user install paths:

```bash
python -m pip index versions agent-context-md
rm -rf /tmp/agents-md-pypi-check
python -m pip install --no-cache-dir --target /tmp/agents-md-pypi-check agent-context-md==<version>
PYTHONPATH=/tmp/agents-md-pypi-check /tmp/agents-md-pypi-check/bin/agents-md --version
uvx --refresh --from agent-context-md==<version> agents-md --version
```

Fetch tags locally:

```bash
git fetch --tags origin
git tag --points-at HEAD
```

## Sources

- PyPI Trusted Publishers: https://docs.pypi.org/trusted-publishers/
- Publishing with a Trusted Publisher: https://docs.pypi.org/trusted-publishers/using-a-publisher/
- PyPI Trusted Publishing security model: https://docs.pypi.org/trusted-publishers/security-model/
