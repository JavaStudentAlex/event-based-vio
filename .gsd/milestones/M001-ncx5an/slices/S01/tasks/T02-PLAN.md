---
estimated_steps: 3
estimated_files: 1
skills_used: []
---

# T02: Write MVSEC loader contract doc (paths, dtypes, timestamp rules)

Why: Document the loader contract and real MVSEC path table so users can point to a dataset and understand what is loaded and validated.
Do: Create docs/datasets/mvsec.md describing the hardcoded HDF5 groups, structured dtypes for events/IMU/poses, timestamp monotonicity guarantees, calibration fields, diagnostics semantics, and the MvsecSequence/metadata shapes. Include a brief note on typical MVSEC sequence paths (e.g., outdoor_day1) without bundling data.
Done-when: The doc exists, is non-empty, and includes the path table and dtype sections.

## Inputs

- `src/nav_benchmark/datasets/mvsec.py`
- `tests/nav_benchmark/datasets/test_mvsec.py`

## Expected Output

- `docs/datasets/mvsec.md`

## Verification

test -s docs/datasets/mvsec.md
