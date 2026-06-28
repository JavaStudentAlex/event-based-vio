import math
import os
import urllib.request

import cv2
import numpy as np

WAYPOINTS = [
    (45.63634167, 34.23058611),
    (45.58718611, 34.22989167),
    (45.56846111, 34.27654722),
    (45.52315000, 34.30896389),
    (45.50459444, 34.34391667),
    (45.47669167, 34.36436111),
    (45.46632778, 34.42085000),
    (45.49096389, 34.47056944),
    (45.51800278, 34.62104167),
]


def deg2num(lat_deg, lon_deg, zoom):
    lat_rad = math.radians(lat_deg)
    n = 2.0**zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    xtile_f = (lon_deg + 180.0) / 360.0 * n
    ytile_f = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return (xtile, ytile, xtile_f, ytile_f)


def get_tile(x, y, z):
    url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as response:
            arr = np.asarray(bytearray(response.read()), dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            return img
    except Exception:
        return np.zeros((256, 256, 3), dtype=np.uint8)


def apply_motion_blur(image, kernel_size=25):
    kernel_h = np.zeros((kernel_size, kernel_size))
    kernel_h[int((kernel_size - 1) / 2), :] = np.ones(kernel_size)
    kernel_h /= kernel_size
    M = cv2.getRotationMatrix2D((kernel_size / 2, kernel_size / 2), 45, 1)
    kernel = cv2.warpAffine(kernel_h, M, (kernel_size, kernel_size))
    kernel /= np.sum(kernel)
    blurred = cv2.filter2D(image, -1, kernel)
    return blurred


out_dir = "/home/jovyan/event-based-vio/waypoint_images"
os.makedirs(out_dir, exist_ok=True)

# 1. Regenerate drone images at zoom 17
print("Regenerating drone images...")
zoom_drone = 17
CROP_SIZE = 400

for i, (lat, lon) in enumerate(WAYPOINTS):
    x, y, x_f, y_f = deg2num(lat, lon, zoom_drone)
    tiles = []
    for dy in [-1, 0, 1]:
        row = []
        for dx in [-1, 0, 1]:
            row.append(get_tile(x + dx, y + dy, zoom_drone))
        tiles.append(np.hstack(row))
    full_image = np.vstack(tiles)

    px_x = int((x_f - x) * 256) + 256
    px_y = int((y_f - y) * 256) + 256

    half_crop = CROP_SIZE // 2
    y1, y2 = max(0, px_y - half_crop), min(768, px_y + half_crop)
    x1, x2 = max(0, px_x - half_crop), min(768, px_x + half_crop)

    crop = full_image[y1:y2, x1:x2]
    blurred_crop = apply_motion_blur(crop, kernel_size=25)

    drone_path = os.path.join(out_dir, f"pt{i + 1}_drone.jpg")
    cv2.imwrite(drone_path, blurred_crop)

# 2. Calculate pixel coordinates on the zoom 12 global map
zoom_global = 12
min_tx, min_ty = float("inf"), float("inf")
max_tx, max_ty = 0, 0

points_t = []
for lat, lon in WAYPOINTS:
    _, _, tx_f, ty_f = deg2num(lat, lon, zoom_global)
    points_t.append((tx_f, ty_f))
    min_tx = min(min_tx, int(tx_f))
    max_tx = max(max_tx, int(tx_f))
    min_ty = min(min_ty, int(ty_f))
    max_ty = max(max_ty, int(ty_f))

min_tx -= 1
min_ty -= 1

print("\n--- GLOBAL POSITIONING DATA ---")
for i, (tx_f, ty_f) in enumerate(points_t):
    px = int((tx_f - min_tx) * 256)
    py = int((ty_f - min_ty) * 256)
    print(f"Waypoint {i + 1}: Pixel Coordinates (X={px}, Y={py}) on global_route_map.jpg")
