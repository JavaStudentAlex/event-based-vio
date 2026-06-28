---
estimated_steps: 18
estimated_files: 3
skills_used: []
---

# T03: Eval CLI and run directory artifact writer

---
skills_used:
  - design-an-interface
  - verify-before-complete
---
Why: The evaluator must be reachable through the same `nav_benchmark.run` module established in S03 and must write the S04 artifact set into a run directory for S05 validation.

Do:
- Extend `src/nav_benchmark/run.py` with an `eval` subcommand: `python -m nav_benchmark.run eval --run-dir <dir> --ground-truth <path>`.
- Add helper flags for deterministic discovery without hiding inputs: `--latest`, `--output-root`, optional `--method`, optional `--sequence`, `--association-tolerance-sec`, `--rpe-delta-m`, `--drift-bin-width-m`, and `--alignment-policy se3`.
- Resolve ground truth from explicit `--ground-truth` first and from `run_manifest.json` metadata only when present; fail clearly if neither exists.
- Read `estimated_trajectory.csv`, call the T01 evaluator, write `ground_truth_aligned.csv`, `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, and call T02 plot writers for PNG/SVG artifacts.
- Keep S03 `run` behavior backward compatible and preserve existing run CLI tests.
- On failure, write diagnostic `metrics.json` with `status=failed`, `reason`, policy fields, and header-only or partial CSV artifacts where safe; exit nonzero so CI detects the problem.
- Optionally update `run_manifest.json` with an evaluation status block after successful eval, but do not make S03 run auto-trigger evaluation.
- Q3 threat surface: validate local path inputs, missing files, malformed CSVs, invalid health labels, insufficient overlap, and unexpected output overwrite behavior.
- Q4 requirement impact: protect R003 by testing that eval reads the fixed project CSV columns and preserves health labels in coverage/series.
- Q5/Q7 negative tests: cover missing ground truth, all invalid estimates, and insufficient timestamp overlap.

Done when: CLI integration tests build a synthetic S03-style run directory, run eval, assert every required artifact exists with content-level checks, validate `metrics.json` policy/coverage/metric fields, validate CSV headers, validate PNG/SVG outputs, and assert failure cases exit nonzero while writing diagnostics.

## Inputs

- `src/nav_benchmark/run.py`
- `src/nav_benchmark/evaluation/metrics.py`
- `src/nav_benchmark/evaluation/plots.py`
- `src/nav_benchmark/trajectory/export.py`
- `src/nav_benchmark/trajectory/models.py`
- `tests/cli/test_run_cli_synthetic.py`
- `tests/cli/test_run_manifest_and_notes.py`

## Expected Output

- `src/nav_benchmark/run.py`
- `tests/cli/test_eval_cli_synthetic.py`
- `tests/evaluation/test_eval_artifact_contract_synthetic.py`

## Verification

rtk uv run --only-dev pytest tests/cli/test_eval_cli_synthetic.py tests/evaluation/test_eval_artifact_contract_synthetic.py -q

## Observability Impact

Wires metrics, CSVs, aligned ground truth, plots, status, and failure diagnostics into the run directory so benchmark state is inspectable from artifacts alone.
