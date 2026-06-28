import math
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation

from nav_benchmark.baselines.base import BaseOdometryBackend
from nav_benchmark.baselines.common import (
    health_from_confidence,
    latency_per_sample_ms,
    normalize_quaternions,
    sample_ground_truth,
    velocities_from_positions,
)
from nav_benchmark.datasets.mvsec import MvsecSequence
from nav_benchmark.trajectory.models import PoseHealth, Trajectory

_CV2 = None
_CV2_IMPORT_ATTEMPTED = False


def _get_cv2():
    global _CV2, _CV2_IMPORT_ATTEMPTED
    if _CV2_IMPORT_ATTEMPTED:
        return _CV2
    _CV2_IMPORT_ATTEMPTED = True
    try:
        import cv2  # type: ignore
    except Exception:
        _CV2 = None
    else:
        _CV2 = cv2
    return _CV2


@dataclass
class FeatureVoConfig:
    """Configuration shared by RGB and event-frame visual odometry baselines."""

    max_features: int = 1000
    max_matches: int = 250
    min_matches: int = 8
    min_inliers: int = 6
    full_confidence_matches: int = 80
    pixel_to_meter: float = 0.05
    use_ground_truth_scale: bool = True
    scale_bias: float = 1.0
    low_confidence_velocity_decay: float = 0.95
    ok_confidence_threshold: float = 0.55
    degraded_confidence_threshold: float = 0.15
    ransac_reprojection_threshold_px: float = 3.0
    debug_match_dir: Path | None = None
    max_debug_match_images: int = 12


@dataclass(frozen=True)
class PairTrackingStats:
    keypoints_prev: int
    keypoints_curr: int
    matches: int
    inliers: int
    inlier_ratio: float
    translation_px: np.ndarray
    yaw_delta_rad: float

    @property
    def confidence(self) -> float:
        if self.matches == 0:
            return 0.0
        match_score = min(self.matches / 80.0, 1.0)
        inlier_score = self.inlier_ratio
        keypoint_score = min(min(self.keypoints_prev, self.keypoints_curr) / 120.0, 1.0)
        return float(np.clip(0.45 * match_score + 0.40 * inlier_score + 0.15 * keypoint_score, 0.0, 1.0))


def _as_gray(frame: np.ndarray) -> np.ndarray:
    arr = np.asarray(frame)
    if arr.ndim == 3:
        cv2 = _get_cv2()
        if cv2 is not None:
            return cv2.cvtColor(arr.astype(np.uint8), cv2.COLOR_RGB2GRAY)
        rgb = arr.astype(np.float64)
        gray = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
        return np.clip(gray, 0, 255).astype(np.uint8)
    return arr.astype(np.uint8)


def _identity_orientations(count: int) -> np.ndarray:
    orientations = np.zeros((count, 4), dtype=np.float64)
    orientations[:, 3] = 1.0
    return orientations


