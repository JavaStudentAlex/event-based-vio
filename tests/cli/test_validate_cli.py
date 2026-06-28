import csv
import glob
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.spatial.transform import Rotation


def _write_non_coplanar_sequence(root: Path) -> None:
    (root / "imu").mkdir(parents=True, exist_ok=True)
    (root / "ground_truth").mkdir(parents=True, exist_ok=True)

    # Write IMU data
    with open(root / "imu" / "imu.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp_s", "ax_mps2", "ay_mps2", "az_mps2", "gx_radps", "gy_radps", "gz_radps"])
        for i in range(10):
            t = float(i)
            writer.writerow([t, 0.1 * i, 0.2 * i, -9.81 + 0.3 * i, 0.1, 0.2, 0.3])

    # Compute integrated trajectory for ground truth
    positions = [[0.0, 0.0, 0.0]]
    orientations = [[0.0, 0.0, 0.0, 1.0]]
    velocities = [[0.0, 0.0, 0.0]]

    for i in range(9):
        dt = 1.0
        R_curr = Rotation.from_quat(orientations[i])
        omega = np.array([0.1, 0.2, 0.3])
        rot_vec = omega * dt
        R_inc = Rotation.from_rotvec(rot_vec)
        R_next = R_curr * R_inc
        orientations.append(R_next.as_quat().tolist())

        a_body = np.array([0.1 * i, 0.2 * i, -9.81 + 0.3 * i])
        gravity = np.array([0.0, 0.0, -9.81])
        a_world = R_curr.apply(a_body) - gravity

        v_curr = np.array(velocities[i])
        v_next = v_curr + a_world * dt
        velocities.append(v_next.tolist())

        p_curr = np.array(positions[i])
        p_next = p_curr + v_curr * dt + 0.5 * a_world * (dt ** 2)
        positions.append(p_next.tolist())

    with open(root / "ground_truth" / "trajectory.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp_s", "x_m", "y_m", "z_m", "yaw_deg",
            "qx", "qy", "qz", "qw", "vx_mps", "vy_mps", "vz_mps"
        ])
        for i in range(10):
            t = float(i)
            p = positions[i]
            q = orientations[i]
            v = velocities[i]
            # Write with a slight offset (0.05m) to avoid identity
            writer.writerow([
                t, p[0] + 0.05, p[1] + 0.05, p[2] + 0.05, 0.0,
                q[0], q[1], q[2], q[3], v[0], v[1], v[2]
            ])


def test_validate_after_run_and_eval(tmp_path):
    """Verify validation passes for a directory with both run and eval artifacts."""
    input_dir = tmp_path / "synthetic_input"
    _write_non_coplanar_sequence(input_dir)

    output_root = tmp_path / "runs"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")

    # 1. Run pipeline
    run_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "run",
        "--method",
        "imu_only",
        "--dataset",
        "synthetic",
        "--sequence",
        "smoke_val",
        "--input",
        str(input_dir),
        "--output-root",
        str(output_root),
    ]
    res_run = subprocess.run(run_cmd, env=env, capture_output=True, text=True)
    assert res_run.returncode == 0, f"Run failed: {res_run.stderr}"

    run_dirs = glob.glob(str(output_root / "*_imu_only_smoke_val"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    # 2. Eval pipeline
    eval_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "eval",
        "--run-dir",
        run_dir,
    ]
    res_eval = subprocess.run(eval_cmd, env=env, capture_output=True, text=True)
    assert res_eval.returncode == 0, f"Eval failed: {res_eval.stderr}"

    # 3. Validate pipeline
    val_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "validate",
        "--run-dir",
        run_dir,
    ]
    res_val = subprocess.run(val_cmd, env=env, capture_output=True, text=True)
    assert res_val.returncode == 0, f"Validation failed: {res_val.stderr}"
    assert "Validation:" in res_val.stdout
    assert "checks passed" in res_val.stdout


