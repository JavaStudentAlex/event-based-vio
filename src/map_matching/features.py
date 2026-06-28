import cv2


def extract_features(image, method="orb"):
    if method == "orb":
        detector = cv2.ORB_create(nfeatures=5000, scaleFactor=1.2, nlevels=8, fastThreshold=10)
    elif method == "akaze":
        detector = cv2.AKAZE_create()
    else:
        raise ValueError(f"Unknown method {method}")

    keypoints, descriptors = detector.detectAndCompute(image, None)
    return keypoints, descriptors
