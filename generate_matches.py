import math
import urllib.request
import numpy as np
import cv2
import os

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
    n = 2.0 ** zoom
    xtile = int((lon_deg + 180.0) / 360.0 * n)
    ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
    # fractional parts
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
    except Exception as e:
        print(f"Failed to fetch tile {z}/{y}/{x}: {e}")
        return np.zeros((256, 256, 3), dtype=np.uint8)

def apply_motion_blur(image, kernel_size=15):
    # Create horizontal motion blur kernel
    kernel_h = np.zeros((kernel_size, kernel_size))
    kernel_h[int((kernel_size - 1)/2), :] = np.ones(kernel_size)
    kernel_h /= kernel_size
    
    # Rotate kernel by 45 degrees to simulate forward-diagonal flight
    M = cv2.getRotationMatrix2D((kernel_size/2, kernel_size/2), 45, 1)
    kernel = cv2.warpAffine(kernel_h, M, (kernel_size, kernel_size))
    kernel /= np.sum(kernel)
    
    blurred = cv2.filter2D(image, -1, kernel)
    return blurred

out_dir = "/home/jovyan/.gemini/antigravity-cli/brain/7687d573-be9d-4088-870e-115302fb2853/scratch/waypoints"
os.makedirs(out_dir, exist_ok=True)

zoom = 17
CROP_SIZE = 400 # drone footprint

for i, (lat, lon) in enumerate(WAYPOINTS):
    print(f"Processing waypoint {i+1}/{len(WAYPOINTS)}...")
    x, y, x_f, y_f = deg2num(lat, lon, zoom)
    
    # Download 3x3 grid
    tiles = []
    for dy in [-1, 0, 1]:
        row = []
        for dx in [-1, 0, 1]:
            row.append(get_tile(x+dx, y+dy, zoom))
        tiles.append(np.hstack(row))
    full_image = np.vstack(tiles)
    
    # Calculate exact pixel coordinate in the 768x768 image
    # center tile is at (256, 256) to (511, 511)
    px_x = int((x_f - x) * 256) + 256
    px_y = int((y_f - y) * 256) + 256
    
    # Crop
    half_crop = CROP_SIZE // 2
    y1, y2 = max(0, px_y - half_crop), min(768, px_y + half_crop)
    x1, x2 = max(0, px_x - half_crop), min(768, px_x + half_crop)
    
    crop = full_image[y1:y2, x1:x2]
    blurred_crop = apply_motion_blur(crop, kernel_size=25)
    
    # Draw red rectangle on full image
    sat_img = full_image.copy()
    cv2.rectangle(sat_img, (x1, y1), (x2, y2), (0, 0, 255), 4)
    
    # Save
    sat_path = os.path.join(out_dir, f"pt{i+1}_sat.jpg")
    drone_path = os.path.join(out_dir, f"pt{i+1}_drone.jpg")
    cv2.imwrite(sat_path, sat_img)
    cv2.imwrite(drone_path, blurred_crop)

print("Done")
