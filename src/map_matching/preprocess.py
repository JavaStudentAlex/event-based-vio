import cv2
import numpy as np


def _to_gray(image: np.ndarray) -> np.ndarray:
    return cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image


def _is_gray_mode(mode: str) -> bool:
    return mode in {"rgb_gray", "clahe", "none"}


def _is_canny_mode(mode: str) -> bool:
    return mode in {"edge_canny", "canny"}


def _apply_clahe(gray: np.ndarray) -> np.ndarray:
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    return clahe.apply(gray)


def preprocess_image(image: np.ndarray, mode: str = "rgb_gray") -> np.ndarray:
    if _is_gray_mode(mode):
        gray = _to_gray(image)
        if mode == "clahe":
            return _apply_clahe(gray)
        return gray
    if _is_canny_mode(mode):
        return cv2.Canny(_to_gray(image), 100, 200)
    return image
