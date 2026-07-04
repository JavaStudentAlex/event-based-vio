---
sliceId: S05
uatType: runtime-executable
verdict: FAIL
attempt: 2
runId: uat:M001-ncx5an:S05:attempt-2
worktreeRoot: /home/jovyan/event-based-vio
date: 2026-06-29T00:32:00.679Z
---

# UAT Result - S05

## Checks

| Check | Mode | Result | Evidence | Notes |
|-------|------|--------|----------|-------|
| Run a synthetic simulation using `PYTHONPATH=src uv run python -m nav_benchmark.run run --method imu_only --dataset synthetic --sequence test_seq --output-root tmp_runs`. | runtime | PASS | gsd_uat_exec:4718a136-a524-4d75-bac6-22acdedf19c1 | The runtime command completed successfully and produced the expected run-directory artifacts. |
| Evaluate the trajectory to produce metrics and error CSVs using `PYTHONPATH=src uv run python -m nav_benchmark.run eval --latest --output-root tmp_runs --ground-truth synthetic`. | runtime | FAIL | gsd_uat_exec:30cd6266-7f0d-41e5-a105-e9cbbaef6950 | The specified `--ground-truth synthetic` path was not accepted by the CLI, so the UAT evaluation step failed before it could satisfy the expected outcome. |
| Validate the run directory using `PYTHONPATH=src uv run python -m nav_benchmark.run validate --latest --output-root tmp_runs`. | runtime | FAIL | gsd_uat_exec:23b03e9d-a105-42d6-8e2c-0f93a3113ff4 | Validation ran against the latest run directory, but `check_failure_notes` failed because the validator expected 'No degraded or lost intervals were detected.' when health counts showed no failures. |
| The output displays a formatted summary table showing passing statuses for `check_trajectory_csv`, `check_tum_file`, `check_run_manifest`, `check_failure_notes`, `check_run_log`, `check_metrics_json`, `check_error_vs_time_csv`, `check_error_vs_distance_csv`, `check_plot_file`, and `check_cross_consistency`, and exits with status code 0. | runtime | FAIL | gsd_uat_exec:23b03e9d-a105-42d6-8e2c-0f93a3113ff4 | The expected all-passing validation summary and zero exit status were not achieved. |

## Overall Verdict

FAIL - S05 UAT fails because the required eval command rejects `--ground-truth synthetic`, and the validate command reports `check_failure_notes` as failing instead of producing an all-pass summary.

## Tool Presentation

```json
{
  "surface": "mcp",
  "presentedTools": [
    "gsd_uat_exec",
    "gsd_uat_result_save",
    "gsd_resume",
    "gsd_milestone_status",
    "gsd_journal_query",
    "find",
    "glob",
    "grep",
    "ls",
    "read"
  ],
  "blockedTools": [
    {
      "name": "edit",
      "reason": "forbidden during run-uat"
    },
    {
      "name": "write",
      "reason": "forbidden during run-uat"
    },
    {
      "name": "gsd_exec",
      "reason": "forbidden during run-uat"
    },
    {
      "name": "gsd_summary_save",
      "reason": "forbidden during run-uat"
    },
    {
      "name": "gsd_save_gate_result",
      "reason": "forbidden during run-uat"
    },
    {
      "name": "search-the-web",
      "reason": "forbidden during run-uat"
    },
    {
      "name": "WebSearch",
      "reason": "forbidden during run-uat"
    },
    {
      "name": "Bash",
      "reason": "forbidden during run-uat"
    },
    {
      "name": "Write",
      "reason": "forbidden during run-uat"
    },
    {
      "name": "Edit",
      "reason": "forbidden during run-uat"
    }
  ],
  "toolPresentationPlanId": "run-uat/default-v1"
}
```

## Gate

Aggregate UAT gate saved as flag.
