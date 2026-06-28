# Task Specification: Satellite–Drone Keypoint Matching and Map-Anchoring Reference Pipeline

## 1. Goal

Build a **satellite-to-drone image matching module** that can use a georeferenced reference image of the flight area and a drone-camera image from the same territory to estimate an approximate absolute position and heading correction.

This task is the **map-anchoring layer** for the navigation pipeline. The relative odometry system estimates motion over time, while this module periodically checks whether the current visual observation can be matched to a known reference map or orthophoto. If a reliable match is found, the system can produce a correction candidate: latitude, longitude, heading, match confidence, and diagnostic images.

The expected role in the wider project is:

```text
Event/RGB/IMU odometry gives relative trajectory
        ↓
Satellite/drone matcher gives occasional absolute correction
        ↓
Fusion layer accepts/rejects correction based on confidence
        ↓
Navigation state drift is bounded and measurable
```

This task should be implemented as an **offline-first evaluation module** before being integrated into an onboard pipeline. The first version should prioritize correctness, diagnostics, and reproducibility over real-time speed.

---

## 2. Area of Interest

The requested area is defined by two diagonal border coordinates.

### 2.1 Input coordinates in DMS format

```text
Point A: 45°39'40.36"N, 34°10'29.15"E
Point B: 45°25'9.49"N, 34°41'28.77"E
```

### 2.2 Converted decimal degrees

```text
Point A latitude:   45.6612111111
Point A longitude:  34.1747638889

Point B latitude:   45.4193027778
Point B longitude:  34.6913250000
```

### 2.3 AOI bounding box

Because the two points are diagonal corners, the normalized bounding box is:

```text
North: 45.6612111111
South: 45.4193027778
West:  34.1747638889
East:  34.6913250000
```

Approximate center:

```text
Center latitude:  45.5402569444
Center longitude: 34.4330444444
```

Approximate AOI size:

```text
North–south distance: ~26.9 km
East–west distance:   ~40.2 km
```

Approximate AOI area:

```text
~1,080 km²
```

### 2.4 Important implementation implication

The full AOI is too large for direct high-resolution keypoint matching as a single image. The matcher must use **tiling and local search windows**.

Recommended working windows:

```text
Coarse overview:       full AOI, low resolution
Initial local search:  2 km × 2 km to 5 km × 5 km
Fine matching crop:    300 m × 300 m to 1 km × 1 km
Final homography crop: one reference tile/crop around the predicted drone location
```

---

## 3. Imagery Resources

The implementation must separate **imagery source** from **matching algorithm**. The matcher should accept any georeferenced raster, not depend on a single provider.

### 3.1 Primary development resource: team-provided authorized high-resolution raster

For detailed keypoint matching, the best practical input is a **high-resolution orthophoto or satellite basemap crop** that the team is allowed to use locally.

Accepted formats:

```text
GeoTIFF: preferred
PNG/JPEG + world file: acceptable
PNG/JPEG + JSON metadata: acceptable
TMS/XYZ tile folder + metadata: acceptable for local experiments
```

Required metadata:

```text
Coordinate reference system, preferably EPSG:4326 or EPSG:3857
Pixel-to-map transform
Image bounds in lat/lon
Ground sampling distance, if known
Attribution/source information
License/use constraints
```

This is the input type the algorithm should target for the hackathon demo.

### 3.2 Sentinel-2: coarse free/open layer

Use Sentinel-2 for:

```text
- full-AOI overview
- coarse land-cover context
- testing geospatial cropping and coordinate conversion
- visualization of the complete search region
```

Do not rely on Sentinel-2 for precise keypoint matching between drone frames and satellite imagery. Its best RGB-relevant bands are 10 m/pixel, which is too coarse for small features.

Reference:

- Copernicus Data Space: Sentinel-2 has 13 spectral bands with four bands at 10 m, six at 20 m, and three at 60 m spatial resolution: https://dataspace.copernicus.eu/data-collections/copernicus-sentinel-missions/sentinel-2

