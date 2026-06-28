# Drift Evaluation

This document outlines the evaluation methodology and metrics computation for the MVSEC Event-Based VIO benchmark. The evaluation command consumes the standardized trajectory export format.

## Overview

The evaluation step (`nav_benchmark.run eval`) compares an estimated trajectory against a ground-truth trajectory to produce a set of performance and coverage metrics. The evaluation relies heavily on explicit configuration for alignment and association.

## Trajectory Processing

The evaluation consumes standard fixed trajectory CSVs as defined in `docs/trajectory/export-contract.md`.

### Health Labels

Trajectory rows include a `health` label which dictates how a pose is handled during evaluation:
- `OK`, `DEGRADED`: Used for metric calculation.
- `LOST`, `INVALID`: Included in coverage and diagnostic reporting, but excluded from numeric aggregated tracking error metrics.

### Timestamp Association

Ground-truth and estimated poses are associated using nearest-neighbor timestamp matching.
- Maximum time difference allowed: `--association-tolerance-sec` (default: 0.1 seconds).
- **No time-offset search:** The system assumes the estimated and ground-truth timestamps are already accurately synchronized.

### Global Alignment

By default, an explicit `se3` global alignment policy is used (Umeyama alignment).
- A single, global SE(3) transformation is computed using all valid associated poses.
- No robust trimming, outlier rejection, or continuous scale correction is performed in the baseline (M001).

## Output Artifacts

Running the evaluation command generates a suite of artifacts in the corresponding run directory.

### `metrics.json`
Contains aggregate metrics and configuration metadata:
- Policy metadata (alignment type, association settings).
- Diagnostic information (number of associated poses, skipped missing data).
- The calculated global alignment SE(3) transform.
- **ATE (Absolute Trajectory Error):** Overall RMSE, mean, median.
- **RPE (Relative Pose Error):** Error over defined delta distances (e.g., 1 meter).
- **Final Drift:** Displacement error at the end of the trajectory.
- **Coverage:** Total evaluation time, and durations categorized as invalid/lost.
- **Drift Bins:** Breakdown of cumulative drift over configured distances (default bins of 20 m).

### Error CSVs
Error values over time and distance are exported to CSVs so plots can be reliably regenerated:
- **`error_vs_time.csv`**: Contains `timestamp`, estimated and aligned ground-truth poses, error components (`x`, `y`, `z`), overall `error_magnitude`, `health`, and `association_residual`.
- **`error_vs_distance.csv`**: Tracks `cumulative_distance`, `error_magnitude`, `health`, `association_residual`, and bounds of the current distance bin.

### Plots
Visual representations are generated using the data from the error CSVs:
- **`trajectory_plot.png` / `.svg`**: Top-down (X-Y) aligned trajectory comparison between the estimate and ground-truth.
- **`drift_over_distance.png` / `.svg`**: Cumulative absolute error plotted against total distance travelled.

### `ground_truth_aligned.csv`
The original ground-truth trajectory, globally aligned to the estimator frame, exported in the standard fixed CSV schema.

## Failures and Negatives

Evaluation is designed to fail predictably:
- Exits with a non-zero code when critical errors occur (missing ground truth, malformed files, mismatched sequence, insufficient overlap).
- Writes diagnostic `metrics.json` outlining the failure reason and preserving any partial output where safe.
