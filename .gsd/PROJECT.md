# Project

## What This Is

This repository is an MVSEC-based event-camera navigation benchmark project for GPS-denied visual-inertial navigation. The immediate project shape is a three-milestone path that first proves a trustworthy benchmark harness, then adds a simple real Event+IMU odometry backend, then adds stronger wrappers and richer comparison/reporting.

## Core Value

The one thing that must work even if everything else is cut: the repo must produce trustworthy, reproducible drift-measured relative odometry benchmark artifacts from sensor data, without silent data loss or ambiguous frame/alignment assumptions.

## Project Shape

- **Complexity:** complex
- **Why:** The project spans dataset ingestion, synchronization, trajectory contracts, odometry backends, evaluation math, plots, CLI artifacts, and later external baseline integration.
- **Web stack:** not a web UI

## Current State

Planning is complete for the primary milestone. No implementation has been validated yet. Existing project context indicates Python 3.13 with `uv`, MVSEC-first scope, CI configured, and no current tests.

## Architecture / Key Patterns

- Use a real Python package under `src/nav_benchmark`.
- Use `h5py` for first-pass MVSEC HDF5 access.
- Use `numpy`, `scipy`, `pandas`, `matplotlib`, `pyyaml`, `rich`, `tqdm`, and `evo` according to their benchmark roles.
- Keep project-owned CSV and `metrics.json` as the stable benchmark contract.
- Export TUM trajectory files for compatibility with SLAM/VIO evaluation tooling.
- Define a stable minimal odometry backend contract in M001 so later `event_imu`, UltimateSLAM, ESVO, or ensemble backends can reuse the same export/evaluation path.
- Generated benchmark artifacts live under `runs/` and should stay untracked.

## Capability Contract

See `.gsd/REQUIREMENTS.md` for the explicit capability contract, requirement status, and coverage mapping.

## Milestone Sequence

- [ ] M001-ncx5an: MVSEC Pipeline and IMU Sanity Benchmark — prove the deterministic MVSEC benchmark harness with `imu_only`, standard artifacts, synthetic CI tests, and drift-over-distance evaluation.
- [ ] M002: First Event+IMU Odometry Backend — add a simple but real Event+IMU relative odometry backend through the M001 backend contract and artifact schema.
- [ ] M003: Strong Baselines and Benchmark Reporting — add stronger wrappers such as UltimateSLAM or ESVO if practical, plus richer runtime/failure reporting and method comparison.
