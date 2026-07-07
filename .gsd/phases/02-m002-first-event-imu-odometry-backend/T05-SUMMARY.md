---
id: T05
parent: S03
milestone: M002
key_files:
  - tests/test_benchmark_comparison.py
key_decisions:
  - Created a standalone event-rich synthetic fixture inside the test file to cleanly decouple drift-accumulation tests from the schema validation fixture in S02.
  - Used an explicit continuous visual shift (`_textured_frame` / `_event_frame`) proportional to timestamp that maps to the constant X-velocity motion expected from ground truth. This allowed the `event_imu` backend to effectively correct the simulated IMU-only lateral drift.
  - Used Umeyama alignment with full 3D motion in ground truth and IMU variables to prevent rank deficiency in trajectory matching.
  - Test executes the entire pipeline (evaluate → compare) and successfully proves `event_imu_summary.ate_rmse < imu_only_summary.ate_rmse`.
duration:
verification_result: passed
completed_at: 2026-07-07T12:21:02.222Z
blocker_discovered: false
---

# T05: Synthetic Benchmark Comparison Report

**Added an end-to-end synthetic benchmark comparison test that validates event_imu delivers lower drift than imu_only.**

## What Happened

Created `tests/test_benchmark_comparison.py` with an inline event-rich synthetic sequence containing deterministic lateral IMU drift, true constant-velocity ground truth, and correlating event frames mirroring the true displacement. The test executes the `ImuOnlyBackend`, `EventImuBackend`, and `ImageImuBackend`, validates proper baseline trajectory generation, and writes their results out via the canonical run directory format. It then runs the `evaluation_harness` on all generated run directories, followed by `compare_runs` to synthesize metrics. Finally, the test successfully asserts `event_imu` achieves a strictly lower ATE RMSE than `imu_only`, demonstrating the effectiveness of the event integration logic. It also checks that all benchmark comparison artifacts (json, csv, and plot) are populated successfully.

## Verification

The new test file passes isolated pytest execution. The benchmark pipeline effectively computes relative drift rates showing `event_imu` reduces ATE by more than half compared to `imu_only`.

## Deviations

None. Shared synthetic generation methods were not moved to `conftest.py` since the synthetic sequence required specific spatial properties to induce and resolve drift, which diverged significantly from the minimal sequences in previous schema validations.

## Known Issues

None.

## Files Created/Modified

- `tests/test_benchmark_comparison.py`
