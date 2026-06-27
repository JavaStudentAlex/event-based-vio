---
estimated_steps: 1
estimated_files: 6
skills_used: []
---

# T04: ExportMetadata completeness and invariants pass

Why: S03/S05 rely on explicit metadata (timestamp unit=seconds, association policy+tolerance, frames, units, quaternion order, per-health counts, TUM filtered rows). Do: ensure ExportMetadata and SyncDiagnostics expose these fields exactly and adjust tests accordingly; keep behavior deterministic and avoid silent drops. Done when: full trajectory test suite passes.

## Inputs

- `src/nav_benchmark/trajectory/models.py`
- `src/nav_benchmark/trajectory/export.py`
- `src/nav_benchmark/trajectory/sync.py`
- `tests/trajectory/test_export.py`
- `tests/trajectory/test_models.py`
- `tests/trajectory/test_sync.py`

## Expected Output

- `src/nav_benchmark/trajectory/models.py`
- `src/nav_benchmark/trajectory/export.py`
- `src/nav_benchmark/trajectory/sync.py`
- `tests/trajectory/test_export.py`
- `tests/trajectory/test_models.py`
- `tests/trajectory/test_sync.py`

## Verification

rtk uv run pytest tests/trajectory -q

## Observability Impact

Standardizes metadata fields for downstream logging and manifests.
