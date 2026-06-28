def compute_confidence(num_inliers, inlier_ratio, reproj_error):
    if num_inliers < 12 or inlier_ratio < 0.10:
        return 0.0, "low_confidence"

    conf = min(1.0, num_inliers / 50.0)
    return conf, "success"
