"""Generate a plausible synthetic IMU stream from the metric ground-truth trajectory (Phase 4).

This is *synthetic* IMU: a constant-speed straight segment reads mostly gravity plus small
noise, while turns produce a non-zero yaw rate (``gz``) and lateral (body-y) acceleration.

Body frame convention: x = forward (heading direction), y = left, z = up. Following the task,
``az`` is reported as ``-gravity`` (plus any vertical acceleration), i.e. the accelerometer reads
the negative gravity vector at rest.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nav_benchmark.synthetic.config import ImuCfg

IMU_HEADER = ["timestamp_s", "ax_mps2", "ay_mps2", "az_mps2", "gx_radps", "gy_radps", "gz_radps"]


@dataclass
class ImuArrays:
    t: np.ndarray
    ax: np.ndarray
    ay: np.ndarray
    az: np.ndarray
    gx: np.ndarray
    gy: np.ndarray
    gz: np.ndarray

    def __len__(self) -> int:
        return int(self.t.size)


def _imu_sample_times(t0: float, t_end: float, rate_hz: float) -> np.ndarray:
    dt = 1.0 / rate_hz
    n = int(np.floor((t_end - t0) / dt + 1e-9)) + 1
    n = max(n, 1)
    return t0 + dt * np.arange(n, dtype=np.float64)


def _add_noise_and_bias(
    values: np.ndarray, noise_std: float, bias_walk_std: float, rng: np.random.Generator
) -> np.ndarray:
    bias = np.cumsum(rng.normal(0.0, bias_walk_std, size=values.shape), axis=0) if bias_walk_std > 0 else 0.0
    noise = rng.normal(0.0, noise_std, size=values.shape) if noise_std > 0 else 0.0
    return values + bias + noise


def synthesize_imu(
    t_traj: np.ndarray,
    yaw_deg_traj: np.ndarray,
    vx_traj: np.ndarray,
    vy_traj: np.ndarray,
    vz_traj: np.ndarray,
    imu_cfg: ImuCfg,
    random_seed: int = 42,
    add_noise: bool = True,
) -> ImuArrays:
    """Resample the trajectory to ``imu_cfg.rate_hz`` and synthesize accel + gyro samples."""
    t_traj = np.asarray(t_traj, dtype=np.float64)
    if t_traj.size < 2:
        raise ValueError("IMU synthesis needs at least 2 trajectory samples")

    t = _imu_sample_times(float(t_traj[0]), float(t_traj[-1]), imu_cfg.rate_hz)
    dt = 1.0 / imu_cfg.rate_hz

    # Resample yaw (unwrapped) and world-frame velocity onto the IMU clock.
    yaw_unwrapped = np.unwrap(np.radians(np.asarray(yaw_deg_traj, dtype=np.float64)))
    yaw = np.interp(t, t_traj, yaw_unwrapped)
    vx = np.interp(t, t_traj, np.asarray(vx_traj, dtype=np.float64))
    vy = np.interp(t, t_traj, np.asarray(vy_traj, dtype=np.float64))
    vz = np.interp(t, t_traj, np.asarray(vz_traj, dtype=np.float64))

    # Yaw rate -> gz; world acceleration via finite differences.
    gz = np.gradient(yaw, dt)
    ax_w = np.gradient(vx, dt)
    ay_w = np.gradient(vy, dt)
    az_w = np.gradient(vz, dt)

    # Rotate horizontal world acceleration into the body frame (x=forward, y=left).
    cos_y, sin_y = np.cos(yaw), np.sin(yaw)
    ax_body = ax_w * sin_y + ay_w * cos_y
    ay_body = -ax_w * cos_y + ay_w * sin_y
    az_body = az_w - imu_cfg.gravity_mps2  # accelerometer reads -gravity at rest

    gx = np.zeros_like(t)
    gy = np.zeros_like(t)

    if add_noise:
        seed = random_seed if imu_cfg.deterministic_noise else None
        rng = np.random.default_rng(seed)
        accel = np.stack([ax_body, ay_body, az_body], axis=1)
        gyro = np.stack([gx, gy, gz], axis=1)
        accel = _add_noise_and_bias(accel, imu_cfg.accel_noise_std, imu_cfg.accel_bias_walk_std, rng)
        gyro = _add_noise_and_bias(gyro, imu_cfg.gyro_noise_std, imu_cfg.gyro_bias_walk_std, rng)
        ax_body, ay_body, az_body = accel[:, 0], accel[:, 1], accel[:, 2]
        gx, gy, gz = gyro[:, 0], gyro[:, 1], gyro[:, 2]

    return ImuArrays(t=t, ax=ax_body, ay=ay_body, az=az_body, gx=gx, gy=gy, gz=gz)


def write_imu_csv(imu: ImuArrays, path: str | Path) -> int:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(IMU_HEADER)
        for i in range(len(imu)):
            writer.writerow(
                [
                    f"{imu.t[i]:.6f}",
                    f"{imu.ax[i]:.6f}",
                    f"{imu.ay[i]:.6f}",
                    f"{imu.az[i]:.6f}",
                    f"{imu.gx[i]:.6f}",
                    f"{imu.gy[i]:.6f}",
                    f"{imu.gz[i]:.6f}",
                ]
            )
    return len(imu)


def imu_from_trajectory_file(
    trajectory_csv: str | Path,
    imu_cfg: ImuCfg,
    out_path: str | Path,
    random_seed: int = 42,
    add_noise: bool = True,
) -> ImuArrays:
    """Read ``ground_truth/trajectory.csv``, synthesize IMU, and write ``imu/imu.csv``."""
    trajectory_csv = Path(trajectory_csv)
    if not trajectory_csv.exists():
        raise FileNotFoundError(f"trajectory not found: {trajectory_csv}")
    data = np.loadtxt(trajectory_csv, delimiter=",", skiprows=1, ndmin=2)
    # Columns: timestamp_s,x,y,z,yaw_deg,qx,qy,qz,qw,vx,vy,vz
    t = data[:, 0]
    yaw_deg = data[:, 4]
    vx, vy, vz = data[:, 9], data[:, 10], data[:, 11]
    imu = synthesize_imu(t, yaw_deg, vx, vy, vz, imu_cfg, random_seed=random_seed, add_noise=add_noise)
    write_imu_csv(imu, out_path)
    return imu
