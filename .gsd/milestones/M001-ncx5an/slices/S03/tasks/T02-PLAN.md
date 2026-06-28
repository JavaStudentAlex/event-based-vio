---
estimated_steps: 8
estimated_files: 2
skills_used: []
---

# T02: CLI entrypoint `python -m nav_benchmark.run` wiring loaders → backend → exporters

Why: Provide an executable run path for imu_only that creates the standard run directory skeleton and trajectory artifacts.
Do:
- Add `src/nav_benchmark/run.py` with argparse-based `run` subcommand and flags: `--method imu_only`, `--dataset {synthetic|mvsec}`, `--sequence <name>`, `--input <path>` (required for mvsec), `--output-root runs`, `--resume`.
- Compose: load sequence (synthetic fixture when dataset=synthetic), invoke `ImuOnlyBackend`, export using `export_project_csv` and `export_tum`.
- Create run dir `runs/<YYYYmmdd_HHMMSS>_imu_only_<sequence>`; if exists and `--resume`, append `-r{N}`.
- Always write `run.log` with start/end markers.
- Add `tests/cli/test_run_cli_synthetic.py` to call the CLI in a temp dir and assert existence and non-emptiness of `estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, and `run.log`.
Done when: CLI test passes producing the expected files for the synthetic dataset.

## Inputs

- `src/nav_benchmark/trajectory/export.py`
- `src/nav_benchmark/trajectory/models.py`
- `src/nav_benchmark/datasets/mvsec.py`
- `src/nav_benchmark/baselines/imu.py`

## Expected Output

- `src/nav_benchmark/run.py`
- `tests/cli/test_run_cli_synthetic.py`

## Verification

rtk uv run pytest tests/cli/test_run_cli_synthetic.py -q

## Observability Impact

Introduces run.log with deterministic start/finish messages to aid triage.
