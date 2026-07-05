---
estimated_steps: 1
estimated_files: 1
skills_used: []
---

# T02: Test extrinsics-aware correction and verify no regressions

Add new tests for the extrinsics-aware event_imu correction path and verify all existing tests still pass.\n\nSteps:\n1. Read existing `tests/baselines/test_event_imu_backend.py` for fixture patterns.\n2. Add a test helper that builds an `MvsecSequence` with a non-trivial IMU-to-camera rotation in `calibration.data` (e.g. 45-degree rotation around Z).\n3. Add test `test_extrinsics_rotation_changes_correction`: run EventImuBackend twice on the same sequence — once with identity extrinsics, once with a 45-degree rotation — and assert positions differ.\n4. Add test `test_extrinsics_fallback_to_identity`: run EventImuBackend on a sequence without `imu_cam_transform_available` and verify diagnostics says `identity_fallback`.\n5. Add test `test_extrinsics_diagnostics_field`: run with calibration extrinsics and verify diagnostics says `calibration`.\n6. Run the full test suite to confirm no regressions.\n\nDone when: all new tests pass, all existing event_imu tests pass, ruff check clean.

## Inputs

- `src/nav_benchmark/baselines/event_imu.py`
- `tests/baselines/test_event_imu_backend.py`
- `src/nav_benchmark/datasets/mvsec.py`

## Expected Output

- `tests/baselines/test_event_imu_backend.py`

## Verification

uv run pytest tests/baselines/test_event_imu_backend.py -q --tb=short
