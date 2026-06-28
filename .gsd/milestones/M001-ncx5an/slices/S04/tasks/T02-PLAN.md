---
estimated_steps: 13
estimated_files: 2
skills_used: []
---

# T02: Trajectory and drift plotting utilities

---
skills_used:
  - verify-before-complete
---
Why: S04 requires visual artifacts, but plots must be generated from the metric series rather than placeholder trajectories. Keeping plotting separate from metrics prevents matplotlib concerns from contaminating numeric tests.

Do:
- Implement `src/nav_benchmark/evaluation/plots.py` using a non-interactive matplotlib backend suitable for CI.
- Add `write_trajectory_plot(...)` that plots estimated trajectory against aligned ground truth, uses equal XY aspect, labels axes in meters, includes method/sequence metadata where available, and writes both PNG and SVG.
- Add `write_drift_over_distance_plot(...)` that plots position error over cumulative distance and overlays 20 m bin median with IQR band from the T01 drift-bin summaries.
- Ensure functions accept the numeric rows/results from `metrics.py` and do not re-parse run directories or recompute metrics.
- Q6 load profile: support CI-scale synthetic tests quickly while avoiding assumptions that prevent later MVSEC-sized series; close figures after writing to avoid memory growth.
- Q7 negative tests: empty series or missing bin data should raise a clear plotting error rather than writing blank artifacts.

Done when: tests create PNG and SVG files in temporary directories, verify they are non-empty and contain expected SVG labels, and prove empty inputs fail clearly.

## Inputs

- `src/nav_benchmark/evaluation/metrics.py`
- `pyproject.toml`

## Expected Output

- `src/nav_benchmark/evaluation/plots.py`
- `tests/evaluation/test_plots_synthetic.py`

## Verification

rtk uv run --only-dev pytest tests/evaluation/test_plots_synthetic.py -q

## Observability Impact

Adds deterministic visual observability through trajectory and drift-over-distance plots generated from the same metric series saved to CSV.
