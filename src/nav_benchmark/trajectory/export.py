import csv
from pathlib import Path

import numpy as np

from nav_benchmark.trajectory.models import ExportMetadata, PoseHealth, Trajectory


def _fmt_opt(val: float | None, dec: int) -> str:
    return f"{val:.{dec}f}" if val is not None and val != "" else ""


def _get_val(arr: np.ndarray | None, i: int, j: int | None = None) -> float | None:
    if arr is None:
        return None
    if j is not None:
        return float(arr[i, j])
    return float(arr[i])


def _get_row(trajectory: Trajectory, i: int) -> list[str]:
    ts = float(trajectory.timestamps[i])
    method = trajectory.method
    x, y, z = trajectory.positions[i]
    qx, qy, qz, qw = trajectory.orientations[i]

    vx = _get_val(trajectory.velocities, i, 0)
    vy = _get_val(trajectory.velocities, i, 1)
    vz = _get_val(trajectory.velocities, i, 2)

    conf = _get_val(trajectory.confidence, i)
    health = str(trajectory.health[i]) if trajectory.health is not None else PoseHealth.OK.value
    lat = _get_val(trajectory.latency_ms, i)

    return [
        f"{ts:.9f}",
        method,
        f"{x:.9f}",
        f"{y:.9f}",
        f"{z:.9f}",
        f"{qx:.9f}",
        f"{qy:.9f}",
        f"{qz:.9f}",
        f"{qw:.9f}",
        _fmt_opt(vx, 9),
        _fmt_opt(vy, 9),
        _fmt_opt(vz, 9),
        _fmt_opt(conf, 9),
        health,
        _fmt_opt(lat, 3),
    ]


def export_project_csv(trajectory: Trajectory, path: str | Path, metadata: ExportMetadata | None = None) -> None:
    """
    Exports a trajectory to the fixed project CSV schema:
    timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms

    Preserves all invalid/degraded rows with their health labels.
    """
    path = Path(path)

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "timestamp",
                "method",
                "x",
                "y",
                "z",
                "qx",
                "qy",
                "qz",
                "qw",
                "vx",
                "vy",
                "vz",
                "confidence",
                "health",
                "latency_ms",
            ]
        )

        for i in range(len(trajectory.timestamps)):
            row = _get_row(trajectory, i)
            writer.writerow(row)

            if metadata is not None:
                health = row[13]
                if health not in metadata.health_counts:
                    metadata.health_counts[health] = 0
                metadata.health_counts[health] += 1


def export_tum(trajectory: Trajectory, path: str | Path, metadata: ExportMetadata | None = None) -> int:
    """
    Exports a trajectory to the TUM format: timestamp x y z qx qy qz qw

    Filters out rows where health is not OK or DEGRADED (i.e. filters LOST and INVALID).
    Returns the number of filtered rows.
    """
    path = Path(path)

    filtered_count = 0

    with open(path, "w") as f:
        for i in range(len(trajectory.timestamps)):
            health = str(trajectory.health[i]) if trajectory.health is not None else PoseHealth.OK.value

            if health in (PoseHealth.LOST.value, PoseHealth.INVALID.value):
                filtered_count += 1
                continue

            ts = float(trajectory.timestamps[i])
            x, y, z = trajectory.positions[i]
            qx, qy, qz, qw = trajectory.orientations[i]

            f.write(f"{ts:.9f} {x:.9f} {y:.9f} {z:.9f} {qx:.9f} {qy:.9f} {qz:.9f} {qw:.9f}\n")

    if metadata is not None:
        metadata.tum_filtered_rows = filtered_count

    return filtered_count
