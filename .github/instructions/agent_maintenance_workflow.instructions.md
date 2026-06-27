---
description: "Workflow for keeping repository agent instructions aligned with the current MVSEC VIO project."
---

# Agent Maintenance Workflow

## Purpose

Use this when editing `AGENTS.md`, `.github/instructions`, `.github/agents`,
`.github/skills`, or repository automation that prompts coding agents.

## Maintenance Rules

- Keep instruction files task-scoped and repository-specific to MVSEC
  visual-inertial odometry, benchmark evaluation, and deterministic ensemble
  fusion.
- Do not add arbitrary tool dependencies that are not in `pyproject.toml` or `package.json`.
- Keep Python version references aligned with `.python-version` and `pyproject.toml`.
- Project-scoped skills belong under `.github/skills`.
- Remove copied instructions from unrelated project domains unless the active
  project plan explicitly reintroduces them.

## Review Checklist

- Agents correctly address dataset replay, baseline integration, evaluation,
  and ensemble fusion responsibilities.
- Documentation commands align with Python 3.13, `uv`, Ruff, pytest, and the
  RTK command wrapper used by Codex sessions.
- No files refer to copied repository domains unrelated to event-based VIO.
