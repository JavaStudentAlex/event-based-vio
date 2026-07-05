---
id: M001-ncx5an
title: "MVSEC Pipeline and IMU Sanity Benchmark"
status: complete
completed_at: 2026-07-05T16:34:44.817Z
key_decisions:
  - Use nearest-neighbor timestamp association within caller-provided tolerance for S02, with mandatory diagnostics.
  - Preserve LOST and INVALID rows in the project CSV while filtering them from TUM export for evo/tool compatibility.
  - Expose a small `BaseOdometryBackend.run(sequence, *, config) -> Trajectory` interface and implement IMU-only behind it.
  - Use global SE(3) alignment over overlapping OK/DEGRADED poses for S04 evaluation without robust trimming or time-offset search.
  - Write stable error series artifacts for time-indexed and distance-indexed evaluation outputs.
key_files:
  - src/nav_benchmark/datasets/mvsec.py
  - src/nav_benchmark/trajectory/export.py
  - src/nav_benchmark/trajectory/sync.py
  - src/nav_benchmark/baselines/base.py
  - src/nav_benchmark/baselines/imu.py
  - src/nav_benchmark/run.py
  - src/nav_benchmark/evaluation/metrics.py
  - src/nav_benchmark/evaluation/harness.py
  - src/nav_benchmark/evaluation/plots.py
  - src/nav_benchmark/validation.py
  - tests/
lessons_learned:
  - Milestone closeout must verify both broad test coverage and artifact-level validation strings because user-facing validator output is part of the contract.
  - Keeping invalid/degraded health labels in the project CSV is important for robustness accounting even when external SLAM tools require filtered TUM trajectories.
  - Synthetic tests are sufficient for CI-level confidence in this milestone, while real MVSEC dataset checks remain a manual or later-milestone concern.
---

# M001-ncx5an: MVSEC Pipeline and IMU Sanity Benchmark

**M001 delivered a trustworthy synthetic-verified MVSEC benchmark foundation with loader contracts, synchronization/export schemas, IMU-only CLI artifacts, drift evaluation, plots, manifests, failure notes, and validation coverage.**

## What Happened

This milestone built the first reproducible benchmark foundation for the event-camera VIO project. S01 established MVSEC-style loader and stream validation contracts. S02 locked deterministic nearest-neighbor synchronization, diagnostics, fixed trajectory CSV schema, and TUM export behavior. S03 introduced the odometry backend interface, IMU-only baseline, and CLI run path that writes the benchmark artifact skeleton. S04 added project-native drift evaluation and plotting for ATE, RPE, final drift, time-indexed error, distance-indexed error, and distance-binned drift. S05 made run manifests, failure notes, and artifact validation part of the normal contract. S06 remediated the validation string mismatch discovered during milestone closeout and reran validation checks. Fresh completion evidence includes `rtk uv run pre-commit run --all-files` passing and `rtk uv run pytest tests -q` reporting 327 passed with 3 non-fatal runtime warnings in ensemble fusion tests.

## Success Criteria Results

| Criterion | Result | Evidence |
|---|---|---|
| `imu_only` runs through one CLI command and writes the complete benchmark artifact set. | MET | S03 and S05 completed CLI/artifact flow and validation coverage. |
| Synthetic CI tests verify the pipeline without requiring MVSEC downloads. | MET | Fresh `rtk uv run pytest tests -q`: 327 passed, 3 warnings. |
| Trajectory exports use the fixed project CSV schema and TUM format. | MET | S02 completed export contracts and diagnostics; policy recorded in project memory. |
| Evaluation reports ATE, RPE, final drift, error over time, error versus distance, and distance-binned drift. | MET | S04 completed evaluator outputs and plots. |
| `run_manifest.json` and `failure_notes.md` are always written. | MET | S05 completed manifest/failure artifacts and validation. |
| Invalid or degraded intervals are preserved in benchmark artifacts, not silently dropped. | MET | S02/S03 health/export policies preserve project CSV diagnostics while maintaining TUM compatibility. |

## Definition of Done Results

- PASS: All six planned slices are complete in the GSD database.
- PASS: Milestone validation was recorded with verdict `pass`.
- PASS: Fresh `rtk uv run pre-commit run --all-files` passed.
- PASS: Fresh `rtk uv run pytest tests -q` passed with 327 tests and 3 warnings.
- PASS: The milestone leaves downstream M002/M003 with stable loader, export, run, evaluation, and validation contracts.

## Requirement Outcomes

M001 advances the active benchmark-foundation requirements covering MVSEC ingestion, synchronization/export, IMU-only CLI baseline, evaluation metrics/artifacts, and failure/manifest validation. Later event+IMU, stronger baselines, learned gating, deployment, and map anchoring requirements remain outside this milestone scope and should be handled by subsequent milestones.

## Deviations

The final S06 remediation slice was added during closeout to fix a validation string mismatch before completing the milestone.

## Follow-ups

Proceed to M002 for the first Event+IMU odometry backend using the stable M001 loader, trajectory, CLI, and evaluation contracts. Investigate the three non-fatal RuntimeWarnings in ensemble fusion tests when M003 strengthens ensemble behavior.
