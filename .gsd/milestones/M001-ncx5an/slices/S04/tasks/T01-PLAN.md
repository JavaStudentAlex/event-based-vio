---
estimated_steps: 17
estimated_files: 3
skills_used: []
---

# T01: Implemented the evaluation metric core layer and serialization functions.

---
skills_used:
  - design-an-interface
  - verify-before-complete
---
Why: S04 needs a trustworthy project-native metric layer before CLI wiring or plotting can be meaningful. This task owns the numeric contract and keeps it independent from argparse and filesystem orchestration.

Do:
- Create the `nav_benchmark.evaluation` package and implement `metrics.py` with small, typed data structures for evaluation configuration, association diagnostics, coverage, alignment result, metric summary, error-vs-time rows, error-vs-distance rows, and drift-bin summaries.
- Add readers/adapters for the S02 project CSV schema and ground-truth trajectory CSVs so evaluation consumes `Trajectory` objects rather than ad hoc dictionaries.
- Use `synchronize_nearest_neighbor` for timestamp association with explicit tolerance and include association residuals in outputs.
- Filter numeric aggregates to OK and DEGRADED estimate rows only; preserve LOST and INVALID in coverage accounting and exported series visibility.
- Implement one global SE(3) alignment over valid associated pairs. Use evo `PoseTrajectory3D` with wxyz quaternions where it simplifies alignment/metric parity, and keep numpy/scipy fallbacks or direct calculations explicit and deterministic.
- Compute ATE RMSE/statistics, RPE at 1.0 meter travelled-distance, final drift, cumulative distance, error-vs-time rows, error-vs-distance rows, and 20 m drift-bin median/IQR summaries.
- Record alignment policy fields: `association_tolerance_sec`, `alignment_policy`, `correct_scale=false`, `time_offset_search=false`, `outlier_rejection=none`, `rpe_delta_m=1.0`, and `drift_bin_width_m=20.0`.
- Q3 threat surface: validate input schemas, finite numeric arrays, monotonic timestamps, health labels, quaternion order, and minimum valid-pair counts so malformed local files cannot produce misleading metrics.
- Q5/Q7 failure and negative tests: cover insufficient valid pairs, all LOST/INVALID rows, non-monotonic timestamps, and non-finite values with explicit errors or failed evaluation status rather than silent drops.

Done when: synthetic tests prove a known translated/rotated trajectory aligns to near-zero ATE, known drift remains measurable, coverage counts LOST/INVALID intervals, error-series schemas are stable, and metric dictionaries are JSON-serializable without NaN/Inf.

## Inputs

- `src/nav_benchmark/trajectory/models.py`
- `src/nav_benchmark/trajectory/export.py`
- `src/nav_benchmark/trajectory/sync.py`
- `src/nav_benchmark/datasets/mvsec.py`
- `pyproject.toml`

## Expected Output

- `src/nav_benchmark/evaluation/__init__.py`
- `src/nav_benchmark/evaluation/metrics.py`
- `tests/evaluation/test_metrics_synthetic.py`

## Verification

rtk uv run --only-dev pytest tests/evaluation/test_metrics_synthetic.py -q

## Observability Impact

Introduces structured evaluation diagnostics, coverage metadata, alignment metadata, and metric summaries that become the canonical contents of `metrics.json`.
