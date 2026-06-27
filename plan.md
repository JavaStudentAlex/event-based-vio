1. **Understand Task**: We need to implement S02: Synchronization and Trajectory Export Contract.
2. **Review Context**: S02-CONTEXT.md specifies:
   - Produce a synchronization policy: nearest-neighbor within an explicit caller-provided tolerance. No hidden interpolation.
   - Synchronization diagnostics: unmatched counts/ranges, tolerance used, first/last matched timestamps, overlap sufficiency.
   - Trajectory data model: positions, orientations, velocities, confidence, health, latency.
   - `export_project_csv(trajectory, ...)`: Writes CSV preserving invalid/degraded rows with health labels.
   - `export_tum(trajectory, ...)`: Writes valid-only TUM, returns filtered-row counts.
   - ExportMetadata API return.
   - Add synthetic validators/tests for all this.
3. **Implementation Details**:
   - `src/nav_benchmark/trajectory/sync.py`:
     - `sync_nearest_neighbor(source_ts, target_ts, tolerance)`: nearest-neighbor matching.
     - `SyncDiagnostics` dataclass.
   - `src/nav_benchmark/trajectory/models.py`:
     - `Trajectory` data model (dataclass/numpy array wrapper).
     - `ExportMetadata` dataclass.
   - `src/nav_benchmark/trajectory/export.py`:
     - `export_project_csv` function.
     - `export_tum` function.
   - `tests/trajectory/test_sync.py`: test nearest-neighbor matching.
   - `tests/trajectory/test_export.py`: test CSV and TUM export formats.
4. **Pre-commit**: We need to run `uv run pre-commit run --hook-stage manual --all-files`.
5. **Update .gsd**: We need to add meaningful details about the implementation to the `.gsd` Markdown state for S02 without changing its status.

Let's write a draft plan and review it.
