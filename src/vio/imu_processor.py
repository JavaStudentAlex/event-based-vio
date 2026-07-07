import math
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class IMUSample:
    """
    Minimal IMU sample for schema-validation flow.

    Attributes
    ----------
    t: float
        Timestamp in seconds.
    ax, ay, az: float
        Linear acceleration (m/s^2) in body frame.
    gx, gy, gz: float
        Angular velocity (rad/s) in body frame.
    """

    t: float
    ax: float
    ay: float
    az: float
    gx: float
    gy: float
    gz: float


class IMUProcessor:
    """
    Tiny IMU integrator stub: integrates angular rates to a quaternion
    with a fixed small dt assumption per step (derived from sample deltas).

    This is intentionally simple and deterministic for S02 schema checks.
    """

    def __init__(self):
        # Identity quaternion (x,y,z,w)
        self.q = (0.0, 0.0, 0.0, 1.0)
        self.t_last: float | None = None

    @staticmethod
    def _quat_mul(a: tuple[float, float, float, float], b: tuple[float, float, float, float]):
        ax, ay, az, aw = a
        bx, by, bz, bw = b
        return (
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw,
            aw * bw - ax * bx - ay * by - az * bz,
        )

    @staticmethod
    def _axis_angle_to_quat(axis: tuple[float, float, float], angle: float):
        x, y, z = axis
        half = 0.5 * angle
        s = math.sin(half)
        c = math.cos(half)
        return (x * s, y * s, z * s, c)

    def step(self, samples: Iterable[IMUSample]) -> tuple[float, float, float, float]:
        for s in samples:
            if self.t_last is None:
                self.t_last = s.t
                continue
            dt = max(0.0, float(s.t - self.t_last))
            self.t_last = s.t
            # Integrate small rotation from gyro
            angle = math.sqrt(s.gx * s.gx + s.gy * s.gy + s.gz * s.gz) * dt
            if angle > 0.0:
                axis = (
                    s.gx / (1e-12 + abs(s.gx) + abs(s.gy) + abs(s.gz)),
                    s.gy / (1e-12 + abs(s.gx) + abs(s.gy) + abs(s.gz)),
                    s.gz / (1e-12 + abs(s.gx) + abs(s.gy) + abs(s.gz)),
                )
                dq = self._axis_angle_to_quat(axis, angle)
                self.q = self._quat_mul(self.q, dq)
        return self.q
