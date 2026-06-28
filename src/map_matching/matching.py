import cv2
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
