import cv2
import numpy as np


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
