# MVSEC Dataset Loader and Stream Contract

This document describes the design, hardcoded HDF5 groups, data schemas, and timestamp validation rules for the MVSEC (Multi-Vehicle Stereo Event Camera) dataset loader implemented in the `nav-benchmark` project.

---

## 1. Hardcoded HDF5 Group Paths

The MVSEC reader directly queries specific HDF5 groups inside the raw `.h5` files. The following table maps the abstract sensor streams to the corresponding internal HDF5 path:

| Stream / Feature | Internal HDF5 Group / Dataset Path | Required Internal Keys |
|---|---|---|
| **Events** | `/davis/left/events` | `ts` (float64), `x` (uint16), `y` (uint16), `p` (int8) |
| **IMU** | `/davis/left/imu` | `ts` (float64), `linear_acceleration_[x/y/z]` (float64), `angular_velocity_[x/y/z]` (float64) |
| **Ground Truth Poses** | `/davis/left/pose` | `ts` (float64), `px/py/pz` (float64), `qx/qy/qz/qw` (float64) |
| **Grayscale Images** | `/davis/left/image_raw` | `ts` (float64), `image_raw` (uint8 array) |
| **Camera Intrinsics** | `/davis/left/camera_info` | `K` (3x3 float64 intrinsics), `D` (distortion parameters), `P` (projection matrix) |
| **IMU-Cam Extrinsics** | `/davis/left/imu_cam_transform` | `imu_cam_transform` (4x4 extrinsic transformation matrix) |

---

## 2. Structured NumPy dtypes

To provide efficient, structured access to event, IMU, and pose streams, the loader parses raw HDF5 data into structured NumPy arrays using the following layout contracts:

### Events (`EVENT_DTYPE`)
Used for the event camera stream:
* `t` (float64): Timestamp in seconds.
* `x` (uint16): Pixel x-coordinate.
* `y` (uint16): Pixel y-coordinate.
* `p` (int8): Polarity (0 or 1).

### IMU (`IMU_DTYPE`)
Used for the linear accelerometer and angular rate sensor stream:
* `t` (float64): Timestamp in seconds.
* `ax`, `ay`, `az` (float64): Linear acceleration along the x, y, and z axes (typically in $m/s^2$).
* `gx`, `gy`, `gz` (float64): Angular velocity around the x, y, and z axes (typically in $rad/s$).

### Poses (`POSE_DTYPE`)
Used for the reference ground-truth trajectory:
* `t` (float64): Timestamp in seconds.
* `x`, `y`, `z` (float64): 3D translation vectors.
* `qx`, `qy`, `qz`, `qw` (float64): Unit quaternion rotation elements.

---

## 3. Timestamp Monotonicity and Validation Rules

* **Monotonicity Check**: Timestamps ($t$) of every sensor stream must be non-decreasing (strictly monotonic $\Delta t \ge 0$). If any timestamp decreases relative to the previous sample ($\Delta t < 0$), the stream is flagged as malformed.
* **Duplicate Timestamps**: Multiple event records can share the exact same timestamp (since multiple events can occur simultaneously). This is allowed and does *not* trigger validation failures.
* **Resolution**: When non-monotonicity is detected, the loader does not crash; instead, it leaves that specific field set to `None`, registers the stream name in `diagnostics.malformed_streams`, and logs the warning.

---

## 4. Calibration Fields

The `Calibration` dataclass manages sensor parameters:
* `intrinsics_available` (bool): True if intrinsic camera matrix `K` is successfully parsed.
* `distortion_available` (bool): True if lens distortion parameters `D` are parsed.
* `extrinsics_available` (bool): True if projection matrix `P` is parsed.
* `imu_cam_transform_available` (bool): True if extrinsic IMU-camera transform `imu_cam_transform` is parsed.
* `data` (dict): Dictionary mapping string keys (`K`, `D`, `P`, `imu_cam_transform`) to their raw NumPy matrices.

---

## 5. Diagnostic Semantics

The loader implements robust diagnostic capture via `LoadDiagnostics`:
* `missing_streams` (list[str]): Lists streams that were entirely missing from the HDF5 file (e.g., `['gt_poses']`).
* `malformed_streams` (list[str]): Lists streams present in the file but failing validation (e.g., non-monotonic timestamps or missing child datasets).
* `layout_mismatch` (bool): Set to `True` if any group lacks critical datasets (e.g., `/davis/left/events` exists, but has no `ts` dataset).
* `layout_errors` (list[str]): Detailed string messages explaining the layout mismatches or timestamp anomalies.

---

## 6. Output Metadata and Sequence Shape

The output of `load_mvsec_sequence` is encapsulated in `MvsecSequence`:
* `metadata` (`SequenceMetadata`):
  * `source_path` (str): Absolute or relative system path to the source H5 file.
  * `sequence_name` (str): Stem of the filename (e.g., `outdoor_day1`).
  * `time_ranges` (dict[str, tuple[float, float]]): Start and end timestamps for each successfully loaded stream.
  * `sample_counts` (dict[str, int]): Number of samples loaded per stream.
* `diagnostics` (`LoadDiagnostics`): Diagnostics information as described above.
* `calibration` (`Calibration`): Sensor calibration parameters.
* Sensor fields (each `None` if missing or malformed):
  * `events`: `np.ndarray` of `EVENT_DTYPE`
  * `imu`: `np.ndarray` of `IMU_DTYPE`
  * `gt_poses`: `np.ndarray` of `POSE_DTYPE`
  * `images`: `np.ndarray` of shape `(N, H, W)` and type `uint8`
  * `image_timestamps`: `np.ndarray` of type `float64`

---

## 7. Typical Sequence Paths

Standard sequences from the MVSEC dataset include:
* **Outdoor Sequences**:
  * `outdoor_day1`: Fast vehicle sequences with high dynamic range and rich structures.
  * `outdoor_day2`
* **Indoor Flying Sequences** (helpful for debugging and rapid baseline iteration):
  * `indoor_flying1`
  * `indoor_flying2`
  * `indoor_flying3`
