import argparse
import json
import os

import cv2

from src.map_matching.aoi import AOI, dms_to_decimal
from src.map_matching.confidence import compute_confidence
from src.map_matching.features import extract_features
from src.map_matching.geometry import pixel_to_latlon
from src.map_matching.matching import estimate_homography, match_descriptors
from src.map_matching.preprocess import preprocess_image
from src.map_matching.visualize import draw_inliers

LAT_A = dms_to_decimal(45, 39, 40.36, "N")
LON_A = dms_to_decimal(34, 10, 29.15, "E")
LAT_B = dms_to_decimal(45, 25, 9.49, "N")
LON_B = dms_to_decimal(34, 41, 28.77, "E")

DEFAULT_AOI = AOI(north=max(LAT_A, LAT_B), south=min(LAT_A, LAT_B), west=min(LON_A, LON_B), east=max(LON_A, LON_B))


def print_aoi(args):
    print(f"North: {DEFAULT_AOI.north:.10f}")
    print(f"South: {DEFAULT_AOI.south:.10f}")
    print(f"West:  {DEFAULT_AOI.west:.10f}")
    print(f"East:  {DEFAULT_AOI.east:.10f}")
    center_lat, center_lon = DEFAULT_AOI.center
    print(f"\nCenter latitude:  {center_lat:.10f}")
    print(f"Center longitude: {center_lon:.10f}")


def match(args):
    os.makedirs(args.out_dir, exist_ok=True)

    drone_img = cv2.imread(args.drone_img)
    ref_img = cv2.imread(args.ref_img)
    if drone_img is None:
        print(f"Error loading {args.drone_img}")
        return
    if ref_img is None:
        print(f"Error loading {args.ref_img}")
        return

    with open(args.ref_meta) as f:
        ref_meta = json.load(f)

    d_pre = preprocess_image(drone_img, mode="clahe" if args.edge_mode == "none" else args.edge_mode)
    r_pre = preprocess_image(ref_img, mode="clahe" if args.edge_mode == "none" else args.edge_mode)

    kp_d, desc_d = extract_features(d_pre, args.method)
    kp_r, desc_r = extract_features(r_pre, args.method)

    if desc_d is None or desc_r is None:
        print("Failed to extract features.")
        return

    raw_matches, good_matches = match_descriptors(desc_d, desc_r, args.method)

    H, inliers = estimate_homography(kp_d, kp_r, good_matches)

    if H is None:
        status = "failed"
        conf = 0.0
        lat, lon = 0.0, 0.0
    else:
        conf, status = compute_confidence(len(inliers), len(inliers) / max(1, len(raw_matches)), 5.0)
        center_px = [drone_img.shape[1] / 2.0, drone_img.shape[0] / 2.0]
        import numpy as np

        pt = np.array([[[center_px[0], center_px[1]]]], dtype=np.float32)
        proj = cv2.perspectiveTransform(pt, H)[0][0]
        lat, lon = pixel_to_latlon(proj[0], proj[1], ref_meta)

    result = {
        "status": status,
        "method": args.method,
        "edge_mode": args.edge_mode,
        "drone_image": args.drone_img,
        "reference_image": args.ref_img,
        "num_keypoints_drone": len(kp_d),
        "num_keypoints_reference": len(kp_r),
        "num_raw_matches": len(raw_matches),
        "num_inlier_matches": len(inliers),
        "inlier_ratio": len(inliers) / max(1, len(raw_matches)),
        "estimated_center_lat": float(lat),
        "estimated_center_lon": float(lon),
        "confidence": float(conf),
    }

    with open(os.path.join(args.out_dir, "match_result.json"), "w") as f:
        json.dump(result, f, indent=2)

    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [float(lon), float(lat)]},
                "properties": {"confidence": float(conf)},
            }
        ],
    }
    with open(os.path.join(args.out_dir, "estimated_pose.geojson"), "w") as f:
        json.dump(geojson, f, indent=2)

    if inliers:
        vis = draw_inliers(drone_img, kp_d, ref_img, kp_r, inliers)
        cv2.imwrite(os.path.join(args.out_dir, "matches_inliers.jpg"), vis)


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("print-aoi")

    parser_match = subparsers.add_parser("match")
    parser_match.add_argument("--drone-img", required=True)
    parser_match.add_argument("--ref-img", required=True)
    parser_match.add_argument("--ref-meta", required=True)
    parser_match.add_argument("--method", default="orb")
    parser_match.add_argument("--edge-mode", default="none")
    parser_match.add_argument("--out-dir", required=True)

    args = parser.parse_args()

    if args.command == "print-aoi":
        print_aoi(args)
    elif args.command == "match":
        match(args)


if __name__ == "__main__":
    main()
