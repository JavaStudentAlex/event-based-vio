# M002: M002: M002: First Event+IMU Odometry Backend

**Vision:** Harden the existing event_imu and image_imu backends with calibrated extrinsics, validate that all methods produce structurally identical artifact sets (R013), and produce a reproducible synthetic benchmark comparison demonstrating event_imu improves drift over imu_only (R012). This milestone closes the loop on event-camera odometry correctness and cross-method comparability.

## Success Criteria

- EventImuBackend uses calibrated IMU-to-camera extrinsics from MVSEC calibration data when available, falling back to identity when not
- event_imu, image_imu, and imu_only all pass the same structural artifact validation: identical CSV columns, identical file set, identical validation result schema
- A reproducible synthetic benchmark comparison shows event_imu ATE lower than imu_only ATE on an event-rich synthetic sequence
- All existing tests continue to pass after extrinsics changes
- R012 and R013 validation status move from unmapped to mapped

## Slices

- [x] **S01: Extrinsics-aware Event+IMU Correction** `risk:high` `depends:[]`
  > After this: After this: EventImuBackend uses calibrated IMU-to-camera rotation from MVSEC calibration data to transform event-derived displacements into the body frame; synthetic tests prove extrinsics path works correctly and existing tests still pass

- [x] **S02: Cross-method Artifact Schema Validation** `risk:medium` `depends:[S01]`
  > After this: After this: a pytest test runs imu_only, event_imu, and image_imu on the same synthetic sequence and asserts they produce structurally identical artifact sets — same CSV columns, same file layout, same validation pass

- [x] **S03: Synthetic Benchmark Comparison Report** `risk:low` `depends:[S01,S02]`
  > After this: After this: a pytest test runs imu_only, event_imu, and image_imu through the compare pipeline on a deterministic synthetic sequence, produces comparison artifacts (metrics JSON, CSV table, plots), and asserts event_imu ATE is lower than imu_only ATE
  > *Implementation note*: T05 added the end-to-end synthetic benchmark comparison test verifying ATE improvements.

## Boundary Map

## Boundary Map
