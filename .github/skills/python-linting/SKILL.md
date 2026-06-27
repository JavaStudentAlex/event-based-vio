---
name: python-linting
description: Run Python linting and formatting checks for the event-based-vio MVSEC benchmark project using uv and Ruff. Use when editing data loading, replay, baseline adapters, evaluation, ensemble code, tests, or repository Python tooling.
---

# Python Linting Skill

## Scope

- Data loading, replay, synchronization, baseline, evaluation, plotting, and
  ensemble Python modules, wherever they are added.
- Tests under `tests/`, when present.
- Configuration source of truth: `pyproject.toml` and `.github/workflows/ci-lint.yml`

All commands should go through `uv`.

## Quality Gates

```bash
uv run --only-dev ruff check .
uv run --only-dev ruff format --check .
```

If tests exist:

```bash
uv run pytest tests -q
```

## Current Formatting Policy

The repository is expected to stay globally Ruff-formatted. Keep generated
artifacts, local agent state, and virtualenv directories excluded through
`pyproject.toml` rather than by narrowing lint commands.

## Guardrails

- Do not change runtime behavior solely to satisfy linting unless the lint issue
  exposes a real bug.
- Re-run the relevant check after fixes.
- Pair linting with pytest or a deterministic smoke check when changes affect
  trajectory schema, timestamp/frame handling, metrics, plotting, or ensemble
  behavior.
