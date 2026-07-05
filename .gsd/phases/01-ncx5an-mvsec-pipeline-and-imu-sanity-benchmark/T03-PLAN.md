---
estimated_steps: 25
estimated_files: 2
skills_used: []
---

# T03: Add regression test for canonical failure_notes string and fix lint

## Why
The validation string mismatch between producer (`run.py`) and validator (`validation.py`) for `failure_notes.md` was fixed in commit 22746d9. The producer now writes `"No degraded or lost intervals were detected."` and the validator expects exactly that string. However, there is no dedicated regression test that specifically guards this canonical string pairing — existing tests exercise the broad validation path but do not assert on the exact producer ↔ validator string contract. Additionally, `tools/record_google_earth_sequence.py` has an unsorted import block (ruff I001).

## Do
1. **Verify the canonical strings still match** — Read `src/nav_benchmark/run.py` line ~88 for the producer string and `src/nav_benchmark/validation.py` lines ~326-327 for the validator expected string. Confirm they are identical: `"No degraded or lost intervals were detected."`.

2. **Add a targeted regression test** in `tests/validation/test_artifact_validation.py` that:
   - Creates a minimal `failure_notes.md` with the canonical clean-run string `"No degraded or lost intervals were detected."`
   - Creates a companion `run_manifest.json` with `health_counts` showing zero failures (all OK)
   - Calls `check_failure_notes(path)` and asserts it passes
   - Then mutates the string to the old mismatch value (e.g. `"No degraded or lost intervals were detected during this run."`) and asserts validation fails
   - This is the regression gate: if producer or validator drift apart, this test catches it

3. **Fix the lint issue** — In `tools/record_google_earth_sequence.py`, reorder the import block at lines 20-23 so `ruff check .` passes. The fix is to put the `from nav_benchmark.data.validation` import on its own line or sort imports per isort rules. Run `rtk uv run --only-dev ruff check --fix tools/record_google_earth_sequence.py` or manually sort the imports.

4. Run verification: `rtk uv run --only-dev ruff check .` and `rtk uv run --only-dev ruff format --check .` to confirm both pass. Then run `rtk uv run --only-dev pytest tests/validation/test_artifact_validation.py -q` to confirm the new regression test passes.

## Done-when
- A test exists that explicitly asserts the canonical `failure_notes.md` string passes validation when health counts are clean, and that a mutated string (the old mismatch) fails validation.
- `ruff check .` exits 0 (lint clean).
- `ruff format --check .` exits 0.
- All validation unit tests pass.

## Key strings to verify
- Producer (run.py ~line 88): `"No degraded or lost intervals were detected."`
- Validator (validation.py ~lines 326-327): expects `"No degraded or lost intervals were detected."` via `not in content` check
- Old broken string was: `"No degraded or lost intervals were detected during this run."`

## Constraints
- Do not weaken validation strictness. The test must assert that only the canonical string passes, not broad aliases.
- Do not redesign the validation framework or CLI.
- Keep the regression test narrow and focused on the specific string contract.

## Inputs

- `src/nav_benchmark/validation.py`
- `src/nav_benchmark/run.py`
- `tests/validation/test_artifact_validation.py`
- `tools/record_google_earth_sequence.py`

## Expected Output

- `tests/validation/test_artifact_validation.py`
- `tools/record_google_earth_sequence.py`

## Verification

rtk uv run --only-dev ruff check . && rtk uv run --only-dev ruff format --check . && rtk uv run --only-dev pytest tests/validation/test_artifact_validation.py -q
