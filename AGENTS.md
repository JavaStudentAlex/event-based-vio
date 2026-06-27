@/home/jovyan/.codex/RTK.md

# Agent Instructions: Event-Based VIO

## Project Mission

This repository implements and benchmarks an MVSEC-based ensemble navigation
pipeline for GPS-denied visual-inertial navigation. The system combines IMU,
grayscale image frames, event-camera streams, and optional future map anchoring
to estimate relative trajectory and compare ensemble performance against
individual odometry baselines.

The project source of truth is:

1. `gsd_mvsec_ensemble_plan.md`
2. `pyproject.toml`
3. `.github/instructions/*.instructions.md`
4. `.github/agents/*.agent.md`
5. `.github/skills/*/SKILL.md`

If these files disagree, follow the plan file first and update the instruction
files as part of the same change.

## Current Scope

Start narrow and reproducible:

- Dataset: MVSEC
- First target sequence: `outdoor_day1`
- Easier debug fallback: `indoor_flying1`
- Sensor streams: IMU, event camera, grayscale frames, ground-truth poses
- First benchmark contract: fixed metrics, fixed output format, fixed
  evaluation protocol

Do not start with learned/RL gating, embedded deployment, or map anchoring until
the deterministic benchmark, baselines, and ensemble v1 are working.

## Dependency Baseline

The initial Python environment must cover four project needs:

1. read MVSEC data
2. process events, images, and IMU streams
3. evaluate trajectories
4. train or test ensemble/fusion logic later

MVSEC streams are available as HDF5 files that mirror ROS bag structure, so
prefer `h5py` for first-pass dataset loading and use `rosbags` when raw `.bag`
support is required. `pyproject.toml` already contains the first dependency
set:

- `numpy`: arrays for events, IMU samples, images, and trajectories
- `scipy`: rotations, interpolation, filtering, and transforms
- `pandas`: CSV trajectory logs and metrics tables
- `matplotlib`: trajectory and error plots
- `opencv-python`: image handling, feature extraction, edge maps, and map
  anchoring prototypes
- `h5py`: MVSEC HDF5 reading
- `rosbags`: ROS bag reading without a full ROS install
- `evo`: standard odometry/SLAM ATE, RPE, and trajectory comparison
- `pyyaml`: dataset, baseline, and metric configuration files
- `tqdm`: progress bars for replay and evaluation
- `rich`: readable terminal logging and debug output
- `scikit-learn`: later ensemble gating, calibration, and lightweight fusion
  experiments

## Required Trajectory Output

Every method must export the same CSV schema:

```text
timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms
```

Use these method names unless a task requires a narrower variant:

- `imu_only`
- `image_imu`
- `event_imu`
- `multimodal_vio`
- `ensemble`

Timestamps are seconds. Quaternions are `qx,qy,qz,qw`. Health values should be
stable machine-readable labels such as `OK`, `DEGRADED`, `LOST`, or `INVALID`.

## Agents We Use

Use specialized agents only when their scope matches the task:

- `dataset-pipeline-engineer`: MVSEC loading, conversion, replay,
  synchronization, calibration handling, and deterministic sensor iteration.
- `vio-baseline-engineer`: IMU-only propagation, image+IMU baseline adapters,
  event+IMU baseline adapters, multimodal baseline adapters, and common
  trajectory export.
- `evaluation-ensemble-engineer`: ATE/RPE/drift metrics, latency/failure
  reporting, trajectory plotting, health scoring, deterministic fusion, and
  benchmark comparisons.

Do not add roles outside dataset replay, baseline integration, evaluation, and
ensemble fusion unless the project plan expands.

## Repository Skills

Project-local skills live under `.github/skills/`:

- `mvsec-benchmarking`: use for benchmark protocol, trajectory schema,
  evaluator, plotting, and reproducibility changes.
- `python-linting`: use after Python source, tests, or tooling changes.
- `python-testing`: use when adding or changing tests or behavior that can be
  checked with pytest.

Do not add stochastic/random-choice skills for benchmark decisions. Benchmark
selection, seeded experiments, metrics, and result claims must be deterministic
and reproducible.

## Coding Rules

- Use Python 3.13 and `uv`; `pyproject.toml` is the dependency and tooling
  source of truth.
- When running shell commands in Codex, prefix commands with `rtk`.
- Keep dataset IO, synchronization, baseline execution, evaluation, and plotting
  in separate modules once code exists.
- Prefer deterministic functions with explicit inputs and outputs.
- Use structured parsers for HDF5, ROS bag, YAML, CSV, and NumPy arrays instead
  of ad hoc text parsing.
- Keep coordinate frames, timestamp units, interpolation policy, alignment
  policy, and quaternion ordering explicit in code and tests.
- Do not commit raw MVSEC archives, extracted large datasets, generated
  trajectories, plots, notebooks with bulky outputs, local caches, secrets, or
  virtual environments.
- Document any external baseline dependency that is not installable through
  `pyproject.toml`.

## Benchmark Rules

- Compare the ensemble against the best individual baseline, not only against
  IMU-only.
- Use the same sequence, time range, alignment policy, and metrics for every
  method in a comparison.
- Track the following required metrics:
  - **Core Trajectory:** ATE, RPE, drift every 20 m, and total drift.
  - **Robustness:** tracking failure rate, invalid-pose intervals, and outlier rate.
  - **Runtime:** latency per update (ms) and odometry frequency.
- Treat missing/invalid poses as benchmark data, not as rows to silently drop.
- Store result metadata with dataset name, sequence, method, commit SHA when
  available, command, and relevant configuration.

## Verification

For Python changes, run the smallest relevant checks first, then broader checks
before claiming completion:

```bash
rtk uv run --only-dev ruff check .
rtk uv run --only-dev ruff format --check .
rtk uv run pytest tests -q
```

If no tests exist yet, say that explicitly and run lint/format checks that can
execute. For benchmark/evaluation changes, include a deterministic smoke test
using tiny synthetic trajectories so correctness does not require downloading
MVSEC.

## PR And Review Notes

PR descriptions should summarize:

- what changed
- why it is needed for the MVSEC benchmark or ensemble plan
- what commands were run
- which dataset-dependent checks were skipped
- any generated artifacts and whether they are intentionally untracked

Code review should prioritize incorrect metrics, timestamp/frame mistakes,
silent data loss, non-reproducible benchmark behavior, and missing tests around
trajectory alignment and evaluator math.
