---
sliceId: S03
uatType: runtime-executable
verdict: PASS
attempt: 1
runId: uat:M001-ncx5an:S03:attempt-1
worktreeRoot: /home/jovyan/event-based-vio
date: 2026-06-28T00:36:32.933Z
---

# UAT Result - S03

## Checks

| Check | Mode | Result | Evidence | Notes |
|-------|------|--------|----------|-------|
| Execute the main run subcommand using the synthetic dataset: uv run python -m nav_benchmark.run --method imu_only --dataset synthetic --sequence unit_synthetic --output-root runs | runtime | PASS | gsd_uat_exec:46baba38-301c-4afe-a951-cc3134bbfc33 |  |
| Verify that a run directory matching runs/<YYYYmmdd_HHMMSS>_imu_only_unit_synthetic/ was created. | artifact | PASS | gsd_uat_exec:0288b066-4401-41ad-a648-eddf509d59e7 |  |
| Assert the presence of estimated_trajectory.csv, estimated_trajectory_tum.txt, run.log, failure_notes.md, run_manifest.json | artifact | PASS | gsd_uat_exec:0288b066-4401-41ad-a648-eddf509d59e7 |  |
| The estimator runs to completion, exports correct trajectory format, and run_manifest.json reports health counts for OK, DEGRADED, LOST, INVALID. | artifact | PASS | gsd_uat_exec:2fcb1a6a-e617-4f8e-8b55-0f061e463d39 |  |

## Overall Verdict

PASS - IMU Only backend CLI integration validated successfully using a synthetic dataset, exporting all required trajectory formats and run manifests.

## Tool Presentation

```json
{
  "model": {
    "provider": "anthropic",
    "id": "claude-3-5-sonnet-20241022",
    "api": "claude-sonnet-4-6"
  },
  "fallbackToolsUsed": [],
  "toolPresentationPlanId": "run-uat/default-v1",
  "surface": "mcp",
  "notes": "Standard execution layout verification.",
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
  ]
}
```

## Gate

Aggregate UAT gate saved as pass.
