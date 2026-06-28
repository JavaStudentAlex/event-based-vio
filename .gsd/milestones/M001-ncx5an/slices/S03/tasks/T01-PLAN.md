---
estimated_steps: 7
estimated_files: 3
skills_used: []
---

# T01: Established BaseOdometryBackend contract, implemented ImuOnlyBackend integration model, and verified with synthetic smoke tests.

Why: Establish a minimal, extensible backend contract and provide the IMU-only propagation to return a valid Trajectory for synthetic data.
Do:
- Create `BaseOdometryBackend` in `src/nav_benchmark/baselines/base.py` with `run(sequence, *, config) -> Trajectory`.
- Implement `ImuOnlyBackend` in `src/nav_benchmark/baselines/imu.py` with simple gyro/acc integration (gravity removal), and health labeling per S03 defaults.
- Add `ImuOnlyConfig` dataclass (gravity, initial pose/velocity, thresholds).
- Write `tests/baselines/test_imu_only_smoke.py` using a tiny synthetic IMU snippet to assert Trajectory shape, monotonic timestamps, fixed method name `imu_only`, and health labels present.
Done when: Test passes and ruff finds no issues.

## Inputs

- `src/nav_benchmark/trajectory/models.py`

## Expected Output

- `src/nav_benchmark/baselines/base.py`
- `src/nav_benchmark/baselines/imu.py`
- `tests/baselines/test_imu_only_smoke.py`

## Verification

rtk uv run pytest tests/baselines/test_imu_only_smoke.py -q
