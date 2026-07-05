# Project

## What This Is

This repository is an MVSEC-based event-camera navigation benchmark project for GPS-denied visual-inertial navigation. The immediate project shape is a three-milestone path that first proves a trustworthy benchmark harness, then adds a simple real Event+IMU odometry backend, then adds stronger wrappers and richer comparison/reporting.

## Core Value

The one thing that must work even if everything else is cut: the repo must produce trustworthy, reproducible drift-measured relative odometry benchmark artifacts from sensor data, without silent data loss or ambiguous frame/alignment assumptions.

## Project Shape

- **Complexity:** complex
- **Why:** The project spans dataset ingestion, synchronization, trajectory contracts, odometry backends, evaluation math, plotting, and machine-learning ensembles across multiple sensor modalities.
- **Milestone sequence:**
  1. M001: MVSEC Pipeline and IMU Sanity Benchmark (prove data flows + relative eval). Note: the final slice of M001 has been overridden by the user to execute completely and directly close out the milestone.
  2. M002: Event-IMU and Image-IMU Baselines (add real vision backends).
  3. M003: Robustness Scoring and Multimodal Ensemble (add fusion/gating).

## Known Constraints

- **Dependency limits:** Follow `pyproject.toml` (numpy, scipy, pandas, matplotlib, opencv-python, h5py, rosbags, evo, pyyaml, scikit-learn).
- **Environment:** Run tests via `uv run pytest`.
- **Runtime:** No ROS installation required; use rosbags to parse `.bag` natively if needed, but prefer MVSEC's provided HDF5 format.
- **State isolation:** Do not commit MVSEC data archives or bulky logs.

## Current State

M001 (MVSEC Pipeline and IMU Sanity Benchmark) is concluding. We are in the final slice (S06) which fixes a validation string mismatch and concludes both the slice and the overall milestone as directed by the user override.

## Milestone Sequence

- [x] M001: M001-ncx5an: MVSEC Pipeline and IMU Sanity Benchmark — Build the first trustworthy benchmark foundation for the MVSEC event-camera navigation project.
- [ ] M001-ncx5an: MVSEC Pipeline and IMU Sanity Benchmark — Build the first trustworthy benchmark foundation for the MVSEC event-camera navigation project.
- [ ] M002: First Event+IMU Odometry Backend — Planned.
- [ ] M003: Strong Baselines and Benchmark Reporting — Planned.
