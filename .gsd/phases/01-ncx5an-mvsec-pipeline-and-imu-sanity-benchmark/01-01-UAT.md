# S01: MVSEC Loader and Stream Contract — UAT

**Milestone:** M001-ncx5an
**Written:** 2026-06-27T19:15:32.232Z

# S01: MVSEC Loader and Stream Contract — UAT

**Milestone:** M001-ncx5an
**Written:** 2026-06-27

## UAT Type

- UAT mode: runtime-executable
- Why this mode is sufficient: The loader and metadata inspection script are command-line utilities and importable libraries. Automated unit tests and execution of the CLI script programmatically verify that all components parse correct and incorrect inputs identically to the specification.

## Preconditions

- Python virtual environment is active with dependencies installed (`uv run`).
- Discovered layout or synthetic metadata schemas match expectations.

## Smoke Test

Verify the example CLI help command executes cleanly within the `uv` environment:
```bash
uv run python3 examples/inspect_mvsec.py --help
```
*Expected Output:*
```
usage: inspect_mvsec.py [-h] --h5 H5
...
```

## Test Cases

### 1. Dataset Loading and Quality Validation
Verify the dataset loader detects missing groups, invalid non-monotonic timestamps, and duplicate timestamps.
1. Run `uv run pytest tests/nav_benchmark/datasets/test_mvsec.py -v`
2. **Expected:** All dataset loading, layout, calibration, and timestamp tests pass successfully.

### 2. Inspector Command Execution
Verify that the example inspect CLI utility executes programmatically against a synthetic HDF5 sequence.
1. Run CLI inspection test case within pytest.
2. **Expected:** Returns status code 0 and reports sequence properties, sample counts, and diagnostics successfully.

