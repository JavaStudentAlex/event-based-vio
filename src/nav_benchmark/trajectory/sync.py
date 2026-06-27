import numpy as np

from nav_benchmark.trajectory.models import SyncDiagnostics


def synchronize_nearest_neighbor(
    source_timestamps: np.ndarray,
    target_timestamps: np.ndarray,
    tolerance_sec: float,
) -> tuple[np.ndarray, np.ndarray, SyncDiagnostics]:
    """
    Synchronizes source timestamps to target timestamps using nearest neighbor matching.

    Args:
        source_timestamps: Timestamps of the source sequence.
        target_timestamps: Timestamps of the target sequence.
        tolerance_sec: Maximum allowed time difference for a match.

    Returns:
        matched_source_indices: Indices of matched source timestamps.
        matched_target_indices: Indices of matched target timestamps.
        diagnostics: SyncDiagnostics object.
    """
    _validate_inputs(source_timestamps, target_timestamps, tolerance_sec)

    if len(source_timestamps) == 0 or len(target_timestamps) == 0:
        return (
            np.empty(0, dtype=np.int64),
            np.empty(0, dtype=np.int64),
            SyncDiagnostics(
                source_count=len(source_timestamps),
                target_count=len(target_timestamps),
                matched_count=0,
                unmatched_source_count=len(source_timestamps),
                unmatched_target_count=len(target_timestamps),
                tolerance_sec=tolerance_sec,
                first_matched_timestamp=None,
                last_matched_timestamp=None,
                overlap_sufficiency=0.0,
                unmatched_source_ranges=[],
                unmatched_target_ranges=[],
            ),
        )

    # Find the nearest target timestamp for each source timestamp
    # using searchsorted
    indices = np.searchsorted(target_timestamps, source_timestamps)

    # searchsorted returns the index of the first element in target that is >= source
    # We need to check both indices and indices - 1 to find the absolute nearest
    idx1 = np.clip(indices - 1, 0, len(target_timestamps) - 1)
    idx2 = np.clip(indices, 0, len(target_timestamps) - 1)

    diff1 = np.abs(target_timestamps[idx1] - source_timestamps)
    diff2 = np.abs(target_timestamps[idx2] - source_timestamps)

    nearest_target_idx = np.where(diff1 < diff2, idx1, idx2)
    min_diff = np.where(diff1 < diff2, diff1, diff2)

    # Filter by tolerance
    valid_mask = min_diff <= tolerance_sec

    source_idx = np.arange(len(source_timestamps))[valid_mask]
    target_idx = nearest_target_idx[valid_mask]
    diffs = min_diff[valid_mask]

    # Deduplicate target matches (keep the source with the smallest diff)
    sort_idx = np.argsort(diffs)
    source_idx = source_idx[sort_idx]
    target_idx = target_idx[sort_idx]

    _, unique_idx = np.unique(target_idx, return_index=True)

    matched_source_indices = source_idx[unique_idx]
    matched_target_indices = target_idx[unique_idx]

    # Sort back by time
    sort_by_time = np.argsort(matched_source_indices)
    matched_source_indices = matched_source_indices[sort_by_time]
    matched_target_indices = matched_target_indices[sort_by_time]

    # Calculate diagnostics
    matched_count = len(matched_source_indices)

    # Find unmatched ranges for source
    unmatched_source_mask = np.ones(len(source_timestamps), dtype=bool)
    unmatched_source_mask[matched_source_indices] = False
    unmatched_source_ranges = _find_ranges(source_timestamps, unmatched_source_mask)

    # Find unmatched ranges for target
    unmatched_target_mask = np.ones(len(target_timestamps), dtype=bool)
    unmatched_target_mask[matched_target_indices] = False
    unmatched_target_ranges = _find_ranges(target_timestamps, unmatched_target_mask)

    max_count = max(len(source_timestamps), len(target_timestamps), 1)

    diagnostics = SyncDiagnostics(
        source_count=len(source_timestamps),
        target_count=len(target_timestamps),
        matched_count=matched_count,
        unmatched_source_count=len(source_timestamps) - matched_count,
        unmatched_target_count=len(target_timestamps) - matched_count,
        tolerance_sec=tolerance_sec,
        first_matched_timestamp=float(source_timestamps[matched_source_indices[0]]) if matched_count > 0 else None,
        last_matched_timestamp=float(source_timestamps[matched_source_indices[-1]]) if matched_count > 0 else None,
        overlap_sufficiency=matched_count / max_count,
        unmatched_source_ranges=unmatched_source_ranges,
        unmatched_target_ranges=unmatched_target_ranges,
    )

    return matched_source_indices, matched_target_indices, diagnostics


def _validate_inputs(
    source_timestamps: np.ndarray,
    target_timestamps: np.ndarray,
    tolerance_sec: float,
) -> None:
    if tolerance_sec < 0:
        raise ValueError("tolerance_sec must be non-negative")
    _check_strictly_increasing(source_timestamps, "source_timestamps")
    _check_strictly_increasing(target_timestamps, "target_timestamps")


def _check_strictly_increasing(timestamps: np.ndarray, name: str) -> None:
    if len(timestamps) > 1 and not np.all(np.diff(timestamps) > 0):
        raise ValueError(f"{name} must be strictly monotonically increasing")


def _find_ranges(timestamps: np.ndarray, mask: np.ndarray) -> list[tuple[float, float]]:
    ranges: list[tuple[float, float]] = []
    if len(timestamps) == 0:
        return ranges

    diffs = np.diff(mask.astype(int))

    starts = np.where(diffs == 1)[0] + 1
    if mask[0]:
        starts = np.insert(starts, 0, 0)

    ends = np.where(diffs == -1)[0]
    if mask[-1]:
        ends = np.append(ends, len(mask) - 1)

    for start, end in zip(starts, ends, strict=False):
        ranges.append((float(timestamps[start]), float(timestamps[end])))

    return ranges
