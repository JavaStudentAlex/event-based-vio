# Command-Line Interface (CLI) Usage Guide

This document describes how to run navigation baselines using the `nav_benchmark.run` CLI entry point.

## Invocation Examples

### 1. Synthetic Dataset
To run the `imu_only` baseline on synthetic data:
```bash
python -m nav_benchmark.run run --method imu_only --dataset synthetic --sequence synthetic_seq
```
*Note: For the synthetic dataset, `--sequence` is required but generates a deterministic synthetic path, and `--input` is not needed.*

### 2. MVSEC Dataset
To run the `imu_only` baseline on a real MVSEC HDF5 dataset sequence (e.g., `outdoor_day1`):
```bash
python -m nav_benchmark.run run --method imu_only --dataset mvsec --sequence outdoor_day1 --input path/to/outdoor_day1.h5
```
*Note: `--input` is required when `--dataset` is set to `mvsec`.*

## CLI Options Reference

The `run` subcommand supports the following arguments:

* `--method` (required): The estimation baseline to run. Supported values:
  * `imu_only`: IMU-only dead-reckoning propagation.
* `--dataset` (required): Dataset source type. Supported values:
  * `synthetic`: Deterministic mock IMU data.
  * `mvsec`: Real MVSEC dataset.
* `--sequence` (required): A descriptive name for the sequence being processed.
* `--input` (required for `mvsec`): Path to the input HDF5 data file.
* `--output-root` (optional, default: `runs`): The directory where all run folders will be generated.
* `--resume` (optional): If present, automatically handles existing run folder collisions by appending suffix increments (e.g., `-r1`, `-r2`).

## Run Directory Structure

Each execution generates a uniquely-named run directory inside `--output-root` formatted as `{timestamp}_{method}_{sequence}` (e.g., `20260628_120000_imu_only_outdoor_day1`).

The generated folder contains:

```text
runs/20260628_120000_imu_only_outdoor_day1/
├── estimated_trajectory.csv     # Trajectory exported using the project-standard CSV schema
├── estimated_trajectory_tum.txt # Trajectory exported in TUM format
├── run.log                      # Log of execution steps and diagnostics
├── run_manifest.json            # Configuration and metadata parameters
└── failure_notes.md             # Summary of tracking state and degraded/lost tracking intervals
```

### Manifest Details
`run_manifest.json` contains:
* Baseline configuration parameter values (e.g. thresholds, initial state).
* Trajectory metadata (gravity direction, source/target frames, timestamp format, units).
* Execution exit status (`success` or `failed`).
* Health counts (number of poses categorised as `OK`, `DEGRADED`, `LOST`, `INVALID`).

### Failure Notes
`failure_notes.md` parses estimated tracking errors and identifies contiguous segments of `DEGRADED` or `LOST` tracking quality based on distance or duration limits.

## Collision & Resume Behavior

By default, if the output directory (e.g., `runs/20260628_120000_imu_only_outdoor_day1`) already exists, the program will terminate with an error to prevent overwriting previous results:
```text
Error: Run directory already exists: runs/20260628_120000_imu_only_outdoor_day1
```

If you specify the `--resume` flag:
1. The runner checks if the target directory exists.
2. If it does, it dynamically probes incrementing suffixes (e.g., `runs/20260628_120000_imu_only_outdoor_day1-r1`, `-r2`, etc.).
3. The runner writes results into the first free suffixed directory, leaving existing directories untouched.
