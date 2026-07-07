---
id: S01
milestone: M002
status: ready
---

# S01: Extrinsics-aware Event+IMU Correction — Context

<!-- Slice-scoped context. Milestone-only sections (acceptance criteria, completion class,
     milestone sequence) do not belong here — those live in the milestone context. -->

## Goal

EventImuBackend uses the calibrated IMU-to-camera rotation from MVSEC calibration data to transform event-derived displacements into the body frame, with synthetic tests proving the extrinsics path works correctly and all existing tests still passing.

## Why this Slice

The current `_event_world_displacement` assumes camera frame equals body frame — a simplification documented in the module docstring. MVSEC provides IMU-to-camera extrinsics in calibration data; using them makes the event-to-body-frame conversion geometrically correct. This is the highest-risk slice in M002 because it changes the core math path. S02 (cross-method schema validation) and S03 (synthetic benchmark comparison) both depend on a correct, extrinsics-aware backend.

## Scope

### In Scope

- Extract the 3×3 rotation from `Calibration.data['T_imu_cam']` (4×4 homogeneous matrix, transforms FROM IMU TO camera frame)
- Validate the extracted rotation: all elements finite, determinant ≈ +1 (tolerance 1e-4)
- Apply the inverse rotation (`R_imu_cam.T`) in `_event_world_displacement` to rotate event-camera-frame velocity into the body/IMU frame before the existing world-body rotation
- Fall back to identity rotation when `imu_cam_transform_available` is `False` or `T_imu_cam` key is absent
- Fall back to identity rotation when the extracted rotation is degenerate, recording the rejection reason in run diagnostics
- Record `extrinsics_applied` (bool) and `extrinsics_source` (string) in run diagnostics
- Add new synthetic tests: extrinsics rotation applied correctly (known 45° rotation), identity fallback path, degenerate rejection path
- All existing event_imu tests pass unchanged — zero modifications to existing test files

### Out of Scope

- Translation lever-arm correction (the `T[:3, 3]` component of the extrinsics matrix) — deferred beyond S01
- Full SE(3) extrinsics application — rotation only for now
- Shared calibration utilities module — the helper stays private in `event_imu.py`
- Real MVSEC integration tests — all tests are synthetic with mock Calibration objects
- Logging warnings when extrinsics are absent — the fallback is silent; diagnostics-only visibility
- Changes to `Calibration` dataclass or MVSEC loader — consume existing structure as-is
- Health label changes due to missing extrinsics — absence of extrinsics does not taint pose health

## Constraints

- D009: rotation-only extrinsics, fallback to identity when absent
- D010: all validation is synthetic — no MVSEC download required in CI
- Calibration key is `T_imu_cam` in `Calibration.data` — 4×4 homogeneous, row-major, convention: transforms a point FROM IMU frame TO camera frame
- Existing `EventImuConfig` dataclass must not require extrinsics — the config is purely for tuning parameters; extrinsics come from `Calibration`
- Degenerate rotation validation: reject if any element is non-finite or `|det(R) - 1.0| >= 1e-4`; fall back to identity + diagnostic flag `extrinsics_rejected_reason`

## Integration Points

### Consumes

- `MvsecSequence.calibration` — `Calibration` dataclass with `imu_cam_transform_available` flag and `data` dict potentially containing `T_imu_cam` key
- `EventImuBackend` interface and `_event_world_displacement` function — the core math path where the extrinsics rotation is inserted
- `Trajectory`, `PoseHealth`, `EstimatorRunResult` — existing output types unchanged

### Produces

- Updated `_event_world_displacement` that applies `R_imu_cam.inv()` before the world-body rotation when valid extrinsics are available
- New private helper `_extrinsics_rotation_from_calibration(calibration: Calibration) -> Rotation | None` in `event_imu.py`
- Run diagnostics fields: `extrinsics_applied` (bool), `extrinsics_source` (str: `"calibration"` or `"identity_fallback"`), optionally `extrinsics_rejected_reason` (str)
- New synthetic test cases covering: correct rotation application, identity fallback, degenerate rejection
- All existing event_imu tests continue to pass without modification

## Open Questions

- **Rotation application order:** The inverse rotation `R_imu_cam.T` should be applied to the camera-frame velocity *before* the world-body rotation. Verify this matches the MVSEC coordinate convention during implementation — current thinking is `v_body = R_cam_to_imu @ v_cam` then `v_world = R_world_body @ v_body`.
- **`T_imu_cam` shape in real MVSEC data:** The loader may store this as a flat array or a 4×4 matrix. The helper should handle reshaping — current thinking is `np.asarray(data).reshape(4, 4)` with a shape guard.
