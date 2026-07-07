---
id: S03
milestone: M002
status: ready
---

# S03: Synthetic Benchmark Comparison Report — Context

<!-- Slice-scoped context. Milestone-only sections (acceptance criteria, completion class,
     milestone sequence) do not belong here — those live in the milestone context. -->

## Goal

A pytest test runs imu_only, event_imu, and image_imu through the full pipeline (backend → export → evaluate → compare) on a deterministic event-rich synthetic sequence, produces comparison artifacts, and asserts event_imu ATE is strictly lower than imu_only ATE.

## Why this Slice

S01 hardened event_imu with calibrated extrinsics and S02 proved all three backends emit structurally identical artifact sets. S03 closes the milestone by proving the extrinsics-corrected event_imu actually delivers better drift performance than pure IMU integration on a controlled synthetic sequence. This formally validates R012 (event_imu improves drift over imu_only) and completes M002.

## Scope

### In Scope

- A single new test file (e.g., `tests/test_benchmark_comparison.py`) exercising the full pipeline for all three backends.
- A purpose-built synthetic fixture with an event-rich motion pattern that gives event_imu a clear, deterministic ATE advantage over imu_only. Longer than S02's minimal fixture (enough timestamps for IMU drift to accumulate meaningfully).
- Full end-to-end pipeline in the test: `backend.run()` → `export_project_csv` / `export_tum` → evaluation harness → `compare_runs` → `write_comparison_artifacts`.
- Core assertion: `event_imu.ate_rmse < imu_only.ate_rmse` (strict less-than, no percentage margin). The synthetic sequence is designed so the gap is large and unambiguous.
- image_imu is included in the comparison pipeline for completeness (appears in comparison table and plots) but no ATE ranking assertion is made about it. Only assert it runs successfully (`ate_rmse is not None`).
- Comparison artifact existence checks: `metrics_comparison.json`, `comparison_table.csv`, and at least one plot file (`.png`) must exist and be non-empty. No deep schema validation of their contents.
- Failure handling: if any backend raises an exception, let pytest's normal exception propagation handle it. No special try/except wrapping or structured failure reports.

### Out of Scope

- CLI changes or new subcommands — S03 is purely a pytest test calling Python APIs directly.
- Scripts or notebooks for manual comparison reproduction.
- Deep schema validation of comparison artifacts (column names, JSON structure) — comparison module internals are already tested in M001.
- ATE assertions involving image_imu (no ranking claim for image_imu vs imu_only or vs event_imu).
- Percentage-margin or statistical significance assertions on the ATE gap.
- Any changes to existing backend implementations, evaluation harness, or comparison module.
- MVSEC data download — everything runs on synthetic data in CI.

## Constraints

- The synthetic fixture must be deterministic and self-contained (no external data, no randomness).
- The event-rich motion pattern must produce a large enough ATE gap that floating-point noise cannot flip the `<` assertion.
- IMU noise in the fixture should be realistic (gyro bias, accelerometer noise) so imu_only drifts naturally.
- Events should encode clean displacement signal (e.g., lateral motion cues) that event_imu can exploit.
- Must respect the evaluation policy from D006: global SE(3) alignment, nearest-neighbor timestamp association, no outlier rejection, no robust trimming.
- The S03 fixture is separate from S02's minimal fixture — different design goals (drift proof vs schema validation).
- Common fixture-building helpers (make_imu, make_events, etc.) may be shared via conftest.py, but assembled sequences are distinct.
- All existing tests must continue to pass.

## Integration Points

### Consumes

- `src/nav_benchmark/baselines/imu.py` — `ImuOnlyBackend` (from M001)
- `src/nav_benchmark/baselines/event_imu.py` — `EventImuBackend` with extrinsics support (from M002/S01)
- `src/nav_benchmark/baselines/image_imu.py` — `ImageImuBackend` (from M001)
- `src/nav_benchmark/trajectory/export.py` — `export_project_csv`, `export_tum` (from M001)
- `src/nav_benchmark/evaluation/harness.py` — evaluation harness that writes metrics.json, error CSVs, plots (from M001/S04)
- `src/nav_benchmark/reporting/compare.py` — `compare_runs`, `write_comparison_artifacts` (from M001)
- `src/nav_benchmark/validation.py` — `validate_run_directory` (from M001, used by evaluation harness)
- D006 alignment policy: global SE(3) alignment, nearest-neighbor association, no outlier rejection

### Produces

- `tests/test_benchmark_comparison.py` — end-to-end synthetic benchmark comparison test
- Purpose-built event-rich synthetic fixture (in the test file or conftest.py)
- R012 formally validated: event_imu ATE < imu_only ATE on deterministic synthetic sequence
- Comparison artifacts produced during test: `metrics_comparison.json`, `comparison_table.csv`, trajectory overlay plot, drift comparison plot

## Open Questions

- **Fixture timestamp count:** Exact number of timestamps for the event-rich fixture TBD during implementation. Needs to be long enough for meaningful IMU drift accumulation but short enough for fast test execution (<1s). Current thinking: 30–100 timestamps.
- **Shared helpers extraction:** Whether to extract common fixture-building helpers (make_imu, make_events, make_frames) into a shared conftest.py depends on how much overlap exists with S02's fixture code. Current thinking: extract if there's meaningful duplication, otherwise keep inline.