### 3.3 OpenAerialMap: best open-license candidate if coverage exists

Use OpenAerialMap when there is coverage for the AOI or for a safe demo area.

Advantages:

```text
- openly licensed imagery
- can be high resolution when available
- suitable for a reproducible public demo
```

Limitations:

```text
- coverage is uneven
- imagery may not exist for this exact AOI
- data quality and capture dates vary by contributor
```

References:

- OpenAerialMap legal page: https://openaerialmap.org/legal/
- AWS Open Data Registry for OpenAerialMap: https://registry.opendata.aws/openaerialmap/

### 3.4 Esri World Imagery: useful basemap, but respect license and attribution

Esri World Imagery can be useful as a high-detail visual basemap, often much more detailed than Sentinel-2. However, it should be treated as a **service-backed basemap** unless the team has a permitted offline/export workflow.

Use it for:

```text
- visual inspection
- demo basemap inside an allowed application
- comparison against locally authorized reference crops
```

Do not assume unrestricted bulk downloading, redistribution, or packaging of raw tiles.

Reference:

- Esri services require proper attribution and are governed by Esri terms: https://www.esri.com/en-us/legal/terms/web-site-service

### 3.5 Google Earth Pro / Google Earth captures

Google Earth Pro can be used locally by the team to create **synthetic/demo reference captures** for experiments, especially because the existing simulator already uses Google Earth flight/capture logic.

Use it for:

```text
- local prototyping
- visual sanity checks
- synthetic drone-vs-reference experiments
- hackathon screenshots generated by the team under permitted usage
```

Do not implement bulk Google tile scraping or cached tile redistribution.

### 3.6 Commercial imagery: best quality if available

If the team gets temporary access to commercial imagery, this is the best source for detailed keypoint matching.

Possible providers:

```text
- Maxar
- Airbus OneAtlas
- Planet
- local national orthophoto portals, if available
```

Expected benefit:

```text
- sub-meter imagery is much better for drone-to-satellite keypoint matching
- roads, buildings, field boundaries, tree lines, and small structures become usable
```

But the code must not depend on a specific commercial source. It should accept a georeferenced raster from any provider.

---

## 4. Core Implementation Deliverable

Create a module called:

```text
satellite_drone_matcher.py
```

or package layout:

```text
src/map_matching/
  __init__.py
  aoi.py
  raster_io.py
  preprocess.py
  features.py
  matching.py
  geometry.py
  confidence.py
  cli.py
```

The implementation should provide:

```text
1. AOI definition from the two border coordinates
2. Reference raster loading and metadata validation
3. Drone image loading
4. Image preprocessing
5. Keypoint detection and descriptor extraction
6. Descriptor matching
7. RANSAC geometric verification
8. Homography or affine transform estimation
9. Drone image center projection into map coordinates
10. Optional heading estimation
11. Match quality scoring
12. Output artifacts for debugging and evaluation
```

---

## 5. Inputs

### 5.1 Required inputs

```text
--drone-img      Path to the drone image or frame
--ref-img        Path to the reference satellite/orthophoto crop
--ref-meta       Path to reference metadata JSON or GeoTIFF transform
--out-dir        Output directory
```

### 5.2 Optional inputs

```text
--aoi            AOI JSON file; defaults to the coordinates above
--method         orb | akaze | sift | superpoint_lightglue
--edge-mode      none | canny | sobel | lsd | event_edge
--prior-lat      optional coarse prior latitude
--prior-lon      optional coarse prior longitude
--prior-radius   optional search radius in meters
--camera-yaw     optional yaw prior from odometry/IMU
--camera-calib   optional camera intrinsics file
--manual-gcps    optional manual control points JSON
```

### 5.3 Reference metadata JSON format

Example:

```json
{
  "source": "authorized_reference_raster",
  "license": "team-provided / permitted local use",
  "crs": "EPSG:4326",
  "west": 34.1747638889,
  "south": 45.4193027778,
  "east": 34.6913250000,
  "north": 45.6612111111,
  "width_px": 12000,
  "height_px": 8000,
  "attribution": "Fill with provider attribution",
  "gsd_m_per_px": 0.5
}
```

