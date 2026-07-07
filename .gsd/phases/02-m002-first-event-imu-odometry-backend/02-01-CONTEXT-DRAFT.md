# S01: Extrinsics-aware Event+IMU Correction — Context (DRAFT)

## Decisions captured so far

1. **Fallback behaviour:** Silent identity fallback — no warning logged. Record `extrinsics_applied: false` in run diagnostics JSON only.
2. **Transform scope:** Rotation-only from `T_imu_cam`. Translation lever-arm deferred beyond S01.
3. **Degenerate extrinsics:** Validate rotation matrix (finite, det ≈ +1). On failure, fall back to identity + diagnostic flag. No abort.
4. **Test strategy:** Synthetic-only. No MVSEC download required. Mock Calibration objects with known rotations.
5. **Existing test compatibility:** Zero changes to existing event_imu tests — they must pass unchanged.
6. **Calibration key:** `T_imu_cam` in `Calibration.data` — 4×4 homogeneous, transforms FROM imu TO camera. Extract `R_imu_cam = T[:3, :3]`, use its inverse to rotate event displacement into body frame.
7. **Helper placement:** Private `_extrinsics_rotation_from_calibration()` in `event_imu.py`. No shared module.
