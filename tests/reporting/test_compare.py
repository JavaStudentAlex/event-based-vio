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
