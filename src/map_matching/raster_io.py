import json
import rasterio
from pathlib import Path

def load_reference_metadata(json_path: str | Path) -> dict:
    with open(json_path, 'r') as f:
        return json.load(f)