---

## 6. Outputs

The module should write the following files:

```text
match_result.json
estimated_pose.geojson
matches_raw.jpg
matches_inliers.jpg
warped_overlay.jpg
debug_keypoints_drone.jpg
debug_keypoints_reference.jpg
```

### 6.1 `match_result.json`

Required fields:

```json
{
  "status": "success | low_confidence | failed",
  "method": "orb",
  "edge_mode": "canny",
  "drone_image": "frames/drone_0001.jpg",
  "reference_image": "data/reference_crop.png",
  "num_keypoints_drone": 1400,
  "num_keypoints_reference": 2200,
  "num_raw_matches": 380,
  "num_inlier_matches": 74,
  "inlier_ratio": 0.1947,
  "median_reprojection_error_px": 2.8,
  "estimated_center_lat": 45.5401,
  "estimated_center_lon": 34.4328,
  "estimated_heading_deg": 81.0,
  "confidence": 0.76,
  "warnings": []
}
```

### 6.2 `estimated_pose.geojson`

The GeoJSON should contain at minimum:

```text
- estimated center point
- optional matched footprint polygon
- confidence score
- source reference image
```

---

## 7. Algorithms to Implement

The project should implement the algorithm in stages. Each stage should be independently testable.

---

### Stage 1: AOI and Coordinate Utilities

Implement utilities for:

```text
- DMS to decimal-degree conversion
- bounding box construction
- AOI center computation
- approximate distance computation
- lat/lon to image pixel conversion
- image pixel to lat/lon conversion
```

Required functions:

```python
def dms_to_decimal(degrees: float, minutes: float, seconds: float, hemisphere: str) -> float:
    ...

@dataclass
class AOI:
    north: float
    south: float
    west: float
    east: float

    @property
    def center(self) -> tuple[float, float]:
        ...

    def contains(self, lat: float, lon: float) -> bool:
        ...
```

Acceptance test:

```text
The two input DMS coordinates must convert exactly into the decimal-degree values listed in Section 2.
```

---

### Stage 2: Reference Raster Loader

Implement a loader for georeferenced imagery.

Preferred support:

```text
1. GeoTIFF via rasterio
2. PNG/JPEG + metadata JSON
3. PNG/JPEG + world file, if easy
```

Required behavior:

```text
- reject missing georeferencing metadata
- report image bounds
- report pixel resolution estimate
- support cropping a local search window by lat/lon bounds
- preserve provider attribution in outputs
```

Recommended libraries:

```text
rasterio
pyproj
shapely
opencv-python
numpy
Pillow
```

---

### Stage 3: Image Preprocessing

Satellite and drone images differ in scale, perspective, illumination, season, and camera angle. Preprocessing should produce several alternative views for matching.

Implement preprocessing modes:

```text
rgb_gray:
  Convert both images to grayscale.

clahe:
  Apply contrast-limited adaptive histogram equalization.

edge_canny:
  Convert both images to edge maps using Canny.

edge_sobel:
  Use gradient magnitude as a structural image.

vegetation_suppressed_optional:
  Reduce color dominance of fields/vegetation if RGB data supports it.
```

Recommended first version:

```text
Use grayscale + CLAHE for ORB/AKAZE.
Use Canny edge maps for event/satellite structural matching.
```

---

### Stage 4: Keypoint Detectors and Descriptors

Implement multiple feature backends behind one interface.

#### 4.1 ORB baseline

ORB should be the default baseline because it is fast and available in standard OpenCV.

Use for:

```text
- first implementation
- CPU-only tests
- embedded-friendly baseline
```

Parameters to expose:

```text
nfeatures
scaleFactor
nlevels
fastThreshold
```

Recommended starting values:

```text
nfeatures = 5000
scaleFactor = 1.2
nlevels = 8
fastThreshold = 10
```

