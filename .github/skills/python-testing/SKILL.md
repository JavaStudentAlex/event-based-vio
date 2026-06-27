---
name: python-testing
description: Run pytest for the event-based-vio MVSEC benchmark project using uv. Use when changing data loading, synchronization, trajectory export, metrics, baseline adapters, ensemble behavior, tests, or debugging failures.
---

# Python Testing Skill

Use this skill to run and inspect Python tests for this repository.

## Scope

- Test directory: `tests/`, when present
- Shared fixtures: `tests/conftest.py`, when present
- Preferred execution wrapper: `uv run ...`
- CI target-selection reference: `.github/workflows/ci-tests.yml`

## Running Tests

```bash
uv run pytest tests -q
```

Suggested targeted commands when tests exist:

```bash
uv run pytest tests/test_replay.py -q
uv run pytest tests/test_trajectory_io.py -q
uv run pytest tests/test_metrics.py -q
uv run pytest tests/test_ensemble.py -q
```

## Target Selection

- MVSEC loader changes -> small synthetic HDF5/CSV/YAML fixtures where possible.
- Replay/synchronization changes -> timestamp ordering and interpolation tests.
- Trajectory IO changes -> required CSV schema and invalid-row handling tests.
- Metric changes -> synthetic ATE, RPE, drift, and failure-count tests.
- Ensemble changes -> deterministic confidence/health/fusion tests.
- Plot/report changes -> `tmp_path` output checks without requiring the full
  MVSEC dataset.

## Pass Criteria

- The selected test command exits with code `0`.
- All collected tests pass.
- Any skipped or blocked external-LLM, deployment, or data-zip checks are named
  explicitly.

## Troubleshooting

If dev dependencies are missing:

```bash
uv sync --group dev
```
