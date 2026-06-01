# Contributing

Thanks for helping improve `agents-md`.

## Local Setup

```bash
python -m pip install -e .[dev]
python -m pytest
```

Run one focused test while iterating:

```bash
python -m pytest tests/test_quality.py::test_scores_core_sections -xvs
```

## Pull Request Expectations

- Keep the core package dependency-light.
- Add or update tests for scanner, generator, lint, or CLI behavior changes.
- Preserve non-destructive update semantics.
- Keep public docs accurate and short.
- Do not commit secrets, real API keys, downloaded browser metadata, or local
  cache/build artifacts.

## Product Guardrails

Ask first before changing:

- Quality score thresholds or scoring weights
- Deduplication rules
- Managed marker comment format
- Default LLM provider/model choices
- Public package metadata

These choices shape user trust and should be discussed as product behavior.
