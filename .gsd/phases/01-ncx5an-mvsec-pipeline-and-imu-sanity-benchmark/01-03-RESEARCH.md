# M001-ncx5an/S03 Slice Research: IMU Only Backend and CLI Run Path

## Summary
Slice S03 designs the minimal backend interface (`src/nav_benchmark/baselines/imu.py` or equivalent interface classes) and orchestrates the CLI run path (`src/nav_benchmark/run.py`). It enables running `imu_only` odometry propagation on both synthetic data and real MVSEC sequence data. The run produces the standard benchmark output structure under the `runs/<timestamp>_imu_only_<sequence_name>/` directory.

## In Scope
- Define the minimal odometry backend contract (e.g. standard interface/base class or helper) for the system.
- Build the `imu_only` integration/propagation backend using IMU linear acceleration, angular velocity, and initial conditions.
- Design the CLI entrypoint at `src/nav_benchmark/run.py` (runnable via `python -m nav_benchmark.run`).
- Integrate the dataset loaders, baseline propagation, and trajectory export logic into a single end-to-end command flow.
- Format the output run skeleton under `runs/` containing `estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, `run.log`, `failure_notes.md`, and `run_manifest.json`.
- Implement robust error handling for missing/degraded data and initialization issues.

## Out of Scope
- Actually evaluating estimated trajectories against ground truth (drift metrics, ATE, RPE, and plots) – this belongs to S04.
- Creating the full manifest validation or automated CI checks verifying all outputs are content-valid – this belongs to S05.
- Event+IMU baseline backend – this belongs to M002.

## Recommendation
1. **Odometry Backend Interface**: Create an abstract base class `BaseOdometryBackend` in a new module (e.g. `src/nav_benchmark/baselines/base.py`) or declare a clear function signature. For M001, since we need to keep it simple, we can have a clean functional signature or simple interface class:
   ```python
   class BaseOdometryBackend(ABC):
       @abstractmethod
       def run(self, sequence: MvsecSequence) -> Trajectory:
           pass
   ```
2. **IMU Integration Backend**: Implement `ImuOnlyBackend` in `src/nav_benchmark/baselines/imu.py` which propagates orientation via gyro integration and positions/velocities via linear acceleration integration (incorporating gravity removal). Provide configuration options for gravity vector, noise filtering, and initial states.
3. **CLI run.py**: Implement the parser and workflow. The command will look like `python -m nav_benchmark.run --method imu_only --dataset mvsec --sequence <name> --input <path> --output-dir <path>`. It should support a synthetic/dummy dataset fallback when no HDF5 file is supplied to run a quick deterministic CI check.
4. **Health State Rules**: Since this is IMU-only, it has no correction mechanism and will drift indefinitely. It should track latency per sample. Health status can transition from `OK` to `DEGRADED` or `LOST` if covariance/variance thresholds are exceeded or simple temporal/drift limits are breached, but the basic model will log health based on time/duration or estimated drift.

## Implementation Landscape
- **Python Standard Library**: `argparse` for CLI subcommands, `logging` for `run.log`, `pathlib` for file layout.
- **IMU propagation logic**: We will use `scipy.spatial.transform.Rotation` (SLERP/integration of angular velocities) and double integration of linear acceleration (removing gravity).
- **Run Directory Skeleton**:
  - `runs/<timestamp>_imu_only_<sequence>/`
    - `estimated_trajectory.csv` (15-column schema)
    - `estimated_trajectory_tum.txt` (TUM schema, filtered to OK/DEGRADED)
    - `run.log` (standard Python logging output)
    - `failure_notes.md` (reproducibility/lost health intervals summary)
    - `run_manifest.json` (metadata containing configuration, sequence, and timing parameters)

## Don't Hand-Roll
- Use standard `scipy.spatial.transform.Rotation` for orientation integration and interpolation rather than manual quaternion/Euler integrations.
- Reuse `src/nav_benchmark/trajectory/export.py` for exporting CSV/TUM.
- Reuse `src/nav_benchmark/datasets/mvsec.py` to parse sequences.
