# S05: Manifest Failure Artifacts and CI Smoke Coverage — Research

## Calibration & Depth
Depth: **Light research**. 
The repository already implements trajectory models, synchronization, run CLI commands, failure notes, evaluation, metrics, and plots. Slice S05 focuses on stabilizing the operational contract by establishing tests and schema validation to ensure the produced artifacts are consistent, correct, and robust.

## Findings
We examined the following existing files and patterns:
1. **`src/nav_benchmark/run.py`**:
   - Manages CLI routing (`run` and `eval` subcommands).
   - Generates `run_manifest.json` via `write_run_manifest()`.
   - Generates `failure_notes.md` via `generate_failure_notes()`.
   - Modifies `run_manifest.json` on evaluation success or failure (adding/updating the `"evaluation"` field).
2. **`src/nav_benchmark/trajectory/export.py`**:
   - Implements `export_project_csv()` and `export_tum()`.
   - The TUM export currently filters out `LOST` and `INVALID` health statuses, ensuring it only exports `OK` and `DEGRADED` positions.
3. **`src/nav_benchmark/evaluation/harness.py`**:
   - Manages evaluation artifacts: `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, and trajectory/drift plots.
4. **CI Testing Coverage**:
   - `tests/cli/test_run_manifest_and_notes.py` validates that `run_manifest.json` and `failure_notes.md` are populated with keys/contents and correctly handle health state transitions.
   - `tests/cli/test_eval_cli_synthetic.py` validates the `eval` subcommand execution, verifying the outputs of metrics, error CSVs, and plots.
   - `tests/evaluation/test_eval_artifact_contract_synthetic.py` verifies the exact CSV column headers and schema layouts for the error reports.

## Constraints & Core Rules
- **Run Directory Artifact Contract**: Every run must write `estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, `run.log`, `failure_notes.md`, and `run_manifest.json` (complete with health status counts, source/target frames, timestamp policies, etc.).
- **TUM Trajectory Rules**: `estimated_trajectory_tum.txt` must only contain `OK` and `DEGRADED` states.
- **Always-Present Failure Notes**: `failure_notes.md` must list any transition boundaries (OK, DEGRADED, LOST, INVALID) with timestamps and durations. If no degradation is present, it must display the exact string: `No degraded or lost intervals were detected.`
- **Test Invariance**: Unit and CLI tests must execute fast and use synthetic sequences (`--dataset synthetic`) so they do not depend on downloading MVSEC HDF5 sequences.

## Implementation Seams
No code files need modification in `src/nav_benchmark` as all core CLI, runner, exporter, and evaluator behaviors already satisfy the requirements outlined in the S05 roadmap.
We will add standard automated smoke tests inside `tests/` to verify that the CLI orchestrator outputs are content-valid (verifying column shapes, file size, manifest keys, and exact status text strings).

## Verification Strategy
We will execute pytest to run all CLI integration tests and check schemas:
- `PYTHONPATH=src pytest tests/cli/`
- `PYTHONPATH=src pytest tests/evaluation/`
- Ruff checks to ensure formatting rules are satisfied: `ruff check .` and `ruff format --check .`.
