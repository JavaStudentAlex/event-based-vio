---
id: S05
milestone: M001-ncx5an
status: ready
---

# S05: Manifest Failure Artifacts and CI Smoke Coverage — Context

## Goal

Finalize the M001 operational artifact contract by enforcing always-present manifest, failure-note, log, metrics, plot, and trajectory artifacts with deterministic CI-friendly content validation.

## Why this Slice

S05 hardens the run/evaluation pipeline delivered by S03 and S04 into a trustworthy benchmark contract. It ensures generated artifacts are not just present but content-valid and cross-consistent, which unblocks M002 from reusing the same artifact and validation contract for future `event_imu` backends.

## Scope

### In Scope

- Standard `run_manifest.json` schema with top-level run metadata and per-phase statuses for run/eval/validation.
- Standard always-present `failure_notes.md` with structured sections and the exact clean-run success sentence: `No degraded or failed intervals detected.`
- `validate` CLI subcommand for existing run directories, e.g. `python -m nav_benchmark.run validate --run-dir <dir>` with optional `--latest` helpers.
- Deterministic synthetic CI smoke coverage for run + eval + validate path.
- Content validation stronger than file existence: required headers, non-empty rows, policy fields, status fields, health counts, TUM filtering consistency, metric policy fields, and non-empty plot files.
- Cross-artifact consistency checks between `estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, `metrics.json`, `run_manifest.json`, and `failure_notes.md`.
- Manual full-MVSEC validation documentation, while ordinary CI remains synthetic-only.

### Out of Scope

- Strict numeric performance thresholds for ATE/RPE/drift in CI.
- Treating DEGRADED/LOST/INVALID intervals as automatic CI failures when they are correctly preserved and reported.
- Real MVSEC dataset downloads or full-dataset execution in ordinary CI.
- Multi-method leaderboards, comparison reports, or M002/M003 backend-specific validation beyond the shared contract.
- Uploading or committing generated run artifacts.

## Constraints

- Generated artifacts remain under untracked `runs/`.
- Validation must be deterministic, fast, and CI-friendly.
- Invalid, degraded, and lost intervals are benchmark data; validation should fail only if they are hidden, inconsistent, or unreported.
- Use content and cross-artifact checks without brittle floating-point thresholds.
- Do not log or persist raw large datasets, secrets, or bulky generated outputs in tracked files.

## Integration Points

### Consumes

- `runs/<run_dir>/estimated_trajectory.csv` — Fixed 15-column project trajectory schema and health labels.
- `runs/<run_dir>/estimated_trajectory_tum.txt` — TUM export that must include OK+DEGRADED rows only.
- `runs/<run_dir>/ground_truth_aligned.csv` — S04 aligned ground-truth artifact.
- `runs/<run_dir>/metrics.json` — Alignment, RPE, drift, coverage, binning, and status metadata.
- `runs/<run_dir>/error_vs_time.csv` — Time-indexed error series.
- `runs/<run_dir>/error_vs_distance.csv` — Distance-indexed error series and drift-related data.
- `runs/<run_dir>/trajectory_plot.png` and `.svg` — Trajectory visualizations generated from metric data.
- `runs/<run_dir>/drift_over_distance.png` and `.svg` — Drift-over-distance visualizations generated from metric data.
- `runs/<run_dir>/run_manifest.json` — Reproducibility metadata, policy fields, paths, health counts, command, version metadata, and per-phase status.
- `runs/<run_dir>/failure_notes.md` and `run.log` — Human-readable diagnostic and operational artifacts.

### Produces

- `src/nav_benchmark/validation.py` or equivalent artifact validation module — Reusable shared contract checks for M001 and future methods.
- `src/nav_benchmark/run.py` validation command wiring — `validate` subcommand and optional latest-run helpers.
- Synthetic CI smoke tests — Verify complete run/eval/validate path and intentionally broken artifact cases.
- Artifact contract documentation — Defines required files, schema expectations, status model, clean success wording, and manual MVSEC validation expectations.

## Open Questions

- Exact validation module name and location — current thinking: keep it project-owned and reusable, such as `src/nav_benchmark/validation.py`.
- Plot validity threshold — current thinking: require existence, nonzero/nontrivial byte size, and optionally image decode where practical; avoid fragile pixel-level assertions.
- Whether `validate` should write a validation report artifact — current thinking: print a concise pass/fail table and exit nonzero on failure for M001; add a report file later only if useful.
