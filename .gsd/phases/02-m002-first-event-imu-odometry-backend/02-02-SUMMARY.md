---
id: S02
parent: M002
milestone: M002
provides:
  - Cross-method validation test
  - Confidence that downstream pipelines can consume artifacts from any of the three backends uniformly
requires:
  - slice: S01
    provides: Calibrated event_imu backend
affects:
  - S03
key_files:
  - tests/test_cross_method_schema.py
key_decisions:
  - Kept the shared synthetic fixture local to tests/test_cross_method_schema.py until another slice needs reuse.
  - Compared mandatory artifact basenames exactly and CSV headers exactly, while allowing method-specific manifest contents and row counts to differ.
patterns_established:
  - (none)
observability_surfaces:
  - none
drill_down_paths:
  - T04-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-07-07T12:21:57.757Z
blocker_discovered: false
---

# S02: Cross-method Artifact Schema Validation

**Added a deterministic cross-method artifact schema validation test ensuring all backends produce structurally identical canonical run artifacts.**

## What Happened

Implemented a deterministic cross-method artifact schema validation test in `tests/test_cross_method_schema.py`. The test creates a shared minimal synthetic sequence with IMU, event, and image data, runs `imu_only`, `event_imu`, and `image_imu` backends on it, and verifies that they produce structurally identical artifact sets. It specifically asserts that all three output a `trajectory.csv`, `tum.txt`, `run_manifest.json`, and `run.log`, that their CSV column names and orders match the canonical 15-column schema, and that all three pass `validate_run_directory`. The test also verifies that quaternion order is `qx,qy,qz,qw` and health labels are within the allowed set. The shared fixture was kept local to the test file for now.

## Verification

Ran `rtk uv run pytest tests/test_cross_method_schema.py -v` successfully, which executed the new test confirming that `imu_only`, `event_imu`, and `image_imu` emit matching run artifact schemas.

## Requirements Advanced

None.

## Requirements Validated

- R013 — The test `tests/test_cross_method_schema.py` programmatically runs all three methods and asserts that their output files and CSV schemas match exactly.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

None.

## Known Limitations

None.

## Follow-ups

None.

## Files Created/Modified

- `tests/test_cross_method_schema.py` — Single cross-method structural validation test file exercising all three backends on one shared synthetic fixture
