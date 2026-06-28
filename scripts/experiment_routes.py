import json

import cv2
import numpy as np

from scripts.simulate_drone import apply_motion_blur
from src.map_matching.geometry import pixel_to_latlon
from src.map_matching.matching import estimate_homography, match_descriptors
from src.map_matching.preprocess import preprocess_image


def run_matcher_on_crop(drone_img, ref_img, ref_meta, method="orb", edge_mode="none"):
    d_pre = preprocess_image(drone_img, mode="clahe" if edge_mode == "none" else edge_mode)
    r_pre = preprocess_image(ref_img, mode="clahe" if edge_mode == "none" else edge_mode)

    # Extract more features for a better chance on small crops
    detector = cv2.ORB_create(nfeatures=10000, scaleFactor=1.2, nlevels=8, fastThreshold=5)
    kp_d, desc_d = detector.detectAndCompute(d_pre, None)
    kp_r, desc_r = detector.detectAndCompute(r_pre, None)

    if desc_d is None or desc_r is None or len(kp_d) == 0 or len(kp_r) == 0:
        return 0.0, 0.0, 0, 0, "failed"

    raw_matches, good_matches = match_descriptors(desc_d, desc_r, method, ratio_thresh=0.85)  # relaxed ratio
    H, inliers = estimate_homography(kp_d, kp_r, good_matches, reproj_thresh=8.0)

    if H is None:
        return 0.0, 0.0, len(raw_matches), len(inliers), "failed"

    status = "success" if len(inliers) >= 12 else "low_confidence"

    center_px = [drone_img.shape[1] / 2.0, drone_img.shape[0] / 2.0]
    pt = np.array([[[center_px[0], center_px[1]]]], dtype=np.float32)
    proj = cv2.perspectiveTransform(pt, H)[0][0]
    lat, lon = pixel_to_latlon(proj[0], proj[1], ref_meta)

    return float(lat), float(lon), len(raw_matches), len(inliers), status


def get_distance(lat1, lon1, lat2, lon2):
    return np.sqrt((lat1 - lat2) ** 2 + (lon1 - lon2) ** 2)


def main():
    ref_path = "data/example_reference.jpg"
    meta_path = "data/example_reference.json"

    ref_img = cv2.imread(ref_path)
    with open(meta_path) as f:
        ref_meta = json.load(f)

    h, w = ref_img.shape[:2]
    # The reference image represents a huge area.
    # A drone at 200m sees a much smaller footprint.
    # Let's use a very small crop (e.g. 60x60 pixels) to simulate the 200m footprint,
    # and then scale it UP to simulate a high-res drone camera (e.g. 800x800).
    crop_size = 60
    drone_camera_size = (800, 800)

    positive_route = [(w // 4, h // 4), (w // 2, h // 2), (3 * w // 4, 3 * h // 4)]

    negative_route = [(w // 4, 3 * h // 4), (w // 2, h // 4), (3 * w // 4, h // 4)]

    routes = {"Positive": positive_route, "Negative": negative_route}

    print("=== MAP MATCHING EXPERIMENT ===")

    for route_name, route_points in routes.items():
        print(f"\n--- {route_name} Route ---")
        for i, (ctrl_x, ctrl_y) in enumerate(route_points):
            wp_num = i + 1
            print(f"Waypoint {wp_num}:")
            ctrl_lat, ctrl_lon = pixel_to_latlon(ctrl_x, ctrl_y, ref_meta)

            if route_name == "Positive":
                drone_x, drone_y = ctrl_x, ctrl_y
            else:
                drone_x = min(w - crop_size // 2 - 1, ctrl_x + 300)
                drone_y = min(h - crop_size // 2 - 1, ctrl_y - 200)

            start_x = max(0, drone_x - crop_size // 2)
            start_y = max(0, drone_y - crop_size // 2)
            drone_crop = ref_img[start_y : start_y + crop_size, start_x : start_x + crop_size]

            # Simulate high-resolution drone camera at 200m altitude
            high_res_drone = cv2.resize(drone_crop, drone_camera_size, interpolation=cv2.INTER_CUBIC)

            # Apply blur to the high-res image (simulating camera motion blur)
            blurred_drone_high_res = apply_motion_blur(high_res_drone, size=15, angle=20)

            img_path = f"data/drone_{route_name.lower()}_wp{wp_num}.jpg"
            cv2.imwrite(img_path, blurred_drone_high_res)

            # For the matcher, we must align the scale.
            # In a real system, the altitude prior (200m) tells us the GSD.
            # We resize the drone image back to the satellite's GSD to match features.
            matcher_input = cv2.resize(blurred_drone_high_res, (crop_size, crop_size), interpolation=cv2.INTER_AREA)

            est_lat, est_lon, num_raw, num_inliers, status = run_matcher_on_crop(
                matcher_input, ref_img, ref_meta, method="orb", edge_mode="none"
            )

            print(f"  Matcher Output: Status={status}, Inliers={num_inliers}/{num_raw}")
            if status == "success" or num_inliers >= 5:
                error = get_distance(est_lat, est_lon, ctrl_lat, ctrl_lon)
                if error < 0.005:
                    print("  [✓] VERDICT: Matcher correctly localized the drone exactly at the control point!")
                else:
                    print(
                        f"  [X] VERDICT: Matcher localized the drone to the WRONG place! (Distance error: {error:.6f})"
                    )
            else:
                print("  [!] VERDICT: Matcher failed (not enough inliers).")


if __name__ == "__main__":
    main()
