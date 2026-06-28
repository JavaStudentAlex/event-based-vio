---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T05: Format python files with ruff format

Run ruff format to auto-format the source and test files to satisfy code styling requirements.

## Inputs

- None specified.

## Expected Output

- `src/nav_benchmark/baselines/imu.py`
- `src/nav_benchmark/run.py`
- `tests/baselines/test_imu_only_smoke.py`

## Verification

uv run ruff format --check .
