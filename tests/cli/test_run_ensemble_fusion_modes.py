"""CLI integration coverage for the ensemble fusion modes."""

import csv
import json
import sys
from pathlib import Path
from unittest import mock

from nav_benchmark.run import main


def _run_ensemble_cli(tiny_sequence: Path, tmp_path: Path, fusion: str) -> Path:
    output_root = tmp_path / "runs"
    argv = [
        "nav_benchmark.run",
        "run",
        "--method",
        "ensemble",
        "--dataset",
        "synthetic",
        "--sequence",
        f"tiny_{fusion}",
        "--input",
        str(tiny_sequence),
        "--output-root",
        str(output_root),
        "--fusion",
        fusion,
    ]
    with mock.patch.object(sys, "argv", argv):
        main()

    run_dirs = list(output_root.glob(f"*_ensemble_tiny_{fusion}"))
    assert len(run_dirs) == 1
    return run_dirs[0]


def test_weighted_ekf_mode_writes_update_logs_and_timeline(tiny_sequence: Path, tmp_path: Path):
    run_dir = _run_ensemble_cli(tiny_sequence, tmp_path, "weighted_ekf")

    assert (run_dir / "estimated_trajectory.csv").exists()
    assert (run_dir / "ensemble_weights.csv").exists()
    assert (run_dir / "backend_status_timeline.png").exists()

    with open(run_dir / "ensemble_updates.csv", newline="", encoding="utf-8") as f:
        updates = list(csv.DictReader(f))
    assert len(updates) > 0
    assert {"timestamp", "method", "accepted", "reason"}.issubset(updates[0].keys())

    with open(run_dir / "rejected_updates.csv", newline="", encoding="utf-8") as f:
        rejected = list(csv.DictReader(f))
    assert all(row["accepted"] == "false" for row in rejected)
    assert all(row["reason"] != "" for row in rejected)

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["config"]["fusion_mode"] == "weighted_ekf"
    assert manifest["method"] == "ensemble"


def test_winner_takes_healthy_mode_produces_one_hot_weights(tiny_sequence: Path, tmp_path: Path):
    run_dir = _run_ensemble_cli(tiny_sequence, tmp_path, "winner_takes_healthy")

    with open(run_dir / "ensemble_weights.csv", newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) > 0
    weight_names = [name for name in rows[0] if name.startswith("w_")]
    for row in rows:
        weights = [float(row[name]) for name in weight_names]
        assert sum(1 for w in weights if w == 1.0) == 1
        assert sum(weights) == 1.0

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["config"]["fusion_mode"] == "winner_takes_healthy"
    assert (run_dir / "backend_status_timeline.png").exists()


def test_default_confidence_weighted_mode_still_works(tiny_sequence: Path, tmp_path: Path):
    run_dir = _run_ensemble_cli(tiny_sequence, tmp_path, "confidence_weighted")

    assert (run_dir / "estimated_trajectory.csv").exists()
    assert (run_dir / "ensemble_weights.csv").exists()
    assert (run_dir / "backend_status_timeline.png").exists()
    assert not (run_dir / "ensemble_updates.csv").exists()

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["config"]["fusion_mode"] == "confidence_weighted"
