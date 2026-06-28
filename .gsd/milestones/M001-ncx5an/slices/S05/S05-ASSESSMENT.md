---
sliceId: S05
uatType: runtime-executable
verdict: FAIL
attempt: 1
runId: uat:M001-ncx5an:S05:attempt-1
worktreeRoot: /home/jovyan/event-based-vio
date: 2026-06-28T13:37:08.728Z
---

# UAT Result - S05

## Checks

| Check | Mode | Result | Evidence | Notes |
|-------|------|--------|----------|-------|
| Run a synthetic simulation using the run command | runtime | PASS | gsd_uat_exec:bbd113a5-8bbd-498a-8710-77bbcab999a4 |  |
| Evaluate the trajectory to produce metrics and error CSVs | runtime | PASS | gsd_uat_exec:243ac3c1-4690-4bbd-8000-393867c7e2b0 |  |
| Validate the run directory using the validate subcommand | runtime | FAIL | gsd_uat_exec:23b03e9d-a105-42d6-8e2c-0f93a3113ff4 |  |

## Overall Verdict

FAIL - UAT validation failed due to a validation string mismatch: validation.py expects 'No degraded or lost intervals were detected.' in the failure notes markdown, but run.py generates 'No degraded or lost intervals were detected during this run.'

## Tool Presentation

```json
{
  "surface": "mcp",
  "toolPresentationPlanId": "run-uat/default-v1",
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
  ]
}
```

## Gate

Aggregate UAT gate saved as flag.
