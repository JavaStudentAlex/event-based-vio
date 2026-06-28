import json

from src.map_matching.geometry import pixel_to_latlon

with open("data/example_reference.json") as f:
    ref_meta = json.load(f)

w = 1536
h = 1024

crop_size = 60

pos = [(w // 4, h // 4), (w // 2, h // 2), (3 * w // 4, 3 * h // 4)]

neg = [(w // 4, 3 * h // 4), (w // 2, h // 4), (3 * w // 4, h // 4)]

print("--- POSITIVE ROUTE ---")
for i, (cx, cy) in enumerate(pos):
    lat, lon = pixel_to_latlon(cx, cy, ref_meta)
    print(f"WP{i + 1}: Latitude: {lat:.6f}, Longitude: {lon:.6f}")

print("\n--- NEGATIVE ROUTE ---")
for i, (cx, cy) in enumerate(neg):
    # This is the expected point
    exp_lat, exp_lon = pixel_to_latlon(cx, cy, ref_meta)
    # This is where the drone actually was
    dx = min(w - crop_size // 2 - 1, cx + 300)
    dy = min(h - crop_size // 2 - 1, cy - 200)
    act_lat, act_lon = pixel_to_latlon(dx, dy, ref_meta)

    print(f"WP{i + 1}:")
    print(f"  Expected Control Point: Lat {exp_lat:.6f}, Lon {exp_lon:.6f}")
    print(f"  Drone's Actual Position: Lat {act_lat:.6f}, Lon {act_lon:.6f} (Off track!)")
