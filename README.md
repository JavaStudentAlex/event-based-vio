# Event-Based VIO

This repository is for an MVSEC-based ensemble navigation pipeline for
GPS-denied visual-inertial odometry. The goal is to compare IMU-only,
image+IMU, event+IMU, multimodal VIO, and a deterministic ensemble on the same
dataset sequence with the same trajectory schema and evaluation protocol.

The working project plan is in `gsd_mvsec_ensemble_plan.md`. Agent-facing
repository instructions are in `AGENTS.md`.

## Current Benchmark Target

- Dataset: MVSEC
- First sequence: `outdoor_day1`
- Debug fallback: `indoor_flying1`
- Streams: IMU, event camera, grayscale frames, ground-truth poses
- Core metrics: ATE, RPE, drift every 20 m, total drift, tracking failures,
  invalid-pose intervals, latency, and odometry frequency

## Development

Python and tooling are managed with `uv` and `pyproject.toml`.

```bash
uv sync --group dev
uv run --only-dev ruff check .
uv run --only-dev ruff format --check .
uv run pytest tests -q
```

The initial runtime dependencies cover four needs: reading MVSEC data,
processing events/images/IMU, evaluating trajectories, and later testing
ensemble or fusion logic. MVSEC streams can be read from HDF5 files that mirror
ROS bag structure, so the first loader should use `h5py` before requiring a full
ROS stack.

| Library | Why it is used |
| --- | --- |
| `numpy` | Arrays for events, IMU data, images, and trajectories |
| `scipy` | Rotations, interpolation, filtering, and transforms |
| `pandas` | CSV trajectory logs and metrics tables |
| `matplotlib` | Trajectory and error plots |
| `opencv-python` | Image handling, feature extraction, edge maps, and map anchoring prototypes |
| `h5py` | MVSEC HDF5 reading |
| `rosbags` | Reading `.bag` files without installing full ROS |
| `evo` | Standard odometry/SLAM ATE, RPE, and trajectory comparison |
| `pyyaml` | Dataset, baseline, and metric configuration files |
| `tqdm` | Progress bars for replay and evaluation |
| `rich` | Readable terminal logging and debugging |
| `scikit-learn` | Later ensemble gating, calibration, and lightweight fusion experiments |

Raw datasets, extracted MVSEC files, generated trajectories, plots, local
caches, and virtual environments should stay untracked.
