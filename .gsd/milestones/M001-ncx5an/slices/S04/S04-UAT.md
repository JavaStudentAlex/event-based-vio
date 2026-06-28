# S04: Drift Evaluation and Plots — UAT

**Milestone:** M001-ncx5an
**Written:** 2026-06-28T11:06:09.532Z

## Preconditions
- A valid run directory containing `estimated_trajectory.csv`.
- Ground truth trajectory CSV corresponding to the sequence.

## UAT Type
- UAT mode: runtime-executable

## Verification Steps
1. Run evaluation via CLI: `PYTHONPATH=src python -m nav_benchmark.run eval --run-dir <run_dir> --ground-truth <gt_path>`
2. Verify CLI returns exit code 0 and outputs message confirming successful evaluation.
3. Verify run directory contains the complete artifact set: `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, `trajectory_plot.png`, `trajectory_plot.svg`, `drift_over_distance.png`, and `drift_over_distance.svg`.
4. Verify numeric values in `metrics.json` are consistent (ATE, RPE, final drift, coverage percent).

## Edge Cases Tested
- Degenerate collinear trajectory data handling (catches evo's Umeyama alignment failures and exits gracefully with diagnostic info).
- Mismatched timestamp bounds and non-overlapping trajectories.
- Empty/missing inputs and invalid CLI parameters.
