---
id: T02
parent: S01
milestone: M001-ncx5an
key_files:
  - docs/datasets/mvsec.md
key_decisions:
  - none
duration: 
verification_result: passed
completed_at: 2026-06-27T19:11:31.712Z
blocker_discovered: false
---

# T02: Created MVSEC loader contract documentation

**Created MVSEC loader contract documentation**

## What Happened

Created the dataset documentation detailing raw HDF5 group paths, structured NumPy dtypes for events, IMU samples, and ground truth poses, timestamp monotonicity verification rules, calibration structures, and sequence diagnostic semantics.

### Q5 — Failure Modes
This task documents the file loading contract which is dependent on local filesystem access to MVSEC HDF5 datasets. If file reads fail due to missing or corrupt data, standard I/O errors are raised or captured. This doc guides users on what happens when these failures occur.

### Q6 — Load Profile
This documentation outlines the data shapes and structures. As event data can be extremely high-frequency (millions of events per sequence), loading entire sequences into structured memory is the primary resource bottleneck. The document specifies the structured shapes that must be managed.

### Q7 — Negative Tests
The documentation details the timestamp monotonicity and layout mismatch validation rules. These rules are tested by negative tests in `tests/nav_benchmark/datasets/test_mvsec.py` which assert correctness under malformed input files or non-monotonic timestamps.

## Verification

Verified the existence and non-emptiness of docs/datasets/mvsec.md via test -s, and verified all linting and test checks pass.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -s docs/datasets/mvsec.md` | 0 | ✅ pass | 14ms |
| 2 | `uv run ruff check . && uv run ruff format --check . && uv run pytest tests -q` | 0 | ✅ pass | 3307ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `docs/datasets/mvsec.md`