#### 4.2 AKAZE baseline

AKAZE can sometimes be more robust to scale/blur changes than ORB.

Use for:

```text
- second baseline
- comparison against ORB
- difficult rural texture cases
```

#### 4.3 SIFT optional baseline

SIFT is often stronger for scale changes and textured scenes, but it can be slower.

Use for:

```text
- offline benchmark
- stronger non-real-time baseline
- checking if ORB/AKAZE failure is algorithmic or data-quality related
```

#### 4.4 Learned features optional extension

If time permits, add:

```text
- SuperPoint + LightGlue
- DISK + LightGlue
- LoFTR
```

Use learned matching for:

```text
- larger viewpoint changes
- weak texture
- satellite/drone appearance gap
- final demo if classical features are unreliable
```

Keep learned methods optional so the baseline remains simple and reproducible.

---

### Stage 5: Descriptor Matching

Implement matching rules per feature type.

#### ORB / AKAZE binary descriptors

Use:

```text
cv2.BFMatcher(cv2.NORM_HAMMING)
```

Apply:

```text
- k-nearest neighbors with k=2
- Lowe ratio test
- optional mutual nearest-neighbor cross-check
```

Recommended ratio threshold:

```text
0.70 to 0.80
```

#### SIFT float descriptors

Use:

```text
cv2.BFMatcher(cv2.NORM_L2)
```

or FLANN if needed.

Recommended ratio threshold:

```text
0.70 to 0.75
```

---

### Stage 6: Geometric Verification

Raw descriptor matches are not enough. The system must use geometry to reject false matches.

Implement:

```text
cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, reprojThreshold)
```

Where:

```text
src_pts = drone image keypoints
inside dst_pts = reference image keypoints
```

Recommended RANSAC threshold:

```text
3 px to 8 px depending on image resolution
```

Minimum acceptance thresholds:

```text
minimum raw matches:        30
minimum inlier matches:     12
minimum inlier ratio:       0.10
max median reproj error:    8 px
```

For a stronger demo, use stricter values:

```text
minimum inlier matches:     30
minimum inlier ratio:       0.20
max median reproj error:    5 px
```

Reference:

- OpenCV homography + feature matching tutorial: https://docs.opencv.org/3.4/d1/de0/tutorial_py_feature_homography.html

---

### Stage 7: Pose Approximation

After estimating the homography from drone image pixels to reference image pixels:

```text
H_drone_to_ref
```

Project the drone image center:

```text
center_drone_px = [width / 2, height / 2, 1]
center_ref_px = H_drone_to_ref @ center_drone_px
center_ref_px = center_ref_px / center_ref_px[2]
```

Then convert the reference pixel coordinate to lat/lon using the raster geotransform.

This gives:

```text
estimated_center_lat
estimated_center_lon
```

### 7.1 Heading estimation

Estimate heading by projecting a vertical image vector into the reference image.

Example:

```text
p0 = drone image center
p1 = point above center in the drone image
p0_ref = H(p0)
p1_ref = H(p1)
heading = atan2(delta_east, delta_north)
```

The first version should label heading as approximate because:

```text
- drone camera may be tilted
- reference map is nadir/orthographic
- homography is only locally valid
- terrain relief and buildings can distort alignment
```

---

## 8. Control Points

Manual control points are needed as a fallback and for evaluation.

### 8.1 Manual GCP JSON format

```json
{
  "points": [
    {
      "id": "road_crossing_001",
      "drone_px": [512, 430],
      "ref_px": [8120, 3910],
      "note": "road crossing"
    },
    {
      "id": "field_corner_002",
      "drone_px": [740, 505],
      "ref_px": [8402, 4177],
      "note": "field boundary corner"
    }
  ]
}
```

### 8.2 Manual GCP use cases

Use manual GCPs to:

```text
- verify coordinate transforms
- create ground-truth checks for a few frames
- debug automatic matching failure
- measure reprojection error
- bootstrap a demo when automatic matching is not yet robust
```

