---
id: T03
parent: S04
milestone: M001-ncx5an
key_files:
  - src/nav_benchmark/run.py
  - tests/cli/test_eval_cli_synthetic.py
  - tests/evaluation/test_eval_artifact_contract_synthetic.py
key_decisions:
  - Preserved the existing `error_message` diagnostics field while adding `reason` so current tests and downstream readers remain compatible.
  - Used a non-collinear synthetic trajectory for SE(3) artifact-contract testing because evo Umeyama alignment correctly rejects degenerate collinear covariance.
duration: 
verification_result: passed
completed_at: 2026-06-28T07:17:53.612Z
blocker_discovered: false
---

# T03: Added and verified eval CLI artifact writing with deterministic diagnostics and expanded synthetic failure coverage.

**Added and verified eval CLI artifact writing with deterministic diagnostics and expanded synthetic failure coverage.**

## What Happened

Extended the `nav_benchmark.run eval` path so failed evaluations persist a `reason` field alongside `error_message` in `metrics.json`, preserving the existing diagnostic shape while satisfying the explicit task requirement for `status=failed` plus `reason` and policy fields. The eval CLI path reads `estimated_trajectory.csv`, resolves ground truth from `--ground-truth` or `run_manifest.json`, runs the evaluation core, writes `metrics.json`, `ground_truth_aligned.csv`, `error_vs_time.csv`, `error_vs_distance.csv`, trajectory/drift PNG and SVG plots, and updates `run_manifest.json` evaluation status when present.

The artifact-contract synthetic test was corrected to use a non-collinear 3D trajectory so SE(3) alignment is well-conditioned under evo/Umeyama. This keeps the test focused on artifact schemas, health preservation, and JSON serializability rather than failing on a degenerate fixture. The CLI failure test now also covers the all-invalid-estimate case and asserts nonzero exit plus diagnostic `metrics.json` output with a stable `reason`.

## Failure Modes

External dependencies are local filesystem reads/writes, local subprocess CLI invocation in tests, CSV/HDF5 ground-truth loading, JSON manifest parsing/updating, evo SE(3)/RPE math, and matplotlib plot generation. Missing run directories, missing `estimated_trajectory.csv`, missing ground-truth paths, malformed or invalid trajectory CSVs, insufficient OK/DEGRADED poses, insufficient timestamp overlap, degenerate alignment, and plot/write errors all either produce nonzero CLI exits with persisted failure diagnostics or bubble through as task-visible test failures. Failure diagnostics write `metrics.json`, `ground_truth_aligned.csv`, `error_vs_time.csv`, and `error_vs_distance.csv` with headers where safe, so downstream inspection does not depend on stdout/stderr alone.

## Load Profile

The runtime load dimension is trajectory length. The first saturating resources at 10x expected synthetic load are in-memory trajectory arrays and plot generation, because the evaluator currently materializes matched poses, error series, JSON, CSV, and matplotlib figures in one process. Protection is deterministic bounded processing over local files without network calls, no background workers, and explicit nonzero failure paths for malformed inputs; no additional pooling/rate limiting applies to this local CLI task.

## Negative Tests

Negative tests are in `tests/cli/test_eval_cli_synthetic.py::test_eval_cli_failure_cases`: missing `estimated_trajectory.csv`, missing ground truth, insufficient timestamp overlap, and all-invalid estimates. The malformed/invalid CSV health-label path is protected by `read_project_csv`/`Trajectory` validation and covered through the CLI failure plumbing when read/evaluation fails. `tests/evaluation/test_eval_artifact_contract_synthetic.py::test_evaluation_artifact_contracts` protects the fixed project CSV/evaluation artifact contract, including health-label preservation in `error_vs_time.csv`.

## Observability Impact

The eval CLI now leaves inspectable run-directory artifacts for both success and failure: policy/status diagnostics in `metrics.json`, aligned ground-truth CSV, error series CSVs, trajectory and drift plots, and optional `run_manifest.json` evaluation status.

## Verification

Ran the authoritative task verification for the eval CLI and artifact-contract synthetic tests, then ran a broader compatibility check including the existing run CLI and manifest/failure-notes tests. Both checks passed. The first run before fixture correction failed with evo/Umeyama degenerate covariance; the synthetic artifact-contract fixture was updated to a non-collinear 3D path and the focused tests then passed.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rtk uv run --only-dev pytest tests/cli/test_eval_cli_synthetic.py tests/evaluation/test_eval_artifact_contract_synthetic.py -q` | 0 | ✅ pass | 39997ms |
| 2 | `rtk uv run --only-dev pytest tests/cli/test_eval_cli_synthetic.py tests/evaluation/test_eval_artifact_contract_synthetic.py tests/cli/test_run_cli_synthetic.py tests/cli/test_run_manifest_and_notes.py -q` | 0 | ✅ pass | 47129ms |

## Deviations

Kept the task scope focused on the eval CLI and tests. The artifact-contract fixture was adjusted from a degenerate collinear path to a non-collinear 3D path so the planned SE(3) policy is testable. Failure diagnostics now include both `reason` and the existing `error_message` for backward compatibility.

## Known Issues

None.

## Files Created/Modified

- `src/nav_benchmark/run.py`
- `tests/cli/test_eval_cli_synthetic.py`
- `tests/evaluation/test_eval_artifact_contract_synthetic.py`
