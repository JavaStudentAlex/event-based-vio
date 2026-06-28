---
estimated_steps: 18
estimated_files: 1
skills_used: []
---

# T01: Implemented run-directory validation module and test suite

**Why:** The S05 contract requires reusable validation checks that verify artifact content and cross-artifact consistency, not just file presence. This module is the core deliverable that the validate CLI subcommand and CI tests will consume.

**Do:**
1. Create `src/nav_benchmark/validation.py` with standalone check functions:
   - `check_trajectory_csv(path)` — Verify 15-column project CSV schema header, non-empty data rows, required health labels, numeric parsability of position/quaternion/velocity columns.
   - `check_tum_file(path)` — Verify TUM format (timestamp tx ty tz qx qy qz qw), no LOST/INVALID rows if a companion CSV exists for cross-check.
   - `check_run_manifest(path)` — Verify required top-level keys: method, dataset, sequence, config, timestamp_policy, gravity, frames, units, alignment, code_version, status, health_counts. Verify health_counts has OK/DEGRADED/LOST/INVALID keys.
   - `check_failure_notes(path)` — Verify markdown structure: '# Run Failure Notes' header, '## Health Summary' section, '## Detected Degraded/Lost Intervals' section. If all counts are zero except OK, verify the exact sentence 'No degraded or lost intervals were detected.'
   - `check_metrics_json(path)` — Verify required keys: status, config, metrics, alignment, diagnostics, coverage, drift_bins. Verify no NaN/Inf string values in numeric fields.
   - `check_error_vs_time_csv(path)` — Verify header columns: timestamp, est_x, est_y, est_z, gt_x, gt_y, gt_z, err_x, err_y, err_z, error_magnitude, health, assoc_residual_sec. Non-empty data rows.
   - `check_error_vs_distance_csv(path)` — Verify header columns include cumulative_distance, error_magnitude, health, assoc_residual_sec, bin_start_m, bin_end_m. Non-empty data rows.
   - `check_plot_file(path)` — Verify file exists and has non-trivial size (>100 bytes).
   - `check_run_log(path)` — Verify run.log exists and is non-empty.
   - `validate_run_directory(run_dir, expect_eval=True)` — Orchestrate all checks for a complete run directory. Return a list of `ValidationResult` named tuples with (check_name, passed, message). The `expect_eval` flag controls whether evaluation artifacts (metrics, error CSVs, plots) are required.
   - `check_cross_consistency(run_dir)` — Verify health_counts in manifest match actual health column distribution in trajectory CSV. Verify TUM row count equals OK+DEGRADED count from trajectory CSV. Verify metrics.json coverage.total_estimate_poses matches trajectory CSV row count.
2. Each check function returns a `ValidationResult(check_name: str, passed: bool, message: str)` dataclass.
3. `validate_run_directory` returns a list of all check results and a boolean `all_passed`.
4. Keep the module import-light — only stdlib + numpy for CSV parsing.

**Done-when:** `src/nav_benchmark/validation.py` exists with all listed functions. Module is importable without errors.

## Inputs

- `src/nav_benchmark/run.py`
- `src/nav_benchmark/evaluation/harness.py`
- `src/nav_benchmark/evaluation/metrics.py`

## Expected Output

- `src/nav_benchmark/validation.py`

## Verification

PYTHONPATH=src uv run python -c "from nav_benchmark.validation import validate_run_directory, check_trajectory_csv, check_run_manifest, check_failure_notes, check_metrics_json, check_cross_consistency; print('All validation functions importable')"
