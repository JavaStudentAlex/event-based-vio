---
id: T04
parent: S02
milestone: M002
key_files:
  - tests/test_cross_method_schema.py
key_decisions:
  - Kept the shared synthetic fixture local to `tests/test_cross_method_schema.py` until another slice needs reuse.
  - Compared mandatory artifact basenames exactly and CSV headers exactly, while allowing method-specific manifest contents and row counts to differ.
duration: 
verification_result: passed
completed_at: 2026-07-07T12:21:02.222Z
blocker_discovered: false
---

# T04: Added a deterministic cross-method schema test that runs imu_only, event_imu, and image_imu on one synthetic sequence and validates matching canonical run artifacts.

**Added a deterministic cross-method schema test that runs imu_only, event_imu, and image_imu on one synthetic sequence and validates matching canonical run artifacts.**

## What Happened

Created `tests/test_cross_method_schema.py` with an inline synthetic MVSEC-like sequence containing IMU, ground truth, grayscale frames, event frames, and raw events so all three target backends can run without MVSEC downloads. The test executes `ImuOnlyBackend`, `EventImuBackend`, and `ImageImuBackend`, writes each trajectory through the canonical project exporters, creates the required run-directory support files, and then asserts every method emits the same mandatory artifact set, the same 15-column CSV schema in order, at least one data row, only valid health labels, and a passing `validate_run_directory(run_dir, expect_eval=False)` result. The test uses the repository’s actual validation contract filenames (`estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, and required `failure_notes.md`) rather than the abstract shorthand in the slice context because `src/nav_benchmark/validation.py` is the authoritative local validator.

## Verification

Fresh verification was run through `gsd_exec`. The task-specific pytest passed, the slice-level pytest set passed, and Ruff check/format-check passed on the new test file after deterministic import organization.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rtk uv run pytest tests/test_cross_method_schema.py -v` | 0 | ✅ pass | 2014ms |
| 2 | `rtk uv run pytest tests/test_event_processor.py tests/test_imu_processor.py tests/test_estimator.py tests/test_cross_method_schema.py -v` | 0 | ✅ pass | 2115ms |
| 3 | `rtk uv run --only-dev ruff check tests/test_cross_method_schema.py` | 0 | ✅ pass | 311ms |
| 4 | `rtk uv run --only-dev ruff format --check tests/test_cross_method_schema.py` | 0 | ✅ pass | 556ms |

## Deviations

Adapted the artifact filenames and required file set to the repository’s current validator contract: `estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, `failure_notes.md`, `run.log`, and `run_manifest.json`. No backend implementation files were changed because the required behavior was already available through existing backend/export/validation surfaces.

## Known Issues

None.

## Files Created/Modified

- `tests/test_cross_method_schema.py`
