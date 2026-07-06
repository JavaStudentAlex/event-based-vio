# Quick Task: Recheck Current Active Slice (M002/S01) Implementation Status

**Date:** 2026-07-06
**Branch:** main

## Active Slice: M002/S01 — Extrinsics-aware Event+IMU Correction

**Status: NOT IMPLEMENTED — the slice is still `pending` with 0/2 tasks complete.**

## What Was Checked

### 1. Source Code Analysis — `event_imu.py` (455 lines)

The `_event_world_displacement` function (line ~205) currently does:
```
velocity_cam → rotation_world_body.apply(velocity_cam) * dt
```
It does **not** apply any IMU-to-camera extrinsics rotation. The camera frame is assumed to equal the body frame — this is exactly the simplification S01 is supposed to fix.

Confirmed: no references to `extrinsic`, `imu_cam`, `R_body_cam`, or `T_imu_cam` anywhere in `event_imu.py`.

### 2. Data Layer — `mvsec.py` (lines 218-220)

The MVSEC loader **already** loads the extrinsics:
- `calibration.imu_cam_transform_available = True`
- `calibration.data["imu_cam_transform"] = f["/davis/left/imu_cam_transform"][:]`

The data is available; it's just not consumed by the backend yet.

### 3. Test Suite — All Tests Pass

- `tests/baselines/test_event_imu_backend.py`: 15 tests pass
- Full test suite: 327 tests pass, 10 warnings (all deprecation-related)
- No existing test references extrinsics

### 4. S01 Plan vs Code Alignment Check

The S01 plan (`.gsd/phases/02-first-event-imu-odometry-backend/02-01-PLAN.md`) defines two tasks:
- **T01**: Wire extrinsics rotation into event_imu correction pipeline
- **T02**: Test extrinsics-aware correction and verify no regressions

Neither has been started.

## Nuances and Clarifications Identified

### Nuance 1: Calibration Key Name Mismatch in Documentation

| Source | Key name used |
|--------|--------------|
| MVSEC loader (`mvsec.py` line 220) | `calibration.data["imu_cam_transform"]` |
| S01 Plan (must-haves, T01) | `imu_cam_transform` ✅ matches loader |
| S01 Context (scope section) | `Calibration.data['T_imu_cam']` ❌ doesn't match |
| S01 Context-Draft (decision 6) | `T_imu_cam` ❌ doesn't match |

**Impact:** The implementation must use `"imu_cam_transform"` (the actual key in the loader), not `"T_imu_cam"` (the key in the context docs). The plan file is correct; the context/context-draft docs have a stale key name. This should be updated before or during implementation.

### Nuance 2: Transform Convention Clarity

The context says `T_imu_cam` "transforms FROM IMU TO camera." This means:
- `R_imu_cam` rotates vectors from IMU frame to camera frame
- To rotate event-camera-frame velocity into body/IMU frame, we need `R_imu_cam.T` (the inverse/transpose)
- The code path: `v_body = R_cam_to_imu @ v_cam`, then `v_world = R_world_body @ v_body`

This is correctly specified in the context but worth being explicit about during implementation, as getting the inverse wrong would silently produce worse results.

### Nuance 3: Shape Handling for Real MVSEC Data

The context notes the loader "may store this as a flat array or a 4×4 matrix." The helper should do `np.asarray(data).reshape(4, 4)` with a shape guard. Current loader code does `f["/davis/left/imu_cam_transform"][:]` which preserves whatever shape HDF5 gives — typically 4×4 but could be (16,). Tests should cover both shapes.

### Nuance 4: Validation of Extracted Rotation

S01 requires validating `det(R) ≈ +1` (tolerance 1e-4). If validation fails, fall back to identity + diagnostic flag. This edge case needs a test.

### Nuance 5: Diagnostics Fields

The plan requires `extrinsics_source` in `self.diagnostics` (values: `"calibration"` or `"identity_fallback"`). Currently `self.diagnostics` is populated by `_diagnostics_summary()` — the new fields need to be set *before* or *after* that call in `EventImuBackend.run()`.

### Nuance 6: S02/S03 Dependencies Are Not Blocked

S02 (cross-method artifact schema validation) and S03 (synthetic benchmark comparison) both depend on S01. They are correctly marked as pending with 0 tasks planned (sketch slices). S01 must complete first.

### Nuance 7: `image_imu` Backend Does NOT Need Extrinsics in S01

The `image_imu.py` backend (58 lines) uses `fuse_imu_and_visual` from `common.py` — a different code path. S01 scope is explicitly limited to `event_imu.py`. S02 will validate cross-method artifact schema parity.

## Verdict

**S01 is ready for implementation.** The plan, context, and codebase are aligned on what needs to happen. The key nuance to watch is the calibration key name (`"imu_cam_transform"` not `"T_imu_cam"`), and the implementer should ensure the inverse rotation direction is correct. No blocking issues found.

## Files Examined
- `src/nav_benchmark/baselines/event_imu.py`
- `src/nav_benchmark/baselines/image_imu.py`
- `src/nav_benchmark/datasets/mvsec.py`
- `tests/baselines/test_event_imu_backend.py`
- `.gsd/phases/02-first-event-imu-odometry-backend/02-ROADMAP.md`
- `.gsd/phases/02-first-event-imu-odometry-backend/02-01-PLAN.md`
- `.gsd/phases/02-first-event-imu-odometry-backend/02-01-CONTEXT.md`
- `.gsd/phases/02-first-event-imu-odometry-backend/02-01-CONTEXT-DRAFT.md`
- `.gsd/ROADMAP.md`
- `.gsd/REQUIREMENTS.md`

## Verification
- Ran `uv run pytest tests/baselines/test_event_imu_backend.py -q` — 15/15 pass
- Ran `uv run pytest tests/ -q` — 327/327 pass
- Grepped all source files for extrinsics references — confirmed none in event_imu.py
- Cross-referenced calibration key names across plan, context, and source code
