---
estimated_steps: 23
estimated_files: 1
skills_used: []
---

# T03: Added comprehensive unit tests for all run-directory validation checks and cross-consistency validation.

**Why:** Each validation check function in `validation.py` needs targeted unit tests with both valid and intentionally broken fixtures to prove correctness before integration testing.

**Do:**
1. Create `tests/validation/test_artifact_validation.py` with pytest tests:
   - `test_check_trajectory_csv_valid` — Write a synthetic 15-column CSV with valid data, assert check passes.
   - `test_check_trajectory_csv_wrong_columns` — Write CSV with missing/wrong header, assert check fails with descriptive message.
   - `test_check_trajectory_csv_empty_data` — Write CSV with header only, assert check fails.
   - `test_check_tum_valid` — Write valid TUM file, assert check passes.
   - `test_check_tum_invalid_format` — Write TUM with wrong column count, assert fails.
   - `test_check_manifest_valid` — Write manifest JSON with all required keys, assert passes.
   - `test_check_manifest_missing_keys` — Write manifest missing health_counts, assert fails.
   - `test_check_failure_notes_valid_clean` — Write clean failure notes with exact success sentence, assert passes.
   - `test_check_failure_notes_valid_degraded` — Write notes with interval sections, assert passes.
   - `test_check_failure_notes_missing_header` — Write notes without required header, assert fails.
   - `test_check_metrics_json_valid` — Write valid metrics JSON, assert passes.
   - `test_check_metrics_json_missing_keys` — Write metrics missing required key, assert fails.
   - `test_check_error_csvs_valid` — Write valid error_vs_time.csv and error_vs_distance.csv, assert both pass.
   - `test_check_error_csvs_wrong_headers` — Write CSVs with wrong headers, assert fails.
   - `test_check_plot_valid` — Write a file >100 bytes, assert passes.
   - `test_check_plot_too_small` — Write a 10-byte file, assert fails.
   - `test_check_cross_consistency_matching` — Build a run directory where manifest health counts match CSV health column distribution, assert passes.
   - `test_check_cross_consistency_mismatch` — Mismatch health counts between manifest and CSV, assert fails.
2. All tests use `tmp_path` fixture and synthetic data — no MVSEC required.

**Done-when:** `PYTHONPATH=src uv run --only-dev pytest tests/validation/test_artifact_validation.py -v` passes all tests.

## Inputs

- `src/nav_benchmark/validation.py`

## Expected Output

- `tests/validation/test_artifact_validation.py`

## Verification

PYTHONPATH=src uv run --only-dev pytest tests/validation/test_artifact_validation.py -v
