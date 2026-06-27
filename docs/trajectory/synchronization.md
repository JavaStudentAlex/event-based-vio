# Synchronization Policy and Trajectory Export Contract

This document locks the synchronization policy and diagnostic fields used to align diverse sensor and model trajectories (e.g., IMU, events, images, ground-truth poses) in the navigation benchmark.

## Synchronization Policy: Nearest Neighbor with Tolerance

When evaluating or fusing visual-inertial odometry (VIO) estimation, we must match timestamps from a **source** sequence (typically the VIO method's outputs or IMU samples) to a **target** sequence (typically the ground-truth trajectory).

The primary matching policy is **Nearest-Neighbor-with-Tolerance**.

### Key Rules and Semantics

1. **Association Policy**: For each source timestamp $t_s$, the algorithm finds the target timestamp $t_t$ that minimizes $|t_s - t_t|$.
2. **Tolerance Window**: A match is valid only if $|t_s - t_t| \le \text{tolerance\_sec}$. If no target timestamp falls within this tolerance, the source timestamp remains unmatched.
3. **Monotonicity**:
   * Timestamps for both sequences must be strictly monotonically increasing.
   * Duplicate timestamps in either sequence are treated as violations of strict monotonicity and will raise a `ValueError`.
4. **Deduplication**:
   * If multiple source timestamps match the same target timestamp, the match with the **smallest absolute time difference** is preserved.
   * If there is a tie in difference, the order of matching prioritizes uniqueness while maintaining chronological ordering.
5. **No Interpolation**: We match to the nearest discrete observation. Interpolation of ground-truth state is intentionally avoided in this layer to preserve raw data association fidelity.

---

## Diagnostics: `SyncDiagnostics`

Every synchronization run returns a `SyncDiagnostics` object. This metadata is serialized and recorded alongside trajectory logs to verify synchronization quality and detect data-loss/coverage anomalies.

### Fields

| Field Name | Type | Unit | Description |
|:---|:---|:---|:---|
| `source_count` | `int` | Count | Total number of timestamps in the source sequence. |
| `target_count` | `int` | Count | Total number of timestamps in the target sequence. |
| `matched_count` | `int` | Count | Number of successfully paired timestamps within tolerance. |
| `unmatched_source_count` | `int` | Count | Number of source timestamps that could not be matched. |
| `unmatched_target_count` | `int` | Count | Number of target timestamps that could not be matched. |
| `tolerance_sec` | `float` | Seconds | The maximum allowed difference threshold used for matching. |
| `first_matched_timestamp` | `float \| None` | Seconds | The timestamp of the first matched source sample, or `None`. |
| `last_matched_timestamp` | `float \| None` | Seconds | The timestamp of the last matched source sample, or `None`. |
| `overlap_sufficiency` | `float` | Ratio (0.0 to 1.0) | Ratio of matched count to the maximum length of either sequence. |
| `unmatched_source_ranges` | `list[tuple[float, float]]` | Seconds (start, end) | List of continuous unmatched source time intervals. |
| `unmatched_target_ranges` | `list[tuple[float, float]]` | Seconds (start, end) | List of continuous unmatched target time intervals. |

---

## Code Interface

The synchronization algorithm resides in `src/nav_benchmark/trajectory/sync.py`:

```python
def synchronize_nearest_neighbor(
    source_timestamps: np.ndarray,
    target_timestamps: np.ndarray,
    tolerance_sec: float,
) -> tuple[np.ndarray, np.ndarray, SyncDiagnostics]:
    """
    Synchronizes source timestamps to target timestamps using nearest neighbor matching.
    """
```

### Constraints and Error Handling

* **Negative Tolerance**: If `tolerance_sec` is negative, a `ValueError("tolerance_sec must be non-negative")` is raised.
* **Non-monotonic Inputs**: If either input array is not strictly monotonically increasing, a `ValueError` indicating the invalid sequence is raised.

---

## Examples

### Complete Overlap (Exact Match)
* **Source**: `[0.0, 1.0, 2.0, 3.0]`
* **Target**: `[0.0, 1.0, 2.0, 3.0]`
* **Tolerance**: `0.1` seconds
* **Result**:
  * Matched Source Indices: `[0, 1, 2, 3]`
  * Matched Target Indices: `[0, 1, 2, 3]`
  * `overlap_sufficiency`: `1.0`

### Partial Match with Unmatched Ranges
* **Source**: `[0.0, 1.05, 2.0, 3.2]`
* **Target**: `[0.0, 1.0, 2.0, 3.0]`
* **Tolerance**: `0.1` seconds
* **Result**:
  * Matched Source Indices: `[0, 1, 2]` (corresponds to values `[0.0, 1.05, 2.0]`)
  * Matched Target Indices: `[0, 1, 2]` (corresponds to values `[0.0, 1.0, 2.0]`)
  * `unmatched_source_ranges`: `[(3.2, 3.2)]`
  * `unmatched_target_ranges`: `[(3.0, 3.0)]`
