---
description: "Behavioral overlay for code writing, review, and refactor tasks in the MVSEC VIO project."
---

# Code Writing Behavior

## Purpose

Use this when a task involves writing or editing code, reviewing code, or refactoring in this repository.

## Core Behavior

- Prioritize reproducible benchmark behavior, explicit coordinate frames,
  timestamp units, and deterministic data handling.
- Make assumptions explicit, particularly around MVSEC sequence names, sensor
  streams, calibration, timestamp alignment, and ground-truth availability.
- Prefer the simplest, most robust architecture.
- Keep dataset IO, replay/synchronization, baseline adapters, evaluation, and
  ensemble fusion separated.
- Preserve the common trajectory schema for every method.
- Treat tracking failures and invalid poses as first-class evaluation data.
- Remove unused imports or helpers created by your changes.

## Execution Pattern

- Think through the simplest viable approach before writing.
- Keep raw data loading separated from derived outputs and plots.
- Keep benchmark configuration explicit and serializable where practical.
- Document any incomplete baseline integration or external dependency that is
  required to reproduce a result.
