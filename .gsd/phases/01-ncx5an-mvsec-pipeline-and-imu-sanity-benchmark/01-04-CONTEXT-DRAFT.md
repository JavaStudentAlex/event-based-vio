---
id: S04
milestone: M001-ncx5an
status: draft
---

# S04: Drift Evaluation and Plots — Context Draft v2

## Goal

Deliver deterministic, project-native evaluation and publication-grade plots for S03 run artifacts, including global SE3 alignment, ATE, RPE@1m, final drift, coverage, error-vs-time, error-vs-distance, and 20 m drift bins, with clear success/failure signaling.

## Why this Slice

S04 transforms raw trajectory artifacts into benchmark evidence with explicit policies documented for alignment, coverage, binning, and invalid-interval handling. This enables S05 to validate the complete artifact contract and CI smoke coverage.

## Confirmed Human Decisions (Rounds 1–3)

- Alignment: Global SE3 across all timestamp-associated valid pairs; no time-offset search in M001. Record alignment transform and stats in metrics.json.
- Invalid treatment: Compute numerics on OK+DEGRADED only; report LOST/INVALID coverage and intervals. Provide coverage fields in metrics.json.
- Drift binning: Fixed 20 m bins with median + IQR; include partial last bin if ≥30% full.
- Entrypoint: Separate explicit `eval` subcommand for existing run directories; add helpers like `--latest`.
- RPE: Distance-basis with 1 m delta, sliding window by default.
- Plot style: Publication-grade PNG + SVG with colorblind-safe palette and equal XY aspect on trajectory plots.
- Eval failure behavior: Write diagnostic artifacts and metrics.json with status=failed and a clear reason; headers-only CSVs if no rows; exit nonzero.
- Evo usage: Keep metrics project-native for M001; TUM remains for interoperability/manual evo checks.
- Success summary: Print a trustworthy benchmark summary with headline metrics, alignment mode, valid coverage, invalid seconds, and artifact paths.

## Scope

### In Scope

- `python -m nav_benchmark.run eval` command operating on a prior S03 run directory.
- Timestamp association per S02, global SE3 alignment, and robust-but-deterministic handling of outliers if needed.
- Computation and export of ATE, RPE@1m, final drift, error_vs_time.csv, error_vs_distance.csv, and drift-over-distance (20 m) plots and CSV support.
- Coverage reporting and invalid/lost intervals visibility in metrics.json (and optional intervals CSV if needed in S05).
- Publication-grade plot generation (PNG + SVG) from actual metric data.
- Clear failure modes with nonzero exit and diagnostic artifacts.

### Out of Scope

- Auto-evaluation at the end of S03 `run`.
- Time-offset estimation, mixed/global+local realignments.
- Penalty-inflated metrics or dual-reporting variants.
- Multi-method leaderboard comparisons or report docs.

## Constraints

- Follow S02 export schema, timestamp precision, and quaternion order.
- Deterministic outputs suitable for CI; no random sampling without a fixed seed.
- Do not hide invalid/lost data; keep it visible via coverage and intervals.
- Plots must reflect computed data — no placeholders.

## Integration Points

### Consumes

- `runs/<run_dir>/estimated_trajectory.csv` — S03 trajectory with health labels.
- Ground-truth source paths/config from `run_manifest.json` or a CLI flag.
- `src/nav_benchmark/trajectory/sync.py` — association policy and diagnostics.

### Produces

- `src/nav_benchmark/evaluation/metrics.py` — ATE, RPE@1m, final drift, coverage.
- `src/nav_benchmark/evaluation/plots.py` — trajectory and drift plots (PNG+SVG).
- `runs/<run_dir>/ground_truth_aligned.csv` — aligned association output for inspection.
- `runs/<run_dir>/metrics.json` — alignment policy and numeric results.
- `runs/<run_dir>/error_vs_time.csv` and `error_vs_distance.csv` — error series.
- `runs/<run_dir>/trajectory_plot.png/.svg`, `drift_over_distance.png/.svg` — plots for reporting.

## Open Questions

- Outlier trimming policy during SE3 estimation — choose none vs fixed-trim based on synthetic test needs.
- Exact CSV columns for error series (component-wise vs magnitude-only); favor completeness with clear headers.
- Whether to optionally append an `evaluation` block into `run_manifest.json` post-eval or keep evaluation metadata only in `metrics.json` for M001.