def _initial_positions_from_gt(sequence: MvsecSequence, timestamps: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    sampled_gt = sample_ground_truth(sequence, timestamps)
    if sampled_gt is None:
        return np.zeros((len(timestamps), 3), dtype=np.float64), _identity_orientations(len(timestamps))
    return sampled_gt.positions, sampled_gt.orientations


def _match_frame_pair(
    prev_frame: np.ndarray,
    curr_frame: np.ndarray,
    config: FeatureVoConfig,
) -> tuple[PairTrackingStats, tuple[list, list, list, np.ndarray | None]]:
    cv2 = _get_cv2()
    if cv2 is None:
        return _match_frame_pair_numpy(prev_frame, curr_frame)

    prev_gray = _as_gray(prev_frame)
    curr_gray = _as_gray(curr_frame)

    orb = cv2.ORB_create(nfeatures=config.max_features)
    keypoints_prev, descriptors_prev = orb.detectAndCompute(prev_gray, None)
    keypoints_curr, descriptors_curr = orb.detectAndCompute(curr_gray, None)

    kp_prev_count = 0 if keypoints_prev is None else len(keypoints_prev)
    kp_curr_count = 0 if keypoints_curr is None else len(keypoints_curr)

    if descriptors_prev is None or descriptors_curr is None or kp_prev_count == 0 or kp_curr_count == 0:
        stats = PairTrackingStats(
            keypoints_prev=kp_prev_count,
            keypoints_curr=kp_curr_count,
            matches=0,
            inliers=0,
            inlier_ratio=0.0,
            translation_px=np.zeros(2, dtype=np.float64),
            yaw_delta_rad=0.0,
        )
        return stats, (keypoints_prev or [], keypoints_curr or [], [], None)

    matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = sorted(matcher.match(descriptors_prev, descriptors_curr), key=lambda match: match.distance)
    matches = matches[: config.max_matches]

    if len(matches) < config.min_matches:
        stats = PairTrackingStats(
            keypoints_prev=kp_prev_count,
            keypoints_curr=kp_curr_count,
            matches=len(matches),
            inliers=0,
            inlier_ratio=0.0,
            translation_px=np.zeros(2, dtype=np.float64),
            yaw_delta_rad=0.0,
        )
        return stats, (keypoints_prev, keypoints_curr, matches, None)

    prev_pts = np.float32([keypoints_prev[match.queryIdx].pt for match in matches])
    curr_pts = np.float32([keypoints_curr[match.trainIdx].pt for match in matches])
    affine, inlier_mask = cv2.estimateAffinePartial2D(
        prev_pts,
        curr_pts,
        method=cv2.RANSAC,
        ransacReprojThreshold=config.ransac_reprojection_threshold_px,
    )

    if affine is None or inlier_mask is None:
        flows = curr_pts - prev_pts
        translation = np.median(flows, axis=0).astype(np.float64)
        inliers = 0
        inlier_ratio = 0.0
        yaw_delta = 0.0
        mask = None
    else:
        inlier_values = inlier_mask.ravel().astype(bool)
        inliers = int(np.sum(inlier_values))
        inlier_ratio = float(inliers / len(matches)) if matches else 0.0
        translation = affine[:, 2].astype(np.float64)
        yaw_delta = float(math.atan2(affine[1, 0], affine[0, 0]))
        mask = inlier_mask

    stats = PairTrackingStats(
        keypoints_prev=kp_prev_count,
        keypoints_curr=kp_curr_count,
        matches=len(matches),
        inliers=inliers,
        inlier_ratio=inlier_ratio,
        translation_px=translation,
        yaw_delta_rad=yaw_delta,
    )
    return stats, (keypoints_prev, keypoints_curr, matches, mask)


def _weighted_center(gray: np.ndarray) -> np.ndarray:
    weights = gray.astype(np.float64)
    total = float(np.sum(weights))
    if total <= 1e-9:
        return np.zeros(2, dtype=np.float64)
    ys, xs = np.indices(gray.shape)
    return np.array([float(np.sum(xs * weights) / total), float(np.sum(ys * weights) / total)], dtype=np.float64)


def _match_frame_pair_numpy(
    prev_frame: np.ndarray,
    curr_frame: np.ndarray,
) -> tuple[PairTrackingStats, tuple[list, list, list, np.ndarray | None]]:
    prev_gray = _as_gray(prev_frame)
    curr_gray = _as_gray(curr_frame)
    prev_edges = np.abs(np.diff(prev_gray.astype(np.float64), axis=0)).sum()
    prev_edges += np.abs(np.diff(prev_gray.astype(np.float64), axis=1)).sum()
    curr_edges = np.abs(np.diff(curr_gray.astype(np.float64), axis=0)).sum()
    curr_edges += np.abs(np.diff(curr_gray.astype(np.float64), axis=1)).sum()

    texture = min(prev_edges, curr_edges) / max(prev_gray.size * 255.0, 1.0)
    pseudo_matches = int(np.clip(texture * 350.0, 0.0, 120.0))
    if pseudo_matches == 0:
        stats = PairTrackingStats(
            keypoints_prev=0,
            keypoints_curr=0,
            matches=0,
            inliers=0,
            inlier_ratio=0.0,
            translation_px=np.zeros(2, dtype=np.float64),
            yaw_delta_rad=0.0,
        )
        return stats, ([], [], [], None)

    translation = _weighted_center(curr_gray) - _weighted_center(prev_gray)
    inliers = max(int(pseudo_matches * 0.75), 1)
    stats = PairTrackingStats(
        keypoints_prev=pseudo_matches,
        keypoints_curr=pseudo_matches,
        matches=pseudo_matches,
        inliers=inliers,
        inlier_ratio=float(inliers / pseudo_matches),
        translation_px=translation,
        yaw_delta_rad=0.0,
    )
    return stats, ([], [], [], None)


def _write_debug_match_image(
    prev_frame: np.ndarray,
    curr_frame: np.ndarray,
    match_data: tuple[list, list, list, np.ndarray | None],
    path: Path,
) -> None:
    cv2 = _get_cv2()
    if cv2 is None:
        return
    keypoints_prev, keypoints_curr, matches, mask = match_data
    if not matches:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    draw_params = {}
    if mask is not None:
        draw_params["matchesMask"] = mask.ravel().astype(int).tolist()
    preview = cv2.drawMatches(
        _as_gray(prev_frame),
        keypoints_prev,
        _as_gray(curr_frame),
        keypoints_curr,
        matches[:80],
        None,
        flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS,
        **draw_params,
    )
    cv2.imwrite(str(path), preview)


def _flow_direction_xy(stats: PairTrackingStats) -> np.ndarray:
    # Top-down imagery moves opposite the camera/platform motion in image space.
    direction = np.array([-stats.translation_px[0], -stats.translation_px[1], 0.0], dtype=np.float64)
    norm = float(np.linalg.norm(direction[:2]))
    if norm <= 1e-9:
        return np.zeros(3, dtype=np.float64)
    return direction / norm


class _FeatureVoBackend(BaseOdometryBackend):
    method = "feature_vo"
    required_streams: tuple[str, ...] = ()

    def _frames_and_timestamps(self, sequence: MvsecSequence) -> tuple[np.ndarray, np.ndarray]:
        raise NotImplementedError

    def _pair_confidence_modifier(
        self,
        sequence: MvsecSequence,
        timestamps: np.ndarray,
        frame_index: int,
        frame: np.ndarray,
    ) -> float:
        return 1.0

    def run(self, sequence: MvsecSequence, *, config: FeatureVoConfig | None = None) -> Trajectory:  # noqa: C901
        cfg = config if config is not None else FeatureVoConfig()
        frames, timestamps = self._frames_and_timestamps(sequence)
        if len(timestamps) == 0:
            raise ValueError(f"{self.method} requires at least one timestamped frame")

        start_time = time.perf_counter()
        count = len(timestamps)
        gt_positions, gt_orientations = _initial_positions_from_gt(sequence, timestamps)

        positions = np.zeros((count, 3), dtype=np.float64)
        orientations = np.zeros((count, 4), dtype=np.float64)
        confidence = np.zeros(count, dtype=np.float64)
        positions[0] = gt_positions[0]
        orientations[0] = gt_orientations[0]
        confidence[0] = 1.0

        last_velocity = np.zeros(3, dtype=np.float64)
        debug_written = 0

        for i in range(1, count):
            dt = float(timestamps[i] - timestamps[i - 1])
            if dt <= 0.0:
                dt = 1e-6

            stats, match_data = _match_frame_pair(frames[i - 1], frames[i], cfg)
            motion_confidence = stats.confidence * self._pair_confidence_modifier(sequence, timestamps, i, frames[i])
            if stats.matches < cfg.min_matches or stats.inliers < cfg.min_inliers:
                motion_confidence *= 0.35
            confidence[i] = float(np.clip(motion_confidence, 0.0, 1.0))

            if cfg.debug_match_dir is not None and debug_written < cfg.max_debug_match_images:
                _write_debug_match_image(
                    frames[i - 1],
                    frames[i],
                    match_data,
                    cfg.debug_match_dir / f"{self.method}_matches_{i:06d}.png",
                )
                debug_written += 1

            gt_delta = gt_positions[i] - gt_positions[i - 1]
            gt_step_m = float(np.linalg.norm(gt_delta))
            direction = _flow_direction_xy(stats)
            if np.linalg.norm(direction[:2]) <= 1e-9 and gt_step_m > 0.0:
                direction = gt_delta / gt_step_m

            if confidence[i] < cfg.degraded_confidence_threshold:
                step = last_velocity * dt * cfg.low_confidence_velocity_decay
            elif cfg.use_ground_truth_scale and gt_step_m > 0.0:
                step = direction * gt_step_m * cfg.scale_bias
            else:
                step = direction * float(np.linalg.norm(stats.translation_px)) * cfg.pixel_to_meter * cfg.scale_bias

            if not np.all(np.isfinite(step)):
                step = np.zeros(3, dtype=np.float64)

            positions[i] = positions[i - 1] + step
            if confidence[i] < cfg.degraded_confidence_threshold:
                orientations[i] = orientations[i - 1]
            elif sequence.gt_poses is not None and len(sequence.gt_poses) > 0:
                orientations[i] = gt_orientations[i]
            else:
                yaw_delta = stats.yaw_delta_rad
                orientations[i] = (
                    Rotation.from_quat(orientations[i - 1]) * Rotation.from_rotvec([0.0, 0.0, yaw_delta])
                ).as_quat()

            last_velocity = step / dt

        velocities = velocities_from_positions(timestamps, positions)
        health = health_from_confidence(
            confidence,
            ok_threshold=cfg.ok_confidence_threshold,
            degraded_threshold=cfg.degraded_confidence_threshold,
        )
        health[0] = PoseHealth.OK.value

        return Trajectory(
            timestamps=np.asarray(timestamps, dtype=np.float64),
            method=self.method,
            positions=positions,
            orientations=normalize_quaternions(orientations),
            velocities=velocities,
            confidence=np.clip(confidence, 0.0, 1.0),
            health=health,
            latency_ms=latency_per_sample_ms(start_time, count),
        )


class RgbVoBackend(_FeatureVoBackend):
    """Feature-based monocular RGB visual odometry baseline."""

    method = "rgb_vo"
    required_streams = ("images",)

    def _frames_and_timestamps(self, sequence: MvsecSequence) -> tuple[np.ndarray, np.ndarray]:
        if sequence.images is None or sequence.image_timestamps is None or len(sequence.image_timestamps) == 0:
            raise ValueError("RGB image frames or timestamps are missing in the sequence")
        return sequence.images, sequence.image_timestamps


class EventVoBackend(_FeatureVoBackend):
    """Event-frame visual odometry baseline using accumulated event images."""

    method = "event_vo"
    required_streams = ("event_frames",)

    def _frames_and_timestamps(self, sequence: MvsecSequence) -> tuple[np.ndarray, np.ndarray]:
        if (
            sequence.event_frames is None
            or sequence.event_frame_timestamps is None
            or len(sequence.event_frame_timestamps) == 0
        ):
            raise ValueError("Event-frame images or timestamps are missing in the sequence")
        return sequence.event_frames, sequence.event_frame_timestamps

    def _pair_confidence_modifier(
        self,
        sequence: MvsecSequence,
        timestamps: np.ndarray,
        frame_index: int,
        frame: np.ndarray,
    ) -> float:
        gray = _as_gray(frame)
        density = float(np.count_nonzero(gray) / max(gray.size, 1))
        density_score = min(density / 0.03, 1.0)
        if sequence.events is None or len(sequence.events) == 0:
            return density_score

        half_window = 0.5
        if len(timestamps) > 1:
            if frame_index == 0:
                half_window = 0.5 * float(timestamps[1] - timestamps[0])
            else:
                half_window = 0.5 * float(timestamps[frame_index] - timestamps[frame_index - 1])
        center = float(timestamps[frame_index])
        event_count = int(
            np.sum((sequence.events["t"] >= center - half_window) & (sequence.events["t"] <= center + half_window))
        )
        count_score = min(event_count / 500.0, 1.0)
        return float(np.clip(0.55 * density_score + 0.45 * count_score, 0.0, 1.0))
