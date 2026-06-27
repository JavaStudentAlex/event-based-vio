---
description: "Read-only review overlay for analysis, QA, and code review tasks."
---

# Read-Only QA Instructions

## Purpose

Use this when the task is to inspect, review, audit, or explain without making changes.

## Rules

- Do not edit files unless explicitly asked.
- Ground findings in repository evidence: files, tests, commands, and observed behavior.
- Check that dataset, sequence, streams, output schema, and metrics match
  `gsd_mvsec_ensemble_plan.md`.
- Check timestamp alignment, coordinate-frame handling, quaternion ordering,
  and trajectory alignment assumptions.
- Check that failures and invalid poses are represented rather than silently
  discarded.
- Check that benchmark claims are backed by commands, artifacts, or tests.
- Distinguish confirmed issues from hypotheses.
- Prioritize findings by incorrect metrics, reproducibility risk, silent data
  loss, and architecture drift.
