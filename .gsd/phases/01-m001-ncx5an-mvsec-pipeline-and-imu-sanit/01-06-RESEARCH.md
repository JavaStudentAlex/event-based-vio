# S06 Research: Remediate validation string mismatch and run validation verification

## Summary

S06 is a narrow closure slice for M001. The relevant code already exists in `src/nav_benchmark/validation.py` and `src/nav_benchmark/run.py`; the likely remaining work is to confirm and, if still present, align one strict status/string comparison rather than redesign validation.

Important current finding: I could not reproduce the mismatch on the current checkout with the focused CLI tests or a manual synthetic `run -> eval -> validate` path. Evidence:

- `gsd_exec[032a8b15-445f-40e3-be31-2cbd44eac4ef]`: `rtk uv run --only-dev pytest tests/cli/test_validate_cli.py -q` passed: `5 passed in 12.83s`.
- `gsd_exec[d0013f91-2078-4538-a0bc-31ee0c02f137]`: manual synthetic `run -> eval -> validate` exited 0 and printed `Validation: 11/11 checks passed.`

The planner should treat S06 as a verify-first remediation: first reproduce the reported mismatch from the exact failing command/artifact if available. If it is no longer reproducible, the executable task can be a regression-proofing/closure task that adds the missing full-path assertion or strengthens existing tests around the canonical strings.

## Requirements

- Supports and validates R003: all estimated trajectory files, manifests, error CSVs, and failure notes must be present and content-valid.
- Do not weaken strict validation to make validation pass. The S06 context explicitly prefers one canonical string representation over broad aliases.

## Skills Activated and Relevant Rules

- `api-design`: no HTTP/API surface applies, but its rule about predictable, honest caller semantics maps to the CLI contract: `validate` success must return exit code 0, failure must return nonzero, and messages should identify exact invalid artifacts.
- `decompose-into-slices`: keep this as a thin vertical tracer through producer string -> validation consumer -> CLI proof, not a broad validation rewrite.
- `design-an-interface`: the relevant design choice is narrow. Options are broad aliases, tolerant normalization at validation only, or a single canonical source/string. Recommend the single canonical source/string because S06 scope says strict canonicalization.
- `grill-me`: the unresolved decision branch is the exact mismatched pair. Executor should identify expected-vs-actual before editing; do not guess or broaden matching.
- `observability`: keep the concise validation report and explicit failure messages; do not hide invalid/degraded/lost states or make validation quietly skip checks.
- `write-docs`: no broad docs work needed. If a public string changes, preserve enough message clarity for a fresh reader to know which artifact failed.

No additional skills were installed. Existing available/project-local Python testing/linting guidance is sufficient; no `npx skills find` was needed for this local Python validation task.

## Implementation Landscape

### `src/nav_benchmark/validation.py`

Purpose: artifact validator for run directories.

Observed structure:

- `ValidationResult(check_name, passed, message)` is the common return shape.
- Baseline checks validate:
  - `estimated_trajectory.csv`
  - `estimated_trajectory_tum.txt`
  - `run_manifest.json`
  - `failure_notes.md`
  - `run.log`
- Evaluation checks validate:
  - `metrics.json`
  - `error_vs_time.csv`
  - `error_vs_distance.csv`
  - `trajectory_plot.png`
  - `drift_over_distance.png`
- Cross-consistency validates health counts and companion artifact consistency.
- `validate_run_directory(run_dir, expect_eval=True)` appends evaluation checks unless `--skip-eval` is used, then returns `(results, all_passed)`.
- `format_validation_report(results)` currently emits one `[PASS]` or `[FAIL]` line per check plus a summary like `Validation: 11/11 checks passed.`

Known validation strictness to preserve:

- `check_trajectory_csv` only accepts health values `OK`, `DEGRADED`, `LOST`, `INVALID`, or blank.
- `check_run_manifest` requires top-level manifest keys including `status`, `alignment`, and `health_counts`, and requires health count keys for all four health states.
- `check_metrics_json` requires core evaluation keys. It does not appear to be a broad compatibility layer.

Natural seam: any canonicalization helper or constant should live in validation-adjacent or producer-adjacent code, then be imported by both producer and validator only if it avoids circular dependencies. Avoid a large new schema module unless the mismatch touches multiple files.

### `src/nav_benchmark/run.py`

Purpose: CLI wiring and artifact production.

Relevant producer behavior from current synthetic proof:

- `write_run_manifest(...)` writes `run_manifest.json` with `status: "success"`.
- The manifest alignment object is currently `{"policy": "nearest_neighbor", "tolerance_sec": None}` from run metadata.
- `eval` writes `metrics.json` using evaluation output. In the manual proof, `metrics.status` was `"OK"` while `run_manifest.status` was `"success"`.
- Failed evaluation artifact writer uses `metrics.status: "failed"`.
- CLI `validate` successfully returns 0 for a complete run and nonzero for expected failures in tests.

The likely string mismatch family is therefore status-like, not file path-like: `success` vs `OK` vs `failed`, or possibly alignment policy strings (`nearest_neighbor` in manifest vs `se3` evaluation alignment). The manual current path accepts these as separate-domain strings, so do not force them to be equal unless a failing test/artifact proves that is the mismatch.

### `src/nav_benchmark/evaluation/metrics.py`

Purpose: evaluation configuration and metric/artifact data.

