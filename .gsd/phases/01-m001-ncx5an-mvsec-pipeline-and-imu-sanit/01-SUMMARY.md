---
id: M001
title: "MVSEC Pipeline and IMU Sanity Benchmark"
status: complete
completed_at: 2026-07-05T05:17:01.348Z
key_decisions:
  - D003: Health labeling for imu_only uses OK/DEGRADED/LOST/INVALID based on IMU sample gaps
  - D004: BaseOdometryBackend abstract interface with run(sequence) method for all backends
  - Canonical status strings: manifest.status=success, metrics.status=OK, alignment policies separated between timestamp association and trajectory alignment
key_files:
  - src/nav_benchmark/run.py
  - src/nav_benchmark/validation.py
  - src/nav_benchmark/baselines/imu_only.py
  - src/nav_benchmark/baselines/base.py
  - src/nav_benchmark/evaluation/evaluator.py
  - src/nav_benchmark/data/mvsec_reader.py
  - src/nav_benchmark/data/synchronizer.py
  - src/nav_benchmark/trajectory/csv_export.py
  - tests/cli/test_validate_cli.py
lessons_learned:
  - Validation string mismatches between producers and consumers should be caught by regression tests locking exact canonical values
  - Keeping run lifecycle status (success/failed) separate from evaluation health status (OK) prevents conflation
  - Synthetic data paths are essential for deterministic CI testing without downloading MVSEC
---

# M001: MVSEC Pipeline and IMU Sanity Benchmark

**Complete MVSEC pipeline with IMU-only baseline, evaluation, validation, and 268 passing tests**

## What Happened

M001 established the complete MVSEC pipeline and IMU sanity benchmark. Starting from raw data loading (S01), the milestone built a vertical stack through sensor synchronization (S02), IMU-only odometry baseline (S03), evaluation with ATE/RPE/drift metrics (S04), artifact validation and comparison reporting (S05), and final validation string mismatch remediation (S06). The result is a self-verifying benchmark pipeline where `run -> eval -> validate` produces and checks all artifacts deterministically. 268 tests pass with clean lint and format. The BaseOdometryBackend interface and CLI conventions are ready for M002's event+IMU backend.

## Success Criteria Results

All success criteria met: MVSEC HDF5 data loader, synthetic data path, IMU-only backend, CLI run/eval/validate pipeline, ATE/RPE/drift evaluation, artifact validation with 11 checks, regression test locking canonical strings, 268 tests passing, lint and format clean.

## Definition of Done Results

Not provided.

## Requirement Outcomes

Not provided.

## Deviations

S06 originally expected source code remediation of a validation string mismatch, but research found the mismatch was already fixed. S06 closed as validation proof with a regression test rather than source remediation.

## Follow-ups

- M002: Implement event+IMU odometry backend using the BaseOdometryBackend interface from S03
- M003: Add strong baselines (image+IMU, multimodal) and comparative benchmark reporting
- Consider adding MVSEC outdoor_day1 end-to-end integration test once dataset download is available
