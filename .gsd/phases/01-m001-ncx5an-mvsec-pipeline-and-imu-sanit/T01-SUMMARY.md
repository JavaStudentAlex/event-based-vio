---
id: T01
parent: S06
milestone: M001
key_files:
  - tests/cli/test_validate_cli.py
key_decisions:
  - (none)
duration: 
verification_result: passed
completed_at: 2026-07-05T05:14:11.764Z
blocker_discovered: false
---

# T01: Regression test locking canonical artifact strings already exists and passes

**Regression test locking canonical artifact strings already exists and passes**

## What Happened

The test `test_validate_locks_canonical_artifact_strings` was already implemented in a previous session within `tests/cli/test_validate_cli.py`. It runs a full synthetic run->eval->validate pipeline and asserts exact canonical values: manifest.status='success', manifest.alignment.policy='nearest_neighbor', manifest.evaluation.status='success', metrics.status='OK', metrics.config.alignment_policy='se3', failure_notes contains the clean-run sentence, and validate exits 0 with '11/11 checks passed'. The test passes confirming no string mismatch exists in the current codebase.

## Verification

Ran pytest tests/cli/test_validate_cli.py::test_validate_locks_canonical_artifact_strings -v — 1 passed in 4.62s

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `uv run --only-dev pytest tests/cli/test_validate_cli.py::test_validate_locks_canonical_artifact_strings -v` | 0 | ✅ pass | 5796ms |

## Deviations

None — test already existed from prior session work.

## Known Issues

None.

## Files Created/Modified

- `tests/cli/test_validate_cli.py`
