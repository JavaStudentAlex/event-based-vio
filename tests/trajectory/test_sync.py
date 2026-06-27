import numpy as np

from nav_benchmark.trajectory.sync import synchronize_nearest_neighbor


def test_synchronize_nearest_neighbor_exact_match():
    source_ts = np.array([0.0, 1.0, 2.0, 3.0])
    target_ts = np.array([0.0, 1.0, 2.0, 3.0])

    s_idx, t_idx, diag = synchronize_nearest_neighbor(source_ts, target_ts, tolerance_sec=0.1)

    np.testing.assert_array_equal(s_idx, [0, 1, 2, 3])
    np.testing.assert_array_equal(t_idx, [0, 1, 2, 3])

    assert diag.matched_count == 4
    assert diag.unmatched_source_count == 0
    assert diag.unmatched_target_count == 0
    assert diag.overlap_sufficiency == 1.0


def test_synchronize_nearest_neighbor_with_tolerance():
    source_ts = np.array([0.0, 1.05, 2.0, 3.2])
    target_ts = np.array([0.0, 1.0, 2.0, 3.0])

    # 1.05 matches 1.0 (diff 0.05 <= 0.1)
    # 3.2 does not match 3.0 (diff 0.2 > 0.1)
    s_idx, t_idx, diag = synchronize_nearest_neighbor(source_ts, target_ts, tolerance_sec=0.1)

    np.testing.assert_array_equal(s_idx, [0, 1, 2])
    np.testing.assert_array_equal(t_idx, [0, 1, 2])

    assert diag.matched_count == 3
    assert diag.unmatched_source_count == 1
    assert diag.unmatched_target_count == 1
    assert diag.unmatched_source_ranges == [(3.2, 3.2)]
    assert diag.unmatched_target_ranges == [(3.0, 3.0)]


def test_synchronize_nearest_neighbor_duplicates():
    # If multiple sources match the same target, the one with the smallest difference should be kept
    source_ts = np.array([0.9, 1.01, 1.1])
    target_ts = np.array([1.0])

    s_idx, t_idx, diag = synchronize_nearest_neighbor(source_ts, target_ts, tolerance_sec=0.5)

    # 1.01 is the closest to 1.0
    np.testing.assert_array_equal(s_idx, [1])
    np.testing.assert_array_equal(t_idx, [0])

    assert diag.matched_count == 1


def test_synchronize_nearest_neighbor_empty():
    source_ts = np.array([])
    target_ts = np.array([1.0, 2.0])

    s_idx, t_idx, diag = synchronize_nearest_neighbor(source_ts, target_ts, tolerance_sec=0.1)

    assert len(s_idx) == 0
    assert len(t_idx) == 0
    assert diag.matched_count == 0
    assert diag.unmatched_source_count == 0
    assert diag.unmatched_target_count == 2
