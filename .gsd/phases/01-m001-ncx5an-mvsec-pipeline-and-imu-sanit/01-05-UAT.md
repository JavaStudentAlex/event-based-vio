# S05: Manifest Failure Artifacts and CI Smoke Coverage — UAT

**Milestone:** M001-ncx5an
**Written:** 2026-06-28T13:03:19.631Z

# UAT for Slice S05: Manifest Failure Artifacts and CI Smoke Coverage

## UAT Type
- UAT mode: runtime-executable

## Preconditions
- Python virtual environment is active with `uv`.
- All code formatted and clean.

## Execution Steps
1. Run a synthetic simulation using the run command:
   ```bash
   PYTHONPATH=src uv run python -m nav_benchmark.run run --method imu_only --dataset synthetic --sequence test_seq --output-root tmp_runs
   ```
2. Evaluate the trajectory to produce metrics and error CSVs:
   ```bash
   PYTHONPATH=src uv run python -m nav_benchmark.run eval --latest --output-root tmp_runs --ground-truth synthetic
   ```
3. Validate the run directory using the validate subcommand:
   ```bash
   PYTHONPATH=src uv run python -m nav_benchmark.run validate --latest --output-root tmp_runs
   ```

## Expected Outcomes
- The validation command discovers the latest run directory in `tmp_runs/` and executes all validation steps.
- The output displays a formatted summary table showing passing statuses for `check_trajectory_csv`, `check_tum_file`, `check_run_manifest`, `check_failure_notes`, `check_run_log`, `check_metrics_json`, `check_error_vs_time_csv`, `check_error_vs_distance_csv`, `check_plot_file`, and `check_cross_consistency`.
- The command exits with a status code of 0.

