import csv
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from nav_benchmark.reporting.compare import compare_runs, load_run_summary, write_comparison_artifacts


def _write_run_dir(
    root: Path,
    name: str,
    method: str,
    *,
    drift_percent: float | None,
    ate_rmse: float = 1.0,
    status: str = "OK",
) -> Path:
    run_dir = root / name
    run_dir.mkdir(parents=True)

    manifest = {"method": method, "sequence": "seq1", "status": "success"}
    (run_dir / "run_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

    metrics = {
        "status": status,
        "metrics": {
            "ate_rmse": ate_rmse,
            "rpe_rmse": 0.5,
            "final_drift": 2.0,
            "cumulative_distance": 100.0,
            "drift_percent": drift_percent,
        },
        "coverage": {"ok_fraction": 0.9, "lost_fraction": 0.05},
        "failures": {"failed_window_count": 1},
        "runtime": {"latency_mean_ms": 3.0, "latency_p95_ms": 6.0, "real_time_factor": 12.0},
        "drift_bins": [
            {"bin_start": 0.0, "bin_end": 20.0, "median_error": 0.4, "iqr_error": 0.1, "pose_count": 10},
            {"bin_start": 20.0, "bin_end": 40.0, "median_error": 0.9, "iqr_error": 0.2, "pose_count": 8},
            {"bin_start": 40.0, "bin_end": 60.0, "median_error": None, "iqr_error": None, "pose_count": 0},
        ],
    }
    (run_dir / "metrics.json").write_text(json.dumps(metrics), encoding="utf-8")
    return run_dir


class TestLoadRunSummary:
    def test_reads_manifest_and_metrics(self, tmp_path):
        run_dir = _write_run_dir(tmp_path, "run_a", "imu_only", drift_percent=8.5)
        summary = load_run_summary(run_dir)

        assert summary.method == "imu_only"
        assert summary.sequence == "seq1"
        assert summary.status == "OK"
        assert summary.drift_percent == 8.5
        assert summary.ate_rmse == 1.0
        assert summary.ok_fraction == 0.9
        assert summary.failed_window_count == 1
        assert summary.real_time_factor == 12.0
        assert len(summary.drift_bins) == 3

    def test_missing_metrics_raises_with_guidance(self, tmp_path):
        run_dir = tmp_path / "run_no_eval"
        run_dir.mkdir()
        (run_dir / "run_manifest.json").write_text(json.dumps({"method": "imu_only"}), encoding="utf-8")

        with pytest.raises(FileNotFoundError, match="run `eval` first"):
            load_run_summary(run_dir)

    def test_missing_manifest_raises(self, tmp_path):
        run_dir = tmp_path / "empty"
        run_dir.mkdir()
        with pytest.raises(FileNotFoundError, match="Run manifest"):
            load_run_summary(run_dir)


class TestCompareRuns:
    def test_ranks_by_drift_percent_with_none_last(self, tmp_path):
        a = _write_run_dir(tmp_path, "a", "imu_only", drift_percent=25.0)
        b = _write_run_dir(tmp_path, "b", "event_imu", drift_percent=3.0)
        c = _write_run_dir(tmp_path, "c", "rgb_vo", drift_percent=None)

        summaries = compare_runs([a, b, c])

        assert [s.method for s in summaries] == ["event_imu", "imu_only", "rgb_vo"]

    def test_requires_at_least_two_runs(self, tmp_path):
        run_dir = _write_run_dir(tmp_path, "solo", "imu_only", drift_percent=1.0)
        with pytest.raises(ValueError, match="at least two"):
            compare_runs([run_dir])


class TestWriteComparisonArtifacts:
    def test_writes_json_table_and_plot(self, tmp_path):
        a = _write_run_dir(tmp_path, "a", "imu_only", drift_percent=25.0)
        b = _write_run_dir(tmp_path, "b", "event_imu", drift_percent=3.0)
        out_dir = tmp_path / "comparison"

        summaries = compare_runs([a, b])
        paths = write_comparison_artifacts(summaries, out_dir)

        payload = json.loads(paths["metrics_comparison"].read_text(encoding="utf-8"))
        assert payload["run_count"] == 2
        assert payload["ranking_by_drift_percent"] == ["event_imu", "imu_only"]
        assert payload["runs"][0]["method"] == "event_imu"

        with open(paths["comparison_table"], newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[0]["method"] == "event_imu"
        assert rows[0]["drift_percent"] == "3.0"
        assert rows[1]["drift_percent"] == "25.0"

        assert paths["drift_plot"].exists()
        assert (out_dir / "backend_comparison_drift.svg").exists()

    def test_duplicate_methods_get_distinct_labels(self, tmp_path):
        a = _write_run_dir(tmp_path, "a", "imu_only", drift_percent=25.0)
        b = _write_run_dir(tmp_path, "b", "imu_only", drift_percent=3.0)
        out_dir = tmp_path / "comparison"

        summaries = compare_runs([a, b])
        paths = write_comparison_artifacts(summaries, out_dir)
        assert paths["drift_plot"].exists()


def test_compare_cli_end_to_end(tmp_path, capsys):
    from nav_benchmark.run import main

    a = _write_run_dir(tmp_path, "a", "imu_only", drift_percent=25.0)
    b = _write_run_dir(tmp_path, "b", "event_imu", drift_percent=3.0)
    out_dir = tmp_path / "cmp"

    argv = ["nav_benchmark.run", "compare", "--run-dirs", str(a), str(b), "--output", str(out_dir)]
    with mock.patch.object(sys, "argv", argv):
        main()

    captured = capsys.readouterr()
    assert "Compared 2 runs" in captured.out
    assert "1. event_imu" in captured.out
    assert (out_dir / "metrics_comparison.json").exists()
    assert (out_dir / "comparison_table.csv").exists()
    assert (out_dir / "backend_comparison_drift.png").exists()


def _add_estimated_trajectory(run_dir: Path, health_labels: list[str]) -> None:
    import numpy as np

    from nav_benchmark.trajectory.export import export_project_csv
    from nav_benchmark.trajectory.models import Trajectory

    count = len(health_labels)
    trajectory = Trajectory(
        timestamps=np.arange(count, dtype=np.float64),
        method="imu_only",
        positions=np.zeros((count, 3)),
        orientations=np.tile([0.0, 0.0, 0.0, 1.0], (count, 1)),
        health=np.array(health_labels, dtype=object),
    )
    export_project_csv(trajectory, run_dir / "estimated_trajectory.csv")


def _add_error_vs_time(run_dir: Path, x_offset: float) -> None:
    header = (
        "timestamp,est_x,est_y,est_z,gt_aligned_x,gt_aligned_y,gt_aligned_z,"
        "error_x,error_y,error_z,error_magnitude,health,association_residual"
    )
    rows = [header]
    for i in range(5):
        t = float(i)
        rows.append(f"{t},{t + x_offset},{t * 0.5},0.0,{t},{t * 0.5},0.0,{x_offset},0,0,{x_offset},OK,0.01")
    (run_dir / "error_vs_time.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")


class TestFailureIntervalAggregation:
    def test_intervals_extracted_from_estimated_trajectory(self, tmp_path):
        run_dir = _write_run_dir(tmp_path, "a", "imu_only", drift_percent=5.0)
        _add_estimated_trajectory(run_dir, ["OK", "OK", "DEGRADED", "DEGRADED", "LOST", "OK", "INVALID"])

        summary = load_run_summary(run_dir)

        assert summary.failure_interval_count == 3
        states = [interval["state"] for interval in summary.failure_intervals]
        assert states == ["DEGRADED", "LOST", "INVALID"]
        degraded = summary.failure_intervals[0]
        assert degraded["t_start"] == 2.0 and degraded["t_end"] == 3.0
        assert summary.failure_total_duration_sec == pytest.approx(1.0 + 0.0 + 0.0)

    def test_missing_trajectory_yields_empty_aggregation(self, tmp_path):
        run_dir = _write_run_dir(tmp_path, "a", "imu_only", drift_percent=5.0)
        summary = load_run_summary(run_dir)
        assert summary.failure_interval_count == 0
        assert summary.failure_intervals == []

    def test_failure_intervals_json_written(self, tmp_path):
        a = _write_run_dir(tmp_path, "a", "imu_only", drift_percent=25.0)
        b = _write_run_dir(tmp_path, "b", "event_imu", drift_percent=3.0)
        _add_estimated_trajectory(a, ["OK", "LOST", "LOST", "OK"])
        _add_estimated_trajectory(b, ["OK", "OK", "OK", "OK"])

        summaries = compare_runs([a, b])
        paths = write_comparison_artifacts(summaries, tmp_path / "cmp")

        payload = json.loads(paths["failure_intervals"].read_text(encoding="utf-8"))
        assert payload["imu_only"]["interval_count"] == 1
        assert payload["imu_only"]["intervals"][0]["state"] == "LOST"
        assert payload["event_imu"]["interval_count"] == 0

        with open(paths["comparison_table"], newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        by_method = {row["method"]: row for row in rows}
        assert by_method["imu_only"]["failure_interval_count"] == "1"


class TestTrajectoryOverlay:
    def test_overlay_written_when_series_available(self, tmp_path):
        a = _write_run_dir(tmp_path, "a", "imu_only", drift_percent=25.0)
        b = _write_run_dir(tmp_path, "b", "event_imu", drift_percent=3.0)
        _add_error_vs_time(a, x_offset=0.4)
        _add_error_vs_time(b, x_offset=0.1)

        summaries = compare_runs([a, b])
        paths = write_comparison_artifacts(summaries, tmp_path / "cmp")

        assert "trajectory_overlay" in paths
        assert paths["trajectory_overlay"].exists()
        assert (tmp_path / "cmp" / "comparison_trajectories.svg").exists()

    def test_overlay_skipped_without_series(self, tmp_path):
        a = _write_run_dir(tmp_path, "a", "imu_only", drift_percent=25.0)
        b = _write_run_dir(tmp_path, "b", "event_imu", drift_percent=3.0)

        summaries = compare_runs([a, b])
        paths = write_comparison_artifacts(summaries, tmp_path / "cmp")

        assert "trajectory_overlay" not in paths
        assert not (tmp_path / "cmp" / "comparison_trajectories.png").exists()


def test_compare_cli_fails_on_unevaluated_run(tmp_path, capsys):
    from nav_benchmark.run import main

    a = _write_run_dir(tmp_path, "a", "imu_only", drift_percent=25.0)
    bare = tmp_path / "bare"
    bare.mkdir()
    (bare / "run_manifest.json").write_text(json.dumps({"method": "rgb_vo"}), encoding="utf-8")

    argv = ["nav_benchmark.run", "compare", "--run-dirs", str(a), str(bare), "--output", str(tmp_path / "cmp")]
    with mock.patch.object(sys, "argv", argv), pytest.raises(SystemExit) as excinfo:
        main()
    assert excinfo.value.code == 1
    assert "Comparison failed" in capsys.readouterr().err
