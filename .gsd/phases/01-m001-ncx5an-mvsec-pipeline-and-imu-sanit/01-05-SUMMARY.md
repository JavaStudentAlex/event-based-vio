---
id: S05
parent: M001-ncx5an
milestone: M001-ncx5an
provides:
  - validate CLI command
  - validation module validation.py
  - CI validation tests
requires:
  - slice: S03
    provides: IMU Only baseline trajectory output skeleton
  - slice: S04
    provides: Trajectory error plots and metrics JSON format
affects:
  - M002
key_files:
  - src/nav_benchmark/validation.py
  - src/nav_benchmark/run.py
key_decisions:
  - Implemented a robust validation framework to verify trajectory columns, finite floats, manifest presence, metrics keys, and health consistency
  - Ensured validate subcommand returns non-zero code on failing validations to allow clean CI integration
  - Refactored complex checks in validation.py to ensure McCabe complexity remains strictly below 10
patterns_established:
  - Reusable validator pattern for run directory outputs
observability_surfaces:
  - validate CLI subcommand exit codes and concise validation reports
drill_down_paths:
  - .gsd/milestones/M001-ncx5an/slices/S05/tasks/T01-SUMMARY.md
  - .gsd/milestones/M001-ncx5an/slices/S05/tasks/T02-SUMMARY.md
  - .gsd/milestones/M001-ncx5an/slices/S05/tasks/T03-SUMMARY.md
  - .gsd/milestones/M001-ncx5an/slices/S05/tasks/T04-SUMMARY.md
  - .gsd/milestones/M001-ncx5an/slices/S05/tasks/T05-SUMMARY.md
duration: ""
verification_result: passed
completed_at: 2026-06-28T13:03:19.631Z
blocker_discovered: false
---

# S05: Manifest Failure Artifacts and CI Smoke Coverage

**Finalized the M001 operational artifact contract by introducing a validation module, wiring a validate CLI subcommand, and adding synthetic CI smoke tests.**

## What Happened

We implemented the artifact validation backend and wired it to the CLI. During this slice, we added tests for all verification checks and a CLI integration test that validates the whole workflow (run -> eval -> validate) using synthetic MVSEC-like inputs. Finally, code formatting was verified and McCabe complexities were reduced below 10 for all functions in the validation module.

## Verification

All 23 validation unit and CLI integration tests in `tests/validation/test_artifact_validation.py` and `tests/cli/test_validate_cli.py` passed cleanly within 62 seconds. The code is formatted, clean, and complies with PEP8 and ruff checks.

## Requirements Advanced

- R003 — Ensured that all estimated trajectory files, manifests, error CSVs, and failure notes are present and checked for validity.

## Requirements Validated

- R003 — All verification checks passed in validation.py and CLI integration tests successfully failed when artifacts were missing or corrupt.

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

- `src/nav_benchmark/validation.py` — Implemented run-directory validation checks and verification module
- `src/nav_benchmark/run.py` — Wired the validate CLI subcommand, latest runs, and output tables
- `tests/validation/test_artifact_validation.py` — Added unit tests for validating trajectory CSV, TUM, manifest, failure notes, and metrics format
- `tests/cli/test_validate_cli.py` — Added integration CLI tests verifying run-evaluation-validation flow and fail states
