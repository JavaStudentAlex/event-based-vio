# Codebase Map

Generated: 2026-06-30T09:27:11Z | Files: 154 | Described: 0/154
<!-- gsd:codebase-meta {"generatedAt":"2026-06-30T09:27:11Z","fingerprint":"4e885bd73f70b404d0d6e645014491b17e0aa875","fileCount":154,"truncated":false} -->

### (root)/
- `.gitignore`
- `.pre-commit-config.yaml`
- `.python-version`
- `AGENTS.md`
- `pyproject.toml`
- `README.md`
- `skills-lock.json`

### .github/
- `.github/PULL_REQUEST_TEMPLATE.md`

### .github/agents/
- `.github/agents/dataset-pipeline-engineer.agent.md`
- `.github/agents/evaluation-ensemble-engineer.agent.md`
- `.github/agents/vio-baseline-engineer.agent.md`

### .github/instructions/
- `.github/instructions/agent_maintenance_workflow.instructions.md`
- `.github/instructions/code_writing_behavior.instructions.md`
- `.github/instructions/delegation_policy.instructions.md`
- `.github/instructions/python_quality_gates.instructions.md`
- `.github/instructions/qa_readonly.instructions.md`
- `.github/instructions/tests.instructions.md`

### .github/scripts/
- `.github/scripts/aps_tools_common.sh`
- `.github/scripts/bootstrap_dev_env.sh`
- `.github/scripts/crap_check.py`
- `.github/scripts/dry_check.py`
- `.github/scripts/install_aps_tools.sh`
- `.github/scripts/precommit_aps_gate.sh`
- `.github/scripts/precommit_coverage_gate.sh`
- `.github/scripts/precommit_gherkin_mutation_gate.sh`
- `.github/scripts/precommit_language_mutation_gate.py`
- `.github/scripts/resolve_gsd_slice.py`
- `.github/scripts/run_acceptance_mutation_worker.py`
- `.github/scripts/run_acceptance_mutation_worker.sh`

### .github/scripts/scripts/
- `.github/scripts/scripts/aps_tools_common.sh`
- `.github/scripts/scripts/bootstrap_dev_env.sh`
- `.github/scripts/scripts/crap_check.py`
- `.github/scripts/scripts/dry_check.py`
- `.github/scripts/scripts/install_aps_tools.sh`
- `.github/scripts/scripts/precommit_aps_gate.sh`
- `.github/scripts/scripts/precommit_coverage_gate.sh`
- `.github/scripts/scripts/precommit_gherkin_mutation_gate.sh`
- `.github/scripts/scripts/precommit_language_mutation_gate.py`
- `.github/scripts/scripts/resolve_gsd_slice.py`
- `.github/scripts/scripts/run_acceptance_mutation_worker.py`
- `.github/scripts/scripts/run_acceptance_mutation_worker.sh`

### .github/skills/mvsec-benchmarking/
- `.github/skills/mvsec-benchmarking/SKILL.md`

### .github/skills/python-linting/
- `.github/skills/python-linting/SKILL.md`

### .github/skills/python-testing/
- `.github/skills/python-testing/SKILL.md`

### .github/skills/string-seed-of-thought/
- `.github/skills/string-seed-of-thought/SKILL.md`

### .github/workflows/
- `.github/workflows/ci-lint.yml`
- `.github/workflows/ci-slow-lane.yml`
- `.github/workflows/ci-structure.yml`
- `.github/workflows/ci-tests.yml`
- `.github/workflows/jules_auto_merge.yml`
- `.github/workflows/jules_next_task.yml`

### .github/workflows/workflows/
- `.github/workflows/workflows/ci-lint.yml`
- `.github/workflows/workflows/ci-slow-lane.yml`
- `.github/workflows/workflows/ci-structure.yml`
- `.github/workflows/workflows/ci-tests.yml`
- `.github/workflows/workflows/jules_auto_merge.yml`
- `.github/workflows/workflows/jules_next_task.yml`

### configs/
- `configs/google_earth_sequence.yaml`

### docs/datasets/
- `docs/datasets/mvsec.md`

### docs/evaluation/
- `docs/evaluation/drift-evaluation.md`

### docs/run/
- `docs/run/cli.md`

### docs/trajectory/
- `docs/trajectory/export-contract.md`
- `docs/trajectory/synchronization.md`

### examples/
- `examples/inspect_mvsec.py`

### outputs/blurred_drone_match/
- `outputs/blurred_drone_match/estimated_pose.geojson`
- `outputs/blurred_drone_match/match_result.json`

### outputs/example_match/
- `outputs/example_match/estimated_pose.geojson`
- `outputs/example_match/match_result.json`

### scripts/
- `scripts/download_mvsec.sh`
- `scripts/draw_routes.py`
- `scripts/experiment_routes.py`
- `scripts/simulate_drone.py`

