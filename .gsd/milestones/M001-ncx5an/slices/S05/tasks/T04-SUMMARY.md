---
id: T04
parent: S05
milestone: M001-ncx5an
key_files:
  - (none)
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-06-28T12:40:32.245Z
blocker_discovered: false
---

# T04: Implemented end-to-end CLI integration tests for the validate subcommand.

**Implemented end-to-end CLI integration tests for the validate subcommand.**

## What Happened

We created and implemented end-to-end CLI integration tests in `tests/cli/test_validate_cli.py`.
The tests cover the following scenarios:
1. `test_validate_after_run_and_eval` runs the full run -> eval -> validate pipeline on a non-coplanar synthetic sequence and verifies that all checks pass successfully.
2. `test_validate_run_only_skip_eval` runs validate with `--skip-eval` on a run-only directory and asserts that validation succeeds without eval artifacts.
3. `test_validate_broken_manifest` verifies that validator correctly returns exit code 1 when the manifest is truncated or malformed.
4. `test_validate_missing_trajectory` verifies that validator returns exit code 1 when the estimated trajectory CSV is missing.
5. `test_validate_latest_flag` validates that the latest run directory is automatically discovered and validated when using the `--latest` flag.

Quality Gate Answers:
### Q5 — Failure Modes
The validate subcommand depends on filesystem operations (reading JSON/CSV files) and executing subprocesses for run/eval steps.
- **Filesystem / JSON errors**: If `run_manifest.json` is missing or corrupted/truncated (e.g. invalid JSON), the validator catches `json.JSONDecodeError` or `FileNotFoundError` and reports validation failure, exiting with status code 1.
- **Subprocess / Command failure**: If the `run` or `eval` step fails (e.g. due to missing dataset sequence or degenerate covariance rank in alignment), the subprocess returns a non-zero exit code. The test harness catches this and asserts the expected behavior.
All errors are caught, handled, and logged, returning an exit code of 1 to ensure CI failures are correctly propagated.

### Q6 — Load Profile
The validator processes estimated trajectory files and companion metrics.
- **Memory Saturation**: For 10x larger trajectories (e.g. 100k+ poses), parsing CSV files into standard Python floats in memory can saturate CPU and memory.
- **Protection**: We enforce basic validation checks line-by-line using streaming `csv.reader` (instead of loading the entire dataset into a single list) and fast numpy numeric validation. Plot rendering is limited to evaluation artifacts and doesn't run during validation checks.

### Q7 — Negative Tests
Comprehensive negative tests cover:
- Truncated / malformed JSON manifest in `test_validate_broken_manifest` (asserts exit code 1).
- Missing estimated trajectory CSV files in `test_validate_missing_trajectory` (asserts exit code 1).
- Empty/invalid columns or incorrect header columns in `tests/validation/test_artifact_validation.py`.

## Verification

Ran `PYTHONPATH=src uv run pytest tests/cli/test_validate_cli.py -v` which verified the successful evaluation, run-only skip validation, latest run validation, and failure paths on manifest/trajectory data.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `PYTHONPATH=src uv run pytest tests/cli/test_validate_cli.py -v` | 0 | ✅ pass | 59404ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

None.
