# Manual MVSEC Runs

This documents how to execute the benchmark against real MVSEC data and records
one performed reference run. Raw MVSEC archives and generated run artifacts are
never committed (`data/` and `runs/` are gitignored).

## 1. Download

```bash
bash scripts/download_mvsec.sh
```

This fetches the rosbag distribution into `data/`:
`indoor_flying1_{data,gt}.bag` (easier debug sequence, ~3.8 GB) and
`outdoor_day1_{data,gt}.bag` (main benchmark sequence, ~19.2 GB).

## 2. Convert rosbags to the loader's HDF5 layout

The loader (`nav_benchmark.datasets.mvsec.load_mvsec_sequence`) reads an HDF5
layout; the MVSEC download ships rosbags. Convert with the pure-Python
converter (no ROS installation required — it uses the `rosbags` package already
in `pyproject.toml`):

```bash
uv run python scripts/convert_mvsec_bag_to_h5.py \
  --data-bag data/indoor_flying1_data.bag \
  --gt-bag data/indoor_flying1_gt.bag \
  --output data/indoor_flying1_5s20s.h5 \
  --start-sec 5 --duration-sec 15
```

Notes:

- `--start-sec/--duration-sec` slice the sequence; omit them to convert
  everything (slower, larger file).
- `--include-images` also converts `/davis/left/image_raw` frames (needed for
  `rgb_vo`/`image_imu`/`multimodal_vio`; not needed for `imu_only`/`event_imu`).
- Camera intrinsics (`K`) are carried over, so `event_imu` uses the real focal
  length instead of its fallback.

## 3. Run, evaluate, validate, compare

```bash
PYTHONPATH=src uv run python -m nav_benchmark.run run --method imu_only \
  --dataset mvsec --sequence indoor_flying1 \
  --input data/indoor_flying1_5s20s.h5 --output-root runs --evaluate

PYTHONPATH=src uv run python -m nav_benchmark.run run --method event_imu \
  --dataset mvsec --sequence indoor_flying1 \
  --input data/indoor_flying1_5s20s.h5 --output-root runs --evaluate

PYTHONPATH=src uv run python -m nav_benchmark.run validate --latest --method event_imu

PYTHONPATH=src uv run python -m nav_benchmark.run compare \
  --run-dirs runs/<imu_only_run> runs/<event_imu_run> \
  --output runs/comparison_indoor_flying1
```

For `outdoor_day1`, substitute the bag/HDF5 names; it is the preferred
milestone target when disk and time allow, with `indoor_flying1` as the easier
debug fallback.

## Recorded reference run (2026-07-05)

Environment: local dev box, `indoor_flying1` slice `[5 s, 20 s)` converted as
above (3,596,426 events, 15,010 IMU samples at ~1 kHz, 1,270 ground-truth
poses, mean event rate ~240 k events/s). Both runs passed `validate` 11/11 and
wrote the full artifact set.

| metric | imu_only | event_imu |
| --- | --- | --- |
| ATE RMSE [m] | 28.7 | 438.3 |
| drift over distance | 68.0 % | 67.2 % |
| approx. real-time factor | 11.4× | 2.4× |
| latency mean [ms/update] | 0.09 | 0.41 |
| odometry frequency [Hz] | 1001 | 1001 |

`event_imu` pair diagnostics from `run_manifest.json → config.run_diagnostics`:
300 event frames (50 ms windows), 297 of 299 pairs applied a correction, mean
shift confidence 0.79, IMU coverage 1.0, focal length 226.38 px from the
converted calibration.

Honest reading of the numbers (this is exactly what M001/M002 require the
benchmark to expose, not a defect of the harness):

- Open-loop IMU integration on real MVSEC data diverges within seconds; both
  methods drift by hundreds of meters over the 15 s slice.
- The event cue is real and active (0.79 mean confidence, 99% of pairs
  corrected) and slightly reduces drift-over-distance, but with a single
  assumed scene depth and position-only bounded corrections it cannot rescue a
  diverging velocity state; after SE(3) alignment its ATE is worse on this
  slice. The backend reports weak accuracy honestly rather than claiming
  bounded navigation.
- Improving absolute accuracy (velocity-state feedback, per-frame depth, real
  event feature tracking) is strong-baseline work beyond M002's scope.