### 8.3 Recommended control-point types

Good control points:

```text
- road intersections
- road bends
- building corners
- bridges
- field boundary corners
- canal/river bends
- isolated tree lines
- sharp shoreline or pond corners
```

Bad control points:

```text
- moving vehicles
- temporary objects
- shadows
- crop texture without stable geometry
- repetitive field patterns
- forest texture
```

---

## 9. Search Strategy

The matcher should not search the whole AOI at full resolution.

### 9.1 Without odometry prior

Use a coarse-to-fine grid:

```text
1. Split AOI into large tiles.
2. Extract low-resolution descriptors or structural edges per tile.
3. Score candidate tiles against the drone frame.
4. Keep top K candidates.
5. Run full-resolution keypoint matching only on top candidates.
```

Recommended first implementation:

```text
K = 5 candidate tiles
coarse tile size = 2 km × 2 km
fine crop size = 500 m × 500 m
```

### 9.2 With odometry prior

Use relative odometry to predict a local search area:

```text
predicted_lat, predicted_lon, uncertainty_radius_m
```

Then search only within:

```text
uncertainty_radius_m + safety_margin
```

Example:

```text
if odometry drift uncertainty is 200 m,
search a 500 m to 1 km local window.
```

This is the expected mode for integration with the drone navigation pipeline.

---

## 10. Matching Modes

Implement three modes.

### 10.1 RGB-to-satellite mode

Input:

```text
RGB drone frame
RGB satellite/orthophoto crop
```

Recommended pipeline:

```text
CLAHE grayscale
ORB or AKAZE
BFMatcher
Lowe ratio test
RANSAC homography
confidence scoring
```

This is the easiest first milestone.

### 10.2 Edge-to-satellite mode

Input:

```text
edge image from drone frame or event accumulation
RGB satellite/orthophoto crop converted to edges
```

Recommended pipeline:

```text
Canny/Sobel/LSD edge extraction
ORB/AKAZE on edge image
descriptor matching
RANSAC homography
confidence scoring
```

This mode is important because the event-camera map-anchoring problem is closer to matching sparse event edges against dense satellite imagery.

### 10.3 Manual-control-point mode

Input:

```text
manually selected drone/reference correspondences
```

Recommended pipeline:

```text
read GCP JSON
estimate homography or affine transform
compute reprojection error
project drone center to reference map
export pose and diagnostics
```

This mode should work even when automatic keypoint matching fails.

---

## 11. Confidence Scoring

The matcher must never silently output a confident position from a weak match.

Compute a confidence score from:

```text
- number of inliers
- inlier ratio
- median reprojection error
- spatial spread of inliers
- homography plausibility
- agreement with odometry prior, if available
```

Suggested formula:

```text
confidence = weighted_score(
    inlier_count_score,
    inlier_ratio_score,
    reprojection_error_score,
    spatial_coverage_score,
    prior_consistency_score
)
```

Minimum status logic:

```text
if homography is missing:
    status = "failed"
elif num_inliers < threshold:
    status = "low_confidence"
elif median_reprojection_error_px > threshold:
    status = "low_confidence"
elif inliers occupy only a tiny image region:
    status = "low_confidence"
else:
    status = "success"
```

Output should include warnings such as:

```text
- too_few_inliers
- high_reprojection_error
- poor_spatial_coverage
- homography_extreme_scale
- homography_extreme_shear
- outside_aoi
- license_missing_attribution
```

---

## 12. Evaluation Metrics

### 12.1 Matching metrics

```text
number of detected keypoints in drone image
number of detected keypoints in reference image
number of raw descriptor matches
number of RANSAC inliers
inlier ratio
median reprojection error in pixels
spatial coverage of inlier matches
runtime per frame
```

### 12.2 Geolocation metrics, if ground truth is available

```text
lat/lon error in meters
heading error in degrees
accept/reject accuracy
false positive match rate
failure rate
```

### 12.3 Navigation integration metrics

