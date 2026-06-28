import os

import cv2
import numpy as np


def apply_motion_blur(image, size=15, angle=45):
    # Create the motion blur kernel
    k = np.zeros((size, size), dtype=np.float32)
    center = size // 2

    # Draw a line in the kernel
    slope = np.tan(np.deg2rad(angle))
    for x in range(size):
        y = int(slope * (x - center) + center)
        if 0 <= y < size:
            k[y, x] = 1.0

    # Normalize the kernel
    k /= np.sum(k)

    # Apply the kernel to the image
    blurred = cv2.filter2D(image, -1, k)
    return blurred


def main():
    ref_path = "data/example_reference.jpg"
    out_path = "data/example_drone.jpg"

    if not os.path.exists(ref_path):
        print(f"File not found: {ref_path}")
        return

    img = cv2.imread(ref_path)
    h, w = img.shape[:2]

    # Simulate 200m height drone crop (e.g. 1/4th the width of the main image)
    crop_size = min(h, w) // 3

    # Take a crop from somewhat off-center to test matching
    start_y = h // 2 - crop_size // 2 - 50
    start_x = w // 2 - crop_size // 2 + 100

    # Ensure bounds
    start_y = max(0, min(start_y, h - crop_size))
    start_x = max(0, min(start_x, w - crop_size))

    drone_img = img[start_y : start_y + crop_size, start_x : start_x + crop_size]

    # Apply motion blur simulating fast forward motion
    blurred_drone = apply_motion_blur(drone_img, size=15, angle=30)

    cv2.imwrite(out_path, blurred_drone)
    print(f"Created simulated drone image at {out_path} with shape {blurred_drone.shape}")


if __name__ == "__main__":
    main()
