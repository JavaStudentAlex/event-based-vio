# S02: Synchronization and Trajectory Export Contract — Research

## Summary
The goal of Slice S02 is to define, implement, and verify a deterministic nearest-neighbor synchronization policy and a trajectory export contract. These ensure that sensor trajectory estimates (or baseline outputs) and ground truth are timestamp-associated without silent drops, and estimated trajectories can be exported to a standard custom CSV schema as well as TUM format.

This research validates the existing codebase structure, libraries, data schemas, and synchronization constraints for S02.

## Implementation Landscape
The synchronization and trajectory export contract features are already implemented in `src/nav_benchmark/trajectory/` and tested in `tests/trajectory/`. The code layout consists of:
- **`src/nav_benchmark/trajectory/models.py`**:
  - `PoseHealth` (StrEnum: `OK`, `DEGRADED`, `LOST`, `INVALID`)
  - `Trajectory` (dataclass checking shapes of positions `(N,3)` and orientations `(N,4)`, and lengths of optional arrays: velocities, confidence, health, latency)
  - `SyncDiagnostics` (dataclass logging source/target/matched counts, tolerance, first/last match timestamp, overlap sufficiency, unmatched range segments)
  - `ExportMetadata` (dataclass tracking units, frames, policy, and stats)
- **`src/nav_benchmark/trajectory/sync.py`**:
  - `synchronize_nearest_neighbor(source_timestamps, target_timestamps, tolerance_sec)`: Finds nearest target timestamp for each source timestamp via binary search (`np.searchsorted`). Deduplicates matches to keep the source with the smallest diff, filters by `tolerance_sec`, and compiles full diagnostic statistics without silently discarding ranges.
- **`src/nav_benchmark/trajectory/export.py`**:
  - `export_project_csv(trajectory, path, metadata)`: Writes a standard CSV with headers mapping `timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms` and tracking per-health counts.
  - `export_tum(trajectory, path, metadata)`: Writes a standard TUM trajectory file (`timestamp x y z qx qy qz qw`), filtering out rows with `LOST` or `INVALID` health statuses, and returning the number of filtered rows.

## Verification Plan
### Automated Tests
The existing tests under `tests/trajectory/` cover the functionality of S02:
- `tests/trajectory/test_models.py`: Validates shape constraints for `Trajectory` data fields.
- `tests/trajectory/test_sync.py`: Verifies nearest-neighbor behavior under exact, tolerance-based, duplicates (smallest diff win), and empty scenarios.
- `tests/trajectory/test_export.py`: Validates CSV formatting, header alignment, empty-optional value emission, health stats, and TUM filter logic.

Verification commands in execution mode:
```bash
rtk uv run --only-dev ruff check .
rtk uv run --only-dev ruff format --check .
rtk uv run pytest tests/trajectory -v
```

## Natural Seams
- **`src/nav_benchmark/trajectory/models.py`**: Decoupled definition of data structures.
- **`src/nav_benchmark/trajectory/sync.py`**: Pure timestamp association algorithm logic using numpy.
- **`src/nav_benchmark/trajectory/export.py`**: IO formatting logic decoupling output formats from estimation models.
- **`tests/trajectory/`**: Target unit tests validation.
