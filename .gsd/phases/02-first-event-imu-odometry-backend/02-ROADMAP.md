# M002: First Event+IMU Odometry Backend

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

- [ ] **S02: Cross-method Artifact Schema Validation** `risk:medium` `depends:[S01]`
  > After this: After this: a pytest test runs imu_only, event_imu, and image_imu on the same synthetic sequence and asserts they produce structurally identical artifact sets — same CSV columns, same file layout, same validation pass

- [ ] **S03: Synthetic Benchmark Comparison Report** `risk:low` `depends:[S01,S02]`
  > After this: After this: a pytest test runs imu_only, event_imu, and image_imu through the compare pipeline on a deterministic synthetic sequence, produces comparison artifacts (metrics JSON, CSV table, plots), and asserts event_imu ATE is lower than imu_only ATE

## Boundary Map

### S01 → S02\n\nProduces:\n- Updated `EventImuBackend` that consumes `Calibration.data` for IMU-to-camera transform\n- New helper `_extrinsics_rotation_from_calibration(calibration) -> Rotation | None`\n- Existing test contract preserved: all current event_imu tests still pass\n\nConsumes:\n- `MvsecSequence.calibration` (from M001)\n- `EventImuBackend` interface (from M001)\n\n### S02 → S03\n\nProduces:\n- Test fixture that runs imu_only, event_imu, image_imu on a shared synthetic sequence\n- Assertion helpers for structural artifact identity (CSV columns, file list, validation schema)\n- R013 mechanically validated\n\nConsumes:\n- Updated `EventImuBackend` from S01\n- `export_project_csv`, `validate_run_directory` from M001\n\n### S03 (terminal)\n\nProduces:\n- Synthetic benchmark comparison test using `compare_runs`\n- Comparison artifacts: `metrics_comparison.json`, `comparison_table.csv`, trajectory overlay plot\n- R012 formally closed\n\nConsumes:\n- All three backends from S01/S02\n- `compare_runs`, `write_comparison_artifacts` from M001 reporting module
