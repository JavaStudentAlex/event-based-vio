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
        print(f"Failed to fetch tile {z}/{y}/{x}: {e}")
        return np.zeros((256, 256, 3), dtype=np.uint8)

zoom = 12

# Find bounding box of tiles
min_tx, min_ty = float('inf'), float('inf')
max_tx, max_ty = 0, 0

points_t = []
for lat, lon in WAYPOINTS:
    tx_f, ty_f = deg2num(lat, lon, zoom)
    points_t.append((tx_f, ty_f))
    min_tx = min(min_tx, int(tx_f))
    max_tx = max(max_tx, int(tx_f))
    min_ty = min(min_ty, int(ty_f))
    max_ty = max(max_ty, int(ty_f))

# Add margin
min_tx -= 1
max_tx += 1
min_ty -= 1
max_ty += 1

print(f"Downloading tiles: X({min_tx}-{max_tx}) Y({min_ty}-{max_ty})")

tiles = []
for ty in range(min_ty, max_ty + 1):
    row = []
    for tx in range(min_tx, max_tx + 1):
        row.append(get_tile(tx, ty, zoom))
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

# Draw line
cv2.polylines(global_map, [pts], isClosed=False, color=(0, 255, 255), thickness=4, lineType=cv2.LINE_AA)

# Draw points
for i, pt in enumerate(pts):
    px, py = pt[0]
    # draw circle
    cv2.circle(global_map, (px, py), 12, (0, 0, 255), -1, cv2.LINE_AA)
    # text background
    cv2.rectangle(global_map, (px+15, py-20), (px+40, py+5), (0,0,0), -1)
    # text
    cv2.putText(global_map, str(i+1), (px+17, py), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2, cv2.LINE_AA)

out_path = "/home/jovyan/event-based-vio/global_route_map.jpg"
cv2.imwrite(out_path, global_map)
print(f"Saved global map to {out_path}")