Relevant strings:

- `EvalConfig.alignment_policy` defaults to `"se3"` and supports at least `"se3"` and `"none"`.
- Evaluation result status observed in produced `metrics.json`: `"OK"`.
- The evaluation config in `metrics.json` includes `alignment_policy: "se3"`, `outlier_rejection: "none"`, `time_offset_search: false`, etc.

This is distinct from manifest timestamp association policy (`nearest_neighbor`). Do not collapse those two meanings.

### Tests

- `tests/cli/test_validate_cli.py` already covers synthetic run/eval/validate and broken artifacts. Current focused run passes.
- `tests/validation/test_artifact_validation.py` covers unit-level validation checks, including manifest keys, failure notes, metrics keys, CSV headers, plot size, and cross-consistency health counts.

Potential missing regression: a targeted assertion for canonical status/alignment strings in produced `run_manifest.json` and `metrics.json`, plus validation success on the same run without `--skip-eval` if that exact path was historically failing.

## Recommendation

1. **First proof before edits:** run the current failing command or focused full-path validation. Use the existing synthetic CLI flow, not real MVSEC.
2. **If mismatch reproduces:** fix the producer to emit the canonical string, or update the validator to expect the producer's canonical string. Do not add broad aliases.
3. **If mismatch does not reproduce:** add/adjust a narrow regression test that locks the current canonical values and full validation success, then run verification. The slice can close as validation proof rather than source remediation.

Recommended canonical-domain separation if status strings are involved:

- `run_manifest.status`: run lifecycle status, currently `"success"`.
- `metrics.status`: evaluation health/status, currently `"OK"` for successful evaluation and `"failed"` for failed artifact stubs.
- trajectory row `health`: pose health, one of `OK`, `DEGRADED`, `LOST`, `INVALID`.

These should not be compared as if they were the same enum unless the schema is intentionally changed.

## Natural Seams for Planner

1. **Reproduction and contract discovery task**
   - Files: no source edits initially.
   - Commands: focused CLI test and/or manual synthetic `run -> eval -> validate`.
   - Output: exact expected vs actual mismatch pair, or proof that it is not reproducible.

2. **Narrow remediation task, only if mismatch reproduces**
   - Likely files: `src/nav_benchmark/run.py`, `src/nav_benchmark/validation.py`, possibly `src/nav_benchmark/evaluation/metrics.py` if evaluation status is the producer.
   - Rule: one canonical string; no fuzzy alias table unless there is a documented legacy artifact requirement, which S06 explicitly excludes.

3. **Regression coverage task**
   - Likely files: `tests/cli/test_validate_cli.py`, `tests/validation/test_artifact_validation.py`.
   - Add the smallest test that would have failed on the mismatch. Prefer full synthetic CLI proof if the bug was user-visible in `validate`; add a unit test only if the string comparison is isolated.

4. **Verification task**
   - Focused: `rtk uv run --only-dev pytest tests/cli/test_validate_cli.py tests/validation/test_artifact_validation.py -q`
   - Broader before completion: `rtk uv run --only-dev ruff check .`, `rtk uv run --only-dev ruff format --check .`, `rtk uv run pytest tests -q` if time allows.

## First Proof

Highest-value first command:

```bash
rtk uv run --only-dev pytest tests/cli/test_validate_cli.py -q
```

Already passed in research on the current checkout.

For an end-to-end proof equivalent to normal usage, create a tiny synthetic input under `.gsd/tmp/...`, run:

```bash
PYTHONPATH=src rtk uv run --only-dev python -m nav_benchmark.run run --method imu_only --dataset synthetic --sequence s06_research --input <synthetic_input> --output-root <runs>
PYTHONPATH=src rtk uv run --only-dev python -m nav_benchmark.run eval --run-dir <run_dir>
PYTHONPATH=src rtk uv run --only-dev python -m nav_benchmark.run validate --run-dir <run_dir>
```

Research proof `gsd_exec[d0013f91-2078-4538-a0bc-31ee0c02f137]` passed and produced:

- `Validation: 11/11 checks passed.`
- `run_manifest.status = "success"`
- `run_manifest.alignment.policy = "nearest_neighbor"`
- `metrics.status = "OK"`
- `metrics.config.alignment_policy = "se3"`

## Risks and Constraints

- Do not confuse three different string domains: manifest lifecycle status, evaluation result status, and per-pose health.
- Do not confuse timestamp association policy (`nearest_neighbor`) with spatial alignment policy (`se3`). Both appear in artifacts and both are valid in their own domain.
- S06 is not a validation UX redesign. Keep the concise report unless a test explicitly requires quieter output.
- Invalid/degraded/lost intervals must remain visible in artifacts and health counts; validation must not filter them out to pass.
- Current state may already contain the intended fix. Planner should avoid assigning unnecessary source edits if the mismatch cannot be reproduced.

## Verification

Minimum focused checks for executor after any change:

```bash
rtk uv run --only-dev pytest tests/cli/test_validate_cli.py tests/validation/test_artifact_validation.py -q
```

Recommended final checks for M001 closure:

```bash
rtk uv run --only-dev ruff check .
rtk uv run --only-dev ruff format --check .
rtk uv run pytest tests -q
```

If no source changes are made because the mismatch is already resolved, still save the validation proof and close S06 with the focused and full-path validation evidence.
