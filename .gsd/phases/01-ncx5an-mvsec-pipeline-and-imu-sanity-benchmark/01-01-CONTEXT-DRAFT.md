# S01: MVSEC Loader and Stream Contract — Context (DRAFT)

## Decisions captured

1. **Partial streams:** Load whatever exists, attach per-stream diagnostics (present/missing/malformed), let the caller decide what's fatal.
2. **Timestamp validation:** Validate and reject — non-monotonic or duplicated timestamps cause stream rejection with clear diagnostics. Downstream code is guaranteed clean timestamps.
3. **Synthetic fixtures:** Schema-correct minimal stubs (correct HDF5 group structure, column shapes, timestamp ordering; simple constant/zero values). Tests the loader contract, not physical realism.
4. **Calibration:** Parse and attach whatever calibration the HDF5 file provides. If absent, diagnostics note it but loader still returns.
5. **Event representation:** Structured NumPy array with dtype (t: f8, x: u2, y: u2, p: i1).
6. **Ground truth:** Raw timestamped SE3 poses (t, x, y, z, qx, qy, qz, qw). No resampling or interpolation — S02 handles that.
7. **Sequence object:** Plain dataclass data container. No iteration, replay, or time-window accessors — those are S02 scope.
8. **HDF5 layout:** Hardcoded path table for known MVSEC groups. On mismatch, raise diagnostic showing found vs. expected paths.
9. **Images:** Eagerly load grayscale frames as (N, H, W) uint8 with timestamps, even though imu_only doesn't use them. Keeps the sequence object complete.