```text
drift before correction
estimated correction magnitude
drift after correction
accepted correction count
rejected correction count
position error versus distance travelled
```

---

## 13. Acceptance Criteria

### 13.1 Minimum viable implementation

The task is complete when the team can run:

```bash
python satellite_drone_matcher.py print-aoi

python satellite_drone_matcher.py match \
  --drone-img data/example_drone.png \
  --ref-img data/example_reference.png \
  --ref-meta data/example_reference.json \
  --out-dir outputs/example_match
```

And the output directory contains:

```text
match_result.json
estimated_pose.geojson
matches_inliers.jpg
```

Minimum success requirements:

```text
- AOI coordinates are correctly converted and printed.
- Reference metadata is validated.
- Keypoints are extracted from both images.
- Descriptor matching runs.
- RANSAC homography is attempted.
- Failure cases are reported explicitly.
- Successful matches produce estimated lat/lon.
```

### 13.2 Strong demo target

The task is strong enough for the hackathon demo when:

```text
- local reference crop is high enough resolution for roads/field/building features
- at least 3 drone/reference examples match successfully
- outputs include visual inlier diagnostics
- low-confidence matches are rejected instead of reported as true positions
- manual GCP fallback works
- the output can be consumed by the future fusion layer
```

---

## 14. Implementation Plan

### Step 1: AOI module

Files:

```text
src/map_matching/aoi.py
```

Implement:

```text
- DMS conversion
- AOI constants
- print-aoi CLI command
- AOI GeoJSON export
- AOI KML export
```

### Step 2: Raster metadata module

Files:

```text
src/map_matching/raster_io.py
```

Implement:

```text
- load PNG/JPEG + JSON metadata
- optional GeoTIFF loading
- pixel_to_latlon
- latlon_to_pixel
- crop_by_latlon_bbox
```

### Step 3: Feature pipeline

Files:

```text
src/map_matching/preprocess.py
src/map_matching/features.py
src/map_matching/matching.py
```

Implement:

```text
- grayscale + CLAHE preprocessing
- Canny edge preprocessing
- ORB backend
- AKAZE backend
- descriptor matching
- ratio test
- RANSAC homography
```

### Step 4: Geometry and pose

Files:

```text
src/map_matching/geometry.py
```

Implement:

```text
- project drone image center through homography
- convert reference pixel to lat/lon
- estimate heading from projected image-up vector
- compute footprint polygon
```

### Step 5: Confidence and diagnostics

Files:

```text
src/map_matching/confidence.py
src/map_matching/visualize.py
```

Implement:

```text
- inlier scoring
- reprojection error
- spatial coverage check
- homography plausibility check
- output visualization images
```

### Step 6: CLI integration

Files:

```text
satellite_drone_matcher.py
```

Commands:

```text
print-aoi
export-aoi-geojson
export-aoi-kml
match
manual-gcp
benchmark-folder
```

---

## 15. Recommended CLI Design

```bash
python satellite_drone_matcher.py print-aoi
```

```bash
python satellite_drone_matcher.py export-aoi-geojson \
  --out data/aoi.geojson
```

```bash
python satellite_drone_matcher.py match \
  --drone-img frames/drone_0001.jpg \
  --ref-img data/reference_crop.png \
  --ref-meta data/reference_crop.json \
  --method orb \
  --edge-mode none \
  --out-dir outputs/match_0001
```

```bash
python satellite_drone_matcher.py match \
  --drone-img frames/drone_0001.jpg \
  --ref-img data/reference_crop.png \
  --ref-meta data/reference_crop.json \
  --method akaze \
  --edge-mode canny \
  --out-dir outputs/match_0001_edges
```

```bash
python satellite_drone_matcher.py manual-gcp \
  --drone-img frames/drone_0001.jpg \
  --ref-img data/reference_crop.png \
  --ref-meta data/reference_crop.json \
  --manual-gcps data/gcps_0001.json \
  --out-dir outputs/manual_0001
```