def test_validate_run_only_skip_eval(tmp_path):
    """Verify validation passes for a run-only directory when using --skip-eval."""
    input_dir = tmp_path / "synthetic_input"
    _write_non_coplanar_sequence(input_dir)

    output_root = tmp_path / "runs"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")

    # 1. Run pipeline
    run_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "run",
        "--method",
        "imu_only",
        "--dataset",
        "synthetic",
        "--sequence",
        "smoke_val",
        "--input",
        str(input_dir),
        "--output-root",
        str(output_root),
    ]
    res_run = subprocess.run(run_cmd, env=env, capture_output=True, text=True)
    assert res_run.returncode == 0

    run_dirs = glob.glob(str(output_root / "*_imu_only_smoke_val"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    # 2. Validate with --skip-eval (should succeed without evaluation artifacts)
    val_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "validate",
        "--run-dir",
        run_dir,
        "--skip-eval",
    ]
    res_val = subprocess.run(val_cmd, env=env, capture_output=True, text=True)
    assert res_val.returncode == 0, f"Validation failed: {res_val.stderr}"
    assert "Validation:" in res_val.stdout


def test_validate_broken_manifest(tmp_path):
    """Verify validation fails if manifest is broken or truncated."""
    input_dir = tmp_path / "synthetic_input"
    _write_non_coplanar_sequence(input_dir)

    output_root = tmp_path / "runs"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")

    # 1. Run pipeline
    run_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "run",
        "--method",
        "imu_only",
        "--dataset",
        "synthetic",
        "--sequence",
        "smoke_val",
        "--input",
        str(input_dir),
        "--output-root",
        str(output_root),
    ]
    res_run = subprocess.run(run_cmd, env=env, capture_output=True, text=True)
    assert res_run.returncode == 0

    run_dirs = glob.glob(str(output_root / "*_imu_only_smoke_val"))
    assert len(run_dirs) == 1
    run_dir = Path(run_dirs[0])

    # Truncate manifest
    manifest_path = run_dir / "run_manifest.json"
    manifest_path.write_text("{broken", encoding="utf-8")

    # 2. Validate (should fail)
    val_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "validate",
        "--run-dir",
        str(run_dir),
        "--skip-eval",
    ]
    res_val = subprocess.run(val_cmd, env=env, capture_output=True, text=True)
    assert res_val.returncode == 1


def test_validate_missing_trajectory(tmp_path):
    """Verify validation fails if estimated trajectory file is missing."""
    input_dir = tmp_path / "synthetic_input"
    _write_non_coplanar_sequence(input_dir)

    output_root = tmp_path / "runs"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")

    # 1. Run pipeline
    run_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "run",
        "--method",
        "imu_only",
        "--dataset",
        "synthetic",
        "--sequence",
        "smoke_val",
        "--input",
        str(input_dir),
        "--output-root",
        str(output_root),
    ]
    res_run = subprocess.run(run_cmd, env=env, capture_output=True, text=True)
    assert res_run.returncode == 0

    run_dirs = glob.glob(str(output_root / "*_imu_only_smoke_val"))
    assert len(run_dirs) == 1
    run_dir = Path(run_dirs[0])

    # Delete estimated_trajectory.csv
    (run_dir / "estimated_trajectory.csv").unlink()

    # 2. Validate (should fail)
    val_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "validate",
        "--run-dir",
        str(run_dir),
        "--skip-eval",
    ]
    res_val = subprocess.run(val_cmd, env=env, capture_output=True, text=True)
    assert res_val.returncode == 1


def test_validate_latest_flag(tmp_path):
    """Verify validate --latest sub-argument works as expected."""
    input_dir = tmp_path / "synthetic_input"
    _write_non_coplanar_sequence(input_dir)

    output_root = tmp_path / "runs"

    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent.parent / "src")

    # 1. Run pipeline
    run_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "run",
        "--method",
        "imu_only",
        "--dataset",
        "synthetic",
        "--sequence",
        "smoke_val",
        "--input",
        str(input_dir),
        "--output-root",
        str(output_root),
    ]
    res_run = subprocess.run(run_cmd, env=env, capture_output=True, text=True)
    assert res_run.returncode == 0

    run_dirs = glob.glob(str(output_root / "*_imu_only_smoke_val"))
    assert len(run_dirs) == 1
    run_dir = run_dirs[0]

    # 2. Eval pipeline
    eval_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "eval",
        "--run-dir",
        run_dir,
    ]
    res_eval = subprocess.run(eval_cmd, env=env, capture_output=True, text=True)
    assert res_eval.returncode == 0

    # 3. Validate with --latest
    val_cmd = [
        sys.executable,
        "-m",
        "nav_benchmark.run",
        "validate",
        "--latest",
        "--output-root",
        str(output_root),
        "--method",
        "imu_only",
        "--sequence",
        "smoke_val",
    ]
    res_val = subprocess.run(val_cmd, env=env, capture_output=True, text=True)
    assert res_val.returncode == 0, f"Latest validate failed: {res_val.stderr}"
    assert "Validation:" in res_val.stdout
