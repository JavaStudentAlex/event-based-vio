---
id: T03
parent: S01
milestone: M001-ncx5an
key_files:
  - examples/inspect_mvsec.py
  - tests/nav_benchmark/datasets/test_mvsec.py
key_decisions:
  - Ensured sys.path dynamically includes the src directory to make the example CLI script executable without PYTHONPATH configuration.
duration: 
verification_result: passed
completed_at: 2026-06-27T19:14:09.825Z
blocker_discovered: false
---

# T03: Added inspect_mvsec.py example CLI, test cases, and verified metadata output structure

**Added inspect_mvsec.py example CLI, test cases, and verified metadata output structure**

## What Happened

Added the example CLI inspect_mvsec.py in the examples directory. The script accepts a path to an HDF5 file, loads it using load_mvsec_sequence, and prints sample counts, time ranges, and detailed diagnostics/calibration availability metadata. Added E402 noqa rules and formatted imports properly so ruff check succeeds. Added two new tests to tests/nav_benchmark/datasets/test_mvsec.py: test_inspect_mvsec_cli_success (which mocks argv to inspect a synthetic file and asserts output structure) and test_inspect_mvsec_cli_missing_file (which asserts graceful exit on non-existent file path). Checked the entire suite and verified that code style and format checks are fully passing.

## Verification

Ran the pytest suite containing the two new CLI tests, and verified that both ruff check and ruff format are clean.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run pytest` | 0 | ✅ pass | 2314ms |
| 2 | `uv run ruff check . && uv run ruff format --check .` | 0 | ✅ pass | 915ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `examples/inspect_mvsec.py`
- `tests/nav_benchmark/datasets/test_mvsec.py`
