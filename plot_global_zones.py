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
    xtile_f = (lon_deg + 180.0) / 360.0 * n
    ytile_f = (1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n
    return (xtile_f, ytile_f)

def get_tile(x, y, z):
    url = f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as response:
            arr = np.asarray(bytearray(response.read()), dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is None: return np.zeros((256, 256, 3), dtype=np.uint8)
            return img
    except Exception as e:
        return np.zeros((256, 256, 3), dtype=np.uint8)

zoom_global = 12
zoom_drone = 17
drone_crop_size = 400

# Calculate the scaling factor
# Since zoom 17 tiles are 2^(17-12) = 32 times larger than zoom 12 tiles
scale_factor = 2 ** (zoom_drone - zoom_global)
footprint_size_global = drone_crop_size / scale_factor  # 400 / 32 = 12.5 pixels

# Bounding box of tiles
min_tx, min_ty = float('inf'), float('inf')
max_tx, max_ty = 0, 0

points_t = []
for lat, lon in WAYPOINTS:
    tx_f, ty_f = deg2num(lat, lon, zoom_global)
    points_t.append((tx_f, ty_f))
    min_tx = min(min_tx, int(tx_f))
    max_tx = max(max_tx, int(tx_f))
    min_ty = min(min_ty, int(ty_f))
    max_ty = max(max_ty, int(ty_f))

min_tx -= 1
max_tx += 1
min_ty -= 1
max_ty += 1

print("Downloading tiles for global map...")
tiles = []
for ty in range(min_ty, max_ty + 1):
    row = []
    for tx in range(min_tx, max_tx + 1):
        row.append(get_tile(tx, ty, zoom_global))
    tiles.append(np.hstack(row))

global_map = np.vstack(tiles)

# Draw route
pts = []
for tx_f, ty_f in points_t:
    px = int((tx_f - min_tx) * 256)
    py = int((ty_f - min_ty) * 256)
    pts.append([px, py])

pts = np.array(pts, np.int32)
pts = pts.reshape((-1, 1, 2))

# Draw connecting line
cv2.polylines(global_map, [pts], isClosed=False, color=(0, 255, 255), thickness=3, lineType=cv2.LINE_AA)

# Draw rectangular figures (zones) for the footprints
half_size = int(math.ceil(footprint_size_global / 2))
# Make it slightly larger so it's easily visible to the user, perhaps double size for visibility
vis_half_size = max(half_size, 10) 

for i, pt in enumerate(pts):
    px, py = pt[0]
    
    # Draw rectangle zone (drone footprint)
    top_left = (px - vis_half_size, py - vis_half_size)
    bottom_right = (px + vis_half_size, py + vis_half_size)
    cv2.rectangle(global_map, top_left, bottom_right, (0, 0, 255), 3) # Red outline
    
    # Label the zone
    text_pos = (px + vis_half_size + 5, py + vis_half_size + 5)
    cv2.putText(global_map, f"Zone {i+1}", text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 3, cv2.LINE_AA) # shadow
    cv2.putText(global_map, f"Zone {i+1}", text_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1, cv2.LINE_AA) # text

out_path = "/home/jovyan/event-based-vio/global_map_zones.jpg"
cv2.imwrite(out_path, global_map)
print(f"Saved new global map with zones to {out_path}")
