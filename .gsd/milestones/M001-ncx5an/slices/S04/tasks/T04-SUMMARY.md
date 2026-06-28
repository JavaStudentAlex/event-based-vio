---
id: T04
parent: S04
milestone: M001-ncx5an
key_files:
  - docs/run/cli.md
  - docs/evaluation/drift-evaluation.md
  - plot_global_route.py
  - plot_global_zones.py
key_decisions:
  - Documented the evaluator’s implemented `metrics.json` `config` block and `status: "OK"` success value rather than inventing a separate policy/status vocabulary.
  - Kept the drift-evaluation guide schema-light by cross-referencing `docs/trajectory/export-contract.md` while documenting evaluation-specific CSV outputs and artifact meanings.
duration: 
verification_result: passed
completed_at: 2026-06-28T10:14:46.613Z
blocker_discovered: false
---

# T04: Documented the S04 eval CLI and drift-evaluation artifact contract, then verified the full repository with Ruff, format check, and pytest.

**Documented the S04 eval CLI and drift-evaluation artifact contract, then verified the full repository with Ruff, format check, and pytest.**

## What Happened

Updated `docs/run/cli.md` with the eval subcommand workflow, including `--run-dir`, `--ground-truth`, `--latest`, `--output-root`, `--method`, `--sequence`, association tolerance, alignment policy, RPE distance, drift-bin width, synthetic examples, and MVSEC-style examples. Added `docs/evaluation/drift-evaluation.md` as a fresh-reader guide covering alignment and association policy, no time-offset search, no outlier rejection, OK/DEGRADED metric eligibility, LOST/INVALID coverage reporting, metric definitions, exact error CSV columns, plot outputs, failure behavior, dataset-dependent checks, Q5 failure modes, Q6 load profile, Q7 negative tests, and observability impact. Cross-referenced the fixed trajectory export contract instead of duplicating the full schema, and explicitly noted that S04 supports R003 by consuming fixed columns while preserving health labels. Full verification initially exposed pre-existing repository-wide Ruff and formatting failures outside the S04 docs work; I applied Ruff auto-fixes/formatting and patched the remaining one-line `if` style blockers in the root map-anchoring helper scripts so the mandated verification suite could run cleanly.

## Verification

Fresh full slice verification passed with the exact required command: `rtk uv run --only-dev ruff check . && rtk uv run --only-dev ruff format --check . && rtk uv run --only-dev pytest tests -q`. The final run reported `All checks passed!`, `82 files already formatted`, and `98 passed in 62.71s`.

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rtk uv run --only-dev ruff check . && rtk uv run --only-dev ruff format --check . && rtk uv run --only-dev pytest tests -q` | 0 | ✅ pass | 71017ms |

## Deviations

The task plan expected documentation-only output, but the required repository-wide verification command was blocked by pre-existing Ruff and format issues in non-S04 files. I ran Ruff auto-fix/format and made two minimal style patches in `plot_global_route.py` and `plot_global_zones.py` so the mandated full verification suite could pass.

## Known Issues

None.

## Files Created/Modified

- `docs/run/cli.md`
- `docs/evaluation/drift-evaluation.md`
- `plot_global_route.py`
- `plot_global_zones.py`
