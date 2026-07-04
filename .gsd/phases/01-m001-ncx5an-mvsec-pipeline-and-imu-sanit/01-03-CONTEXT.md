---
id: S03
milestone: M001-ncx5an
status: ready
---

# S03: IMU Only Backend and CLI Run Path — Context

## Goal

Provide a one-command `imu_only` backend and CLI run path on synthetic data that writes the required trajectory artifacts and run skeleton for downstream evaluation.

## Why this Slice

S03 turns the synchronization/export contracts from S02 into an executable baseline path. It unblocks S04 by producing real run directories and artifacts, and it establishes a minimal backend interface and CLI conventions that M002 (Event+IMU) will reuse.

## Scope

### In Scope

- Minimal odometry backend interface and `imu_only` implementation.
- CLI entrypoint `python -m nav_benchmark.run` with subcommand+flags shape and sensible synthetic defaults.
- Deterministic IMU-only propagation sufficient for smoke validation.
- Project CSV and TUM exports via S02 contract.
- Timestamped run directory creation under `runs/`, explicit `--resume` handling, `run.log`, `failure_notes.md`, and `run_manifest.json`.
- Practical health labeling that preserves rows (OK, DEGRADED, LOST, INVALID) with counts recorded in artifacts.
- Console UX: info logs, progress bar, and an end-of-run artifact confidence summary.
- Optional manual MVSEC execution via a local HDF5 path with clear failure diagnostics (tests remain synthetic-only).

### Out of Scope

- Evaluator alignment, metrics (`metrics.json`), error CSVs, and plots (S04 owns these).
- Event+IMU and other backends (M002/M003).
- Dataset downloads or heavy real-data exercises in CI.
- Rich plugin framework beyond the minimal backend contract.

## Constraints

- Respect S01 sequence loader structures and S02 trajectory/export contracts; no alternate schemas.
- Deterministic, reproducible behavior; never silently drop invalid/degraded rows.
- CLI failures return nonzero while still writing diagnostic artifacts when feasible.
- All generated outputs live under untracked `runs/`.
- Record gravity convention, initialization assumptions, and health thresholds in `run_manifest.json`.

## Integration Points

### Consumes

- `src/nav_benchmark/datasets/mvsec.py` — sequence object and loader diagnostics.
- `src/nav_benchmark/trajectory/models.py` — trajectory data model and health label schema.
- `src/nav_benchmark/trajectory/export.py` — CSV/TUM exporters per fixed schema.
- `src/nav_benchmark/trajectory/sync.py` — synchronization diagnostics referenced in manifest.

### Produces

- `src/nav_benchmark/baselines/imu.py` — IMU-only backend returning the common result shape.
- `src/nav_benchmark/run.py` — CLI orchestration for `run imu_only` and future methods.
- `runs/<YYYYmmdd_HHMMSS>_imu_only_<source-sequence>/estimated_trajectory.csv` — primary trajectory artifact.
- `runs/<YYYYmmdd_HHMMSS>_imu_only_<source-sequence>/estimated_trajectory_tum.txt` — TUM export (OK/DEGRADED only).
- `runs/<YYYYmmdd_HHMMSS>_imu_only_<source-sequence>/run.log` — execution log.
- `runs/<YYYYmmdd_HHMMSS>_imu_only_<source-sequence>/failure_notes.md` — always-present notes (success case: "No degraded or failed intervals detected." or similar with counts).
- `runs/<YYYYmmdd_HHMMSS>_imu_only_<source-sequence>/run_manifest.json` — reproducibility metadata (method, dataset/sequence, config, timestamp policy, gravity/frames/units, alignment placeholder, code version if available, status, and health counts).

## Open Questions

- Final numeric thresholds for LOST/DEGRADED; choose conservative deterministic defaults and codify in tests and manifest.
- Exact `--resume` behavior (suffix `-r{N}` vs `_resume/` subdir); pick the simpler to implement/verify.
- Real MVSEC invocation flags spelling (e.g., `--dataset mvsec --sequence outdoor_day1 --input <path>`); finalize in docs alongside manual run instructions.
