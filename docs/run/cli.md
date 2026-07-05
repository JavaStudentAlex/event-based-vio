# Command-Line Interface (CLI) Usage Guide

This document describes how to run navigation baselines using the `nav_benchmark.run` CLI entry point.

## Invocation Examples

### 1. Synthetic Dataset
To run the `imu_only` baseline on deterministic in-memory synthetic IMU data:
```bash
python -m nav_benchmark.run run --method imu_only --dataset synthetic --sequence synthetic_seq
```

To run it on a generated synthetic sequence directory from the recorder:
```bash
python -m nav_benchmark.run run --method imu_only --dataset synthetic --sequence synthetic_seq --input path/to/generated_sequence
```

The generated sequence layout must contain `imu/imu.csv`. When
`ground_truth/trajectory.csv` is present, the IMU baseline initializes from the
first ground-truth pose and velocity.

### 2. MVSEC Dataset
To run the `imu_only` baseline on a real MVSEC HDF5 dataset sequence (e.g., `outdoor_day1`):
```bash
python -m nav_benchmark.run run --method imu_only --dataset mvsec --sequence outdoor_day1 --input path/to/outdoor_day1.h5
```
*Note: `--input` is required when `--dataset` is set to `mvsec`.*

### 3. Event+IMU on MVSEC
To run the `event_imu` backend (IMU propagation with event-frame shift corrections)
on an MVSEC HDF5 file — see
[`docs/run/mvsec-manual-runs.md`](mvsec-manual-runs.md) for converting the MVSEC
rosbag distribution into this layout:
```bash
python -m nav_benchmark.run run --method event_imu --dataset mvsec \
  --sequence indoor_flying1 --input data/indoor_flying1.h5 --evaluate
```

### 4. External baseline via subprocess adapter
To run an external SLAM/VIO tool through the adapter (see
[`docs/baselines/external.md`](../baselines/external.md)):
```bash
python -m nav_benchmark.run run --method external --dataset mvsec \
  --sequence outdoor_day1 --input data/outdoor_day1.h5 \
  --external-command "ultimateslam_wrapper --input data/converted --output /tmp/us.tum" \
  --external-trajectory /tmp/us.tum \
  --external-tool-name ultimateslam \
  --external-version-command "ultimateslam_wrapper --version"
```

## CLI Options Reference

The `run` subcommand supports the following arguments:

* `--method` (required): The estimation baseline to run. Supported values:
  * `imu_only`: IMU-only dead-reckoning propagation.
  * `rgb_vo`: Feature-based monocular RGB visual odometry.
  * `event_vo`: Feature-based visual odometry on accumulated event frames.
  * `event_imu`: IMU propagation corrected by phase-correlation shifts between
    fixed-time event frames (gyro-compensated, norm-bounded corrections).
  * `image_imu`: IMU propagation fused with RGB visual odometry.
  * `multimodal_vio`: IMU propagation fused with RGB and event cues.
  * `ensemble`: Fusion across all baselines (see `--fusion`).
  * `external`: Externally produced trajectory, either imported from a file or
    produced by running an external tool via `--external-command`.
* `--dataset` (required): Dataset source type. Supported values:
  * `synthetic`: Deterministic mock IMU data.
  * `mvsec`: Real MVSEC dataset.
* `--sequence` (required): A descriptive name for the sequence being processed.
* `--input` (required for `mvsec`, optional for `synthetic`): Path to the input HDF5 data file or generated synthetic sequence directory.
* `--output-root` (optional, default: `runs`): The directory where all run folders will be generated.
* `--resume` (optional): If present, automatically handles existing run folder collisions by appending suffix increments (e.g., `-r1`, `-r2`).
* `--event-window-ms` (optional, default: `50`): Fixed-time window for event
  frames built from raw events and for event-stream diagnostics.
* `--fusion` (optional): Ensemble fusion mode (`confidence_weighted`,
  `weighted_ekf`, `winner_takes_healthy`).
* `--evaluate` (optional): Evaluate against ground truth immediately after the
  run and write the evaluation artifacts into the run directory.
* `--ground-truth` (optional): Ground-truth override used with `--evaluate`.
* `--external-trajectory` (required for `external`): Trajectory file to import
  (TUM or project CSV). With `--external-command`, the file the tool is
  expected to write.
* `--external-format` (optional, default `auto`): `tum`, `csv`, or `auto`.
* `--external-command` (optional): Command that runs the external tool as a
  subprocess before importing `--external-trajectory`.
* `--external-workdir`, `--external-timeout-sec`, `--external-tool-name`,
  `--external-version-command` (optional): Working directory, timeout
  (default 3600 s), manifest tool name, and version probe for the external
  command. Exit status, stderr tail, duration, and version are recorded in
  `run_manifest.json`; failures still write the manifest and failure notes.

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

## Evaluation

Use the `eval` subcommand after a `run` subcommand has written a run directory
containing `estimated_trajectory.csv`. The evaluator consumes the fixed project
trajectory export contract documented in
[`docs/trajectory/export-contract.md`](../trajectory/export-contract.md); it
expects those columns to exist and preserves the estimator `health` labels in
evaluation artifacts rather than redefining the schema here.

