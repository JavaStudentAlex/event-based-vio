---
id: S02
milestone: M002
status: ready
---

# S02: Cross-method Artifact Schema Validation — Context

<!-- Slice-scoped context. Milestone-only sections (acceptance criteria, completion class,
     milestone sequence) do not belong here — those live in the milestone context. -->

## Goal

A pytest test runs imu_only, event_imu, and image_imu on the same synthetic sequence and asserts they produce structurally identical run-phase artifact sets — same mandatory files present, same CSV columns in name and order, and all three pass `validate_run_directory`.

## Why this Slice

S01 hardened event_imu with calibrated extrinsics; S02 now proves that all three backends emit artifacts in a uniform shape that downstream consumers (the S03 comparison pipeline, the evaluator, CI checks) can rely on without method-specific branching. Until this is mechanically validated, R013 (cross-method comparability) remains unproven and S03 cannot safely compare outputs. Ordering after S01 ensures the updated event_imu backend is the one being validated.

## Scope

### In Scope

- Single new test file `tests/test_cross_method_schema.py` that exercises all three backends on one shared synthetic fixture.
- Structural assertions on the **mandatory run-phase artifact set**: `trajectory.csv`, `tum.txt`, `run_manifest.json`, `run.log`.
- CSV column identity: `trajectory.csv` columns must match in name and order across all three methods, matching the 15-column project schema.
- Non-emptiness: each `trajectory.csv` must have ≥1 data row; row counts are allowed to differ across methods.
- Health label validation: the `health` column in each method's CSV must contain only values from the allowed set `{OK, DEGRADED, LOST, INVALID}`. No cross-method comparison of which labels appear.
- Re-use of existing `validate_run_directory(run_dir, expect_eval=False)` on each method's output directory; all three must pass.
- Method-specific diagnostics fields inside `run_manifest.json` are allowed to differ (e.g., `extrinsics_source` in event_imu).
- Optional/extra files produced by only some backends (e.g., `failure_notes.md`, diagnostic plots) are ignored by the structural comparison.

### Out of Scope

- Evaluation artifacts (metrics.json, error CSVs, plots) — deferred to S03.
- Row-count equality or timestamp alignment across methods.
- Semantic correctness of trajectory values (that's backend unit tests and S03).
- Deep manifest schema comparison (top-level or nested key identity across methods).
- Evaluator-readiness smoke testing.
- Any changes to backend implementations — S02 is purely observational/validation.

## Constraints

- The synthetic fixture must be minimal (5–10 timestamps) with IMU, event, and grayscale data so all three backends can consume it without modification.
- Must run deterministically in CI without MVSEC data download.
- Must respect the 15-column CSV schema from D001: `timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms`.
- Quaternion order is `qx,qy,qz,qw` (D001).
- Existing backend tests must continue to pass unchanged.

## Integration Points

### Consumes

- `src/nav_benchmark/baselines/imu.py` — `ImuOnlyBackend` (from M001/S03)
- `src/nav_benchmark/baselines/event_imu.py` — `EventImuBackend` with extrinsics support (from M002/S01)
- `src/nav_benchmark/baselines/image_imu.py` — `ImageImuBackend` (from M001)
- `src/nav_benchmark/trajectory/export.py` — `export_project_csv`, `export_tum` (from M001/S02)
- `src/nav_benchmark/validation.py` — `validate_run_directory` (from M001)
- Existing synthetic sequence/fixture patterns from `tests/` (to extend or model the shared fixture)

### Produces

- `tests/test_cross_method_schema.py` — single cross-method structural validation test file
- Shared synthetic fixture (likely a `@pytest.fixture` in the same file or in `conftest.py`) producing a sequence consumable by all three backends
- Assertion helpers for file-set presence, CSV column identity, and health label validation (may be inline or factored into helpers)
- R013 mechanically validated upon all assertions passing

## Open Questions

- **Fixture placement:** Whether the shared synthetic fixture lives inside `test_cross_method_schema.py` or in a shared `conftest.py` depends on whether other tests in M002/S03 will reuse it. Current thinking: start in the test file, extract to conftest if S03 needs it.
- **run_manifest.json validity:** `validate_run_directory` already checks this file; no additional JSON schema assertion is planned unless validation gaps are found during implementation.
