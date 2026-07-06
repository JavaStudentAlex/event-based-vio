"""End-to-end smoke: JEPA pretraining -> PPO training -> rl_gated benchmark run.

Tiny budgets throughout (seconds, not minutes): the goal is to prove the full
implementation chain works through the real CLI, not to train a useful policy.
"""

import csv
import json
import sys
from unittest import mock

import pytest

from nav_benchmark.run import main


def _main(argv: list[str]) -> None:
    with mock.patch.object(sys, "argv", ["nav_benchmark.run", *argv]):
        main()


@pytest.fixture(scope="module")
def journey(tmp_path_factory, tiny_sequence):
    """Run JEPA pretraining and PPO training once for all assertions below."""
    root = tmp_path_factory.mktemp("rl_journey")
    jepa_checkpoint = root / "jepa.pt"
    _main(
        [
            "train-jepa",
            "--dataset",
            "synthetic",
            "--input",
            str(tiny_sequence),
            "--output",
            str(jepa_checkpoint),
            "--steps",
            "25",
            "--batch-size",
            "8",
            "--embed-dim",
            "16",
            "--hidden-dim",
            "32",
            "--device",
            "cpu",
            "--seed",
            "3",
        ]
    )
    train_dir = root / "rl"
    _main(
        [
            "train-rl",
            "--dataset",
            "synthetic",
            "--input",
            str(tiny_sequence),
            "--output-dir",
            str(train_dir),
            "--jepa",
            str(jepa_checkpoint),
            "--window-sec",
            "0.2",
            "--stride-sec",
            "0.1",
            "--eval-holdout",
            "2",
            "--control-period-ms",
            "25",
            "--iterations",
            "2",
            "--steps-per-iteration",
            "12",
            "--eval-every",
            "1",
            "--patience-evals",
            "5",
            "--device",
            "cpu",
            "--seed",
            "3",
        ]
    )
    return root, jepa_checkpoint, train_dir


def test_train_jepa_writes_checkpoint_and_summary(journey):
    _root, jepa_checkpoint, _train_dir = journey
    assert jepa_checkpoint.exists()
    summary = json.loads(jepa_checkpoint.with_name("jepa_training.json").read_text(encoding="utf-8"))
    assert summary["pair_count"] > 0
    assert summary["final_loss_mean"] == pytest.approx(summary["final_loss_mean"])
    assert any(name.endswith(":rgb") or name.endswith(":events") for name in summary["streams_used"])


def test_train_rl_writes_checkpoints_journal_and_report(journey):
    _root, _jepa_checkpoint, train_dir = journey
    assert (train_dir / "policy_best.pt").exists()
    assert (train_dir / "policy_last.pt").exists()

    report = json.loads((train_dir / "report.json").read_text(encoding="utf-8"))
    assert report["train_episodes"] >= 1
    assert report["eval_episodes"] >= 1
    assert "best_improvement" in report
    assert report["final_evaluation"]["cases"]
    assert report["best_single_backend_mean_final_error_m"]

    records = [json.loads(line) for line in (train_dir / "training_log.jsonl").read_text(encoding="utf-8").splitlines()]
    types = {record["type"] for record in records}
    assert "iteration" in types
    assert "eval" in types


def test_rl_gated_run_produces_full_artifact_contract(journey, tiny_sequence, tmp_path):
    _root, jepa_checkpoint, train_dir = journey
    output_root = tmp_path / "runs"
    _main(
        [
            "run",
            "--method",
            "ensemble",
            "--dataset",
            "synthetic",
            "--sequence",
            "tiny_rl_gated",
            "--input",
            str(tiny_sequence),
            "--output-root",
            str(output_root),
            "--fusion",
            "rl_gated",
            "--policy",
            str(train_dir / "policy_best.pt"),
            "--jepa",
            str(jepa_checkpoint),
        ]
    )
    run_dirs = list(output_root.glob("*_ensemble_tiny_rl_gated"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    assert (run_dir / "estimated_trajectory.csv").exists()
    assert (run_dir / "ensemble_weights.csv").exists()
    assert (run_dir / "ensemble_updates.csv").exists()
    assert (run_dir / "rejected_updates.csv").exists()
    assert (run_dir / "backend_status_timeline.png").exists()

    with open(run_dir / "rl_trust_log.csv", newline="", encoding="utf-8") as f:
        trust_rows = list(csv.DictReader(f))
    assert len(trust_rows) > 0
    trust_columns = [name for name in trust_rows[0] if name.startswith("trust_")]
    assert len(trust_columns) == 5
    for row in trust_rows:
        for column in trust_columns:
            assert 0.0 <= float(row[column]) <= 1.0

    manifest = json.loads((run_dir / "run_manifest.json").read_text(encoding="utf-8"))
    assert manifest["method"] == "ensemble"
    assert manifest["config"]["fusion_mode"] == "rl_gated"
    assert manifest["config"]["ensemble"]["policy"].endswith("policy_best.pt")
    assert manifest["status"] == "success"


def test_missing_policy_flag_is_a_parser_error(tiny_sequence, tmp_path):
    with pytest.raises(SystemExit):
        _main(
            [
                "run",
                "--method",
                "ensemble",
                "--dataset",
                "synthetic",
                "--sequence",
                "tiny_no_policy",
                "--input",
                str(tiny_sequence),
                "--output-root",
                str(tmp_path / "runs"),
                "--fusion",
                "rl_gated",
            ]
        )


def test_jepa_trained_policy_requires_jepa_source_at_run_time(journey, tiny_sequence, tmp_path):
    _root, _jepa_checkpoint, train_dir = journey
    with pytest.raises(ValueError, match="JEPA"):
        _main(
            [
                "run",
                "--method",
                "ensemble",
                "--dataset",
                "synthetic",
                "--sequence",
                "tiny_missing_jepa",
                "--input",
                str(tiny_sequence),
                "--output-root",
                str(tmp_path / "runs"),
                "--fusion",
                "rl_gated",
                "--policy",
                str(train_dir / "policy_best.pt"),
            ]
        )


def test_policy_without_feature_metadata_is_rejected():
    from nav_benchmark.rl.ppo import PpoAgent, PpoConfig
    from nav_benchmark.rl.runner import restore_policy_configs

    agent = PpoAgent(PpoConfig(obs_dim=4, act_dim=2))
    with pytest.raises(ValueError, match="metadata"):
        restore_policy_configs(agent)
