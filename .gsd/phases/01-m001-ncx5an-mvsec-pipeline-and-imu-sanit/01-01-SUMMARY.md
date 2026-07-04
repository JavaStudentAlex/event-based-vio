---
id: S01
parent: M001-ncx5an
milestone: M001-ncx5an
provides:
  - MvsecSequence data container containing validated monotonic sensor streams
  - LoadDiagnostics and Calibration structures mapping availability of variables
  - A synthetic HDF5 sequence file generator for CI validation
requires:
  []
affects:
  []
key_files:
  - src/nav_benchmark/datasets/mvsec.py
  - docs/datasets/mvsec.md
  - examples/inspect_mvsec.py
  - tests/nav_benchmark/datasets/test_mvsec.py
key_decisions:
  - Configured examples/inspect_mvsec.py to dynamically add src to sys.path so the module imports correctly when executed from any directory.
patterns_established:
  - Dataset loader returning MvsecSequence container along with separate diagnostics dataclass to handle dirty data gracefully
observability_surfaces:
  - load_mvsec_sequence diagnostics mapping missing, present, and malformed flags
  - inspect_mvsec.py printouts of dataset statistics and diagnostics
drill_down_paths:
  - .gsd/milestones/M001-ncx5an/slices/S01/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001-ncx5an/slices/S01/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001-ncx5an/slices/S01/tasks/T03-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-06-27T19:15:32.232Z
blocker_discovered: false
---

# S01: MVSEC Loader and Stream Contract

**Delivered verified MVSEC dataset loader module, diagnostic schema, contract documentation, and metadata inspection CLI.**

## What Happened

During Slice S01, the MVSEC HDF5 loader interface, validation framework, and sequence representation were verified. In Task T01, we verified that the existing loader correctly processes event, IMU, image, and ground-truth pose datasets, checks for timestamp monotonicity and duplicate records, and outputs layout diagnostic details. Unit tests were run using pytest, and python linting/formatting checks were run using ruff. In Task T02, we created the contract documentation (docs/datasets/mvsec.md) explaining the internal HDF5 structures and path names. In Task T03, we built the inspect_mvsec.py example script to allow manual and pipeline inspections, and added corresponding unit tests. All tests pass successfully and all style/formatting requirements are satisfied.

## Verification

Verified that ruff formatting, ruff linting, and pytest unit tests for the dataset loader and CLI inspect script all pass successfully. Exits 0 in the uv run context.

## Requirements Advanced

None.

## Requirements Validated

None.

## New Requirements Surfaced

None.

## Requirements Invalidated or Re-scoped

None.

## Operational Readiness

None.

## Deviations

None.

## Known Limitations

Real MVSEC HDF5 sequence runs require manual downloading and setup, as the test suite uses synthetic schema-correct stub files for validation.

## Follow-ups

None.

## Files Created/Modified

- `docs/datasets/mvsec.md` — Created documentation for MVSEC HDF5 loader contract, dataset schema, and diagnostics
- `examples/inspect_mvsec.py` — Implemented metadata inspection CLI for quick diagnostics of MVSEC sequence files
- `tests/nav_benchmark/datasets/test_mvsec.py` — Added unit tests to verify CLI execution and CLI standard error output handling
