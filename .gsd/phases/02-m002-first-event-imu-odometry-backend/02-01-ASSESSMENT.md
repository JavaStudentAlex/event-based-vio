---
sliceId: S01
uatType: runtime-executable
verdict: PASS
attempt: 1
runId: uat:M002:S01:attempt-1
worktreeRoot: /home/jovyan/event-based-vio
date: 2026-07-07T05:28:16.572Z
---

# UAT Result - S01

## Checks

| Check | Mode | Result | Evidence | Notes |
|-------|------|--------|----------|-------|
| Verify all tests under tests/baselines/test_event_imu_backend.py pass. | runtime | PASS | gsd_uat_exec:9cd753e5-439e-4d30-ba5b-6cbaa4a53311 | Passed cleanly with 22 passed tests |
| Verify extrinsics apply properly natively and fallback to identity without them. | runtime | PASS | gsd_uat_exec:e9fc837b-a330-46d8-8f68-433d7981f8cf | Using dummy dataset instances proved that correctly formatted extrinsics yield extrinsics_source='calibration' and when absent they safely fallback to 'identity_fallback'. |
| Verify degenerate extrinsics gracefully fallback instead of crashing. | runtime | PASS | gsd_uat_exec:e9fc837b-a330-46d8-8f68-433d7981f8cf | Sending an all NaN transform returned identity fallback and provided non_finite_elements string to rejected reason appropriately |

## Overall Verdict

PASS - All test cases pass. Pytest suite ran cleanly, and dedicated mock scripts validated that extrinsics are properly handled and reported gracefully without runtime failures.

## Tool Presentation

```json
{
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
  "surface": "mcp",
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

Aggregate UAT gate saved as pass.
