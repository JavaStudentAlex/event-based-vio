import math
from dataclasses import dataclass

def dms_to_decimal(degrees: float, minutes: float, seconds: float, hemisphere: str) -> float:
    decimal = degrees + minutes / 60.0 + seconds / 3600.0
    if hemisphere.upper() in ['S', 'W']:
        decimal = -decimal
    return decimal

@dataclass
class AOI:
    north: float
    south: float
    west: float
    east: float

    @property
    def center(self) -> tuple[float, float]:
        return ((self.north + self.south) / 2.0, (self.east + self.west) / 2.0)

    def contains(self, lat: float, lon: float) -> bool:
        return self.south <= lat <= self.north and self.west <= lon <= self.east
