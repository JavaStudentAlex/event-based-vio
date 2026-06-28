---
estimated_steps: 12
estimated_files: 1
skills_used: []
---

# T02: Wired the validate CLI subcommand into run.py and implemented test coverage

**Why:** The S05 contract requires `python -m nav_benchmark.run validate --run-dir <dir>` and `--latest` to invoke the validation module and print a pass/fail table with a nonzero exit code on failure.

**Do:**
1. In `src/nav_benchmark/run.py`, add a `validate` subparser in the `main()` function alongside the existing `run` and `eval` subparsers.
2. The validate subparser accepts:
   - `--run-dir <path>` — Path to a specific run directory.
   - `--latest` — Use `discover_latest_run_dir()` to find the most recent run directory. Accepts optional `--method` and `--sequence` filters.
   - `--skip-eval` — Skip evaluation artifact checks (for run-only directories).
3. In the command handler, call `validate_run_directory(run_dir, expect_eval=not args.skip_eval)` from `nav_benchmark.validation`.
4. Print a concise pass/fail table to stdout: one line per check showing `[PASS]` or `[FAIL]` prefix, check name, and message.
5. Print a summary line: 'Validation: X/Y checks passed.' Exit 0 if all passed, exit 1 if any failed.
6. Either `--run-dir` or `--latest` must be specified; error otherwise.

**Done-when:** `python -m nav_benchmark.run validate --help` shows the expected arguments. The validate subcommand is wired to call `validate_run_directory`.

## Inputs

- `src/nav_benchmark/run.py`
- `src/nav_benchmark/validation.py`

## Expected Output

- `src/nav_benchmark/run.py`

## Verification

PYTHONPATH=src uv run python -m nav_benchmark.run validate --help
