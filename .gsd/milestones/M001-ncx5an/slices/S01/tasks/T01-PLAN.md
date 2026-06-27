---
estimated_steps: 3
estimated_files: 2
skills_used: []
---

# T01: Verified MVSEC dataset loader and ran code style and formatting checks.

Why: Prove the existing MVSEC loader and tests uphold the slice contract so downstream slices can trust the sequence object and diagnostics.
Do: Use uv via rtk to run ruff lint/format checks and execute the dataset loader tests. Tests cover events, IMU, images, ground truth, calibration, timestamp monotonicity, and layout mismatch diagnostics.
Done-when: All commands exit 0 and tests pass without xfail/skip for required behaviors.

## Inputs

- `src/nav_benchmark/datasets/mvsec.py`
- `tests/nav_benchmark/datasets/test_mvsec.py`

## Expected Output

- `src/nav_benchmark/datasets/mvsec.py`
- `tests/nav_benchmark/datasets/test_mvsec.py`

## Verification

rtk uv run --only-dev ruff check . && rtk uv run --only-dev ruff format --check . && rtk uv run pytest tests/nav_benchmark/datasets/test_mvsec.py -q
