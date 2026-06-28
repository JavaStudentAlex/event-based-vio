import cv2
import numpy as np
import os
import glob

# Paths
data_dir = "/home/jovyan/.gemini/antigravity-cli/brain/7687d573-be9d-4088-870e-115302fb2853/scratch/waypoints"
out_dir = "/home/jovyan/.gemini/antigravity-cli/brain/7687d573-be9d-4088-870e-115302fb2853/scratch/matching_results"
os.makedirs(out_dir, exist_ok=True)

# Initialize SIFT detector
sift = cv2.SIFT_create()

# FLANN parameters
FLANN_INDEX_KDTREE = 1
index_params = dict(algorithm=FLANN_INDEX_KDTREE, trees=5)
search_params = dict(checks=50)
flann = cv2.FlannBasedMatcher(index_params, search_params)

for i in range(1, 10):
    sat_path = os.path.join(data_dir, f"pt{i}_sat.jpg")
    drone_path = os.path.join(data_dir, f"pt{i}_drone.jpg")
    
    if not os.path.exists(sat_path) or not os.path.exists(drone_path):
        continue
        
    sat_img = cv2.imread(sat_path)
    drone_img = cv2.imread(drone_path)
    
    gray_sat = cv2.cvtColor(sat_img, cv2.COLOR_BGR2GRAY)
    gray_drone = cv2.cvtColor(drone_img, cv2.COLOR_BGR2GRAY)
    
    # Find keypoints and descriptors
    kp1, des1 = sift.detectAndCompute(gray_drone, None)
    kp2, des2 = sift.detectAndCompute(gray_sat, None)
    
    if des1 is None or len(des1) < 2 or des2 is None or len(des2) < 2:
        print(f"Waypoint {i}: Not enough keypoints detected.")
        continue

    # KNN Match
    try:
        matches = flann.knnMatch(des1, des2, k=2)
    except Exception as e:
        print(f"Waypoint {i}: KNN match failed: {e}")
        continue
    
    # Lowe's ratio test
    good_matches = []
    for match in matches:
        if len(match) == 2:
            m, n = match
            if m.distance < 0.7 * n.distance:
                good_matches.append(m)
            
    print(f"Waypoint {i}: Found {len(good_matches)} good matches.")
    
    if len(good_matches) > 10:
        src_pts = np.float32([kp1[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        dst_pts = np.float32([kp2[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)
        
        # Find Homography using RANSAC
        M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        
        if M is not None:
            matchesMask = mask.ravel().tolist()
            
            # Get corners of the drone image
            h, w = gray_drone.shape
            pts = np.float32([[0, 0], [0, h-1], [w-1, h-1], [w-1, 0]]).reshape(-1, 1, 2)
            
            # Project corners to satellite image
            dst = cv2.perspectiveTransform(pts, M)
            
            # Draw calculated footprint in GREEN (Calculated) over the RED (Ground Truth)
            sat_matched = sat_img.copy()
            sat_matched = cv2.polylines(sat_matched, [np.int32(dst)], True, (0, 255, 0), 4, cv2.LINE_AA)
            
            # Draw match lines for visualization
            draw_params = dict(matchColor=(0, 255, 0), # draw matches in green
                               singlePointColor=None,
                               matchesMask=matchesMask, # draw only inliers
                               flags=2)
            
            result_img = cv2.drawMatches(drone_img, kp1, sat_matched, kp2, good_matches, None, **draw_params)
            
            out_path = os.path.join(out_dir, f"pt{i}_matched.jpg")
            cv2.imwrite(out_path, result_img)
            print(f"Waypoint {i}: Success! Calculated homography and saved match visualization.")
        else:
            print(f"Waypoint {i}: Failed to compute homography.")
    else:
        print(f"Waypoint {i}: Not enough good matches to compute homography (needed > 10, got {len(good_matches)}).")

print("Matching complete. Results saved to scratch/matching_results/")
