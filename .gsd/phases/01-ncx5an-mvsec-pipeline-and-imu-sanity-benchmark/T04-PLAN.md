---
estimated_steps: 29
estimated_files: 4
skills_used: []
---

# T04: Full verification suite and end-to-end synthetic validation proof

## Why
The full M001 artifact contract must be proven end-to-end: a synthetic `run → eval → validate` pipeline must exit 0 with all checks passed, and the complete test suite must be green. This is the closure proof for M001 — it demonstrates that all artifacts produced by the benchmark pipeline are accepted by the validation module without string mismatches or artifact contract violations.

## Do
1. **Run the full test suite** to confirm no regressions from T03 changes:
   ```
   rtk uv run --only-dev pytest tests/ -q
   ```
   All 155+ tests must pass (the count may increase by the regression test added in T03).

2. **Run lint and format checks**:
   ```
   rtk uv run --only-dev ruff check .
   rtk uv run --only-dev ruff format --check .
   ```
   Both must exit 0.

3. **Run a standalone synthetic end-to-end validation proof** to verify the complete `run → eval → validate` path. This can be done by running the existing `test_validate_after_run_and_eval` test individually, or by invoking the CLI directly in a temp directory:
   - Create a synthetic input directory using the test helper pattern from `tests/cli/test_validate_cli.py`
   - Run: `python -m nav_benchmark.run run --method imu_only --dataset synthetic --sequence smoke --input <input_dir> --output-root <output_dir>`
   - Run: `python -m nav_benchmark.run eval --run-dir <run_dir>`
   - Run: `python -m nav_benchmark.run validate --run-dir <run_dir>`
   - Confirm exit code 0 and output contains "checks passed"

4. **Confirm validation still rejects broken artifacts** — Run `test_validate_broken_manifest` and `test_validate_missing_trajectory` tests to confirm nonzero exits on invalid runs.

## Done-when
- All tests pass (`pytest tests/ -q` shows 0 failures).
- Lint and format are clean.
- The synthetic `run → eval → validate` path exits 0 with all checks passed.
- Broken artifact tests still fail validation (nonzero exit).

## Constraints
- No MVSEC data required — all proofs use synthetic data.
- Do not modify source files in this task — this is verification only.

## Inputs

- `src/nav_benchmark/validation.py`
- `src/nav_benchmark/run.py`
- `tests/validation/test_artifact_validation.py`
- `tests/cli/test_validate_cli.py`

## Expected Output

- Update the implementation and proof artifacts needed for this task.

## Verification

rtk uv run --only-dev pytest tests/ -q && rtk uv run --only-dev ruff check . && rtk uv run --only-dev ruff format --check .
