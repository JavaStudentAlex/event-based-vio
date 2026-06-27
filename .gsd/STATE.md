# GSD State

**Active Milestone:** M001-ncx5an: MVSEC Pipeline and IMU Sanity Benchmark
**Active Slice:** S03: IMU Only Backend and CLI Run Path
**Phase:** planning
**Requirements Status:** 0 active · 0 validated · 0 deferred · 0 out of scope

## Milestone Registry
- 🔄 **M001-ncx5an:** MVSEC Pipeline and IMU Sanity Benchmark
- ⬜ **M002:** First Event+IMU Odometry Backend
- ⬜ **M003:** Strong Baselines and Benchmark Reporting

## Recent Decisions
- D001 (architecture): Nearest-neighbor timestamp association within caller-provided tolerance (no interpolation in S02); diagnostics are mandatory and include counts, ranges, first/last matched ts, overlap sufficiency; CSV export preserves all rows with health labels per fixed 15-column schema; TUM export includes only valid (OK/DEGRADED) poses and records filtered counts; timestamps are UNIX seconds with 9 decimal places; quaternion order is qx,qy,qz,qw. -> Locks externally-visible behavior so S03 CLI/backends and S04 evaluator can rely on deterministic association and artifact formats; avoids downstream rewrites and ensures CI can validate contract with synthetic fixtures.

## Blockers
- None

## Next Action
Slice S03 has no DB tasks. Plan slice tasks before execution.
