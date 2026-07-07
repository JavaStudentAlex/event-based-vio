# Project

## What This Is

This repository is an MVSEC-based event-camera navigation benchmark project for GPS-denied visual-inertial navigation. The current active filesystem plan has been reduced to the remaining benchmark-reporting milestone while preserving the durable requirements, decisions, and project knowledge captured from earlier work.

## Core Value

The one thing that must work even if everything else is cut: the repo must produce trustworthy, reproducible drift-measured relative odometry benchmark artifacts from sensor data, without silent data loss or ambiguous frame/alignment assumptions.

## Project Shape

- **Complexity:** complex
- **Why:** The project spans dataset ingestion, synchronization, trajectory contracts, odometry backends, evaluation math, plotting, and machine-learning ensembles across multiple sensor modalities.
- **Milestone sequence:**
  1. M003: Strong Baselines and Benchmark Reporting.

## Known Constraints

- **Dependency limits:** Follow `pyproject.toml` (numpy, scipy, pandas, matplotlib, opencv-python, h5py, rosbags, evo, pyyaml, scikit-learn).
- **Environment:** Run tests via `uv run pytest`.
- **Runtime:** No ROS installation required; use rosbags to parse `.bag` natively if needed, but prefer MVSEC's provided HDF5 format.
- **State isolation:** Do not commit MVSEC data archives or bulky logs.

## Current State

Completed milestone artifact directories for M001 and M002 have been intentionally removed from the filesystem at the user's request. Their requirements, decisions, and knowledge remain preserved in the root GSD registers.

## Milestone Sequence

- [ ] M003: Strong Baselines and Benchmark Reporting — Planned.
