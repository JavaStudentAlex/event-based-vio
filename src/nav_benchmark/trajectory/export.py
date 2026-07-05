import csv
from pathlib import Path

import numpy as np

from nav_benchmark.trajectory.models import ExportMetadata, PoseHealth, Trajectory

PROJECT_TRAJECTORY_COLUMNS = [
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

    row = [
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
    for values in trajectory.extra_columns.values():
        value = values[i]
        if isinstance(value, str):
            row.append(value)
        else:
            row.append(_fmt_opt(float(value), 9))
    return row


def export_project_csv(trajectory: Trajectory, path: str | Path, metadata: ExportMetadata | None = None) -> None:
    """
    Exports a trajectory to the fixed project CSV schema:
    timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms

    Preserves all invalid/degraded rows with their health labels.
    """
    path = Path(path)

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([*PROJECT_TRAJECTORY_COLUMNS, *trajectory.extra_columns.keys()])

        for i in range(len(trajectory.timestamps)):
            row = _get_row(trajectory, i)
            writer.writerow(row)

            if metadata is not None:
                health = row[13]
                if health not in metadata.health_counts:
                    metadata.health_counts[health] = 0
                metadata.health_counts[health] += 1


def _parse_tum_row(line: str, line_number: int) -> list[float]:
    parts = line.split()
    if len(parts) != 8:
        raise ValueError(f"TUM line {line_number} has {len(parts)} fields, expected 8")
    try:
        return [float(part) for part in parts]
    except ValueError as exc:
        raise ValueError(f"TUM line {line_number} has a non-numeric field") from exc


def read_tum_trajectory(path: str | Path, *, method: str = "external") -> Trajectory:
    """Read a TUM trajectory file (``timestamp x y z qx qy qz qw``) into the project model.

    Blank lines and ``#`` comments are skipped. Timestamps must be strictly increasing.
    """
    path = Path(path)
    rows: list[list[float]] = []
    with open(path, encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            rows.append(_parse_tum_row(line, line_number))

    if not rows:
        raise ValueError(f"TUM trajectory {path} contains no pose rows")

    values = np.asarray(rows, dtype=np.float64)
    timestamps = values[:, 0]
    if np.any(np.diff(timestamps) <= 0.0):
        raise ValueError(f"TUM trajectory {path} timestamps are not strictly increasing")

    return Trajectory(
        timestamps=timestamps,
        method=method,
        positions=values[:, 1:4],
        orientations=values[:, 4:8],
    )


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
