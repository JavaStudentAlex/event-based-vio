---
id: S03
milestone: M001-ncx5an
status: draft
---

# S03: IMU Only Backend and CLI Run Path — Context Draft v2

## Goal

Deliver a one-command `imu_only` run path on synthetic data through a minimal backend interface, producing valid estimated trajectory artifacts and the required run skeleton for downstream evaluation.

## Why this Slice

S03 connects the synchronization/export contract (S02) to an executable baseline backend and CLI. It unblocks S04 by producing real run artifacts and codifies backend/CLI conventions that M002 will reuse for `event_imu`.

## Confirmed Human Decisions (Rounds 1–3)

- CLI shape: subcommand + flags: `python -m nav_benchmark.run run imu_only --dataset synthetic --sequence tiny --output runs/ --verbose` with sensible defaults.
- Run directory: timestamped naming like `runs/{YYYYmmdd_HHMMSS}_{method}_{source-seq}/`; support `--resume` rather than overwrite; always write manifest, log, failure notes.
- Health policy: practical defaults that preserve rows; mark LOST on large gaps (~>5× median dt or >0.2s), INVALID on NaN/Inf, DEGRADED on sustained accel inconsistency; record counts in manifest/notes.
- Runtime UX: info logs + progress bar, then a crisp end-of-run summary (sample counts, health counts, artifact paths).
- Failure semantics: always create skeleton and partial artifacts when possible; exit nonzero on failure.
- S03 artifact boundary: now → `estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, `run.log`, `failure_notes.md`, `run_manifest.json`; S04 owns metrics, alignment, error CSVs, plots.
- IMU initialization: synthetic-known defaults: identity pose and zero velocity unless fixture metadata supplies start; fixed gravity convention recorded in manifest; real MVSEC requires explicit config/metadata before claiming meaningful motion.
- MVSEC scope: accept a local HDF5 path best-effort now; tests and proof remain synthetic-only; fail clearly with structured diagnostics if layout/calibration missing.
- “Done” feel: artifact confidence summary stating what’s valid now and what’s intentionally deferred (metrics/plots in S04).

## Scope

### In Scope

- Minimal odometry backend interface and `imu_only` baseline.
- Synthetic default CLI run path; optional manual MVSEC path acceptance with clear failure messages.
- Deterministic propagation sufficient for smoke tests and artifact generation.
- Project CSV and TUM export via S02.
- Timestamped run directory, resume semantics, logging, manifest, and failure notes.
- Practical health labeling with preserved rows and recorded counts.
- User-facing progress and end-of-run artifact confidence summary.

### Out of Scope

- Metrics, alignment, error CSVs, and plots (S04).
- Event+IMU and other backends (M002/M003).
- Dataset downloads in CI; ordinary CI stays synthetic.
- Rich plugin system beyond minimal backend contract.

## Constraints

- Conform strictly to S02 models and export contracts.
- Deterministic, CI-friendly behavior; no silent row drops.
- Nonzero exit on failure while still writing diagnostic artifacts when feasible.
- Outputs under untracked `runs/`.

## Integration Points

### Consumes

- `src/nav_benchmark/datasets/mvsec.py` — sequence and loader diagnostics.
- `src/nav_benchmark/trajectory/models.py` — trajectory and health label schema.
- `src/nav_benchmark/trajectory/export.py` — CSV/TUM export functions.
- `src/nav_benchmark/trajectory/sync.py` — diagnostics for manifest.

### Produces

- `src/nav_benchmark/baselines/imu.py` — IMU-only backend.
- `src/nav_benchmark/run.py` — CLI run orchestration.
- `runs/<ts>_imu_only_<source-sequence>/estimated_trajectory.csv` — trajectory.
- `runs/<ts>_imu_only_<source-sequence>/estimated_trajectory_tum.txt` — TUM export.
- `runs/<ts>_imu_only_<source-sequence>/run.log` — logs.
- `runs/<ts>_imu_only_<source-sequence>/failure_notes.md` — notes.
- `runs/<ts>_imu_only_<source-sequence>/run_manifest.json` — reproducibility metadata.

## Open Questions

- Exact numeric thresholds for health states — choose conservative deterministic values; document in manifest and tests.
- Resume semantics detail — append `-r{N}` suffix vs `_resume/` subdir; decide based on simplicity and testability.
- Real MVSEC invocation flags — exact spelling for `--input`, `--dataset mvsec`, and `--sequence outdoor_day1`; confirm in docs.
