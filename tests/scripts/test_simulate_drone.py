import numpy as np

import scripts.simulate_drone as simulate_drone


def test_apply_motion_blur_spreads_bright_pixel_horizontally():
    image = np.zeros((7, 7), dtype=np.uint8)
    image[3, 3] = 255

    blurred = simulate_drone.apply_motion_blur(image, size=5, angle=0)

    assert blurred.shape == image.shape
    assert blurred.dtype == image.dtype
    assert np.count_nonzero(blurred[3, 1:6]) == 5
    assert np.count_nonzero(blurred[:3]) == 0
