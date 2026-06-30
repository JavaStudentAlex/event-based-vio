from __future__ import annotations

import cv2
import numpy as np
import pytest

from map_matching.confidence import compute_confidence
from map_matching.features import extract_features
from map_matching.matching import estimate_homography, match_descriptors
from map_matching.preprocess import preprocess_image


def test_preprocess_image_modes() -> None:
    image = np.zeros((32, 32, 3), dtype=np.uint8)
    image[8:24, 8:24, 0] = 255
    image[10:22, 10:22, 1] = 180

    gray = preprocess_image(image, mode="rgb_gray")
    clahe = preprocess_image(image, mode="clahe")
    unchanged = preprocess_image(image, mode="none")
    edges = preprocess_image(image, mode="edge_canny")
    fallback = preprocess_image(image, mode="unknown")

    assert gray.shape == (32, 32)
    assert clahe.shape == (32, 32)
    assert unchanged.shape == (32, 32)
    assert edges.shape == (32, 32)
    assert fallback is image


def test_match_descriptors_filters_ratio_matches() -> None:
    desc1 = np.array([[0] * 32, [255] * 32], dtype=np.uint8)
    desc2 = np.array([[0] * 32, [15] * 32, [255] * 32, [240] * 32], dtype=np.uint8)

    raw_matches, good_matches = match_descriptors(desc1, desc2, method="orb", ratio_thresh=0.75)

    assert len(raw_matches) == 2
    assert len(good_matches) == 2
    assert match_descriptors(None, desc2) == ([], [])
    assert match_descriptors(desc1.astype(np.float32), desc2.astype(np.float32), method="sift")[0]


def test_estimate_homography_handles_too_few_and_inliers() -> None:
    kp1 = [
        cv2.KeyPoint(0.0, 0.0, 1.0),
        cv2.KeyPoint(10.0, 0.0, 1.0),
        cv2.KeyPoint(10.0, 10.0, 1.0),
        cv2.KeyPoint(0.0, 10.0, 1.0),
    ]
    kp2 = [
        cv2.KeyPoint(2.0, 3.0, 1.0),
        cv2.KeyPoint(12.0, 3.0, 1.0),
        cv2.KeyPoint(12.0, 13.0, 1.0),
        cv2.KeyPoint(2.0, 13.0, 1.0),
    ]
    matches = [cv2.DMatch(i, i, 0.0) for i in range(4)]

    homography, inliers = estimate_homography(kp1, kp2, matches[:3])
    assert homography is None
    assert inliers == []

    homography, inliers = estimate_homography(kp1, kp2, matches)
    assert homography is not None
    assert len(inliers) == 4


def test_feature_extraction_and_confidence() -> None:
    image = np.zeros((64, 64), dtype=np.uint8)
    cv2.circle(image, (32, 32), 12, 255, thickness=2)

    keypoints, descriptors = extract_features(image, method="orb")
    assert isinstance(keypoints, tuple)
    assert descriptors is None or descriptors.shape[0] == len(keypoints)

    with pytest.raises(ValueError, match="Unknown method sift"):
        extract_features(image, method="sift")

    assert compute_confidence(4, 0.5, 1.0) == (0.0, "low_confidence")
    assert compute_confidence(20, 0.2, 1.0) == (0.4, "success")
    assert compute_confidence(80, 0.5, 1.0) == (1.0, "success")
