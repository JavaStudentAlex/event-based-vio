import cv2
import numpy as np


def _descriptor_matcher(method):
    return cv2.BFMatcher(cv2.NORM_HAMMING) if method in ["orb", "akaze"] else cv2.BFMatcher(cv2.NORM_L2)


def _passes_ratio(match_pair, ratio_thresh):
    if len(match_pair) != 2:
        return False
    m, n = match_pair
    return m.distance < ratio_thresh * n.distance


def match_descriptors(desc1, desc2, method="orb", ratio_thresh=0.75):
    if desc1 is None or desc2 is None:
        return [], []
    matcher = _descriptor_matcher(method)

    raw_matches = matcher.knnMatch(desc1, desc2, k=2)
    good_matches = [match[0] for match in raw_matches if _passes_ratio(match, ratio_thresh)]

    return raw_matches, good_matches


def _matched_points(kp1, kp2, matches):
    src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    return src_pts, dst_pts


def _homography_inliers(matches, mask):
    if mask is None:
        return []
    return [m for i, m in enumerate(matches) if mask[i][0]]


def estimate_homography(kp1, kp2, matches, reproj_thresh=5.0):
    if len(matches) < 4:
        return None, []

    src_pts, dst_pts = _matched_points(kp1, kp2, matches)
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, reproj_thresh)
    return H, _homography_inliers(matches, mask)
