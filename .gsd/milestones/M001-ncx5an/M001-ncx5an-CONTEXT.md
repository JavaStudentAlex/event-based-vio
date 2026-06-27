# M001-ncx5an: MVSEC Pipeline and IMU Sanity Benchmark

**Gathered:** 2026-06-27
**Status:** Ready for planning

## Project Description

This milestone establishes the first trustworthy, reproducible benchmark foundation for an MVSEC-based GPS-denied event-camera navigation project. It does not claim drift-bounded navigation yet. It produces a **drift-measured relative odometry benchmark** by loading MVSEC-style sensor data, running an `imu_only` sanity baseline, exporting standard artifacts, and evaluating drift growth versus distance travelled.

The full project path is three milestones:

1. M001-ncx5an — MVSEC Pipeline and IMU Sanity Benchmark
2. M002 — First Event+IMU Odometry Backend
3. M003 — Strong Baselines and Benchmark Reporting

## Why This Milestone

The project needs a trustworthy benchmark harness before adding Event+IMU odometry, stronger external baselines, ensemble logic, or map anchoring. The first proof is that the repo can ingest event-camera/IMU/ground-truth data, handle timestamps and frames explicitly, produce a relative trajectory artifact, and measure drift without silent data loss.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Run a single CLI command for `imu_only` on a synthetic CI fixture and produce the full benchmark artifact set.
- Use the same command shape for a documented/manual MVSEC run on `outdoor_day1`, with `indoor_flying1` as the easier debug fallback.
- Inspect trajectory exports, drift metrics, plots, manifest metadata, logs, and failure notes to understand how the benchmark handled the run.

### Entry point / environment

- Entry point: `python -m nav_benchmark.run`
- Environment: local Python development environment managed by `uv`; ordinary CI uses synthetic data only.
- Live dependencies involved: local MVSEC HDF5 files for manual/full-dataset runs; none for ordinary synthetic CI.

## Completion Class

- Contract complete means: synthetic tests prove the loader contract, timestamp synchronization, trajectory CSV/TUM export, metric calculations, drift-over-distance bins, artifact validation, and CLI smoke path.
- Integration complete means: `imu_only` runs through the real backend/export/evaluation/plot/manifest/failure-artifact pipeline through one CLI entrypoint.
- Operational complete means: run directories include reproducibility metadata, status, logs, and failure notes; no external service lifecycle is involved.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- `imu_only` can run through one command and write the complete M001 artifact set.
- The evaluator reports drift growth versus distance travelled with explicit SE3 alignment metadata.
- Artifact checks validate contents, not only existence: CSVs have required columns and non-empty rows, TUM export follows TUM format, `metrics.json` includes drift and alignment fields, and plots are generated from actual metric data.
- Invalid/degraded intervals are explicitly recorded in benchmark artifacts, not only mentioned in logs.
- Full MVSEC execution remains documented/manual because ordinary CI must not require large dataset downloads.

## Architectural Decisions

### Package the benchmark as `src/nav_benchmark`

**Decision:** Build implementation under a real Python package, starting with modules such as `datasets/mvsec.py`, `sync.py`, `calibration.py`, `trajectory.py`, `baselines/imu.py`, `evaluation/metrics.py`, `evaluation/plots.py`, and `run.py`.

**Rationale:** The project needs reusable seams across M001, M002, and M003. A package keeps dataset loading, synchronization, baselines, export, evaluation, plotting, and CLI wiring testable instead of becoming a pile of scripts.

**Alternatives Considered:**
- Top-level folders such as `data_tools/`, `baselines/`, and `evaluation/` — closer to `milestone_1_event_imu_vio.md`, but weaker for imports, tests, and future backend replacement.
- One script first — fastest initially, but risks creating a script blob and delaying the backend interface needed by M002.

### Use `h5py` for first-pass MVSEC access

**Decision:** Use `h5py` for direct HDF5 file/group/dataset/attribute access in the MVSEC loader.

**Rationale:** MVSEC streams are available as HDF5 files that mirror ROS bag structure, and the project dependency baseline already includes `h5py`.

**Alternatives Considered:**
- `rosbags` first — useful when raw `.bag` support is required, but unnecessary for the first HDF5 loader path.

### Keep project artifacts authoritative and TUM export interoperable

**Decision:** Project CSV and `metrics.json` are the stable benchmark contract; TUM export is required for compatibility with common SLAM/VIO tools such as `evo`.

**Rationale:** The project needs custom fields for method, velocity, confidence, health, latency, invalid intervals, alignment policy, drift-over-distance outputs, and run status. `evo` compatibility is useful, but it should not replace project-owned artifacts.

**Alternatives Considered:**
- Make `evo` the only evaluator — rejected because drift-over-distance artifacts, failure visibility, latency fields, and fixed project schema are required.

### Default to explicit SE3 alignment for M001 evaluation

