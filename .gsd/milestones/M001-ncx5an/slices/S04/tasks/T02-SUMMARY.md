---
id: T02
parent: S04
milestone: M001-ncx5an
key_files:
  - src/nav_benchmark/evaluation/plots.py
  - tests/evaluation/test_plots_synthetic.py
key_decisions:
  - D008: Implemented plotting module using non-interactive Agg backend to support clean CLI execution without X server dependencies.
  - D009: Decoupled plotting input data structures from file-parsing concerns to maintain modularity and isolation of the visualization layer.
duration: 
verification_result: passed
completed_at: 2026-06-28T05:56:33.839Z
blocker_discovered: false
---

# T02: Implemented trajectory and drift plotting utilities with Agg backend and verified them via synthetic test cases.

**Implemented trajectory and drift plotting utilities with Agg backend and verified them via synthetic test cases.**

## What Happened

Implemented the trajectory and drift plotting utilities in `src/nav_benchmark/evaluation/plots.py` utilizing the non-interactive matplotlib 'Agg' backend. Added `write_trajectory_plot` to plot estimated vs aligned ground-truth trajectories with an equal XY aspect ratio, properly labeled axes in meters, and sequence metadata integration. Added `write_drift_over_distance_plot` which handles position error over cumulative distance with a raw ATE trace overlaid by 20m bin median values and corresponding IQR bands. Implemented negative bounds checking for empty trajectory results, None results, or invalid bin data to raise `PlottingError` consistently. Implemented a comprehensive test suite in `tests/evaluation/test_plots_synthetic.py` testing successful plot outputs as well as negative edge cases. Checked all files with Ruff and confirmed formatting and code standard compliance.

## Verification

Executed pytest test suite on synthetic plotting tests to verify PNG and SVG generation, correct text contents within SVG format, and PlottingError raising on invalid input trajectories. verified Ruff formatting and checks.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rtk uv run --only-dev pytest tests/evaluation/test_plots_synthetic.py -q` | 0 | ✅ pass | 12274ms |
| 2 | `rtk uv run --only-dev ruff check src/nav_benchmark/evaluation/plots.py tests/evaluation/test_plots_synthetic.py` | 0 | ✅ pass | 6089ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/nav_benchmark/evaluation/plots.py`
- `tests/evaluation/test_plots_synthetic.py`
