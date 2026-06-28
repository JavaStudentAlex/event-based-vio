# S03: IMU Only Backend and CLI Run Path

**Goal:** One-command imu_only baseline and CLI path on synthetic data that writes the required run skeleton and trajectory artifacts for downstream evaluation.
**Demo:** One command runs `imu_only` on synthetic data through the backend interface and writes the required run directory skeleton with valid trajectory artifacts.

## Must-Haves

- `python -m nav_benchmark.run --method imu_only --dataset synthetic --sequence unit_synthetic --output-root runs` creates `runs/<YYYYmmdd_HHMMSS>_imu_only_unit_synthetic/` with:
- estimated_trajectory.csv (15 fixed columns per R003)
- estimated_trajectory_tum.txt (OK/DEGRADED only)
- run.log (non-empty)
- failure_notes.md (always present; summarizes degraded/lost counts or states none)
- run_manifest.json (includes method, dataset/sequence, config, timestamp policy, gravity/frames/units, alignment placeholder, code version if available, status, and health counts)
- Backend contract exists (`BaseOdometryBackend`) and `ImuOnlyBackend` returns a valid Trajectory object.
- Synthetic smoke tests pass without requiring MVSEC downloads.
- Lint/style checks pass with ruff.

## Proof Level

- This slice proves: integration

## Integration Closure

Wires dataset loader + IMU-only backend + trajectory exporters into a single CLI run path that produces S04/S05 inputs.

## Verification

- Adds structured run.log, manifest fields (health counts, thresholds, timestamp policy), and deterministic run directory naming for post-mortem inspection.

## Tasks

- [x] **T01: Established BaseOdometryBackend contract, implemented ImuOnlyBackend integration model, and verified with synthetic smoke tests.** `est:1h`
  Why: Establish a minimal, extensible backend contract and provide the IMU-only propagation to return a valid Trajectory for synthetic data.
  Do:
  - Create `BaseOdometryBackend` in `src/nav_benchmark/baselines/base.py` with `run(sequence, *, config) -> Trajectory`.
  - Implement `ImuOnlyBackend` in `src/nav_benchmark/baselines/imu.py` with simple gyro/acc integration (gravity removal), and health labeling per S03 defaults.
  - Add `ImuOnlyConfig` dataclass (gravity, initial pose/velocity, thresholds).
  - Write `tests/baselines/test_imu_only_smoke.py` using a tiny synthetic IMU snippet to assert Trajectory shape, monotonic timestamps, fixed method name `imu_only`, and health labels present.
  Done when: Test passes and ruff finds no issues.
  - Files: `src/nav_benchmark/baselines/base.py`, `src/nav_benchmark/baselines/imu.py`, `tests/baselines/test_imu_only_smoke.py`
  - Verify: rtk uv run pytest tests/baselines/test_imu_only_smoke.py -q

- [ ] **T02: CLI entrypoint `python -m nav_benchmark.run` wiring loaders → backend → exporters** `est:1h`
  Why: Provide an executable run path for imu_only that creates the standard run directory skeleton and trajectory artifacts.
  Do:
  - Add `src/nav_benchmark/run.py` with argparse-based `run` subcommand and flags: `--method imu_only`, `--dataset {synthetic|mvsec}`, `--sequence <name>`, `--input <path>` (required for mvsec), `--output-root runs`, `--resume`.
  - Compose: load sequence (synthetic fixture when dataset=synthetic), invoke `ImuOnlyBackend`, export using `export_project_csv` and `export_tum`.
  - Create run dir `runs/<YYYYmmdd_HHMMSS>_imu_only_<sequence>`; if exists and `--resume`, append `-r{N}`.
  - Always write `run.log` with start/end markers.
  - Add `tests/cli/test_run_cli_synthetic.py` to call the CLI in a temp dir and assert existence and non-emptiness of `estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, and `run.log`.
  Done when: CLI test passes producing the expected files for the synthetic dataset.
  - Files: `src/nav_benchmark/run.py`, `tests/cli/test_run_cli_synthetic.py`
  - Verify: rtk uv run pytest tests/cli/test_run_cli_synthetic.py -q

- [ ] **T03: Manifest and failure-notes generation with health counts** `est:45m`
  Why: Downstream evaluation (S04/S5) depends on reproducible metadata and explicit failure visibility.
  Do:
  - In the CLI flow, compute health counts from the Trajectory and ExportMetadata and write `run_manifest.json` with method, dataset/sequence, gravity, timestamp/alignment placeholders, thresholds, code version (if available), and counts.
  - Always write `failure_notes.md`: summarize degraded/lost intervals or state that none were detected; include counts and short guidance.
  - Add `tests/cli/test_run_manifest_and_notes.py` that executes the synthetic CLI run and asserts presence, JSON validity, and required top-level manifest keys; also asserts `failure_notes.md` exists and is non-empty.
  Done when: Manifest and notes tests pass.
  - Files: `src/nav_benchmark/run.py`, `tests/cli/test_run_manifest_and_notes.py`
  - Verify: rtk uv run pytest tests/cli/test_run_manifest_and_notes.py -q

- [ ] **T04: CLI usage doc stub** `est:20m`
  Why: Provide quick-start guidance for humans running the slice manually.
  Do:
  - Create `docs/run/cli.md` with invocation examples for synthetic and MVSEC, description of run directory structure, and notes on resume behavior.
  Done when: Doc exists and is non-empty with required headings.
  - Files: `docs/run/cli.md`
  - Verify: test -s docs/run/cli.md

## Files Likely Touched

- src/nav_benchmark/baselines/base.py
- src/nav_benchmark/baselines/imu.py
- tests/baselines/test_imu_only_smoke.py
- src/nav_benchmark/run.py
- tests/cli/test_run_cli_synthetic.py
- tests/cli/test_run_manifest_and_notes.py
- docs/run/cli.md
