# S03: IMU Only Backend and CLI Run Path — UAT

**Milestone:** M001-ncx5an
**Written:** 2026-06-28T00:33:31.426Z

# UAT Assessment: S03 Integration

## UAT Type
- UAT mode: runtime-executable

## Preconditions
- Python environment loaded via `uv`.
- Minimal synthetic dataset generator operational.

## Execution Steps
1. Execute the main run subcommand using the synthetic dataset:
   ```bash
   uv run python -m nav_benchmark.run --method imu_only --dataset synthetic --sequence unit_synthetic --output-root runs
   ```
2. Verify that a run directory matching `runs/<YYYYmmdd_HHMMSS>_imu_only_unit_synthetic/` was created.
3. Assert the presence of:
   - `estimated_trajectory.csv`
   - `estimated_trajectory_tum.txt`
   - `run.log`
   - `failure_notes.md`
   - `run_manifest.json`

## Expected Outcomes
- The estimator runs to completion.
- Trajectory exports contain correct format and shape.
- `run_manifest.json` correctly reports counts for all health statuses (OK, DEGRADED, LOST, INVALID).

