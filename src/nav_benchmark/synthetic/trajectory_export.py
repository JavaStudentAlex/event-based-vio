"""Convert the raw drone state log into a metric ground-truth trajectory.

Reads ``metadata/raw_state_log.csv`` (lat/lon/alt/heading/speed) and writes
``ground_truth/trajectory.csv`` in the local ENU frame:

    timestamp_s,x_m,y_m,z_m,yaw_deg,qx,qy,qz,qw,vx_mps,vy_mps,vz_mps

Conventions (see :mod:`nav_benchmark.synthetic.geo`): ENU positions, yaw = compass
heading (0=N, 90=E), roll = pitch = 0, quaternion in (qx, qy, qz, qw) order, velocity
derived from heading and speed.
"""

import csv
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from nav_benchmark.synthetic.geo import enu_from_geo

TRAJECTORY_HEADER = [
    "timestamp_s",
    "x_m",
    "y_m",
    "z_m",
    "yaw_deg",
    "qx",
    "qy",
    "qz",
    "qw",
    "vx_mps",
    "vy_mps",
    "vz_mps",
]


@dataclass
class TrajectoryArrays:
    t: np.ndarray
    x: np.ndarray
    y: np.ndarray
    z: np.ndarray
    yaw_deg: np.ndarray
    quat_xyzw: np.ndarray  # (N, 4)
    vx: np.ndarray
    vy: np.ndarray
    vz: np.ndarray
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0)  # (lat0, lon0, alt0)


def compute_trajectory(
    t: np.ndarray,
    lat: np.ndarray,
    lon: np.ndarray,
    alt: np.ndarray,
    heading_deg: np.ndarray,
    speed_mps: np.ndarray,
) -> TrajectoryArrays:
    """Compute ENU positions, yaw quaternions, and velocities from a raw state log.

    The first sample defines the local origin, so it maps to ``(x, y) = (0, 0)``.
    """
    t = np.asarray(t, dtype=np.float64)
    lat = np.asarray(lat, dtype=np.float64)
    lon = np.asarray(lon, dtype=np.float64)
    alt = np.asarray(alt, dtype=np.float64)
    heading_deg = np.asarray(heading_deg, dtype=np.float64)
    speed_mps = np.asarray(speed_mps, dtype=np.float64)

    if t.size == 0:
        raise ValueError("Cannot build a trajectory from an empty state log")

    lat0, lon0, alt0 = float(lat[0]), float(lon[0]), float(alt[0])
    x, y, z = enu_from_geo(lat, lon, alt, lat0, lon0, alt0)

    yaw_rad = np.radians(heading_deg)
    # Pure yaw rotation about +z (ENU up); quaternion in (qx, qy, qz, qw) order.
    half = 0.5 * yaw_rad
    quat = np.zeros((yaw_rad.size, 4), dtype=np.float64)
    quat[:, 2] = np.sin(half)
    quat[:, 3] = np.cos(half)

    vx = speed_mps * np.sin(yaw_rad)
    vy = speed_mps * np.cos(yaw_rad)
    vz = np.zeros_like(vx)

    return TrajectoryArrays(
        t=t,
        x=np.asarray(x, dtype=np.float64),
        y=np.asarray(y, dtype=np.float64),
        z=np.asarray(z, dtype=np.float64),
        yaw_deg=heading_deg,
        quat_xyzw=quat,
        vx=vx,
        vy=vy,
        vz=vz,
        origin=(lat0, lon0, alt0),
    )


def write_trajectory_csv(traj: TrajectoryArrays, path: str | Path) -> int:
    """Write a :class:`TrajectoryArrays` to the ground-truth CSV schema. Returns row count."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    n = traj.t.size
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(TRAJECTORY_HEADER)
        for i in range(n):
            qx, qy, qz, qw = traj.quat_xyzw[i]
            writer.writerow(
                [
                    f"{traj.t[i]:.6f}",
                    f"{traj.x[i]:.6f}",
                    f"{traj.y[i]:.6f}",
                    f"{traj.z[i]:.6f}",
                    f"{traj.yaw_deg[i]:.6f}",
                    f"{qx:.9f}",
                    f"{qy:.9f}",
                    f"{qz:.9f}",
                    f"{qw:.9f}",
                    f"{traj.vx[i]:.6f}",
                    f"{traj.vy[i]:.6f}",
                    f"{traj.vz[i]:.6f}",
                ]
            )
    return n


def _read_raw_state_log(path: str | Path) -> dict[str, np.ndarray]:
    data = np.loadtxt(path, delimiter=",", skiprows=1, ndmin=2)
    if data.shape[1] < 6:
        raise ValueError(f"raw_state_log.csv must have 6 columns, got {data.shape[1]}")
    return {
        "t": data[:, 0],
        "lat": data[:, 1],
        "lon": data[:, 2],
        "alt": data[:, 3],
        "heading_deg": data[:, 4],
        "speed_mps": data[:, 5],
    }


def export_trajectory(raw_state_log_path: str | Path, out_path: str | Path) -> TrajectoryArrays:
    """Read a raw state log and write the metric ground-truth trajectory CSV."""
    raw_state_log_path = Path(raw_state_log_path)
    if not raw_state_log_path.exists():
        raise FileNotFoundError(f"raw state log not found: {raw_state_log_path}")
    cols = _read_raw_state_log(raw_state_log_path)
    traj = compute_trajectory(cols["t"], cols["lat"], cols["lon"], cols["alt"], cols["heading_deg"], cols["speed_mps"])
    write_trajectory_csv(traj, out_path)
    return traj
