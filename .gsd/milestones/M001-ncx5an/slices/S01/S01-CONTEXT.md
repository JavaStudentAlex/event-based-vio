---
id: S01
milestone: M001-ncx5an
status: ready
---

# S01: MVSEC Loader and Stream Contract — Context

<!-- Slice-scoped context. Milestone-only sections (acceptance criteria, completion class,
     milestone sequence) do not belong here — those live in the milestone context. -->

## Goal

Deliver a loader that reads MVSEC-style HDF5 files (real or synthetic) into a common sequence dataclass carrying events, IMU, images, ground-truth poses, calibration, timestamp metadata, and per-stream diagnostics.

## Why this Slice

Every downstream slice — synchronization (S02), the IMU backend (S03), evaluation (S04), and CI artifact validation (S05) — depends on a trustworthy, contract-stable sequence object. S01 establishes the data shapes, timestamp guarantees, and diagnostic surface that the rest of M001 builds on. It also produces the synthetic fixture that makes all CI tests possible without MVSEC downloads.

## Scope

### In Scope

- MVSEC HDF5 loader using `h5py` with a hardcoded path table for known group names (`/davis/left/events`, `/davis/left/imu`, etc.).
- Diagnostic diff on layout mismatch: loader reports found-vs-expected HDF5 paths with a clear error.
- Per-stream diagnostics: each stream is tagged present, missing, or malformed. The loader returns whatever it can load; the caller decides what absence is fatal.
- Timestamp validation: reject any stream whose timestamps are non-monotonic or contain duplicates. Downstream code is guaranteed clean, monotonic timestamps.
- Event camera data stored as a structured NumPy array with dtype `(t: float64, x: uint16, y: uint16, p: int8)`.
- IMU data stored as a structured NumPy array with dtype `(t: float64, ax, ay, az, gx, gy, gz: float64)`.
- Ground-truth poses stored as a structured NumPy array `(t, x, y, z, qx, qy, qz, qw: float64)`. Raw timestamps, no resampling or interpolation — S02 owns that.
- Grayscale images loaded eagerly as `(N, H, W)` uint8 with a matching timestamp array. Keeps the sequence object complete even though `imu_only` does not use images.
- Calibration: parse and attach whatever the HDF5 file provides (camera intrinsics, distortion, extrinsics, IMU-camera transforms). If absent, diagnostics note it but the loader still returns.
- Sequence object is a plain Python dataclass — data container only. No iteration, replay, time-window slicing, or sync logic; those belong to S02.
- Sequence metadata: source file path, sequence name, per-stream time ranges, sample counts.
- Synthetic MVSEC-like HDF5 fixture: schema-correct minimal stubs with correct group structure, column shapes, dtypes, and monotonic timestamps. Values are simple (zeros, constants, tiny counts). Tests the loader contract, not physical realism.
- Unit tests covering: successful load, per-stream diagnostics for missing/malformed streams, timestamp rejection for non-monotonic and duplicate cases, layout mismatch diagnostics, calibration presence and absence, dtype and shape validation.

### Out of Scope

- Timestamp resampling, interpolation, or synchronization across streams (S02).
- Time-window accessors, iterator/replay API, or any sync logic on the sequence object (S02).
- Trajectory export or CSV/TUM writing (S02).
- Odometry backend interface or IMU integration (S03).
- Evaluation, metrics, or plotting (S04).
- Physically plausible synthetic fixtures with known motion — deferred to S02/S03 when numerical end-to-end checks are needed.
- `rosbags` support for raw `.bag` files — deferred until needed.
- Auto-discovery of HDF5 layout by shape heuristics — explicit path table only.
- Configurable YAML-based path mapping — hardcoded table is sufficient for M001.

## Constraints

- Python 3.13, `uv`, dependencies from `pyproject.toml` (specifically `h5py`, `numpy`).
- Tests must run without MVSEC downloads — synthetic fixture only.
- Quaternion ordering is `qx, qy, qz, qw` to match the project CSV schema.
- Timestamp units are seconds (float64).
- No raw MVSEC archives, generated outputs, or large caches committed to the repo.
- Loader must respect D003 (`h5py` for first-pass access).

## Integration Points

### Consumes

- MVSEC HDF5 files (real, manual runs) — `outdoor_day1` primary, `indoor_flying1` debug fallback.
- Synthetic HDF5 fixture (CI) — built by this slice.

### Produces

- `MvsecSequence` dataclass — common sequence object consumed by S02 (sync), S03 (backend), and beyond.
- `LoadDiagnostics` — per-stream presence/absence/malformation report, timestamp validation results, layout match status.
- `Calibration` dataclass — parsed calibration fields with per-field availability diagnostics.
- `SequenceMetadata` — source path, sequence name, per-stream time ranges and sample counts.
- Synthetic HDF5 fixture file — reused by S02–S05 loader-level tests.
- Loader module at `src/nav_benchmark/datasets/mvsec.py`.

## Open Questions

- Exact MVSEC HDF5 group paths for `outdoor_day1` and `indoor_flying1` must be verified during implementation. The hardcoded path table should be validated against available documentation or sample files, and updated if paths differ by sequence. — Current thinking: start with documented paths, fail loudly on mismatch, update the table when real files are tested.
- Whether ground-truth poses in MVSEC are body-frame or sensor-frame, and which quaternion convention they use, needs to be checked and documented. — Current thinking: load raw, document discovered convention, and let S02/evaluation handle any frame conversion.