### src/map_matching/
- `src/map_matching/__init__.py`
- `src/map_matching/aoi.py`
- `src/map_matching/confidence.py`
- `src/map_matching/features.py`
- `src/map_matching/geometry.py`
- `src/map_matching/matching.py`
- `src/map_matching/preprocess.py`
- `src/map_matching/raster_io.py`
- `src/map_matching/visualize.py`

### src/nav_benchmark/
- `src/nav_benchmark/__init__.py`
- `src/nav_benchmark/run.py`
- `src/nav_benchmark/validation.py`

### src/nav_benchmark/baselines/
- `src/nav_benchmark/baselines/base.py`
- `src/nav_benchmark/baselines/common.py`
- `src/nav_benchmark/baselines/event_imu.py`
- `src/nav_benchmark/baselines/image_imu.py`
- `src/nav_benchmark/baselines/imu.py`
- `src/nav_benchmark/baselines/multimodal_vio.py`
- `src/nav_benchmark/baselines/visual.py`

### src/nav_benchmark/datasets/
- `src/nav_benchmark/datasets/__init__.py`
- `src/nav_benchmark/datasets/mvsec.py`
- `src/nav_benchmark/datasets/synthetic.py`

### src/nav_benchmark/ensemble/
- `src/nav_benchmark/ensemble/__init__.py`
- `src/nav_benchmark/ensemble/confidence_weighted.py`

### src/nav_benchmark/evaluation/
- `src/nav_benchmark/evaluation/__init__.py`
- `src/nav_benchmark/evaluation/harness.py`
- `src/nav_benchmark/evaluation/metrics.py`
- `src/nav_benchmark/evaluation/plots.py`

### src/nav_benchmark/synthetic/
- `src/nav_benchmark/synthetic/__init__.py`
- `src/nav_benchmark/synthetic/config.py`
- `src/nav_benchmark/synthetic/drone_model.py`
- `src/nav_benchmark/synthetic/event_visualizer.py`
- `src/nav_benchmark/synthetic/frame_source.py`
- `src/nav_benchmark/synthetic/geo.py`
- `src/nav_benchmark/synthetic/imageio.py`
- `src/nav_benchmark/synthetic/imu_from_trajectory.py`
- `src/nav_benchmark/synthetic/metadata_writer.py`
- `src/nav_benchmark/synthetic/pipeline.py`
- `src/nav_benchmark/synthetic/preview.py`
- `src/nav_benchmark/synthetic/recorder.py`
- `src/nav_benchmark/synthetic/rgb_to_events.py`
- `src/nav_benchmark/synthetic/trajectory_export.py`

### src/nav_benchmark/trajectory/
- `src/nav_benchmark/trajectory/__init__.py`
- `src/nav_benchmark/trajectory/export.py`
- `src/nav_benchmark/trajectory/models.py`
- `src/nav_benchmark/trajectory/sync.py`

### tests/
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_validation.py`

### tests/baselines/
- `tests/baselines/test_imu_only_smoke.py`
- `tests/baselines/test_visual_event_ensemble.py`

### tests/cli/
- `tests/cli/test_eval_cli_synthetic.py`
- `tests/cli/test_run_cli_synthetic.py`
- `tests/cli/test_run_manifest_and_notes.py`
- `tests/cli/test_validate_cli.py`

### tests/evaluation/
- `tests/evaluation/test_eval_artifact_contract_synthetic.py`
- `tests/evaluation/test_harness_synthetic_sequence.py`
- `tests/evaluation/test_metrics_synthetic.py`
- `tests/evaluation/test_plots_synthetic.py`

### tests/map_matching/
- `tests/map_matching/test_processing.py`

### tests/nav_benchmark/
- `tests/nav_benchmark/__init__.py`

### tests/nav_benchmark/datasets/
- `tests/nav_benchmark/datasets/__init__.py`
- `tests/nav_benchmark/datasets/test_mvsec.py`
- `tests/nav_benchmark/datasets/test_synthetic_sequence.py`

### tests/scripts/
- `tests/scripts/test_experiment_routes.py`
- `tests/scripts/test_simulate_drone.py`

### tests/synthetic/
- `tests/synthetic/test_config.py`
- `tests/synthetic/test_frame_source.py`
- `tests/synthetic/test_geo.py`
- `tests/synthetic/test_imu_from_trajectory.py`
- `tests/synthetic/test_preview.py`
- `tests/synthetic/test_recorder.py`
- `tests/synthetic/test_rgb_to_events.py`

### tests/trajectory/
- `tests/trajectory/test_export_contract_synthetic.py`
- `tests/trajectory/test_export.py`
- `tests/trajectory/test_models.py`
- `tests/trajectory/test_sync.py`

### tests/validation/
- `tests/validation/test_artifact_validation.py`

### tools/
- `tools/build_events_from_rgb.py`
- `tools/preview_sequence.py`
- `tools/record_google_earth_sequence.py`
- `tools/validate_sequence.py`
