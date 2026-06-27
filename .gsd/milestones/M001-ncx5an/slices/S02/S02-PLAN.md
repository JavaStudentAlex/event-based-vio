# S02: Synchronization and Trajectory Export Contract

**Goal:** Define and verify deterministic sync policy and the trajectory export contract so IMU-derived trajectories and ground truth are timestamp-associated without silent drops, and a synthetic trajectory exports valid project CSV plus TUM with explicit metadata and diagnostics.
**Demo:** IMU samples and ground truth are timestamp-associated without silent drops, and a synthetic trajectory exports valid project CSV plus TUM files.

## Must-Haves

- Nearest-neighbor-with-tolerance sync is documented and verified; duplicates and empty-stream edge cases covered by tests.
- export_project_csv writes the exact 15-column schema with health labels preserved and velocities/latency fields emitted; tests assert header and row shapes.
- export_tum writes only valid poses (OK/DEGRADED), returns filtered-row counts; tests assert counts and line format.
- ExportMetadata enumerates timestamp unit (seconds), association policy+tolerance, frames, units, quaternion order (qx,qy,qz,qw), per-health counts, and TUM filtered rows.
- Lint, format, and tests pass under rtk/uv.
- Two docs authored: docs/trajectory/synchronization.md and docs/trajectory/export-contract.md.

## Proof Level

- This slice proves: Contract-level unit + synthetic integration tests; deterministic fixtures only.

## Integration Closure

S03 backends/CLI consume Trajectory + ExportMetadata and call export_project_csv/export_tum; evaluator in S04 relies on TUM validity and CSV schema stability.

## Verification

- Structured SyncDiagnostics and ExportMetadata make association and export behavior auditable in logs/manifests.

## Tasks

- [x] **T01: Locked nearest-neighbor synchronization policy, added validation checks and tests, and documented the synchronization contract.** `est:2h`
  Why: Downstream S03/S04 depend on a stable, explicit timestamp association policy and diagnostics. Do: finalize nearest-neighbor-with-tolerance behavior, ensure diagnostics fields are stable and documented, and add a focused doc describing policy, fields, units, and failure modes. Done when: sync tests pass and docs/trajectory/synchronization.md exists with the policy, tolerance semantics, diagnostics fields, and examples.
  - Files: `src/nav_benchmark/trajectory/sync.py`, `src/nav_benchmark/trajectory/models.py`, `tests/trajectory/test_sync.py`, `docs/trajectory/synchronization.md`
  - Verify: rtk uv run pytest tests/trajectory/test_sync.py -q && test -f docs/trajectory/synchronization.md

- [ ] **T02: CSV + TUM export contract spec; author export contract doc** `est:2h`
  Why: All methods must emit the same CSV schema and interoperable TUM; S03/S05 will consume metadata. Do: verify/export behavior and author an export-contract doc that fixes column order/types, health filtering rules, quaternion order, and time base. Done when: export tests pass and docs/trajectory/export-contract.md exists capturing schema, filtering rules, and metadata fields.
  - Files: `src/nav_benchmark/trajectory/export.py`, `src/nav_benchmark/trajectory/models.py`, `tests/trajectory/test_export.py`, `docs/trajectory/export-contract.md`
  - Verify: rtk uv run pytest tests/trajectory/test_export.py -q && test -f docs/trajectory/export-contract.md

- [ ] **T03: Synthetic end-to-end validator for export contract** `est:2h`
  Why: CI needs a deterministic synthetic proof that exercises project CSV and TUM export end-to-end, including per-health counts and filtered-row stats. Do: add a dedicated synthetic test that builds a small Trajectory with OK/DEGRADED/LOST/INVALID rows, calls both exporters to a temp path, then asserts header/row shapes, health label preservation, TUM filtering, and metadata counts. Done when: new test passes locally.
  - Files: `tests/trajectory/test_export_contract_synthetic.py`, `src/nav_benchmark/trajectory/export.py`, `src/nav_benchmark/trajectory/models.py`
  - Verify: rtk uv run pytest tests/trajectory/test_export_contract_synthetic.py -q

- [ ] **T04: ExportMetadata completeness and invariants pass** `est:1.5h`
  Why: S03/S05 rely on explicit metadata (timestamp unit=seconds, association policy+tolerance, frames, units, quaternion order, per-health counts, TUM filtered rows). Do: ensure ExportMetadata and SyncDiagnostics expose these fields exactly and adjust tests accordingly; keep behavior deterministic and avoid silent drops. Done when: full trajectory test suite passes.
  - Files: `src/nav_benchmark/trajectory/models.py`, `src/nav_benchmark/trajectory/export.py`, `src/nav_benchmark/trajectory/sync.py`, `tests/trajectory/test_export.py`, `tests/trajectory/test_models.py`, `tests/trajectory/test_sync.py`
  - Verify: rtk uv run pytest tests/trajectory -q

- [ ] **T05: Slice gate: lint, format, and test suite** `est:0.5h`
  Why: Enforce deterministic quality gates before S02 is considered done. Do: run ruff lint + format checks and the trajectory test subset to ensure style and behavior stability. Done when: all commands exit 0.
  - Files: `pyproject.toml`, `src/nav_benchmark/trajectory/`, `tests/trajectory/`
  - Verify: rtk uv run --only-dev ruff check . && rtk uv run --only-dev ruff format --check . && rtk uv run pytest tests/trajectory -q

## Files Likely Touched

- src/nav_benchmark/trajectory/sync.py
- src/nav_benchmark/trajectory/models.py
- tests/trajectory/test_sync.py
- docs/trajectory/synchronization.md
- src/nav_benchmark/trajectory/export.py
- tests/trajectory/test_export.py
- docs/trajectory/export-contract.md
- tests/trajectory/test_export_contract_synthetic.py
- tests/trajectory/test_models.py
- pyproject.toml
- src/nav_benchmark/trajectory/
- tests/trajectory/
