# GSD State

**Active Milestone:** M001-ncx5an: MVSEC Pipeline and IMU Sanity Benchmark
**Active Slice:** S02: Synchronization and Trajectory Export Contract
**Phase:** planning
**Requirements Status:** 0 active · 0 validated · 0 deferred · 0 out of scope

## Milestone Registry
- 🔄 **M001-ncx5an:** MVSEC Pipeline and IMU Sanity Benchmark
- ⬜ **M002:** First Event+IMU Odometry Backend
- ⬜ **M003:** Strong Baselines and Benchmark Reporting

## Recent Decisions
- D003 (2026-06-27): Use `h5py` for first-pass MVSEC loading -> Read MVSEC HDF5 files directly with `h5py`; reserve `rosbags` for raw bag support later
- D004 (2026-06-27): Keep project artifacts authoritative and TUM export interoperable -> Project CSV and `metrics.json` are the stable contract; TUM export supports SLAM/VIO tools such as `evo`
- D005 (2026-06-27): Default M001 evaluation to explicit SE3 alignment -> Timestamp-associate estimates and ground truth, align with SE3 by default, and record policy in metrics/manifest metadata
- D006 (2026-06-27): Define a stable minimal odometry backend interface in M001 -> `imu_only`, future `event_imu`, and later wrappers return a common result shape consumed by shared export/evaluation
- D007 (2026-06-27): Store generated benchmark outputs under `runs/` -> Generated run artifacts live under `runs/` and should stay untracked

## Blockers
- None

## Next Action
Slice S02 has no DB tasks. Plan slice tasks before execution.