**Decision:** Timestamp-associate estimated and ground-truth trajectories, then use an explicit SE3 alignment policy by default. Record the policy in `metrics.json` and `run_manifest.json`.

**Rationale:** SE3 alignment makes early evaluator results interpretable while frame/calibration assumptions are still being hardened. Alignment must be documented so results are not overclaimed.

**Alternatives Considered:**
- Origin-only relative comparison — useful later, but harsher while loader/frame assumptions are still being proven.
- Implement both alignment modes in M001 — richer, but extra scope before the core harness works.

### Define a stable minimal odometry backend interface in M001

**Decision:** M001 defines a small backend contract so `imu_only`, future `event_imu`, and later external wrappers return the same result shape.

**Rationale:** M002 must add Event+IMU without rewriting export/evaluation. M003 must be able to add UltimateSLAM/ESVO wrappers without breaking the artifact contract.

**Alternatives Considered:**
- Add the interface only when Event+IMU exists — rejected because it would likely force refactoring before M002.
- Build a rich plugin framework now — rejected as overbuilt before external wrapper needs are proven.

### Store generated benchmark outputs under `runs/`

**Decision:** Generated benchmark outputs live under `runs/` and should remain untracked.

**Rationale:** `runs/` cleanly separates generated benchmark outputs from source/config/docs and matches the user’s earlier command examples.

**Alternatives Considered:**
- `experiments/` — matches the source note, but can blur generated outputs with reusable experiment docs/configs.

## Error Handling Strategy

- Dataset loading failures fail fast with a clear message naming the missing file, HDF5 group, dataset, or calibration field.
- Unsupported MVSEC layout raises a structured loader error that includes the discovered path and expected stream names.
- Timestamp validation rejects non-monotonic, duplicated, missing, or unit-ambiguous timestamps with diagnostics.
- Synchronization must not silently drop large unmatched ranges. It reports unmatched counts, tolerance used, first/last matched timestamps, and failure intervals.
- Required calibration fields are mandatory for real MVSEC runs; synthetic tests may use explicit synthetic calibration.
- IMU integration divergence should preserve rows when possible with `health=DEGRADED` or `health=LOST`.
- Invalid poses are benchmark data and must remain visible with stable health labels such as `OK`, `DEGRADED`, `LOST`, or `INVALID`.
- Export should avoid leaving partial success without a `run.log`, `failure_notes.md`, or failure state explaining what failed.
- Evaluation distinguishes no ground-truth overlap, insufficient valid poses, alignment failure, and metric computation failure.
- CLI failures return nonzero exit codes while still writing diagnostic artifacts where possible.
- Logs include paths, shapes, counts, time ranges, and method/config metadata, but not raw full datasets or secrets.

## Risks and Unknowns

- MVSEC HDF5 layout and calibration fields may vary by sequence — loader assumptions must be explicit and tested against synthetic fixtures before manual MVSEC runs.
- Timestamp units and stream alignment can make metrics invalid — synchronization validation and manifest metadata are mandatory.
- Frame assumptions can make drift metrics misleading — frames, units, and alignment policy must be recorded in `run_manifest.json` and `metrics.json`.
- Silent sample drops would make outputs untrustworthy — unmatched samples and invalid intervals must be visible in benchmark artifacts.
- Plot files can exist without meaningful data — artifact validation must check that plots are generated from actual metric data.
- Event+IMU complexity is deferred to M002 — M001 should not accidentally overreach into a state-of-the-art backend.

## Existing Codebase / Prior Art

- `pyproject.toml` — declares Python 3.13, core dependencies (`h5py`, `numpy`, `scipy`, `pandas`, `matplotlib`, `evo`, `pyyaml`, `rich`, `tqdm`, `rosbags`, `opencv-python`) and dev tools (`pytest`, `ruff`, `pre-commit`, etc.).
- `AGENTS.md` — establishes MVSEC-first scope, first target `outdoor_day1`, debug fallback `indoor_flying1`, required trajectory CSV schema, benchmark rules, and verification expectations.
- `.github/skills/mvsec-benchmarking/SKILL.md` — reinforces fixed trajectory schema, explicit alignment policy, ATE/RPE/drift metrics, visible failed intervals, and synthetic CI tests.
- `milestone_1_event_imu_vio.md` — source context describing the broader first Event+IMU VIO milestone; split here into M001 foundation, M002 Event+IMU backend, and M003 stronger wrappers/reporting.

## Relevant Requirements

