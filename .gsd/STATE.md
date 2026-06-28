# GSD State

**Active Milestone:** None
**Active Slice:** None
**Phase:** pre-planning
**Requirements Status:** 0 active · 0 validated · 0 deferred · 0 out of scope

## Milestone Registry

## Recent Decisions
- D003 (architecture): Health labeling for imu_only: default OK; DEGRADED when either (a) IMU sample gap dt > 0.03 s and <= 0.10 s, or (b) \ -> \
- D004 (architecture): Introduce `src/nav_benchmark/baselines/base.py` defining `BaseOdometryBackend` with `run(sequence, *, config) -> Trajectory`. Provide `ImuOnlyBackend` in `src/nav_benchmark/baselines/imu.py` with a simple dataclass `ImuOnlyConfig` (gravity vector, initial pose/velocity, health thresholds). Keep interface minimal and functional to enable later backends (image_imu, event_imu, multimodal). -> A tiny, explicit interface isolates the CLI orchestration from backend specifics, simplifies testing, and allows swap-in of additional backends in later milestones without touching the run path.
- D005 (M001-ncx5an/S04): Design of S04 evaluation and plotting utilities pipeline -> Implement project-native Python evaluation script and metric calculations using numpy/scipy directly where appropriate, supplemented by evo's core geometry and metrics modules. We construct evo PoseTrajectory3D using the wxyz quaternion convention and align trajectories globally using evo's Umeyama SE(3) alignment. We write out metrics.json, error_vs_time.csv, error_vs_distance.csv, trajectory_plot.png, and drift_over_distance.png.
- D006 (M001-ncx5an/S04): S04 alignment and outlier policy for drift evaluation -> Use nearest-neighbor timestamp association followed by one global SE(3) alignment over overlapping OK and DEGRADED estimate poses with no robust trimming, no outlier rejection, no time-offset search, and no local/sliding realignment in M001.
- D007 (M001-ncx5an/S04): S04 error series artifact schema -> Write error_vs_time.csv with timestamp, estimated_xyz, aligned_ground_truth_xyz, xyz error, error magnitude, health, and association residual columns; write error_vs_distance.csv with cumulative distance, error magnitude, health, association residual, and 20 m bin fields used by the drift plot.

## Blockers
- DB unavailable — runtime markdown state derivation is disabled

## Next Action
Open or create the canonical GSD database before deriving workflow state. If this project only has markdown state, run /gsd migrate explicitly.
