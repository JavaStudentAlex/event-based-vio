# Codebase Map

Generated: 2026-06-27T18:12:27Z | Files: 47 | Described: 0/47
<!-- gsd:codebase-meta {"generatedAt":"2026-06-27T18:12:27Z","fingerprint":"9757035e7a148ad1b0722fe635cda63e47cfa91f","fileCount":47,"truncated":false} -->

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

### scripts/
- `scripts/download_mvsec.sh`

### src/nav_benchmark/
- `src/nav_benchmark/__init__.py`

### src/nav_benchmark/datasets/
- `src/nav_benchmark/datasets/__init__.py`
- `src/nav_benchmark/datasets/mvsec.py`

### tests/
- `tests/__init__.py`

### tests/nav_benchmark/
- `tests/nav_benchmark/__init__.py`

### tests/nav_benchmark/datasets/
- `tests/nav_benchmark/datasets/__init__.py`
- `tests/nav_benchmark/datasets/test_mvsec.py`