To evaluate a completed run with an explicit ground-truth file:
```bash
python -m nav_benchmark.run eval \
  --run-dir runs/20260628_120000_imu_only_outdoor_day1 \
  --ground-truth path/to/ground_truth.csv
```

For a generated synthetic sequence directory, `--ground-truth` may point either
to the ground-truth CSV or to the sequence directory that contains
`ground_truth/trajectory.csv`:
```bash
python -m nav_benchmark.run eval \
  --run-dir runs/20260628_120000_imu_only_synthetic_seq \
  --ground-truth path/to/generated_sequence
```

For an MVSEC-style run, pass either a project-format ground-truth CSV or the
MVSEC HDF5 file containing ground-truth pose streams:
```bash
python -m nav_benchmark.run eval \
  --run-dir runs/20260628_120000_imu_only_outdoor_day1 \
  --ground-truth path/to/outdoor_day1.h5 \
  --association-tolerance-sec 0.1 \
  --alignment-policy se3
```

If `--ground-truth` is omitted, the evaluator reads `run_manifest.json`. For a
generated synthetic sequence directory recorded as `input`, it automatically
uses `input/ground_truth/trajectory.csv`.

To evaluate the newest eligible run under an output root, use `--latest` instead
of `--run-dir`. Optional `--method` and `--sequence` flags filter the search by
`run_manifest.json` before the newest `estimated_trajectory.csv` is selected:
```bash
python -m nav_benchmark.run eval \
  --latest \
  --output-root runs \
  --method imu_only \
  --sequence outdoor_day1 \
  --ground-truth path/to/outdoor_day1.h5
```

Evaluation options:

* `--run-dir`: Run directory to evaluate. Required unless `--latest` is set.
* `--latest`: Discover the newest run directory in `--output-root` that contains
  `estimated_trajectory.csv`; combine with `--method` and `--sequence` to avoid
  accidentally evaluating an unrelated run.
* `--ground-truth`: Ground-truth source. Accepts a project trajectory CSV, a
  generated synthetic sequence directory, or an MVSEC `.h5`/`.hdf5` file. If
  omitted, the evaluator attempts to resolve the input recorded in
  `run_manifest.json`.
* `--output-root`: Root used only by `--latest` discovery. Defaults to `runs`.
* `--method`: Optional `--latest` filter matching the manifest method.
* `--sequence`: Optional `--latest` filter matching the manifest sequence and
  plot labels.
* `--association-tolerance-sec`: Nearest-neighbor timestamp association window
  in seconds. Defaults to `0.1`.
* `--alignment-policy`: Global alignment policy, either `se3` or `none`.
  Defaults to `se3`.
* `--rpe-delta-m`: Distance delta for RPE calculations. Defaults to `1.0` meter.
* `--drift-bin-width-m`: Width of drift summary bins. Defaults to `20.0` meters.

Evaluation writes `metrics.json`, `error_vs_time.csv`,
`error_vs_distance.csv`, `ground_truth_aligned.csv`, `trajectory_plot.{png,svg}`,
and `drift_plot.{png,svg}` into the run directory. `metrics.json` includes the
status, config settings, association diagnostics, trajectory error, drift,
runtime latency/frequency, coverage, and failed-frame/window counts. On failure,
`metrics.json` is still written with `status: "failed"`, `reason`, and
`error_message`, and the CSV artifacts are initialized with headers for
inspection.

See [`docs/evaluation/drift-evaluation.md`](../evaluation/drift-evaluation.md)
for the alignment policy, metric definitions, CSV columns, plot meanings, and
dataset-dependent checks.

## Comparison

Use the `compare` subcommand to aggregate two or more evaluated run
directories into one report:
```bash
python -m nav_benchmark.run compare \
  --run-dirs runs/<run_a> runs/<run_b> \
  --output runs/comparison
```

It writes into `--output`:

* `metrics_comparison.json` — all run summaries, ranked by drift percent.
* `comparison_table.csv` — one row per run: ATE/RPE, drift, coverage,
  failure-interval count and total duration, latency mean/p95, and the
  approximate real-time factor.
* `failure_intervals.json` — aggregated contiguous `DEGRADED`/`LOST`/`INVALID`
  intervals per method, extracted from each run's `estimated_trajectory.csv`.
* `backend_comparison_drift.{png,svg}` — drift-over-distance comparison.
* `comparison_trajectories.{png,svg}` — estimated-vs-ground-truth XY overlay
  across methods (written when the runs contain evaluated `error_vs_time.csv`).

## Dataset Conversion for External Adapters

Use the `convert` subcommand to export a sequence's streams to a plain layout
that external tool wrappers can consume (see
[`docs/baselines/external.md`](../baselines/external.md)):
```bash
python -m nav_benchmark.run convert --dataset mvsec --sequence outdoor_day1 \
  --input data/outdoor_day1.h5 --output-dir data/converted/outdoor_day1
```
This writes `events.csv`, `imu.csv`, `ground_truth.csv`, `images/` +
`image_timestamps.csv` (each only when the stream exists), and a
`conversion_manifest.json` recording counts and time ranges.

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
