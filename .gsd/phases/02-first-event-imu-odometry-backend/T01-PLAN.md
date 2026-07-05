---
estimated_steps: 1
estimated_files: 2
skills_used: []
---

# T01: Wire extrinsics rotation into event_imu correction pipeline

Add a helper function `_extrinsics_rotation_from_calibration(calibration: Calibration) -> Rotation | None` that extracts the IMU-to-camera rotation from `calibration.data` when `imu_cam_transform_available` is True. Wire it into `EventImuBackend.run()` so the rotation is resolved once at startup and passed into `_event_world_displacement()`. In that function, apply the inverse extrinsics rotation to convert the camera-frame velocity into the body frame before rotating by the world-body orientation. When calibration is absent or lacks extrinsics, fall back to identity (current behavior). Add `extrinsics_source` to `self.diagnostics` with value `calibration` or `identity_fallback`.\n\nSteps:\n1. Read `src/nav_benchmark/baselines/event_imu.py` and `src/nav_benchmark/datasets/mvsec.py` Calibration class.\n2. Add `_extrinsics_rotation_from_calibration()` near existing calibration helpers.\n3. In `EventImuBackend.run()`, resolve the extrinsics rotation and record it in diagnostics.\n4. Update `_event_world_displacement()` signature to accept an optional `cam_to_body: Rotation` parameter.\n5. Apply `cam_to_body.apply(velocity_cam)` before the `rotation_world_body.apply()` call.\n6. Verify lint passes.

## Inputs

- `src/nav_benchmark/baselines/event_imu.py`
- `src/nav_benchmark/datasets/mvsec.py`
- `src/nav_benchmark/baselines/base.py`

## Expected Output

- `src/nav_benchmark/baselines/event_imu.py`

## Verification

uv run --only-dev ruff check src/nav_benchmark/baselines/event_imu.py
