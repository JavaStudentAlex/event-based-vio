# S01: MVSEC Loader and Stream Contract — Research

## Summary
The goal of Slice S01 is to establish a loader that reads MVSEC-style HDF5 files into a common sequence object (`MvsecSequence`) with per-stream diagnostics, metadata, calibration, and timestamp checks.

The implementation is already present in `src/nav_benchmark/datasets/mvsec.py`, and test coverage is written in `tests/nav_benchmark/datasets/test_mvsec.py`. The loader implementation reads:
- Davis left events from `/davis/left/events` (`ts`, `x`, `y`, `p`)
- IMU data from `/davis/left/imu` (`ts`, `linear_acceleration_*`, `angular_velocity_*`)
- Ground-truth poses from `/davis/left/pose` (`ts`, `px`, `py`, `pz`, `qx`, `qy`, `qz`, `qw`)
- Grayscale images from `/davis/left/image_raw` (`ts`, `image_raw`)
- Calibration information from `/davis/left/camera_info` (`K`, `D`, `P`) and `/davis/left/imu_cam_transform`

This aligns perfectly with the goals of this slice.

## Active Requirements
- **R001 — MVSEC sensor ingestion:** Ingest events, IMU, camera calibration, and ground-truth poses from local dataset files.
- **R002 — Timestamp validation and diagnostics:** Verify timestamps are monotonic and flag missing/malformed groups.

## Implementation Landscape
- **Source Paths:**
  - `src/nav_benchmark/datasets/mvsec.py`: Contains structured dtypes (`EVENT_DTYPE`, `IMU_DTYPE`, `POSE_DTYPE`), dataclasses (`LoadDiagnostics`, `Calibration`, `SequenceMetadata`, `MvsecSequence`), helper loader functions, and `load_mvsec_sequence`.
  - `tests/nav_benchmark/datasets/test_mvsec.py`: Tests standard loading, missing streams, non-monotonic timestamps, layout mismatches, missing/partial calibration, and missing images/poses using synthetic HDF5 datasets.
- **Natural Seams:**
  - The dataset loading module is fully decoupled from synchronization, baseline execution, and trajectory evaluation.
  - The synthetic HDF5 generation is encapsulated in a pytest fixture for reuse across other slices.

## Recommendation
Since the implementation of `mvsec.py` and its corresponding tests is already complete, the planner should focus the execution phase on verifying that `pytest tests/nav_benchmark/datasets/test_mvsec.py` runs and passes successfully, resolving any potential issues if they arise. No new loader features are needed unless verification flags unexpected failures.
