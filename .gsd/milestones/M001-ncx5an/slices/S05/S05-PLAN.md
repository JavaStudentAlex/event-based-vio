# S05: Manifest Failure Artifacts and CI Smoke Coverage

**Goal:** Finalize the M001 operational artifact contract by implementing a reusable run-directory validation module, wiring a `validate` CLI subcommand, and adding deterministic synthetic CI smoke tests that verify artifact content validity and cross-artifact consistency — not just file presence.
**Demo:** The benchmark run always writes `run_manifest.json`, `failure_notes.md`, logs, and CI-friendly tests validate artifact contents rather than file presence alone.

## Must-Haves

- 1. `src/nav_benchmark/validation.py` exists and provides reusable check functions for all run-directory artifacts (trajectory CSV schema, TUM filtering, manifest required keys, failure_notes structure, metrics.json schema, error CSV schemas, plot file validity, and cross-artifact consistency).\n2. `python -m nav_benchmark.run validate --run-dir <dir>` exits 0 for a valid run directory and non-zero for broken artifacts, printing a concise pass/fail table.\n3. `python -m nav_benchmark.run validate --latest` discovers and validates the most recent run directory.\n4. New tests in `tests/cli/test_validate_cli.py` verify the validate subcommand against synthetic run+eval output and intentionally broken artifacts.\n5. New tests in `tests/validation/test_artifact_validation.py` unit-test individual validation check functions against synthetic fixtures.\n6. All existing tests continue to pass: `PYTHONPATH=src uv run --only-dev pytest tests -q`.\n7. Ruff lint and format checks pass: `uv run --only-dev ruff check .` and `uv run --only-dev ruff format --check .`.

## Proof Level

- This slice proves: CI-synthetic: all validation logic is covered by deterministic synthetic tests that do not require MVSEC downloads.

## Integration Closure

S05 consumes S03 CLI/backend path (run directory layout, manifest, failure notes) and S04 evaluator outputs (metrics.json, error CSVs, plots, aligned ground truth). The validation module codifies the complete artifact contract as executable checks, providing downstream milestones a reusable validation entry point.

## Verification

- Adds `validate` CLI subcommand output (pass/fail table to stdout) and structured validation check results. No new log files or persistent artifacts beyond console output and exit code.

## Tasks

- [x] **T01: Implemented run-directory validation module and test suite** `est:medium`
  **Why:** The S05 contract requires reusable validation checks that verify artifact content and cross-artifact consistency, not just file presence. This module is the core deliverable that the validate CLI subcommand and CI tests will consume.
  - Files: `src/nav_benchmark/validation.py`
  - Verify: PYTHONPATH=src uv run python -c "from nav_benchmark.validation import validate_run_directory, check_trajectory_csv, check_run_manifest, check_failure_notes, check_metrics_json, check_cross_consistency; print('All validation functions importable')"

- [x] **T02: Wired the validate CLI subcommand into run.py and implemented test coverage** `est:small`
  **Why:** The S05 contract requires `python -m nav_benchmark.run validate --run-dir <dir>` and `--latest` to invoke the validation module and print a pass/fail table with a nonzero exit code on failure.
  - Files: `src/nav_benchmark/run.py`
  - Verify: PYTHONPATH=src uv run python -m nav_benchmark.run validate --help

- [x] **T03: Added comprehensive unit tests for all run-directory validation checks and cross-consistency validation.** `est:medium`
  **Why:** Each validation check function in `validation.py` needs targeted unit tests with both valid and intentionally broken fixtures to prove correctness before integration testing.
  - Files: `tests/validation/test_artifact_validation.py`
  - Verify: PYTHONPATH=src uv run --only-dev pytest tests/validation/test_artifact_validation.py -v

- [x] **T04: Implemented end-to-end CLI integration tests for the validate subcommand.** `est:medium`
  **Why:** The validate subcommand must work end-to-end: run synthetic → eval → validate, confirming the full pipeline produces valid artifacts. Also need to verify validate catches intentionally broken artifacts.
  - Files: `tests/cli/test_validate_cli.py`
  - Verify: PYTHONPATH=src uv run --only-dev pytest tests/cli/test_validate_cli.py -v

- [ ] **T05: Full regression suite and lint verification** `est:small`
  **Why:** S05 must not break any existing tests. The final task verifies the complete test suite, lint, and format checks pass together.
  - Files: `src/nav_benchmark/validation.py`, `src/nav_benchmark/run.py`, `tests/validation/test_artifact_validation.py`, `tests/cli/test_validate_cli.py`
  - Verify: uv run --only-dev ruff check . && uv run --only-dev ruff format --check . && PYTHONPATH=src uv run --only-dev pytest tests -q

## Files Likely Touched

- src/nav_benchmark/validation.py
- src/nav_benchmark/run.py
- tests/validation/test_artifact_validation.py
- tests/cli/test_validate_cli.py
