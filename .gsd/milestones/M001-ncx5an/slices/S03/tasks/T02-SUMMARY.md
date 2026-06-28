---
id: T02
parent: S03
milestone: M001-ncx5an
key_files:
  - src/nav_benchmark/run.py
  - tests/cli/test_run_cli_synthetic.py
key_decisions:
  - Implemented argparse CLI command routing under the nav_benchmark.run module
  - Structured output directories with datetime timestamp naming and resume suffix checks
duration: 
verification_result: passed
completed_at: 2026-06-28T00:23:15.144Z
blocker_discovered: false
---

# T02: CLI entrypoint python -m nav_benchmark.run wiring loaders -> backend -> exporters

**CLI entrypoint python -m nav_benchmark.run wiring loaders -> backend -> exporters**

## What Happened

Created CLI entrypoint `src/nav_benchmark/run.py` to wire data loader configuration, estimation baseline runner, and trajectory exporters. Added `tests/cli/test_run_cli_synthetic.py` to test both direct invocation with mock args and subprocess invocation. Tested `--resume` directory safety mechanisms, dataset input verification, and validated output artifacts (estimated_trajectory.csv, estimated_trajectory_tum.txt, run.log) are generated with correct contents.

## Verification

CLI execution and output files verified using pytest tests/cli/test_run_cli_synthetic.py

## Verification Evidence

| # | Command | Exit Code | Verdict | Duration |
|---|---------|-----------|---------|----------|
| 1 | `rtk uv run pytest tests/cli/test_run_cli_synthetic.py -q` | 0 | ✅ pass | 6994ms |

## Deviations

None.

## Known Issues

None.

## Files Created/Modified

- `src/nav_benchmark/run.py`
- `tests/cli/test_run_cli_synthetic.py`
