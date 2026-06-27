# GSD State

**Active Milestone:** M001-ncx5an: MVSEC Pipeline and IMU Sanity Benchmark
**Active Slice:** S01: MVSEC Loader and Stream Contract
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
Slice S01 has no DB tasks. Plan slice tasks before execution.

## Implementation Notes
- **S01**: Added core MVSEC stream dataclasses and structured numpy arrays matching `EVENT_DTYPE`, `IMU_DTYPE`, and `POSE_DTYPE`. Implemented HDF5 `load_mvsec_sequence` using hardcoded paths (`/davis/left/*`). Added `LoadDiagnostics` generation for missing, malformed, and misaligned layouts with duplicate/non-monotonic timestamp validation. Added unit test fixture generator producing schema-compliant synthetic `synthetic_mvsec.h5` and validating loaders behaviour. Added `src` directory to `PYTHONPATH` via pyproject.toml to ensure imports resolve smoothly during tests.