- R001 — M001 establishes MVSEC sensor ingestion.
- R002 — M001 validates timestamp synchronization and calibration handling.
- R003 — M001 defines the standard CSV and TUM trajectory contract.
- R004 — M001 implements `imu_only` dead reckoning as the sanity baseline.
- R005 — M001 aligns estimated and ground-truth trajectories and computes metrics.
- R006 — M001 produces drift growth versus distance artifacts.
- R007 — M001 provides the one-command benchmark entrypoint.
- R008 — M001 writes `run_manifest.json` for reproducibility metadata.
- R009 — M001 preserves invalid/degraded intervals and always writes `failure_notes.md`.
- R010 — M001 adds CI-friendly synthetic smoke tests.
- R011 — M001 defines the backend interface for later methods.
- R012/R013 — M001 prepares, but does not implement, the M002 Event+IMU backend and shared method artifact proof.

## Scope

### In Scope

- MVSEC-first loader for event camera, IMU, calibration, ground truth, and timestamps.
- Synthetic MVSEC-like fixtures for ordinary CI.
- Timestamp validation and synchronization without silent drops.
- Calibration/frame/unit metadata handling.
- Standard trajectory CSV export using the project schema.
- TUM trajectory export.
- Minimal odometry backend interface.
- `imu_only` dead reckoning baseline.
- CLI entrypoint `python -m nav_benchmark.run`.
- SE3-aligned evaluation against ground truth.
- ATE, RPE, final drift, position error over time, position error versus distance travelled, and distance-binned drift such as every 20 meters.
- Required artifacts: `estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, `ground_truth_aligned.csv`, `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, `trajectory_plot.png`, `drift_over_distance.png`, `run.log`, `failure_notes.md`, and `run_manifest.json`.
- Artifact content validation.
- Manual full-MVSEC run documentation.

### Out of Scope / Non-Goals

- Event+IMU backend implementation; M002 owns it.
- UltimateSLAM or ESVO production wrappers; M003 owns them if practical.
- Event-only visual odometry baseline.
- Full ensemble learning.
- RL/PPO fusion policy.
- Map or orthophoto anchoring.
- Satellite matching.
- Embedded optimization or hard real-time deployment.
- Full MVSEC dataset downloads in ordinary CI.

## Technical Constraints

- Use Python 3.13 and `uv`.
- Keep benchmark choices deterministic and reproducible.
- Do not require full MVSEC data for ordinary CI.
- Do not commit raw MVSEC archives, generated run artifacts, plots, large caches, secrets, or virtual environments.
- Keep coordinate frames, timestamp units, interpolation policy, alignment policy, and quaternion ordering explicit in code and tests.
- Preserve missing/invalid poses as benchmark data; do not silently drop them.

## Integration Points

- MVSEC HDF5 files — real/manual dataset source for event, IMU, calibration, and ground truth streams.
- Synthetic fixtures — ordinary CI source for deterministic pipeline checks.
- `evo`/TUM interoperability — supported through TUM export and optional standard trajectory evaluation where it fits.
- `runs/` output directories — generated benchmark artifacts and run metadata.
- M002 backend — consumes M001 backend interface, trajectory schema, evaluator, artifact validation, and CLI conventions.

## Testing Requirements

M001 tests should be fast, deterministic, and CI-friendly. They should not require MVSEC downloads.

Required synthetic test coverage:

- Loader behavior with tiny fake MVSEC-like samples.
- Timestamp monotonicity and synchronization behavior.
- Detection/reporting of unmatched or invalid intervals.
- Trajectory CSV schema and non-empty row validation.
- TUM export format validation.
- IMU-only backend smoke behavior on simple known motion.
- Metric calculation for ATE/RPE/final drift/error over time/error over distance.
- Distance-binned drift, including 20-meter-style bins.
- CLI smoke run that writes a complete artifact set.
- Artifact validation that checks contents, not only file existence.

Full MVSEC checks should be documented/manual or separately marked as dataset-dependent checks.

## Acceptance Criteria

M001 is complete when:

- `imu_only` can run through the full benchmark path from the CLI.
- Synthetic CI tests pass without requiring MVSEC downloads.
- Full MVSEC execution is documented/manual and points to `outdoor_day1` with `indoor_flying1` as debug fallback.
- The required artifact set exists and is content-valid.
- `run_manifest.json` records method, dataset/sequence, config, timestamp policy, alignment policy, frames, units, code version if available, and run status.
- `failure_notes.md` is always present; successful runs state `No degraded or failed intervals detected.`
- Invalid/degraded intervals are explicitly recorded in benchmark artifacts, not only mentioned in logs.
- Metrics document alignment/frame assumptions and include drift growth versus distance travelled.
- No timestamps, samples, or invalid intervals are silently dropped.
- The M001 backend/export/evaluation contract is ready for M002 `event_imu` to reuse unchanged.

## Open Questions

- Exact MVSEC HDF5 group names and calibration paths must be verified during S01 implementation against available sample files or documented layouts.
- Whether to use `evo` internally for any metrics in M001, versus only writing TUM for compatibility, should be decided during S04 based on fit and testability.
- Future M002 and M003 need their own detailed context discussions before implementation.
