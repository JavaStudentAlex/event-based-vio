# M001-ncx5an: MVSEC Pipeline and IMU Sanity Benchmark

**Vision:** Build the first trustworthy benchmark foundation for the MVSEC event-camera navigation project. M001 proves that the repo can load MVSEC-style sensor data, run the `imu_only` sanity baseline, export standard artifacts, and evaluate drift growth versus distance travelled. This is a drift-measured relative odometry benchmark, not yet a drift-bounded navigation system.

## Success Criteria

- `imu_only` runs through one CLI command and writes the complete benchmark artifact set.
- Synthetic CI tests verify the pipeline without requiring MVSEC downloads.
- Trajectory exports use the fixed project CSV schema and TUM format.
- Evaluation reports ATE, RPE, final drift, error over time, error versus distance, and distance-binned drift.
- `run_manifest.json` and `failure_notes.md` are always written.
- Invalid or degraded intervals are preserved in benchmark artifacts, not silently dropped.

## Slices

- [x] **S01: MVSEC Loader and Stream Contract** `risk:high` `depends:[]`
  > After this: A tiny synthetic MVSEC-like fixture and a documented real MVSEC path can be loaded into a common sequence object with events, IMU, calibration, ground truth, and timestamp metadata.

- [ ] **S02: Synchronization and Trajectory Export Contract** `risk:high` `depends:[S01]`
  > After this: IMU samples and ground truth are timestamp-associated without silent drops, and a synthetic trajectory exports valid project CSV plus TUM files.

- [ ] **S03: IMU Only Backend and CLI Run Path** `risk:medium` `depends:[S02]`
  > After this: One command runs `imu_only` on synthetic data through the backend interface and writes the required run directory skeleton with valid trajectory artifacts.

- [ ] **S04: Drift Evaluation and Plots** `risk:high` `depends:[S02,S03]`
  > After this: The evaluator aligns estimates to ground truth with explicit SE3 policy and produces valid `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, trajectory plot, and drift-over-distance plot.

- [ ] **S05: Manifest Failure Artifacts and CI Smoke Coverage** `risk:medium` `depends:[S03,S04]`
  > After this: The benchmark run always writes `run_manifest.json`, `failure_notes.md`, logs, and CI-friendly tests validate artifact contents rather than file presence alone.

## Boundary Map

### S01 -> S02

Produces:
- Common sequence object for events, IMU, calibration, ground truth, timestamp metadata, and discovered source metadata.
- Loader diagnostics for missing groups, shape mismatches, timestamp issues, and calibration availability.

Consumes:
- nothing (first slice)

### S02 -> S03

Produces:
- Synchronization policy and diagnostics.
- Trajectory data model with project CSV and TUM export.
- Explicit frame, unit, timestamp, and alignment metadata shape.

Consumes:
- S01 sequence object.

### S03 -> S04

Produces:
- Minimal odometry backend contract.
- `imu_only` backend result shape.
- CLI run path that writes estimated trajectory artifacts.

Consumes:
- S02 trajectory export contract.

### S04 -> S05

Produces:
- Ground-truth alignment output.
- `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, `trajectory_plot.png`, and `drift_over_distance.png`.
- Metric metadata including SE3 alignment policy and drift-over-distance fields.

Consumes:
- S03 run artifacts and S02 trajectory contract.

### S05 -> M002

Produces:
- Validated artifact contract for all methods.
- Required `run_manifest.json`, always-present `failure_notes.md`, logs, and explicit invalid/degraded interval recording.
- CI smoke coverage for the complete M001 benchmark path.

Consumes:
- S03 CLI/backend path and S04 evaluator/plot outputs.
