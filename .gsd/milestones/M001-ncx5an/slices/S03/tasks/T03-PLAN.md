---
estimated_steps: 6
estimated_files: 2
skills_used: []
---

# T03: Manifest and failure-notes generation with health counts

Why: Downstream evaluation (S04/S5) depends on reproducible metadata and explicit failure visibility.
Do:
- In the CLI flow, compute health counts from the Trajectory and ExportMetadata and write `run_manifest.json` with method, dataset/sequence, gravity, timestamp/alignment placeholders, thresholds, code version (if available), and counts.
- Always write `failure_notes.md`: summarize degraded/lost intervals or state that none were detected; include counts and short guidance.
- Add `tests/cli/test_run_manifest_and_notes.py` that executes the synthetic CLI run and asserts presence, JSON validity, and required top-level manifest keys; also asserts `failure_notes.md` exists and is non-empty.
Done when: Manifest and notes tests pass.

## Inputs

- `src/nav_benchmark/trajectory/export.py`
- `src/nav_benchmark/trajectory/models.py`
- `src/nav_benchmark/run.py`

## Expected Output

- `tests/cli/test_run_manifest_and_notes.py`

## Verification

rtk uv run pytest tests/cli/test_run_manifest_and_notes.py -q

## Observability Impact

Adds structured manifest fields and an always-on failure-notes artifact to surface degraded/lost behavior.
