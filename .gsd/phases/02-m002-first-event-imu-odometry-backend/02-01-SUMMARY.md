---
id: S01
parent: M002
milestone: M002
provides:
  - Updated EventImuBackend with geometrically correct event velocity frame shifting
  - MvsecSequence Calibration loading support into the odometry paths
requires:
  - slice: M001
    provides: MvsecSequence.calibration dataclass interfaces.
affects:
  - S02
  - S03
key_files:
  - src/nav_benchmark/baselines/event_imu.py
  - tests/baselines/test_event_imu_backend.py
key_decisions:
  - Rotation-only extrinsics are read from T_imu_cam; if absent or degenerate, the system safely falls back to identity and records 'identity_fallback' in diagnostics.
patterns_established:
  - Graceful dataset fallback: missing dataset parameters automatically switch to conservative identity transforms while exposing the fallback in structured diagnostics outputs.
observability_surfaces:
  - The EventImuBackend.diagnostics dict now exposes the `extrinsics_source` field (calibration or identity_fallback) and `extrinsics_applied` boolean.
drill_down_paths:
  []
duration: ""
verification_result: passed
completed_at: 2026-07-06T20:25:25.290Z
blocker_discovered: false
---

# S01: Extrinsics-aware Event+IMU Correction

**Modified EventImuBackend to extract and apply calibrated IMU-to-camera rotations from MVSEC, improving geometric correctness.**

## What Happened

We introduced extrinsics-aware correction for the event+IMU odometry pipeline. A new helper, `_extrinsics_rotation_from_calibration`, was added to safely parse the `T_imu_cam` homogeneous matrix from MVSEC calibration files. If the matrix is degenerate or absent, we fall back to an identity rotation and log this decision inside `EventImuBackend.diagnostics` using the `extrinsics_source` field (either `calibration` or `identity_fallback`). 

In the core `_event_world_displacement` function, the camera-frame velocity is now pre-rotated by the inverse of the IMU-to-camera rotation (converting it into the body frame) before the world-body rotation applies. We validated this geometrically correct path with new unit tests asserting that synthetic runs differ identically according to the supplied transformation, while previously written tests function unchanged. Linting is clean and test coverage passes.

## Verification

Ran `uv run pytest tests/baselines/test_event_imu_backend.py -q --tb=short` and observed 22 passed checks in 1.32 seconds. Ran `uv run --only-dev ruff check src/nav_benchmark/baselines/event_imu.py src/nav_benchmark/datasets/mvsec.py` and saw all checks passed.

## Requirements Advanced

- R012 — S01 hardened the event_imu pipeline by removing the simplistic camera=body frame assumption.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

None.

## Known Limitations

Extrinsics application is rotation-only. Translation lever-arm correction (T[:3, 3]) is deferred to later milestones.

## Follow-ups

None.

## Files Created/Modified

- `src/nav_benchmark/baselines/event_imu.py` — Added IMU-to-camera extrinsics reading from Calibration.data and applied inverse rotation in _event_world_displacement; wired into EventImuBackend.run() and updated diagnostics.
- `tests/baselines/test_event_imu_backend.py` — Added synthetic test cases for extrinsics-aware correction, testing 45-degree rotation, identity fallback, and diagnostics reporting.
