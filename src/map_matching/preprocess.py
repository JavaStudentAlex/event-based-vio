import cv2
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
