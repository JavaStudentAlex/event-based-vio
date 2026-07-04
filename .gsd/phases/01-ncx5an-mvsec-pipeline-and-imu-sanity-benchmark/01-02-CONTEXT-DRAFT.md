---
id: S02
milestone: M001-ncx5an
status: draft
---

# S02: Synchronization and Trajectory Export Contract — Context (Draft)

## Goal

Define and prove a synchronization policy and export contract so IMU samples and ground truth can be timestamp-associated without silent drops, and a synthetic trajectory can export valid project CSV plus interoperable TUM files with clear metadata and diagnostics.

## Why this Slice

S02 locks the data association behavior and trajectory artifact contract that S03’s backend/CLI and S04’s evaluator will consume. Getting sync/exports right now prevents later rewrite risk and ensures deterministic, testable behavior before adding the `imu_only` backend or SE3-aligned metrics.

## Scope

### In Scope

- Timestamp association behavior between IMU-derived trajectory and ground truth using nearest-neighbor within an explicit tolerance (no hidden interpolation).
- Synchronization diagnostics: unmatched counts/ranges, first/last matched timestamps, tolerance used, and overlap sufficiency assessment.
- Trajectory export functions for the project CSV schema and TUM format.
- Export policy for invalid/degraded poses: CSV preserves rows with health labels; TUM filters to valid-only and records filtered counts.
- Must-see export metadata: timestamp unit (seconds), association policy and tolerance, source/target frames, units, quaternion order (qx,qy,qz,qw), per-health counts, and TUM filtered-row counts.
- Synthetic proof: tiny fixtures and validators that assert association diagnostics, CSV schema/content, and TUM line format and filtering.

### Out of Scope

- Implementing `imu_only` or any backend logic (S03).
- CLI orchestration, run directories, and `run_manifest.json`/`failure_notes.md` materialization (S03/S05).
- SE3 alignment and evaluation metrics/plots (S04).
- Real MVSEC end-to-end runs in CI (documented/manual later); CI stays synthetic.
- Advanced interpolation policies or multi-mode association (deferred unless later slices request).

## Constraints

- Use Python 3.13 and `uv`; keep behavior deterministic and reproducible.
- Do not silently drop timestamps, samples, or invalid intervals.
- Conform to the fixed project CSV schema:
  `timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms`.
- Preserve invalid/degraded intervals in CSV with stable labels: OK, DEGRADED, LOST, INVALID.
- TUM export must be compatible with standard tools (e.g., evo) and exclude invalid rows.
- All policies and units must be explicit in metadata returned by S02 APIs.

## Integration Points

### Consumes

- `MvsecSequence` from S01 — Monotonic, validated sensor streams and loader diagnostics.
- Project CSV schema (AGENTS.md) — Shapes trajectory export columns and types.

### Produces

- Synchronization policy + `SyncDiagnostics` — counts, ranges, tolerance, overlap, unmatched summaries.
- `Trajectory` data model suitable for export.
- `export_project_csv(trajectory, ...)` — Writes CSV preserving health and invalid rows.
- `export_tum(trajectory, ...)` — Writes valid-only TUM; returns filtered-row counts.
- `ExportMetadata` — timestamp unit, association policy/tolerance, frames, units, quaternion order, health counts, TUM filtered rows (for S03/S05 to surface in manifests).
- Synthetic validators/tests for association, CSV schema/content, and TUM format.

## Open Questions

- TUM time base and precision — seconds as float with 9 decimal places vs alternative; rounding vs truncation.
- Duplicate timestamp policy — reject, de-dup last-wins, or jitter? (TUM typically expects strictly increasing timestamps.)
- `method` field for S02 synthetic exports — use `imu_only` for consistency vs a dedicated `synthetic_*` label to avoid confusion with S03.
- Where to materialize metadata in S02 — return via API only vs also writing a sidecar JSON now (S03 can place it into run manifests).
- Whether to add an explicit `invalid_intervals.csv` sidecar now or rely on CSV health labels + diagnostics only.
- What to emit for `latency_ms` in synthetic exports — constant 0 vs computed placeholder; ensure validators cover permitted values.
