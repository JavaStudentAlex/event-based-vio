# S04: Drift Evaluation and Plots

**Goal:** Implement deterministic drift evaluation and plotting for S03 run artifacts: associate estimates to ground truth, globally align with explicit SE(3) policy, compute ATE/RPE/final-drift/coverage/drift bins, and write metrics, error series, aligned ground truth, and plots through an explicit eval CLI command.
**Demo:** The evaluator aligns estimates to ground truth with explicit SE3 policy and produces valid `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, trajectory plot, and drift-over-distance plot.

## Must-Haves

- `python -m nav_benchmark.run eval --run-dir <dir> --ground-truth <path>` evaluates a synthetic S03-style run directory without requiring MVSEC downloads.
- Evaluation consumes the S02 fixed trajectory CSV schema and preserves health labels; OK and DEGRADED rows are used for numerics while LOST and INVALID rows are reported in coverage and excluded from numeric aggregate metrics.
- Global alignment policy is explicit: nearest-neighbor timestamp association, no time-offset search, one global SE(3) fit, no robust trimming or outlier rejection in M001.
- Run directory outputs include `ground_truth_aligned.csv`, `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, `trajectory_plot.png`, `trajectory_plot.svg`, `drift_over_distance.png`, and `drift_over_distance.svg`.
- `metrics.json` records status, policy metadata, alignment transform, synchronization diagnostics, ATE, RPE@1m, final drift, coverage, invalid/lost durations, and 20 m bin configuration.
- Error CSVs contain enough columns to regenerate plots from numeric series; plots are generated from those series and are not placeholders.
- Failure cases write diagnostic artifacts and exit nonzero rather than silently succeeding.
- Synthetic unit and CLI tests validate metrics, alignment, coverage, artifact schemas, plot creation, and negative/failure behavior.
- Supporting requirement R003 remains protected by consuming the fixed project CSV columns and validating health-label preservation during evaluation.

## Proof Level

- This slice proves: High: deterministic synthetic unit tests for alignment and metrics, deterministic plotting tests using temporary files, CLI integration tests over a synthetic run directory, negative tests for insufficient/invalid data, plus full ruff and pytest verification. Real MVSEC execution is not required for S04 proof.

## Integration Closure

S04 closes the S02/S03 integration boundary by reading `estimated_trajectory.csv` emitted by the existing run CLI, using S02 trajectory models/export/synchronization semantics, accepting ground truth via explicit `--ground-truth` or manifest metadata, and writing the complete evaluator artifact set that S05 will validate. The roadmap remains unchanged because existing code confirms S02/S03 artifacts and dependencies match the S04 assumptions.

## Verification

- Adds benchmark observability surfaces in `metrics.json` status/policy/diagnostic blocks, error series CSVs, aligned ground-truth inspection CSV, deterministic trajectory and drift plots, and nonzero-failure diagnostic output for missing, mismatched, or insufficient evaluation inputs.

## Tasks

- [x] **T01: Implemented the evaluation metric core layer and serialization functions.** `est:1 day`
  ---
  skills_used:
    - design-an-interface
    - verify-before-complete
  ---
  Why: S04 needs a trustworthy project-native metric layer before CLI wiring or plotting can be meaningful. This task owns the numeric contract and keeps it independent from argparse and filesystem orchestration.
  - Files: `src/nav_benchmark/evaluation/__init__.py`, `src/nav_benchmark/evaluation/metrics.py`, `tests/evaluation/test_metrics_synthetic.py`
  - Verify: rtk uv run --only-dev pytest tests/evaluation/test_metrics_synthetic.py -q

- [x] **T02: Implemented trajectory and drift plotting utilities with Agg backend and verified them via synthetic test cases.** `est:0.5 day`
  ---
  skills_used:
    - verify-before-complete
  ---
  Why: S04 requires visual artifacts, but plots must be generated from the metric series rather than placeholder trajectories. Keeping plotting separate from metrics prevents matplotlib concerns from contaminating numeric tests.
  - Files: `src/nav_benchmark/evaluation/plots.py`, `tests/evaluation/test_plots_synthetic.py`
  - Verify: rtk uv run --only-dev pytest tests/evaluation/test_plots_synthetic.py -q

- [ ] **T03: Eval CLI and run directory artifact writer** `est:1 day`
  ---
  skills_used:
    - design-an-interface
    - verify-before-complete
  ---
  Why: The evaluator must be reachable through the same `nav_benchmark.run` module established in S03 and must write the S04 artifact set into a run directory for S05 validation.
  - Files: `src/nav_benchmark/run.py`, `tests/cli/test_eval_cli_synthetic.py`, `tests/evaluation/test_eval_artifact_contract_synthetic.py`
  - Verify: rtk uv run --only-dev pytest tests/cli/test_eval_cli_synthetic.py tests/evaluation/test_eval_artifact_contract_synthetic.py -q

- [ ] **T04: Evaluation documentation and full slice verification** `est:0.5 day`
  ---
  skills_used:
    - write-docs
    - verify-before-complete
  ---
  Why: S04 changes the public benchmark workflow by adding an explicit eval command and a new artifact contract. Executors and S05 need documentation that a fresh reader can use without reading the implementation.
  - Files: `docs/run/cli.md`, `docs/evaluation/drift-evaluation.md`
  - Verify: rtk uv run --only-dev ruff check . && rtk uv run --only-dev ruff format --check . && rtk uv run --only-dev pytest tests -q

## Files Likely Touched

- src/nav_benchmark/evaluation/__init__.py
- src/nav_benchmark/evaluation/metrics.py
- tests/evaluation/test_metrics_synthetic.py
- src/nav_benchmark/evaluation/plots.py
- tests/evaluation/test_plots_synthetic.py
- src/nav_benchmark/run.py
- tests/cli/test_eval_cli_synthetic.py
- tests/evaluation/test_eval_artifact_contract_synthetic.py
- docs/run/cli.md
- docs/evaluation/drift-evaluation.md
