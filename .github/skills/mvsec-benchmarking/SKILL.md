---
name: mvsec-benchmarking
description: Use for MVSEC benchmark protocol, trajectory schema, evaluation metrics, plotting, baseline comparison, health scoring, and deterministic ensemble-fusion changes.
---

# MVSEC Benchmarking Skill

Use this skill when a task touches benchmark design, MVSEC replay,
trajectory output, evaluation metrics, baseline comparison, plots, or ensemble
fusion.

## Source Of Truth

- `gsd_mvsec_ensemble_plan.md`
- `AGENTS.md`
- `pyproject.toml`

## Benchmark Contract

- First dataset: MVSEC
- First sequence: `outdoor_day1`
- Debug fallback: `indoor_flying1`
- Streams: IMU, event camera, grayscale frames, ground-truth poses
- Required methods: `imu_only`, `image_imu`, `event_imu`, `multimodal_vio`,
  `ensemble`

## Library Roles

- Use `h5py` for first-pass MVSEC HDF5 access.
- Use `rosbags` only when raw `.bag` support is needed.
- Use `numpy`, `scipy`, and `opencv-python` for sensor processing,
  interpolation, transforms, and image/event-derived features.
- Use `pandas` for CSV logs and metrics tables.
- Use `evo` for standard trajectory evaluation where its model fits the
  benchmark.
- Use `matplotlib` for plots, `pyyaml` for configuration, `tqdm` for progress,
  and `rich` for readable terminal output.
- Reserve `scikit-learn` for later ensemble gating, calibration, and lightweight
  fusion experiments after deterministic baselines are in place.

Every method must export:

```text
timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms
```

## Evaluation Rules

- Align estimated trajectories to ground truth with an explicit policy.
- Compute ATE, RPE, drift every 20 m, total drift, orientation error, invalid
  pose count, tracking-failure intervals, latency, and odometry frequency.
- Compare the ensemble against the best single baseline, not only IMU-only.
- Keep failed tracking intervals visible in results.
- Record dataset, sequence, method, command/configuration, and commit SHA when
  available.

## Testing Rules

- Use synthetic trajectories for normal unit tests.
- Do not require full MVSEC downloads for ordinary CI.
- Mark full-dataset and external-baseline checks separately.
- Avoid stochastic choices in benchmark setup, metric calculation, and result
  reporting.
