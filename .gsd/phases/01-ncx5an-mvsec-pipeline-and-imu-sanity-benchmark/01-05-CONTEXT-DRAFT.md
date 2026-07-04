---
id: S05
milestone: M001-ncx5an
status: draft
---

# S05: Manifest Failure Artifacts and CI Smoke Coverage — Context Draft

## Goal

Finalize the M001 operational artifact contract by enforcing always-present manifest/failure/log artifacts and CI-friendly synthetic content validation for the complete run/eval path.

## Why this Slice

S05 is the integration hardening slice. S03 and S04 produce the backend, evaluation, metrics, and plot artifacts; S05 makes them trustworthy by validating content and cross-artifact consistency rather than just file presence. It also creates the artifact contract that M002 can reuse unchanged for future methods.

## Confirmed Human Decisions So Far

- `run_manifest.json` shape: use a flat top-level manifest with a per-phase status block. Include method, dataset/sequence, timestamps, overall status, `phases.run`, `phases.eval`, policies, health counts, paths, command, and version metadata.
- Status model: use clear enums such as `SUCCESS`, `PARTIAL`, `FAILED`, and phase-level `SKIPPED` where evaluation was not run.
- `failure_notes.md`: always present, with structured sections such as Run summary, Degraded/failed intervals, Failures, and Next actions. On clean successful runs, include the canonical fixed sentence: `No degraded or failed intervals detected.`
- CI smoke checks: enforce deterministic content checks and cross-artifact consistency without brittle numeric thresholds. Check headers, non-empty rows, TUM filtering consistency, manifest policy/health fields, metrics policy fields, and non-empty plot files.
- Validation entrypoint: add a separate explicit `validate` subcommand for existing run directories, e.g. `python -m nav_benchmark.run validate --run-dir <dir>` with optional `--latest` helpers.
- CI failure policy: fail on missing/empty required artifacts or consistency failures. Do not fail merely because LOST/INVALID/DEGRADED intervals exist if they are correctly preserved and reported.

## Scope

### In Scope

- Artifact contract validator for S03/S04 outputs.
- `validate` CLI path for existing run directories.
- Standard `run_manifest.json` schema with overall and per-phase status.
- Standard `failure_notes.md` structure and exact clean-run success sentence.
- Synthetic CI smoke coverage for complete run + eval + validate path.
- Cross-artifact checks: trajectory CSV health counts, TUM row filtering, metrics alignment/drift policy fields, plot non-empty/generated-from-data checks, manifest path/policy consistency.
- Documentation of manual full-MVSEC validation expectations and why CI remains synthetic-only.

### Out of Scope

- Strict numeric benchmark thresholds for ATE/RPE/drift in CI.
- Treating degraded/invalid intervals as automatic CI failures.
- Multi-method comparison reports or leaderboards.
- Dataset downloads or real MVSEC execution in ordinary CI.

## Constraints

- Generated artifacts remain under untracked `runs/`.
- Validation must be deterministic, fast, and CI-friendly.
- Invalid/degraded/lost intervals are benchmark data and must be accepted when correctly recorded.
- Content validation is stronger than file existence but should avoid brittle floating-point expectations.

## Integration Points

### Consumes

- `runs/<run_dir>/estimated_trajectory.csv` — fixed project trajectory schema and health labels.
- `runs/<run_dir>/estimated_trajectory_tum.txt` — TUM export, should match OK+DEGRADED count from project CSV.
- `runs/<run_dir>/ground_truth_aligned.csv` — S04 aligned GT output.
- `runs/<run_dir>/metrics.json` — alignment, RPE, drift, coverage, and status metadata.
- `runs/<run_dir>/error_vs_time.csv` and `error_vs_distance.csv` — non-empty metric series.
- `runs/<run_dir>/trajectory_plot.png/.svg` and `drift_over_distance.png/.svg` — plot outputs.
- `runs/<run_dir>/run_manifest.json` — reproducibility metadata and phase statuses.
- `runs/<run_dir>/failure_notes.md` and `run.log` — diagnostic and human-readable operational artifacts.

### Produces

- Artifact validation module (likely `src/nav_benchmark/validation.py` or `src/nav_benchmark/artifacts.py`) — reusable contract checks.
- CLI validation path under `src/nav_benchmark/run.py` — `validate` subcommand.
- Tests validating the synthetic run/eval/validate smoke path and intentionally broken artifact cases.
- Documentation of artifact contract and manual full-MVSEC checks.

## Open Questions

- Exact module path/name for artifact validation — current thinking: keep it project-owned and reusable by future methods.
- Plot validity threshold — current thinking: use minimum byte size plus successful file decode where easy; avoid image-content assertions.
- Whether `validate` writes a validation report artifact or only exits/prints — current thinking: print a pass/fail table now; optional report can be added later if useful.
