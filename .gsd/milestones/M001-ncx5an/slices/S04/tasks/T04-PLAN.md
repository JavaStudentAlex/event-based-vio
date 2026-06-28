---
estimated_steps: 13
estimated_files: 2
skills_used: []
---

# T04: Documented the S04 eval CLI and drift-evaluation artifact contract, then verified the full repository with Ruff, format check, and pytest.

---
skills_used:
  - write-docs
  - verify-before-complete
---
Why: S04 changes the public benchmark workflow by adding an explicit eval command and a new artifact contract. Executors and S05 need documentation that a fresh reader can use without reading the implementation.

Do:
- Update `docs/run/cli.md` with the eval invocation, `--run-dir`, `--ground-truth`, `--latest`, filter flags, and examples for synthetic and MVSEC-style runs.
- Add `docs/evaluation/drift-evaluation.md` documenting alignment policy, association tolerance, no time-offset search, no outlier rejection, OK/DEGRADED numeric filtering, LOST/INVALID coverage reporting, metric definitions, error CSV columns, plot outputs, failure behavior, and which checks remain dataset-dependent.
- Cross-reference the fixed trajectory export contract rather than duplicating the entire S02 schema.
- Run full slice verification after docs and code are in place.
- Q4 requirement impact: note that S04 supports R003 by consuming fixed columns and preserving health labels in evaluation artifacts.

Done when: documentation describes exactly how to run and interpret S04 outputs, and the full verification suite passes with ruff, format check, and pytest.

## Inputs

- `docs/run/cli.md`
- `docs/trajectory/export-contract.md`
- `src/nav_benchmark/run.py`
- `src/nav_benchmark/evaluation/metrics.py`
- `src/nav_benchmark/evaluation/plots.py`

## Expected Output

- `docs/run/cli.md`
- `docs/evaluation/drift-evaluation.md`

## Verification

rtk uv run --only-dev ruff check . && rtk uv run --only-dev ruff format --check . && rtk uv run --only-dev pytest tests -q

## Observability Impact

Documents the evaluation observability contract so S05 and future benchmark users can validate artifacts by meaning rather than file presence.
