"""Round-trip tests for the MVSEC rosbag → project HDF5 converter."""

from pathlib import Path

import numpy as np
import pytest
from rosbags.rosbag1 import Writer
from rosbags.typesys import Stores, get_types_from_msg, get_typestore

import scripts.convert_mvsec_bag_to_h5 as converter
from nav_benchmark.datasets.mvsec import load_mvsec_sequence

_EVENT_DEF = """uint16 x
uint16 y
time ts
bool polarity
"""

_EVENT_ARRAY_DEF = """std_msgs/Header header
uint32 height
uint32 width
dvs_msgs/Event[] events
"""

_BASE_SEC = 100


def _typestore():
    typestore = get_typestore(Stores.ROS1_NOETIC)
    types = {}
    types.update(get_types_from_msg(_EVENT_DEF, "dvs_msgs/msg/Event"))
    types.update(get_types_from_msg(_EVENT_ARRAY_DEF, "dvs_msgs/msg/EventArray"))
    typestore.register(types)
    return typestore


def _time(typestore, t: float):
    Time = typestore.types["builtin_interfaces/msg/Time"]
    sec = int(t)
    return Time(sec=sec, nanosec=round((t - sec) * 1e9))


def _header(typestore, t: float):
    Header = typestore.types["std_msgs/msg/Header"]
    return Header(seq=0, stamp=_time(typestore, t), frame_id="davis")


def _event_array(typestore, t: float, events: list[tuple[int, int, float, bool]]):
    Event = typestore.types["dvs_msgs/msg/Event"]
    EventArray = typestore.types["dvs_msgs/msg/EventArray"]
    return EventArray(
        header=_header(typestore, t),
        height=8,
        width=8,
        events=[Event(x=x, y=y, ts=_time(typestore, ts), polarity=polarity) for x, y, ts, polarity in events],
    )


def _imu_msg(typestore, t: float, ax: float):
    Imu = typestore.types["sensor_msgs/msg/Imu"]
    Quaternion = typestore.types["geometry_msgs/msg/Quaternion"]
    Vector3 = typestore.types["geometry_msgs/msg/Vector3"]
    covariance = np.zeros(9, dtype=np.float64)
    return Imu(
        header=_header(typestore, t),
        orientation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0),
        orientation_covariance=covariance,
        angular_velocity=Vector3(x=0.01, y=0.02, z=0.03),
        angular_velocity_covariance=covariance,
        linear_acceleration=Vector3(x=ax, y=0.0, z=9.81),
        linear_acceleration_covariance=covariance,
    )


def _camera_info_msg(typestore, t: float):
    CameraInfo = typestore.types["sensor_msgs/msg/CameraInfo"]
    RegionOfInterest = typestore.types["sensor_msgs/msg/RegionOfInterest"]
    return CameraInfo(
        header=_header(typestore, t),
        height=8,
        width=8,
        distortion_model="plumb_bob",
        D=np.zeros(4, dtype=np.float64),
        K=np.array([226.5, 0.0, 4.0, 0.0, 226.5, 4.0, 0.0, 0.0, 1.0]),
        R=np.eye(3, dtype=np.float64).reshape(-1),
        P=np.zeros(12, dtype=np.float64),
        binning_x=0,
        binning_y=0,
        roi=RegionOfInterest(x_offset=0, y_offset=0, height=0, width=0, do_rectify=False),
    )


def _image_msg(typestore, t: float, seed: int):
    Image = typestore.types["sensor_msgs/msg/Image"]
    rng = np.random.default_rng(seed)
    pixels = rng.integers(0, 255, size=(8, 8), dtype=np.uint8)
    return Image(
        header=_header(typestore, t),
        height=8,
        width=8,
        encoding="mono8",
        is_bigendian=0,
        step=8,
        data=pixels.reshape(-1),
    )


def _pose_msg(typestore, t: float, x: float):
    PoseStamped = typestore.types["geometry_msgs/msg/PoseStamped"]
    Pose = typestore.types["geometry_msgs/msg/Pose"]
    Point = typestore.types["geometry_msgs/msg/Point"]
    Quaternion = typestore.types["geometry_msgs/msg/Quaternion"]
    return PoseStamped(
        header=_header(typestore, t),
        pose=Pose(position=Point(x=x, y=0.5, z=1.0), orientation=Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)),
    )


def _write(writer: Writer, connection, typestore, msg, t: float) -> None:
    writer.write(connection, int(t * 1e9), typestore.serialize_ros1(msg, msg.__msgtype__))