---

## 16. Repository Integration

Recommended repository additions:

```text
README_MAP_MATCHING.md
requirements-map-matching.txt
satellite_drone_matcher.py
src/map_matching/
  aoi.py
  raster_io.py
  preprocess.py
  features.py
  matching.py
  geometry.py
  confidence.py
  visualize.py
data/
  aoi.geojson
  aoi.kml
  manual_gcps.example.json
outputs/
  .gitkeep
```

Recommended dependencies:

```text
numpy
opencv-python
Pillow
rasterio
pyproj
shapely
geopandas optional
matplotlib optional
```

Do not commit large downloaded imagery to Git. Store reference rasters outside the repo or under a gitignored data directory.

Recommended `.gitignore` additions:

```text
data/reference_rasters/
data/tiles/
outputs/
*.tif
*.tiff
*.jp2
```

---

## 17. Risks and Mitigations

### Risk 1: Public free imagery is not detailed enough

Mitigation:

```text
Use Sentinel-2 only for overview.
Use OpenAerialMap where available.
Use authorized high-resolution raster crops for real matching.
Use Google Earth Pro/local simulator captures for synthetic demo experiments.
```

### Risk 2: Rural terrain has repetitive fields

Mitigation:

```text
Prefer roads, crossings, water edges, field corners, and buildings.
Reject low spatial coverage matches.
Use odometry prior to restrict search.
```

### Risk 3: Drone view is oblique but map is nadir

Mitigation:

```text
Prefer near-nadir drone frames for first demo.
Use homography only locally.
Add camera calibration and approximate ground-plane assumptions later.
```

### Risk 4: False positives over similar fields

Mitigation:

```text
Use RANSAC inliers, spatial coverage, homography plausibility, and odometry prior consistency.
Return low_confidence instead of a false position.
```

### Risk 5: License or attribution problems

Mitigation:

```text
Store source and attribution in reference metadata.
Do not bulk scrape or redistribute proprietary basemap tiles.
Use open data or authorized team-provided rasters for shared artifacts.
```

---

## 18. Definition of Done

The task is done when:

```text
1. The AOI from the two coordinates is represented in code.
2. The matcher accepts a drone image and a georeferenced reference crop.
3. ORB and AKAZE matching are implemented.
4. RANSAC homography verification is implemented.
5. Estimated center lat/lon is exported when confidence is sufficient.
6. Failed or weak matches are explicitly rejected.
7. Manual GCP fallback is implemented.
8. Diagnostic images are saved.
9. A README explains how to run the module.
10. A small reproducible test case is included using safe, non-sensitive or synthetic imagery.
```

---

## 19. Suggested First Engineering Ticket

Title:

```text
Implement AOI-aware satellite/drone keypoint matcher with ORB, AKAZE, RANSAC, and manual GCP fallback
```

Description:

```text
Create a map-matching module for the drone navigation project. The module shall use the AOI defined by the diagonal coordinates 45°39'40.36"N, 34°10'29.15"E and 45°25'9.49"N, 34°41'28.77"E. It shall load a drone image and a georeferenced reference image, extract keypoints, match descriptors, verify matches with RANSAC homography, and output an estimated center position, optional heading, confidence score, GeoJSON, and visual diagnostics.

The first implementation shall support ORB and AKAZE, grayscale/CLAHE preprocessing, optional Canny edge mode, metadata-based pixel-to-lat/lon conversion, and manual control-point fallback. The matcher shall not silently accept weak matches; it must return low_confidence or failed when inliers, reprojection error, or spatial coverage are insufficient.
```

Acceptance criteria:

```text
- `print-aoi` prints the normalized AOI bounds and center.
- `match` produces `match_result.json`, `estimated_pose.geojson`, and `matches_inliers.jpg`.
- Weak matches are rejected with diagnostic warnings.
- Manual GCP mode estimates a transform and reports reprojection error.
- The implementation works with PNG/JPEG + metadata JSON and optionally GeoTIFF.
```

