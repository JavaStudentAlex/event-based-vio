# M001-ncx5an/S04 Slice Research: Drift Evaluation and Plots

## Summary
Slice S04 implements the evaluation and plotting utilities to analyze odometry trajectory estimates against ground truth. It aligns trajectories globally using SE(3) Umeyama alignment (or optionally keeps them in identity frames), computes position error metrics (ATE, RPE, final drift, coverage), and exports structured files: `ground_truth_aligned.csv`, `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, and PNG/SVG visual plots of the estimated trajectory and binned drift-over-distance.

## In Scope
- Global SE(3) Umeyama trajectory alignment of estimates to ground truth.
- ATE (Absolute Trajectory Error) RMSE and statistical computation.
- RPE (Relative Pose Error) computed at 1.0 meter intervals.
- Final drift and drift growth vs distance travelled.
- Time-indexed (`error_vs_time.csv`) and distance-indexed (`error_vs_distance.csv`) position errors.
- Visual plots: `trajectory_plot.png` / `.svg` (estimated vs aligned ground-truth) and `drift_over_distance.png` / `.svg` showing drift growth.
- Exclusion of `LOST` and `INVALID` poses from metric calculations, while tracking their coverage/durations in metadata.

## Out of Scope
- Time-offset estimation or calibration calibration optimization.
- Sliding-window or sub-trajectory realignments.
- Penalty-inflated metrics or multiple estimator comparisons in a single run.

## Recommendations and Plan

### 1. Verification of evo Library Seams
We will import and use the standard Python library `evo` to perform the alignment and core error calculations.
- Create `PoseTrajectory3D` objects from numpy arrays using:
  ```python
  from evo.core.trajectory import PoseTrajectory3D
  traj = PoseTrajectory3D(
      positions_xyz=positions,  # Shape (N, 3)
      orientations_quat_wxyz=orientations_wxyz,  # Shape (N, 4), converted from xyzw
      timestamps=timestamps  # Shape (N,)
  )
  ```
- To perform global SE(3) alignment:
  ```python
  import copy
  traj_est_aligned = copy.deepcopy(traj_est)
  traj_est_aligned.align(traj_ref, correct_scale=False, correct_only_scale=False)
  ```
- Absolute Trajectory Error (ATE) calculation:
  ```python
  from evo.core import metrics
  # Translation APE
  ape_metric = metrics.APE(metrics.PoseRelation.translation_part)
  ape_metric.process_data((traj_ref, traj_est_aligned))
  ate_rmse = ape_metric.get_statistic(metrics.StatisticsType.rmse)
  ```
- Relative Pose Error (RPE) calculation at delta = 1.0 meter:
  ```python
  from evo.core.units import Unit
  rpe_metric = metrics.RPE(
      metrics.PoseRelation.translation_part,
      delta=1.0,
      delta_unit=Unit.meters,
      all_pairs=True
  )
  rpe_metric.process_data((traj_ref, traj_est_aligned))
  rpe_rmse = rpe_metric.get_statistic(metrics.StatisticsType.rmse)
  ```

### 2. Distance-Binned Drift Computation
- For each estimated pose, we compute cumulative distance traveled on OK/DEGRADED status poses.
- Position error $e(d)$ is measured relative to the aligned ground-truth.
- We bin drift rates into bins (e.g. 20m increments) and compute local drift percentage metrics.

### 3. Matplotlib Plots
- Trajectory Plot: Estimated vs Aligned Ground-Truth (3D trajectory and/or XY projection).
- Drift Plot: Position error (m) vs cumulative distance traveled (m), highlighting binned intervals.

## Verification Strategy
- **Synthetic Unit Tests**: Write unit tests in `tests/evaluation/test_metrics.py` and `test_plots.py` with small pre-calculated trajectories (e.g., constant translation/rotation offset) to confirm alignment math and metric outputs.
- **CLI Integration Test**: Add an `eval` command to `nav_benchmark.run` and test that running evaluation on a run folder writes all files correctly and passes content validation checks.
