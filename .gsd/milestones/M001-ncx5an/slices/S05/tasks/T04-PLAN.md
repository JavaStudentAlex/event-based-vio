---
estimated_steps: 11
estimated_files: 1
skills_used: []
---

# T04: Implemented end-to-end CLI integration tests for the validate subcommand.

**Why:** The validate subcommand must work end-to-end: run synthetic → eval → validate, confirming the full pipeline produces valid artifacts. Also need to verify validate catches intentionally broken artifacts.

**Do:**
1. Create `tests/cli/test_validate_cli.py` with pytest tests:
   - `test_validate_after_run_and_eval` — Use subprocess to run the full pipeline: `python -m nav_benchmark.run run --method imu_only --dataset synthetic --sequence smoke_val --output-root <tmp>`, then `python -m nav_benchmark.run eval --run-dir <dir>`, then `python -m nav_benchmark.run validate --run-dir <dir>`. Assert exit code 0 and stdout contains 'Validation:' summary line with all checks passed.
   - `test_validate_run_only_skip_eval` — Run the pipeline without eval, use `validate --run-dir <dir> --skip-eval`. Assert exit code 0 (eval artifacts not required).
   - `test_validate_broken_manifest` — Create a run directory with a truncated/invalid `run_manifest.json`, run validate, assert exit code 1.
   - `test_validate_missing_trajectory` — Create a run directory missing `estimated_trajectory.csv`, run validate, assert exit code 1.
   - `test_validate_latest_flag` — Run synthetic pipeline, then use `validate --latest --method imu_only` to find and validate the latest run directory. Assert exit code 0.
2. All tests use `tmp_path` and `subprocess.run` with `PYTHONPATH=src` env.
3. Tests must be deterministic and not require MVSEC data.

**Done-when:** `PYTHONPATH=src uv run --only-dev pytest tests/cli/test_validate_cli.py -v` passes all tests.

## Inputs

- `src/nav_benchmark/run.py`
- `src/nav_benchmark/validation.py`

## Expected Output

- `tests/cli/test_validate_cli.py`

## Verification

PYTHONPATH=src uv run --only-dev pytest tests/cli/test_validate_cli.py -v
