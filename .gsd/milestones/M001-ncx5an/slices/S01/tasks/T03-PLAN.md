---
estimated_steps: 3
estimated_files: 1
skills_used: []
---

# T03: Add example CLI: inspect MVSEC file metadata

Why: Provide a minimal, deterministic example that exercises the loader and prints sequence metadata for quick sanity checks without needing full synchronization.
Do: Add examples/inspect_mvsec.py that accepts --h5 <path> and prints stream sample counts and time ranges, plus whether calibration fields are present, using load_mvsec_sequence.
Done-when: The script exists and is non-empty. (Running it against real data is manual, not part of CI.)

## Inputs

- `src/nav_benchmark/datasets/mvsec.py`

## Expected Output

- `examples/inspect_mvsec.py`

## Verification

test -s examples/inspect_mvsec.py
