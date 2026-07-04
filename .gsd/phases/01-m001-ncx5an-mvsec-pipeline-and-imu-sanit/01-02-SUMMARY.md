---
id: S02
parent: M001-ncx5an
milestone: M001-ncx5an
provides:
  - Trajectory data model
  - synchronize_nearest_neighbor function
  - export_project_csv function
  - export_tum function
  - ExportMetadata shape and stats
requires:
  - slice: S01
    provides: MvsecSequence loader structure and timestamps
affects:
  - S03
  - S04
key_files:
  - src/nav_benchmark/trajectory/sync.py
  - src/nav_benchmark/trajectory/export.py
  - src/nav_benchmark/trajectory/models.py
  - docs/trajectory/synchronization.md
  - docs/trajectory/export-contract.md
key_decisions:
  - Strictly enforce monotonicity in trajectory timestamps and non-negative tolerances during nearest-neighbor synchronization
  - Filters out LOST and INVALID pose health labels in the TUM trajectory export format to maintain compatibility with evo
  - Enforced required fields and value consistency assertions in models to prevent partial or invalid trajectory objects
patterns_established:
  - Structured Trajectory dataclasses with numpy assertions
  - Nearest-neighbor matching diagnostics for timestamp validation
observability_surfaces:
  - SyncDiagnostics objects returned by sync operations
  - ExportMetadata counts recorded in exported files and manifests
drill_down_paths:
  - .gsd/milestones/M001-ncx5an/slices/S02/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001-ncx5an/slices/S02/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001-ncx5an/slices/S02/tasks/T03-SUMMARY.md
  - .gsd/milestones/M001-ncx5an/slices/S02/tasks/T04-SUMMARY.md
  - .gsd/milestones/M001-ncx5an/slices/S02/tasks/T05-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-06-27T23:00:46.834Z
blocker_discovered: false
---

# S02: Synchronization and Trajectory Export Contract

**Locked synchronization policy and trajectory export formats with diagnostics, models, and synthetic tests.**

## What Happened

Slice S02 defines and implements the core trajectory data models, synchronization policy, and export contract for the MVSEC VIO benchmark project.

During this slice:
1. We locked the nearest-neighbor-with-tolerance synchronization policy, ensuring strictly monotonic timestamps and non-negative tolerances.
2. We defined and implemented dataclasses for Trajectory, SyncDiagnostics, and ExportMetadata, with complete value constraints and sum consistency validation.
3. We implemented CSV export mapping strictly to the 15-column schema, preserving health information (OK, DEGRADED, LOST, INVALID).
4. We implemented TUM export, filtering out invalid/lost states (LOST, INVALID) to ensure compatibility with standard tools like evo, and returned filtered counts.
5. We verified all functionality using comprehensive unit and synthetic end-to-end integration tests. All quality gates (ruff style, format, and pytest tests) are passing.
6. Detailed documentation was added for both synchronization and export contracts.

## Verification

Executed pytest suite on `tests/trajectory` proving synchronization constraints, nearest neighbor tolerance matching, project CSV columns/health mapping, and TUM export filter mechanics behave exactly as specified. Verified Ruff linting and formatting compliance with 0 errors.

## Requirements Advanced

- R003 — Enforced fixed columns and health labels for relative odometry outputs

## Requirements Validated

- R003 — tests/trajectory/test_export_contract_synthetic.py verifies header, column formatting, health tracking, and TUM filtering

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

None.

## Known Limitations

None.

## Follow-ups

None.

## Files Created/Modified

- `src/nav_benchmark/trajectory/sync.py` — Nearest-neighbor-with-tolerance sync implementation and models
- `src/nav_benchmark/trajectory/export.py` — Trajectory export (CSV and TUM) implementation
- `src/nav_benchmark/trajectory/models.py` — Dataclass models for Trajectory, SyncDiagnostics, and ExportMetadata
- `tests/trajectory/` — Tests for synchronization, models, and export logic
- `docs/trajectory/synchronization.md` — Synchronization contract documentation
- `docs/trajectory/export-contract.md` — Trajectory export contract documentation
