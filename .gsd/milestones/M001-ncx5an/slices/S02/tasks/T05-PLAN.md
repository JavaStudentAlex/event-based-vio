---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T05: Slice gate: lint, format, and test suite

Why: Enforce deterministic quality gates before S02 is considered done. Do: run ruff lint + format checks and the trajectory test subset to ensure style and behavior stability. Done when: all commands exit 0.

## Inputs

- `pyproject.toml`
- `src/nav_benchmark/trajectory/`
- `tests/trajectory/`

## Expected Output

- `pyproject.toml`
- `src/nav_benchmark/trajectory/`
- `tests/trajectory/`

## Verification

rtk uv run --only-dev ruff check . && rtk uv run --only-dev ruff format --check . && rtk uv run pytest tests/trajectory -q
