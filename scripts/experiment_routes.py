import json

import cv2
import numpy as np

from map_matching.geometry import pixel_to_latlon
from map_matching.matching import estimate_homography, match_descriptors
from map_matching.preprocess import preprocess_image
from scripts.simulate_drone import apply_motion_blur


def _preprocess_pair(drone_img, ref_img, edge_mode):
    mode = "clahe" if edge_mode == "none" else edge_mode
    return preprocess_image(drone_img, mode=mode), preprocess_image(ref_img, mode=mode)


def _detect_orb_features(drone_img, ref_img):
    detector = cv2.ORB_create(nfeatures=10000, scaleFactor=1.2, nlevels=8, fastThreshold=5)
    kp_d, desc_d = detector.detectAndCompute(drone_img, None)
    kp_r, desc_r = detector.detectAndCompute(ref_img, None)
    return kp_d, desc_d, kp_r, desc_r


def _failed_match(raw_matches=(), inliers=()):
    return 0.0, 0.0, len(raw_matches), len(inliers), "failed"


def _descriptors_missing(desc_d, desc_r):
    return desc_d is None or desc_r is None


def _keypoints_missing(kp_d, kp_r):
    return len(kp_d) == 0 or len(kp_r) == 0


def _features_missing(kp_d, desc_d, kp_r, desc_r):
    return _descriptors_missing(desc_d, desc_r) or _keypoints_missing(kp_d, kp_r)


def _project_crop_center(drone_img, homography, ref_meta):
    center_px = [drone_img.shape[1] / 2.0, drone_img.shape[0] / 2.0]
    pt = np.array([[[center_px[0], center_px[1]]]], dtype=np.float32)
    proj = cv2.perspectiveTransform(pt, homography)[0][0]
    return pixel_to_latlon(proj[0], proj[1], ref_meta)


def run_matcher_on_crop(drone_img, ref_img, ref_meta, method="orb", edge_mode="none"):
    d_pre, r_pre = _preprocess_pair(drone_img, ref_img, edge_mode)

    # Extract more features for a better chance on small crops
    kp_d, desc_d, kp_r, desc_r = _detect_orb_features(d_pre, r_pre)

    if _features_missing(kp_d, desc_d, kp_r, desc_r):
        return _failed_match()

    raw_matches, good_matches = match_descriptors(desc_d, desc_r, method, ratio_thresh=0.85)  # relaxed ratio
    H, inliers = estimate_homography(kp_d, kp_r, good_matches, reproj_thresh=8.0)

    if H is None:
        return _failed_match(raw_matches, inliers)

    status = "success" if len(inliers) >= 12 else "low_confidence"
    lat, lon = _project_crop_center(drone_img, H, ref_meta)

    return float(lat), float(lon), len(raw_matches), len(inliers), status


def get_distance(lat1, lon1, lat2, lon2):
    return np.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)


def _load_reference():
    ref_img = cv2.imread("data/example_reference.jpg")
    with open("data/example_reference.json", encoding="utf-8") as f:
        return ref_img, json.load(f)


def _routes(width, height):
    positive_route = [
        (width // 4, height // 4),
        (width // 2, height // 2),
        (3 * width // 4, 3 * height // 4),
    ]
    negative_route = [
        (width // 4, 3 * height // 4),
        (width // 2, height // 4),
        (3 * width // 4, height // 4),
    ]
    return {"Positive": positive_route, "Negative": negative_route}


def _drone_crop_center(route_name, ctrl_x, ctrl_y, width, height, crop_size):
    if route_name == "Positive":
        return ctrl_x, ctrl_y
    return min(width - crop_size // 2 - 1, ctrl_x + 300), min(height - crop_size // 2 - 1, ctrl_y - 200)


def _matcher_input(ref_img, drone_x, drone_y, crop_size, drone_camera_size):
    start_x = max(0, drone_x - crop_size // 2)
    start_y = max(0, drone_y - crop_size // 2)
    drone_crop = ref_img[start_y : start_y + crop_size, start_x : start_x + crop_size]
    high_res_drone = cv2.resize(drone_crop, drone_camera_size, interpolation=cv2.INTER_CUBIC)
    blurred_drone_high_res = apply_motion_blur(high_res_drone, size=15, angle=20)
    matcher_input = cv2.resize(blurred_drone_high_res, (crop_size, crop_size), interpolation=cv2.INTER_AREA)
    return blurred_drone_high_res, matcher_input


def _print_verdict(status, num_inliers, est_lat, est_lon, ctrl_lat, ctrl_lon):
    if status != "success" and num_inliers < 5:
        print("  [!] VERDICT: Matcher failed (not enough inliers).")
        return
    error = get_distance(est_lat, est_lon, ctrl_lat, ctrl_lon)
    if error < 0.005:
        print("  [✓] VERDICT: Matcher correctly localized the drone exactly at the control point!")
        return
    print(f"  [X] VERDICT: Matcher localized the drone to the WRONG place! (Distance error: {error:.6f})")


def _run_route_waypoint(route_name, waypoint_number, control_point, ref_img, ref_meta, crop_size, drone_camera_size):
    height, width = ref_img.shape[:2]
    ctrl_x, ctrl_y = control_point
    print(f"Waypoint {waypoint_number}:")
    ctrl_lat, ctrl_lon = pixel_to_latlon(ctrl_x, ctrl_y, ref_meta)
    drone_x, drone_y = _drone_crop_center(route_name, ctrl_x, ctrl_y, width, height, crop_size)
    blurred_drone_high_res, matcher_input = _matcher_input(ref_img, drone_x, drone_y, crop_size, drone_camera_size)
    img_path = f"data/drone_{route_name.lower()}_wp{waypoint_number}.jpg"
    cv2.imwrite(img_path, blurred_drone_high_res)
    est_lat, est_lon, num_raw, num_inliers, status = run_matcher_on_crop(
        matcher_input, ref_img, ref_meta, method="orb", edge_mode="none"
    )
    print(f"  Matcher Output: Status={status}, Inliers={num_inliers}/{num_raw}")
    _print_verdict(status, num_inliers, est_lat, est_lon, ctrl_lat, ctrl_lon)


def main():
    ref_img, ref_meta = _load_reference()
    height, width = ref_img.shape[:2]
    crop_size = 60
    drone_camera_size = (800, 800)

    print("=== MAP MATCHING EXPERIMENT ===")
    for route_name, route_points in _routes(width, height).items():
        print(f"\n--- {route_name} Route ---")
        for i, control_point in enumerate(route_points, start=1):
            _run_route_waypoint(route_name, i, control_point, ref_img, ref_meta, crop_size, drone_camera_size)


if __name__ == "__main__":
    main()
