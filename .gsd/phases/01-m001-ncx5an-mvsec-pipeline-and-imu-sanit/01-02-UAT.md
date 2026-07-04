# S02: Synchronization and Trajectory Export Contract — UAT

**Milestone:** M001-ncx5an
**Written:** 2026-06-27T23:00:46.834Z

# UAT Specification for S02: Synchronization and Trajectory Export Contract

## UAT Type
- UAT mode: runtime-executable

## Preconditions
1. Python environment set up with `uv`.
2. Clean source and test directory.

## Execution Steps

### Run Trajectory Sync & Export Unit Tests
Verify the math, constraints, exceptions, and formatting behavior of synchronization and export modules.
```bash
rtk uv run pytest tests/trajectory -q
```
Expected output:
- 22 passed tests (100% pass rate).

### Run Linter & Formatter Verification
Verify the code style of the implemented files.
```bash
rtk uv run --only-dev ruff check .
rtk uv run --only-dev ruff format --check .
```
Expected output:
- No style violations, all formats clean.