@pytest.fixture(scope="module")
def mvsec_bags(tmp_path_factory) -> tuple[Path, Path]:
    root = tmp_path_factory.mktemp("bags")
    typestore = _typestore()

    data_bag = root / "mini_data.bag"
    with Writer(data_bag) as writer:
        events_conn = writer.add_connection("/davis/left/events", "dvs_msgs/msg/EventArray", typestore=typestore)
        imu_conn = writer.add_connection("/davis/left/imu", "sensor_msgs/msg/Imu", typestore=typestore)
        info_conn = writer.add_connection("/davis/left/camera_info", "sensor_msgs/msg/CameraInfo", typestore=typestore)
        image_conn = writer.add_connection("/davis/left/image_raw", "sensor_msgs/msg/Image", typestore=typestore)

        base = float(_BASE_SEC)
        first_events = [(1, 2, base + 0.05, True), (3, 4, base + 0.10, False), (5, 6, base + 0.15, True)]
        second_events = [(2, 2, base + 0.60, False), (7, 7, base + 0.70, True)]
        _write(writer, events_conn, typestore, _event_array(typestore, base + 0.05, first_events), base + 0.05)
        _write(writer, events_conn, typestore, _event_array(typestore, base + 0.60, second_events), base + 0.60)

        for i in range(5):
            t = base + 0.2 * i
            _write(writer, imu_conn, typestore, _imu_msg(typestore, t, ax=0.1 * i), t)

        _write(writer, info_conn, typestore, _camera_info_msg(typestore, base), base)
        _write(writer, image_conn, typestore, _image_msg(typestore, base + 0.1, seed=1), base + 0.1)
        _write(writer, image_conn, typestore, _image_msg(typestore, base + 0.5, seed=2), base + 0.5)

    gt_bag = root / "mini_gt.bag"
    with Writer(gt_bag) as writer:
        pose_conn = writer.add_connection("/davis/left/pose", "geometry_msgs/msg/PoseStamped", typestore=typestore)
        for i in range(3):
            t = float(_BASE_SEC) + 0.3 * i
            _write(writer, pose_conn, typestore, _pose_msg(typestore, t, x=float(i)), t)

    return data_bag, gt_bag


class TestFullConversion:
    def test_round_trip_through_loader(self, mvsec_bags, tmp_path):
        data_bag, gt_bag = mvsec_bags
        output = tmp_path / "mini.h5"

        rc = converter.main(
            [
                "--data-bag",
                str(data_bag),
                "--gt-bag",
                str(gt_bag),
                "--output",
                str(output),
                "--include-images",
            ]
        )
        assert rc == 0

        sequence = load_mvsec_sequence(output)
        assert sequence.events is not None and len(sequence.events) == 5
        assert sequence.imu is not None and len(sequence.imu) == 5
        assert sequence.gt_poses is not None and len(sequence.gt_poses) == 3
        assert sequence.images is not None and len(sequence.images) == 2

        np.testing.assert_array_equal(sequence.events["p"], [1, -1, 1, -1, 1])
        np.testing.assert_array_equal(sequence.events["x"], [1, 3, 5, 2, 7])
        assert np.all(np.diff(sequence.events["t"]) >= 0.0)
        np.testing.assert_allclose(sequence.imu["gz"], 0.03)
        np.testing.assert_allclose(sequence.gt_poses["x"], [0.0, 1.0, 2.0])
        assert sequence.calibration.intrinsics_available
        assert sequence.calibration.data["K"][0] == pytest.approx(226.5)

    def test_window_slicing_filters_all_streams(self, mvsec_bags, tmp_path):
        data_bag, gt_bag = mvsec_bags
        output = tmp_path / "sliced.h5"

        rc = converter.main(
            [
                "--data-bag",
                str(data_bag),
                "--gt-bag",
                str(gt_bag),
                "--output",
                str(output),
                "--start-sec",
                "0.0",
                "--duration-sec",
                "0.45",
            ]
        )
        assert rc == 0

        sequence = load_mvsec_sequence(output)
        # Only the first event burst (<= base+0.45) and the first three IMU samples fit.
        assert len(sequence.events) == 3
        assert len(sequence.imu) == 3
        assert len(sequence.gt_poses) == 2

    def test_without_gt_bag_omits_pose_group(self, mvsec_bags, tmp_path):
        data_bag, _ = mvsec_bags
        output = tmp_path / "no_gt.h5"

        rc = converter.main(["--data-bag", str(data_bag), "--output", str(output)])
        assert rc == 0

        sequence = load_mvsec_sequence(output)
        assert sequence.gt_poses is None
        assert sequence.images is None

    def test_empty_window_returns_error(self, mvsec_bags, tmp_path):
        data_bag, _ = mvsec_bags
        output = tmp_path / "empty.h5"

        rc = converter.main(
            [
                "--data-bag",
                str(data_bag),
                "--output",
                str(output),
                "--start-sec",
                "500.0",
                "--duration-sec",
                "1.0",
            ]
        )
        assert rc == 1
        assert not output.exists()
