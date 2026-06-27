# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? | Made By |
|---|------|-------|----------|--------|-----------|------------|---------|
| D001 |  | architecture | Synchronization and export policy for S02 | Nearest-neighbor timestamp association within caller-provided tolerance (no interpolation in S02); diagnostics are mandatory and include counts, ranges, first/last matched ts, overlap sufficiency; CSV export preserves all rows with health labels per fixed 15-column schema; TUM export includes only valid (OK/DEGRADED) poses and records filtered counts; timestamps are UNIX seconds with 9 decimal places; quaternion order is qx,qy,qz,qw. | Locks externally-visible behavior so S03 CLI/backends and S04 evaluator can rely on deterministic association and artifact formats; avoids downstream rewrites and ensures CI can validate contract with synthetic fixtures. | Yes | agent |
