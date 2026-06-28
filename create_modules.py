import os

files = {
    "src/map_matching/raster_io.py": """import json
import rasterio
from pathlib import Path

def load_reference_metadata(json_path: str | Path) -> dict:
    with open(json_path, 'r') as f:
        return json.load(f)
""",
    "src/map_matching/preprocess.py": """import cv2
import numpy as np

def preprocess_image(image: np.ndarray, mode: str = "rgb_gray") -> np.ndarray:
    if mode == "rgb_gray" or mode == "clahe" or mode == "none":
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        if mode == "clahe":
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
            return clahe.apply(gray)
        return gray
    elif mode == "edge_canny" or mode == "canny":
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        return cv2.Canny(gray, 100, 200)
    return image
""",
    "src/map_matching/features.py": """import cv2

def extract_features(image, method="orb"):
    if method == "orb":
        detector = cv2.ORB_create(nfeatures=5000, scaleFactor=1.2, nlevels=8, fastThreshold=10)
    elif method == "akaze":
        detector = cv2.AKAZE_create()
    else:
        raise ValueError(f"Unknown method {method}")
    
    keypoints, descriptors = detector.detectAndCompute(image, None)
    return keypoints, descriptors
""",
    "src/map_matching/matching.py": """import cv2
import numpy as np

def match_descriptors(desc1, desc2, method="orb", ratio_thresh=0.75):
    if desc1 is None or desc2 is None:
        return [], []
    if method in ["orb", "akaze"]:
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
    else:
        matcher = cv2.BFMatcher(cv2.NORM_L2)
    
    raw_matches = matcher.knnMatch(desc1, desc2, k=2)
    
    good_matches = []
    for match in raw_matches:
        if len(match) == 2:
            m, n = match
            if m.distance < ratio_thresh * n.distance:
                good_matches.append(m)
            
    return raw_matches, good_matches

def estimate_homography(kp1, kp2, matches, reproj_thresh=5.0):
    if len(matches) < 4:
        return None, []
        
    src_pts = np.float32([kp1[m.queryIdx].pt for m in matches]).reshape(-1, 1, 2)
    dst_pts = np.float32([kp2[m.trainIdx].pt for m in matches]).reshape(-1, 1, 2)
    
    H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, reproj_thresh)
    if mask is None:
        inliers = []
    else:
        inliers = [m for i, m in enumerate(matches) if mask[i][0]]
        
    return H, inliers
""",
    "src/map_matching/geometry.py": """import numpy as np
import cv2

def project_center(H, width, height):
    center = np.array([[[width / 2.0, height / 2.0]]], dtype=np.float32)
    projected = cv2.perspectiveTransform(center, H)
    return projected[0][0]

def pixel_to_latlon(px_x, px_y, metadata):
    # Simplistic approximation using metadata bounds
    w = metadata.get("width_px", 1000)
    h = metadata.get("height_px", 1000)
    west = metadata.get("west", 0.0)
    east = metadata.get("east", 0.0)
    north = metadata.get("north", 0.0)
    south = metadata.get("south", 0.0)
    lon = west + (px_x / w) * (east - west)
    lat = north - (px_y / h) * (north - south)
    return lat, lon
""",
    "src/map_matching/confidence.py": """def compute_confidence(num_inliers, inlier_ratio, reproj_error):
    if num_inliers < 12 or inlier_ratio < 0.10:
        return 0.0, "low_confidence"
    
    conf = min(1.0, num_inliers / 50.0)
    return conf, "success"
""",
    "src/map_matching/visualize.py": """import cv2

def draw_inliers(img1, kp1, img2, kp2, matches):
    return cv2.drawMatches(img1, kp1, img2, kp2, matches, None, 
                          matchColor=(0, 255, 0), singlePointColor=(255, 0, 0), 
                          flags=cv2.DrawMatchesFlags_NOT_DRAW_SINGLE_POINTS)
""",
    "satellite_drone_matcher.py": """import argparse
import sys
import json
import cv2
import os

from src.map_matching.aoi import dms_to_decimal, AOI
from src.map_matching.raster_io import load_reference_metadata
from src.map_matching.preprocess import preprocess_image
from src.map_matching.features import extract_features
from src.map_matching.matching import match_descriptors, estimate_homography
from src.map_matching.geometry import pixel_to_latlon, project_center
from src.map_matching.confidence import compute_confidence
from src.map_matching.visualize import draw_inliers

LAT_A = dms_to_decimal(45, 39, 40.36, "N")
LON_A = dms_to_decimal(34, 10, 29.15, "E")
LAT_B = dms_to_decimal(45, 25, 9.49, "N")
LON_B = dms_to_decimal(34, 41, 28.77, "E")

DEFAULT_AOI = AOI(
    north=max(LAT_A, LAT_B),
    south=min(LAT_A, LAT_B),
    west=min(LON_A, LON_B),
    east=max(LON_A, LON_B)
)

def print_aoi(args):
    print(f"North: {DEFAULT_AOI.north:.10f}")
    print(f"South: {DEFAULT_AOI.south:.10f}")
    print(f"West:  {DEFAULT_AOI.west:.10f}")
    print(f"East:  {DEFAULT_AOI.east:.10f}")
    center_lat, center_lon = DEFAULT_AOI.center
    print(f"\\nCenter latitude:  {center_lat:.10f}")
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
        
    with open(args.ref_meta, 'r') as f:
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
        conf, status = compute_confidence(len(inliers), len(inliers)/max(1,len(raw_matches)), 5.0)
        center_px = [drone_img.shape[1]/2.0, drone_img.shape[0]/2.0]
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
        "inlier_ratio": len(inliers)/max(1, len(raw_matches)),
        "estimated_center_lat": lat,
        "estimated_center_lon": lon,
        "confidence": conf
    }
    
    with open(os.path.join(args.out_dir, "match_result.json"), "w") as f:
        json.dump(result, f, indent=2)
        
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {
                    "type": "Point",
                    "coordinates": [lon, lat]
                },
                "properties": {
                    "confidence": conf
                }
            }
        ]
    }
    with open(os.path.join(args.out_dir, "estimated_pose.geojson"), "w") as f:
        json.dump(geojson, f, indent=2)
        
    if inliers:
        vis = draw_inliers(drone_img, kp_d, ref_img, kp_r, inliers)
        cv2.imwrite(os.path.join(args.out_dir, "matches_inliers.jpg"), vis)

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    parser_print = subparsers.add_parser("print-aoi")
    
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
""",
}

for path, content in files.items():
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w") as f:
        f.write(content)

print("Files created.")
