# Decisions Register

<!-- Append-only. Never edit or remove existing rows.
     To reverse a decision, add a new row that supersedes it.
     Read this file at the start of any planning or research phase. -->

| # | When | Scope | Decision | Choice | Rationale | Revisable? | Made By |
|---|------|-------|----------|--------|-----------|------------|---------|
| D001 | 2026-06-27 | M001-ncx5an | Split the original Event+IMU VIO milestone into three milestones | M001 is MVSEC Pipeline and IMU Sanity Benchmark; M002 is First Event+IMU Odometry Backend; M003 is Strong Baselines and Benchmark Reporting | The source file scope was large enough to couple dataset ingestion, synchronization, baseline implementation, evaluation, reporting, runtime/failure handling, and external wrappers. Splitting lets M001 prove the benchmark harness before Event+IMU and external wrapper complexity. | Yes | User + GSD |
| D002 | 2026-06-27 | M001-ncx5an | Use a real Python package for benchmark code | Implement under `src/nav_benchmark` with dataset, sync, calibration, trajectory, baseline, evaluation, plotting, and CLI modules | A package keeps imports, tests, and backend replacement clean across M001, M002, and M003. | Yes | User + GSD |
| D003 | 2026-06-27 | M001-ncx5an | Use `h5py` for first-pass MVSEC loading | Read MVSEC HDF5 files directly with `h5py`; reserve `rosbags` for raw bag support later | MVSEC streams are available as HDF5 and the project dependency baseline already includes `h5py`. | Yes | User + GSD |
| D004 | 2026-06-27 | M001-ncx5an | Keep project artifacts authoritative and TUM export interoperable | Project CSV and `metrics.json` are the stable contract; TUM export supports SLAM/VIO tools such as `evo` | The project needs custom health, latency, invalid interval, alignment, and drift-over-distance fields that generic tools do not fully cover. | Yes | User + GSD |
| D005 | 2026-06-27 | M001-ncx5an | Default M001 evaluation to explicit SE3 alignment | Timestamp-associate estimates and ground truth, align with SE3 by default, and record policy in metrics/manifest metadata | SE3 alignment makes early results interpretable while frame/calibration assumptions are being hardened, as long as the policy is explicit. | Yes | User + GSD |
| D006 | 2026-06-27 | M001-ncx5an | Define a stable minimal odometry backend interface in M001 | `imu_only`, future `event_imu`, and later wrappers return a common result shape consumed by shared export/evaluation | M002 should add Event+IMU without refactoring the benchmark harness. A rich plugin framework would be premature. | Yes | User + GSD |
| D007 | 2026-06-27 | M001-ncx5an | Store generated benchmark outputs under `runs/` | Generated run artifacts live under `runs/` and should stay untracked | This matches the desired CLI examples and separates generated artifacts from source/config/docs. | Yes | User + GSD |
