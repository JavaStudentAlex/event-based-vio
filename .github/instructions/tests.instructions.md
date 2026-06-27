---
applyTo: "**/tests/**/*"
description: "Test conventions, organization, and verification patterns for MVSEC VIO."
---

# Test Instructions

## Scope

This covers pytest tests under `tests/` and any verification used to prove
repository behavior.

## Tooling Rules

- Use `uv run pytest ...` for tests.
- Focus on unit tests for core utilities and small integration tests for data
  replay, trajectory export, metrics, and ensemble logic.

## Conventions

- Test trajectory CSV parsing/export with the required schema.
- Test timestamp normalization and synchronization with tiny synthetic samples.
- Test ATE, RPE, drift, invalid-pose counting, and failure interval handling
  with small trajectories where expected values are known.
- Use `tmp_path` for generated trajectory, plot, and metadata outputs.
- Use synthetic fixtures instead of requiring the full MVSEC dataset in normal
  unit tests.
- Mark full-dataset or external-baseline checks explicitly so they can be
  skipped when MVSEC or third-party tools are unavailable.
