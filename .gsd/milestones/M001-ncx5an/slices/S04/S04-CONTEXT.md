---
id: S04
milestone: M001-ncx5an
status: ready
---

# S04: Drift Evaluation and Plots — Context

## Goal

Provide deterministic, project-native evaluation and publication-grade plots for S03 run artifacts, including global SE3 alignment, ATE, RPE@1m, final drift, coverage, error-vs-time, error-vs-distance, and 20 m drift bins.

## Why this Slice

S04 turns S03 trajectory artifacts into benchmark evidence. It consumes the fixed S02 contracts and produces the metrics and plots that S05 will validate. Clear alignment/coverage policies and failure signaling make early results interpretable without overclaiming.

## Scope

### In Scope

- Explicit evaluation entrypoint: `python -m nav_benchmark.run eval --run-dir <dir>` with helpers like `--latest`/filters.
- Timestamp association per S02; global SE3 alignment over overlapping valid pairs (no time-offset search in M001).
- Metrics: ATE, RPE at 1 m travelled-distance (sliding window), final drift, error over time, error over distance, 20 m drift-binned statistics.
- Coverage accounting: valid ratio, LOST/INVALID seconds, longest gap; keep invalid/lost visible without polluting numerics.
- Plots: trajectory (equal XY aspect) and drift-over-distance with median+IQR; export PNG and SVG.
- Deterministic behavior and diagnostic artifacts on failure (status, reason, partial/headers-only CSVs), nonzero exit code.

### Out of Scope

- Auto-running evaluation at the end of S03; evaluation remains an explicit command.
- Time-offset estimation and sliding/local realignments.
- Penalty-inflated or dual-reporting metric variants.
- Multi-method leaderboard/report documents; later milestones own those.

## Constraints

- Adhere to S02 trajectory schema: fixed CSV columns, UNIX-seconds timestamps (9 dp), quaternion order qx,qy,qz,qw; TUM export semantics unchanged.
- Compute numerics on OK+DEGRADED only; LOST/INVALID excluded from numerics but fully reported as coverage/intervals.
- Plots must be generated from actual metric series — no placeholders.
- Deterministic, CI-friendly outputs; no silent row drops or stochastic choices without fixed seed.
- Record alignment transform, policy, coverage, and binning config in metrics.json; avoid overclaiming.

## Integration Points

### Consumes

- `runs/<run_dir>/estimated_trajectory.csv` — Estimated trajectory with health labels from S03.
- Ground-truth source path via `runs/<run_dir>/run_manifest.json` or an explicit `--ground-truth` flag — Input for association/alignment.
- `src/nav_benchmark/trajectory/sync.py` — Nearest-neighbor association and diagnostics per S02.
- `src/nav_benchmark/trajectory/models.py` and `export.py` — Shared trajectory representations and CSV helpers.

### Produces

- `src/nav_benchmark/evaluation/metrics.py` — Global SE3 alignment + ATE, RPE@1m, final drift, coverage.
- `src/nav_benchmark/evaluation/plots.py` — Trajectory and drift-over-distance plotting utilities.
- `runs/<run_dir>/ground_truth_aligned.csv` — Associated/aligned GT for inspection.
- `runs/<run_dir>/metrics.json` — Numeric results and policies (alignment, coverage, binning, RPE basis/window).
- `runs/<run_dir>/error_vs_time.csv` — Time-indexed position error series.
- `runs/<run_dir>/error_vs_distance.csv` — Distance-indexed position error series and drift bins.
- `runs/<run_dir>/trajectory_plot.png` and `.svg` — Estimated vs ground-truth trajectory plot.
- `runs/<run_dir>/drift_over_distance.png` and `.svg` — 20 m drift-binned plot with median and IQR band.

## Open Questions

- Outlier handling for SE3 fit: none vs fixed robust trimming; choose simplest deterministic policy that passes synthetic tests, and record in metrics.json.
- Exact columns for error series CSVs: include timestamps/distance, xyz error, magnitude, health, and association residual; finalize in tests/docs.
- Whether to add an `evaluation` status block back into run_manifest.json after eval (in addition to metrics.json) for quick scanning; acceptable either way in M001.
