# Trajectory Export Contract

This document defines the deterministic synchronization and trajectory export contract for the GPS-denied visual-inertial navigation evaluation pipeline. All methods, baselines, and ensemble configurations must produce files matching the schemas and constraints defined here to ensure interoperability with the evaluation suite (`evo` and local plotting tools).

## 1. Project Trajectory CSV Format

Every method MUST export trajectories to a CSV file with the following column schema:

```text
timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms
```

### Schema & DataType Specifications

| Column | Type | Description | Mandatory/Optional | Format / Resolution |
|---|---|---|---|---|
| `timestamp` | `float` | Pose timestamp in seconds | Mandatory | Floating point (e.g. `%.9f` representing seconds) |
| `method` | `string` | Method identifier | Mandatory | String, e.g. `imu_only`, `image_imu`, `event_imu`, `multimodal_vio`, `ensemble` |
| `x`, `y`, `z` | `float` | Position in meters | Mandatory | Floating point (`%.9f`) |
| `qx`, `qy`, `qz`, `qw` | `float` | Orientation quaternion | Mandatory | Floating point (`%.9f`), unit-length |
| `vx`, `vy`, `vz` | `float` | Linear velocity in m/s | Optional | Floating point (`%.9f`) or empty string |
| `confidence` | `float` | Tracker confidence score | Optional | Range `[0.0, 1.0]` or empty string |
| `health` | `string` | Pose status / health | Mandatory | `OK`, `DEGRADED`, `LOST`, `INVALID` |
| `latency_ms` | `float` | Update latency in milliseconds | Optional | Floating point (`%.3f`) or empty string |

### Health Mapping Rules
The `health` column acts as the signal state of the estimator at a given frame:
- **`OK`**: Tracking is active, accurate, and within nominal parameter bounds.
- **`DEGRADED`**: Tracking is active but suffering from sub-optimal conditions (e.g. low feature count, poor illumination, IMU bias walk). Poses are still exported.
- **`LOST`**: The estimator has lost tracking. Trajectory entries are maintained in the project CSV to preserve timeline diagnostics, but are filtered out in standard TUM trajectory evaluations.
- **`INVALID`**: Input data was corrupted or initialization failed. Similar to `LOST`, poses are preserved for timeline analytics but filtered out in downstream metrics.

---

## 2. TUM Trajectory Export Format

For compatibility with standard trajectory evaluation libraries (e.g., `evo`), the `export_tum` command exports a space-separated format:
```text
timestamp x y z qx qy qz qw
```

### Health Filtering Rules in TUM
To prevent invalid poses from contaminating trajectory metrics (like ATE and RPE):
- Only poses with health `OK` or `DEGRADED` are written to the TUM file.
- Poses with health `LOST` or `INVALID` are silently skipped.
- The return value of the TUM exporter indicates the total count of filtered poses, and this is updated in `ExportMetadata.tum_filtered_rows`.

---

## 3. Metadata and Diagnostics

To guarantee auditable benchmarking, `ExportMetadata` gathers data-capture context.

### Python Dataclass Definition
```python
@dataclass
class ExportMetadata:
    timestamp_unit: str = "seconds"
    association_policy: str = "nearest_neighbor"
    association_tolerance_sec: float | None = None
    source_frame: str = "imu"
    target_frame: str = "world"
    position_units: str = "meters"
    orientation_format: str = "quaternion_xyzw"
    health_counts: dict[str, int] = field(default_factory=dict)
    tum_filtered_rows: int = 0
```

### Diagnostic Tracking
- **`health_counts`**: Tracks the frequency of each `PoseHealth` state in the final trajectory to assess tracker reliability over the entire run.
- **`tum_filtered_rows`**: Tracks how many bad poses were omitted from evaluation to ensure tracking failure rates are reported accurately in the final benchmark.
