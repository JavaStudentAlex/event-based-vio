---
estimated_steps: 4
estimated_files: 1
skills_used: []
---

# T04: Created CLI usage documentation guide detailing invocation examples, run directory structure, and resume behavior.

Why: Provide quick-start guidance for humans running the slice manually.
Do:
- Create `docs/run/cli.md` with invocation examples for synthetic and MVSEC, description of run directory structure, and notes on resume behavior.
Done when: Doc exists and is non-empty with required headings.

## Inputs

- `src/nav_benchmark/run.py`

## Expected Output

- `docs/run/cli.md`

## Verification

test -s docs/run/cli.md
