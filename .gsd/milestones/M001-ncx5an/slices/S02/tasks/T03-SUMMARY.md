---
id: T03
parent: S02
milestone: M001-ncx5an
key_files:
  - (none)
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-06-27T22:25:45.613Z
blocker_discovered: false
---

# T03: Added synthetic end-to-end validator test suite for trajectory CSV and TUM export formats.

**Added synthetic end-to-end validator test suite for trajectory CSV and TUM export formats.**

## What Happened

Added a comprehensive synthetic end-to-end test suite (`tests/trajectory/test_export_contract_synthetic.py`) to verify the correctness of the trajectory export contract. The tests generate a synthetic `Trajectory` containing rows for all four pose health states (`OK`, `DEGRADED`, `LOST`, `INVALID`). It validates that `export_project_csv` correctly outputs the header, formats values, preserves custom health labels, and aggregates diagnostics (such as `health_counts`) inside `ExportMetadata`. It also verifies that `export_tum` correctly filters out `LOST` and `INVALID` rows, outputs the correct filtered row count, and stores `tum_filtered_rows` in the metadata. Finally, it tests empty trajectory handling to ensure graceful behavior.

### Q5 — Failure Modes
The primary external dependency is the filesystem. If writing to the destination path fails (e.g. permission denied, disk full, missing parent directory), the underlying Python file operations will raise standard `OSError` exceptions. These bubble up directly to the caller, preventing silent failures and ensuring the pipeline stops and alerts the user.

### Q6 — Load Profile
For a trajectory with 10x typical pose count (e.g., 500k poses), the first resource to saturate would be memory if full lists were buffered, and disk I/O. The implementation mitigates this by writing lines incrementally to a buffered file object in a single pass, keeping memory consumption bound by the `Trajectory` object size.

### Q7 — Negative Tests
Negative scenarios and boundary conditions are covered:
- Empty trajectory handling (`test_export_empty_trajectory` in `tests/trajectory/test_export_contract_synthetic.py`).
- Trajectories with only filtered-out health states (`test_export_tum_health_filter` in `tests/trajectory/test_export.py`).
- Missing or optional values formatting logic (`test_fmt_opt_edge_cases` and `test_export_project_csv_edge_cases` in `tests/trajectory/test_export.py`).

## Verification

Ran the synthetic end-to-end validator test suite via pytest, formatting code and checking format/lint compliance.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rtk uv run pytest tests/trajectory/test_export_contract_synthetic.py -q` | 0 | ✅ pass | 1090ms |
| 2 | `rtk uv run --only-dev ruff check . && rtk uv run --only-dev ruff format .` | 0 | ✅ pass | 15803ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

None.
