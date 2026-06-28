---
estimated_steps: 8
estimated_files: 4
skills_used: []
---

# T05: Full regression suite and lint verification

**Why:** S05 must not break any existing tests. The final task verifies the complete test suite, lint, and format checks pass together.

**Do:**
1. Run `uv run --only-dev ruff check .` and fix any lint issues in new files.
2. Run `uv run --only-dev ruff format --check .` and fix any format issues in new files.
3. Run `PYTHONPATH=src uv run --only-dev pytest tests -q` to verify the complete test suite passes including all pre-existing and new tests.
4. If any test failures occur in new S05 files, fix the issues in `src/nav_benchmark/validation.py`, `src/nav_benchmark/run.py`, `tests/validation/test_artifact_validation.py`, or `tests/cli/test_validate_cli.py`.
5. Confirm no regressions in existing S01-S04 tests.

**Done-when:** All three verification commands exit 0.

## Inputs

- `src/nav_benchmark/validation.py`
- `src/nav_benchmark/run.py`
- `tests/validation/test_artifact_validation.py`
- `tests/cli/test_validate_cli.py`

## Expected Output

- `src/nav_benchmark/validation.py`
- `src/nav_benchmark/run.py`
- `tests/validation/test_artifact_validation.py`
- `tests/cli/test_validate_cli.py`

## Verification

uv run --only-dev ruff check . && uv run --only-dev ruff format --check . && PYTHONPATH=src uv run --only-dev pytest tests -q
