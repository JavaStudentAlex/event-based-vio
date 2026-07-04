---
id: S02
milestone: M001-ncx5an
status: ready
---

# S02: Synchronization and Trajectory Export Contract — Context

## Goal

Define and verify a deterministic synchronization policy and trajectory export contract so IMU-derived trajectories and ground truth are timestamp-associated without silent drops, and a synthetic trajectory exports valid project CSV plus interoperable TUM files with explicit metadata and diagnostics.

## Why this Slice

S02 locks the user-visible behavior for time association and artifact export that S03’s backend/CLI and S04’s evaluator depend on. Deciding this now prevents downstream rewrite risk, ensures deterministic synthetic proofs for CI, and establishes clear failure modes before adding `imu_only` or SE3-aligned metrics.

## Scope

### In Scope

- Timestamp association policy: nearest-neighbor within an explicit, caller-provided tolerance; no hidden interpolation in S02.
- Synchronization diagnostics: unmatched counts and ranges, tolerance used, first/last matched timestamps, and overlap sufficiency.
- Trajectory export functions for the fixed project CSV schema and TUM format.
- Invalid/degraded pose handling: CSV preserves rows with health labels; TUM includes only valid poses and records filtered counts.
- Must-see export metadata: timestamp unit (seconds), association policy and tolerance, source/target frames, units, quaternion order (qx,qy,qz,qw), per-health counts, and TUM filtered-row counts.
- Synthetic proof package: tiny fixtures and validators that assert association diagnostics, CSV schema/content, and TUM line format and filtering.

### Out of Scope

- Implementing `imu_only` backend logic (S03).
- CLI orchestration and run directory manifests (S03/S05).
- SE3 alignment and evaluation metrics/plots (S04).
- Real MVSEC end-to-end in CI (manual/documented later); CI stays synthetic.
- Multiple association modes or interpolation in S02 (deferred until needed by later slices).

## Constraints

- Python 3.13 with `uv`; deterministic and reproducible behavior.
- No silent drops of timestamps, samples, or invalid intervals.
- CSV schema fixed:
  `timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms`.
- Stable health labels: OK, DEGRADED, LOST, INVALID.
- TUM export compatible with `evo` and standard tools; invalid rows filtered.
- All policies/units explicit in returned metadata from S02 APIs.

## Integration Points

### Consumes

- `MvsecSequence` from S01 — validated monotonic sensor streams and loader diagnostics.
- CSV schema definition (AGENTS.md) — columns and types for export.

### Produces

- `SyncDiagnostics` — unmatched counts/ranges, tolerance, overlap sufficiency, first/last matched timestamps.
- `Trajectory` data model — positions, orientations, velocities, confidence, health, latency.
- `export_project_csv(trajectory, ...)` — Writes CSV preserving invalid/degraded rows with health labels.
- `export_tum(trajectory, ...)` — Writes valid-only TUM; returns filtered-row counts.
- `ExportMetadata` (API return) — timestamp unit, association policy/tolerance, frames, units, quaternion order, per-health counts, TUM filtered rows; consumed by S03/S05 for manifests.
- Synthetic validators/tests — association behavior, CSV schema/content, TUM line format and filtering.

## Open Questions

- TUM time base and precision are set to UNIX seconds (float) with 9 decimal places. Confirm whether any tools in our target set require relative seconds; if so, document a conversion helper rather than changing the export.
- Duplicate timestamps policy is to reject with diagnostics. If real MVSEC data exhibits benign duplicates, should S02 add an opt-in de-dup mode (first/last-wins) guarded by explicit config?
- Where to expose invalid-interval summaries beyond CSV health labels: rely on `SyncDiagnostics` only, or add an optional `invalid_intervals.csv` in S03 when runs exist?
- What to emit for `latency_ms` in synthetic exports: constant 0 vs computed placeholder; ensure validators accept both as long as numeric and non-negative.

## Implementation Notes

- **Models**: `Trajectory`, `SyncDiagnostics`, `ExportMetadata`, and `PoseHealth` models have been implemented in `src/nav_benchmark/trajectory/models.py`. The `PoseHealth` choices map accurately to `OK`, `DEGRADED`, `LOST`, `INVALID`.
- **Synchronization Policy**: A deterministic `synchronize_nearest_neighbor` policy has been added in `src/nav_benchmark/trajectory/sync.py`, matching sources to targets exactly within the caller-provided `tolerance_sec` without any silent interpolation. Diagnostics cover tracking match counts, range gaps, overlap sufficiency, and exact timestamps to expose mismatches directly.
- **Export Formats**: Implemented `export_project_csv` and `export_tum` in `src/nav_benchmark/trajectory/export.py`. CSV export preserves every row with complete metadata labels, mapping directly to the 15-column benchmark contract schema. TUM export strictly filters out `LOST` and `INVALID` rows while returning filtered statistics through the updated `ExportMetadata`.
- **Testing**: Added rigorous synthetic unit tests for the nearest-neighbor sync (including exact, duplicates, and empty edge cases) and both trajectory export utilities in `tests/trajectory/`.
