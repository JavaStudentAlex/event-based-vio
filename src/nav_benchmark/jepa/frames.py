"""Frame and ego-motion preprocessing for the JEPA model (numpy/cv2 only).

Frames from any stream (RGB or event frames, uint8 or float, with or without
channels) are normalised to a 32x32 grayscale patch grid with per-patch
standardisation. Ego-motion conditioning between consecutive frames comes
from a reference trajectory (IMU-only propagation), so it never requires
ground truth and is available identically at training and inference time.
"""

import cv2
import numpy as np
from scipy.spatial.transform import Rotation, Slerp

INPUT_SIZE = 32
PATCH_SIZE = 8
GRID = INPUT_SIZE // PATCH_SIZE
NUM_PATCHES = GRID * GRID
PATCH_DIM = PATCH_SIZE * PATCH_SIZE
EGO_DIM = 7  # body-frame translation (3), relative rotation vector (3), dt (1)


def to_gray_float(frame: np.ndarray) -> np.ndarray:
    """Convert any frame layout to float32 grayscale in [0, 1]."""
    array = np.asarray(frame)
    if array.ndim == 3:
        array = array.mean(axis=2)
    array = array.astype(np.float32)
    peak = float(array.max()) if array.size else 0.0
    if peak > 1.0:
        array = array / 255.0
    return np.clip(array, 0.0, 1.0)


def frame_patches(frame: np.ndarray) -> np.ndarray:
    """Standardised ``(NUM_PATCHES, PATCH_DIM)`` features for one frame."""
    gray = to_gray_float(frame)
    resized = cv2.resize(gray, (INPUT_SIZE, INPUT_SIZE), interpolation=cv2.INTER_AREA)
    patches = resized.reshape(GRID, PATCH_SIZE, GRID, PATCH_SIZE).transpose(0, 2, 1, 3).reshape(NUM_PATCHES, PATCH_DIM)
    mean = patches.mean(axis=1, keepdims=True)
    std = patches.std(axis=1, keepdims=True)
    return ((patches - mean) / (std + 1e-6)).astype(np.float32)


def stack_frame_patches(frames: np.ndarray) -> np.ndarray:
    """Patch features for a stack of frames: ``(N, NUM_PATCHES, PATCH_DIM)``."""
    return np.stack([frame_patches(frames[i]) for i in range(len(frames))], axis=0)


def _interp_positions(t: np.ndarray, positions: np.ndarray, query: np.ndarray) -> np.ndarray:
    return np.stack([np.interp(query, t, positions[:, axis]) for axis in range(3)], axis=1)


def _slerp_rotations(t: np.ndarray, quats: np.ndarray, query: np.ndarray) -> Rotation:
    if len(t) < 2:
        return Rotation.from_quat(np.tile(quats[0], (len(query), 1)))
    clipped = np.clip(query, t[0], t[-1])
    return Slerp(t, Rotation.from_quat(quats))(clipped)


def ego_motion_features(
    reference_times: np.ndarray,
    reference_positions: np.ndarray,
    reference_quats_xyzw: np.ndarray,
    frame_times: np.ndarray,
) -> np.ndarray:
    """Ego-motion conditioning between consecutive frames: ``(N-1, EGO_DIM)``."""
    frame_times = np.asarray(frame_times, dtype=np.float64)
    if len(frame_times) < 2:
        return np.zeros((0, EGO_DIM), dtype=np.float32)
    positions = _interp_positions(reference_times, reference_positions, frame_times)
    rotations = _slerp_rotations(reference_times, reference_quats_xyzw, frame_times)

    features = np.zeros((len(frame_times) - 1, EGO_DIM), dtype=np.float64)
    matrices = rotations.as_matrix()
    for k in range(len(frame_times) - 1):
        rotation_k = Rotation.from_matrix(matrices[k])
        dp_world = positions[k + 1] - positions[k]
        features[k, 0:3] = rotation_k.inv().apply(dp_world)
        features[k, 3:6] = (rotation_k.inv() * Rotation.from_matrix(matrices[k + 1])).as_rotvec()
        features[k, 6] = frame_times[k + 1] - frame_times[k]
    return features.astype(np.float32)
