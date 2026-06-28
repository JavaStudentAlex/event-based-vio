---
id: T04
parent: S03
milestone: M001-ncx5an
key_files:
  - docs/run/cli.md
key_decisions:
  - Created comprehensive CLI usage documentation under docs/run/cli.md to guide manual invocation and directory structure understanding.
duration: 
verification_result: passed
completed_at: 2026-06-28T00:31:48.012Z
blocker_discovered: false
---

# T04: Created CLI usage documentation guide detailing invocation examples, run directory structure, and resume behavior.

**Created CLI usage documentation guide detailing invocation examples, run directory structure, and resume behavior.**

## What Happened

Authored the command-line interface usage guide under `docs/run/cli.md`. The documentation details invocation examples for both synthetic and MVSEC sequence runs, descriptions of the run directory structure (estimated_trajectory.csv, estimated_trajectory_tum.txt, run.log, run_manifest.json, failure_notes.md), and documentation of the collision and resume behavior.

### Q5 — Failure Modes
This task delivers static Markdown documentation and does not introduce runtime dependencies, APIs, or subprocesses.

### Q6 — Load Profile
This task does not have a runtime load dimension.

### Q7 — Negative Tests
This task is documentation-only and does not contain runnable code or associated negative tests.

## Verification

Verified the existence and non-emptiness of the CLI usage documentation via file checks.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `test -s docs/run/cli.md` | 0 | ✅ pass | 88ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `docs/run/cli.md`
