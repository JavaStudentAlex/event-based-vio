---
description: "Policy for delegating work to specialized agents while preserving repository contracts."
---

# Delegation Policy

## Purpose

Use this when splitting work across specialized LLM agents or reviewing work
produced by another agent.

## Rules

- Every delegated agent must treat `AGENTS.md` and their respective role definitions as the base contract.
- Keep MVSEC loading, conversion, synchronization, and replay with
  `dataset-pipeline-engineer`.
- Keep IMU-only, image+IMU, event+IMU, and multimodal baseline adapters with
  `vio-baseline-engineer`.
- Keep ATE/RPE/drift metrics, plotting, health scoring, and deterministic
  fusion with `evaluation-ensemble-engineer`.
- Synthesize delegated results before editing; do not blindly apply patches.
- Verify merged or adopted work in the current session before claiming it works.

## Good Delegation Targets

- Asking the dataset agent to inspect MVSEC stream layout and propose loader
  interfaces.
- Asking the baseline agent to verify that all adapters emit the common
  trajectory schema.
- Asking the evaluation agent to review ATE/RPE alignment policy and failure
  accounting.
