---
applyTo: "**/*.py"
description: "Python linting, formatting, and test gate policy."
---

# Python Quality Gates

## Tooling Rules

- Use `uv run ...` from the repository root.
- Use `pyproject.toml` as the source of truth for tool configuration.
- Use Ruff for linting.
- Use `pytest` for running tests.

## Quality Gates

Run from the repository root when Python code changes:

```bash
uv run --only-dev ruff check .
uv run --only-dev ruff format --check .
```

If tests exist, also run:

```bash
uv run pytest tests -q
```

## Review Policy

- Check that production code uses clear type hints around trajectory rows,
  sensor samples, and metric results.
- Ensure timestamp units, coordinate frames, and quaternion ordering are
  explicit at module boundaries.
- Ensure benchmark math is covered by deterministic tests where feasible.
- Ensure dataset-dependent checks can be skipped explicitly without pretending
  the full MVSEC benchmark ran.
