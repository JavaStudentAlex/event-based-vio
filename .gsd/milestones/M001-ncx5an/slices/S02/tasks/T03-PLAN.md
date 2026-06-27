---
estimated_steps: 1
estimated_files: 3
skills_used: []
---

# T03: Synthetic end-to-end validator for export contract

Why: CI needs a deterministic synthetic proof that exercises project CSV and TUM export end-to-end, including per-health counts and filtered-row stats. Do: add a dedicated synthetic test that builds a small Trajectory with OK/DEGRADED/LOST/INVALID rows, calls both exporters to a temp path, then asserts header/row shapes, health label preservation, TUM filtering, and metadata counts. Done when: new test passes locally.

## Inputs

- `src/nav_benchmark/trajectory/export.py`
- `src/nav_benchmark/trajectory/models.py`

## Expected Output

- `tests/trajectory/test_export_contract_synthetic.py`

## Verification

rtk uv run pytest tests/trajectory/test_export_contract_synthetic.py -q
