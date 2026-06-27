---
id: T02
parent: S02
milestone: M001-ncx5an
key_files:
  - docs/trajectory/export-contract.md
key_decisions:
  - Defined export schema columns and health status representation mapping
duration: 
verification_result: passed
completed_at: 2026-06-27T22:22:15.829Z
blocker_discovered: false
---

# T02: Documented the CSV and TUM export contract and verified export diagnostics and formatting constraints.

**Documented the CSV and TUM export contract and verified export diagnostics and formatting constraints.**

## What Happened

Drafted the Trajectory Export Contract document detailing the CSV format, TUM export format, health mapping rules, and diagnostic tracking dataclass properties. Verified that all existing unit tests check edge cases, optional velocities, confidence levels, and different health statuses correctly.

## Failure Modes
The filesystem operations (writing output CSV and TUM formats) are external dependencies. If the destination directory does not exist or has write-permission issues, Python standard exceptions (e.g., FileNotFoundError, PermissionError) will bubble up cleanly to the runner.

## Load Profile
The primary bottleneck under 10x expected load (large trajectories with >100k poses) is disk I/O and standard Python string serialization. The current implementation uses memory-efficient buffered file writes and simple loop operations.

## Negative Tests
Negative cases and boundaries (such as None/empty values in optional columns, invalid orientations, and filtering of LOST/INVALID health values in TUM outputs) are covered by:
- `tests/trajectory/test_export.py:test_fmt_opt_edge_cases`
- `tests/trajectory/test_export.py:test_export_project_csv_edge_cases`
- `tests/trajectory/test_export.py:test_export_tum_health_filter`

## Verification

Executed pytest validation suite against the trajectory export module, confirming format, health checks, and metadata extraction are fully functional.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rtk uv run pytest tests/trajectory/test_export.py -q && test -f docs/trajectory/export-contract.md` | 0 | ✅ pass | 3981ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `docs/trajectory/export-contract.md`
