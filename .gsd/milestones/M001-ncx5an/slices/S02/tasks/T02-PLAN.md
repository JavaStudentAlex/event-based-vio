---
estimated_steps: 1
estimated_files: 4
skills_used: []
---

# T02: Documented the CSV and TUM export contract and verified export diagnostics and formatting constraints.

Why: All methods must emit the same CSV schema and interoperable TUM; S03/S05 will consume metadata. Do: verify/export behavior and author an export-contract doc that fixes column order/types, health filtering rules, quaternion order, and time base. Done when: export tests pass and docs/trajectory/export-contract.md exists capturing schema, filtering rules, and metadata fields.

## Inputs

- `src/nav_benchmark/trajectory/export.py`
- `tests/trajectory/test_export.py`

## Expected Output

- `docs/trajectory/export-contract.md`

## Verification

rtk uv run pytest tests/trajectory/test_export.py -q && test -f docs/trajectory/export-contract.md

## Observability Impact

Pins ExportMetadata contents consumed by manifests and evaluators.
