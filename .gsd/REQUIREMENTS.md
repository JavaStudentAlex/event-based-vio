# Requirements

This file is the explicit capability and coverage contract for the project.

## Active

### R001 — The system can load MVSEC event camera, IMU, calibration, ground-truth trajectory, and timestamp data from local dataset files.
- Class: core-capability
- Status: active
- Description: The system can load MVSEC event camera, IMU, calibration, ground-truth trajectory, and timestamp data from local dataset files.
- Why it matters: Every downstream odometry and evaluation result depends on trustworthy dataset ingestion.
- Source: user
- Primary owning slice: M001-ncx5an/S01
- Supporting slices: none
- Validation: mapped
- Notes: First target sequence is `outdoor_day1`; `indoor_flying1` is the easier debug fallback.

### R002 — Event, IMU, and ground-truth streams are timestamp-validated and synchronized with explicit calibration/frame assumptions.
- Class: core-capability
- Status: active
- Description: Event, IMU, and ground-truth streams are timestamp-validated and synchronized with explicit calibration/frame assumptions.
- Why it matters: Silent timestamp or frame mistakes make drift metrics untrustworthy.
- Source: user
- Primary owning slice: M001-ncx5an/S01
- Supporting slices: M001-ncx5an/S02
- Validation: mapped
- Notes: Timestamp units, frame assumptions, and sync tolerance must be recorded.

### R003 — Every method exports the project CSV trajectory schema and a TUM-compatible trajectory file.
- Class: integration
- Status: active
- Description: Every method exports the project CSV trajectory schema and a TUM-compatible trajectory file.
- Why it matters: IMU-only, Event+IMU, and future baselines must be comparable through the same artifact contract.
- Source: user
- Primary owning slice: M001-ncx5an/S02
- Supporting slices: M001-ncx5an/S03
- Validation: mapped
- Notes: Required CSV columns are `timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms`.

### R004 — The benchmark can run an `imu_only` dead reckoning baseline that produces an estimated relative trajectory.
- Class: primary-user-loop
- Status: active
- Description: The benchmark can run an `imu_only` dead reckoning baseline that produces an estimated relative trajectory.
- Why it matters: This verifies IMU loading, timestamp handling, integration logic, export, and evaluation before Event+IMU complexity is added.
- Source: user
- Primary owning slice: M001-ncx5an/S03
- Supporting slices: M001-ncx5an/S02
- Validation: mapped
- Notes: The baseline is expected to drift; accuracy is not the proof target.

### R005 — The evaluator aligns estimated trajectories to ground truth with an explicit SE3 policy and computes trajectory error metrics.
- Class: core-capability
- Status: active
- Description: The evaluator aligns estimated trajectories to ground truth with an explicit SE3 policy and computes trajectory error metrics.
- Why it matters: The project must measure relative odometry drift against ground truth in a repeatable way.
- Source: user
- Primary owning slice: M001-ncx5an/S04
- Supporting slices: M001-ncx5an/S02, M001-ncx5an/S03
- Validation: mapped
- Notes: Metrics include ATE, RPE, final drift, position error over time, and distance-binned drift.

### R006 — The benchmark produces explicit error-versus-distance and drift-over-distance outputs, including distance bins such as every 20 meters.
- Class: differentiator
- Status: active
- Description: The benchmark produces explicit error-versus-distance and drift-over-distance outputs, including distance bins such as every 20 meters.
- Why it matters: Drift growth versus distance travelled is the most important milestone metric for GPS-denied relative navigation.
- Source: user
- Primary owning slice: M001-ncx5an/S04
- Supporting slices: none
- Validation: mapped
- Notes: This is drift-measured, not a claim of drift-bounded navigation.

### R007 — A CLI command loads a sequence, runs a selected method, exports trajectories, evaluates against ground truth, and writes run artifacts.
- Class: primary-user-loop
- Status: active
- Description: A CLI command loads a sequence, runs a selected method, exports trajectories, evaluates against ground truth, and writes run artifacts.
- Why it matters: Reproducibility depends on a single documented path instead of manual scripts.
- Source: user
- Primary owning slice: M001-ncx5an/S03
- Supporting slices: M001-ncx5an/S04, M001-ncx5an/S05
- Validation: mapped
- Notes: Planned entrypoint is `python -m nav_benchmark.run`.

### R008 — Each run writes `run_manifest.json` with method, dataset/sequence, config, timestamp policy, alignment policy, frames, units, code version if available, and run status.
- Class: operability
- Status: active
- Description: Each run writes `run_manifest.json` with method, dataset/sequence, config, timestamp policy, alignment policy, frames, units, code version if available, and run status.
- Why it matters: Benchmark results must be auditable and reproducible.
- Source: user
- Primary owning slice: M001-ncx5an/S05
- Supporting slices: M001-ncx5an/S03, M001-ncx5an/S04
- Validation: mapped
- Notes: Manifest is required for successful and failed/degraded runs.

### R009 — Invalid/degraded intervals are explicitly recorded in benchmark artifacts and `failure_notes.md` is always present.
- Class: failure-visibility
- Status: active
- Description: Invalid/degraded intervals are explicitly recorded in benchmark artifacts and `failure_notes.md` is always present.
- Why it matters: Commands that run but silently hide invalid data are unacceptable.
- Source: user
- Primary owning slice: M001-ncx5an/S05
- Supporting slices: M001-ncx5an/S02, M001-ncx5an/S04
- Validation: mapped
- Notes: Successful runs may state `No degraded or failed intervals detected.`

### R010 — Fast synthetic tests verify loading, synchronization, trajectory export, metric calculation, plots, and CLI smoke behavior without MVSEC downloads.
- Class: quality-attribute
- Status: active
- Description: Fast synthetic tests verify loading, synchronization, trajectory export, metric calculation, plots, and CLI smoke behavior without MVSEC downloads.
- Why it matters: Ordinary CI must verify the pipeline contract despite large dataset constraints.
- Source: user
- Primary owning slice: M001-ncx5an/S05
- Supporting slices: M001-ncx5an/S01, M001-ncx5an/S02, M001-ncx5an/S03, M001-ncx5an/S04
- Validation: mapped
- Notes: Full MVSEC checks are documented/manual or separately marked dataset checks.

### R011 — M001 defines a minimal backend interface that returns trajectory, health/failure intervals, latency/runtime stats where available, and assumptions metadata.
- Class: integration
- Status: active
- Description: M001 defines a minimal backend interface that returns trajectory, health/failure intervals, latency/runtime stats where available, and assumptions metadata.
- Why it matters: M002 and M003 need to add methods without changing export/evaluation contracts.
- Source: inferred
- Primary owning slice: M001-ncx5an/S03
- Supporting slices: M001-ncx5an/S02
- Validation: mapped
- Notes: Avoid overbuilding a plugin system before external wrappers exist.

### R012 — Add a simple but real Event+IMU relative odometry backend that uses event packets, event frames, or time surfaces with IMU propagation/correction.
- Class: core-capability
- Status: active
- Description: Add a simple but real Event+IMU relative odometry backend that uses event packets, event frames, or time surfaces with IMU propagation/correction.
- Why it matters: This is the first required event-camera GPS-denied odometry capability.
- Source: user
- Primary owning slice: M002/S03
- Supporting slices: M002/S01
- Validation: mapped
- Notes: Backend code exists from M001. M002 validates correctness (S01 extrinsics hardening) and produces a benchmark comparison proving event_imu improves over imu_only (S03).

### R014 — The project should support stronger baselines such as UltimateSLAM or ESVO if practical.
- Class: differentiator
- Status: active
- Description: The project should support stronger baselines such as UltimateSLAM or ESVO if practical.
- Why it matters: Strong reference baselines are useful for later comparison and ensemble work.
- Source: user
- Primary owning slice: M003/provisional
- Supporting slices: M001-ncx5an/S03, M002/provisional
- Validation: unmapped
- Notes: External integration risk is intentionally deferred.

## Validated

### R013 — `event_imu` and later methods must produce the same artifact set and schema as `imu_only`.
- Class: integration
- Status: validated
- Description: `event_imu` and later methods must produce the same artifact set and schema as `imu_only`.
- Why it matters: Comparisons are only meaningful if method outputs are structurally identical.
- Source: user
- Primary owning slice: M002/S02
- Supporting slices: M002/S01
- Validation: Mechanically validated by tests/test_cross_method_schema.py added in M002/S02, which runs imu_only, event_imu, and image_imu on the same synthetic sequence and asserts identical artifact structure.
- Notes: M002/S02 adds a cross-method test that runs imu_only, event_imu, and image_imu on the same synthetic sequence and asserts identical artifact structure.

## Deferred

### R015 — Build production-quality wrappers around UltimateSLAM or ESVO if integration is practical.
- Class: integration
- Status: deferred
- Description: Build production-quality wrappers around UltimateSLAM or ESVO if integration is practical.
- Why it matters: These methods may provide stronger event-based reference performance.
- Source: user
- Primary owning slice: M003/provisional
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred out of M001 and M002 until the benchmark harness and first Event+IMU backend exist.

### R016 — Add deeper runtime/resource profiling such as CPU/GPU usage and real-time factor reporting.
- Class: operability
- Status: deferred
- Description: Add deeper runtime/resource profiling such as CPU/GPU usage and real-time factor reporting.
- Why it matters: Embedded feasibility eventually needs performance evidence.
- Source: user
- Primary owning slice: M003/provisional
- Supporting slices: none
- Validation: unmapped
- Notes: M001 may include basic latency fields, but not full profiling.

### R017 — Compare multiple methods and summarize robustness/failure behavior across runs.
- Class: differentiator
- Status: deferred
- Description: Compare multiple methods and summarize robustness/failure behavior across runs.
- Why it matters: Later ensemble decisions need evidence about when each method fails.
- Source: inferred
- Primary owning slice: M003/provisional
- Supporting slices: none
- Validation: unmapped
- Notes: Deferred until at least `imu_only` and `event_imu` exist.

### R018 — Add an event-only or event-frame visual odometry baseline.
- Class: differentiator
- Status: deferred
- Description: Add an event-only or event-frame visual odometry baseline.
- Why it matters: It may help isolate the value of IMU fusion.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: unmapped
- Notes: Not required for M001.

## Out of Scope

### R019 — Do not implement absolute correction through map or orthophoto anchoring in these initial benchmark milestones.
- Class: anti-feature
- Status: out-of-scope
- Description: Do not implement absolute correction through map or orthophoto anchoring in these initial benchmark milestones.
- Why it matters: Relative odometry must exist before anchoring is meaningful.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Candidate future work after relative pipeline and baselines exist.

### R020 — Do not implement satellite-image matching in the initial benchmark milestones.
- Class: anti-feature
- Status: out-of-scope
- Description: Do not implement satellite-image matching in the initial benchmark milestones.
- Why it matters: It would distract from proving the relative odometry core.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Future stretch work only.

### R021 — Do not implement RL/PPO policy learning for fusion in the initial milestones.
- Class: anti-feature
- Status: out-of-scope
- Description: Do not implement RL/PPO policy learning for fusion in the initial milestones.
- Why it matters: Deterministic baselines and metrics must exist before learned policy work.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Explicitly deferred by project instructions.

### R022 — Do not implement full ensemble learning in these initial milestones.
- Class: anti-feature
- Status: out-of-scope
- Description: Do not implement full ensemble learning in these initial milestones.
- Why it matters: The project first needs individual baselines and comparable artifacts.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Future work after baselines exist.

### R023 — Do not optimize for embedded deployment or hard real-time operation in M001.
- Class: anti-feature
- Status: out-of-scope
- Description: Do not optimize for embedded deployment or hard real-time operation in M001.
- Why it matters: Functional correctness and benchmark trustworthiness come first.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Basic latency fields may exist, but embedded hardening is later.

### R024 — Ordinary CI must not require full MVSEC downloads.
- Class: constraint
- Status: out-of-scope
- Description: Ordinary CI must not require full MVSEC downloads.
- Why it matters: Large datasets make CI slow, brittle, and environment-dependent.
- Source: user
- Primary owning slice: none
- Supporting slices: none
- Validation: n/a
- Notes: Full MVSEC checks are manual or separately marked dataset checks.

## Traceability

| ID | Class | Status | Primary owner | Supporting | Proof |
|---|---|---|---|---|---|
| R001 | core-capability | active | M001-ncx5an/S01 | none | mapped |
| R002 | core-capability | active | M001-ncx5an/S01 | M001-ncx5an/S02 | mapped |
| R003 | integration | active | M001-ncx5an/S02 | M001-ncx5an/S03 | mapped |
| R004 | primary-user-loop | active | M001-ncx5an/S03 | M001-ncx5an/S02 | mapped |
| R005 | core-capability | active | M001-ncx5an/S04 | M001-ncx5an/S02, M001-ncx5an/S03 | mapped |
| R006 | differentiator | active | M001-ncx5an/S04 | none | mapped |
| R007 | primary-user-loop | active | M001-ncx5an/S03 | M001-ncx5an/S04, M001-ncx5an/S05 | mapped |
| R008 | operability | active | M001-ncx5an/S05 | M001-ncx5an/S03, M001-ncx5an/S04 | mapped |
| R009 | failure-visibility | active | M001-ncx5an/S05 | M001-ncx5an/S02, M001-ncx5an/S04 | mapped |
| R010 | quality-attribute | active | M001-ncx5an/S05 | M001-ncx5an/S01, M001-ncx5an/S02, M001-ncx5an/S03, M001-ncx5an/S04 | mapped |
| R011 | integration | active | M001-ncx5an/S03 | M001-ncx5an/S02 | mapped |
| R012 | core-capability | active | M002/S03 | M002/S01 | mapped |
| R013 | integration | validated | M002/S02 | M002/S01 | Mechanically validated by tests/test_cross_method_schema.py added in M002/S02, which runs imu_only, event_imu, and image_imu on the same synthetic sequence and asserts identical artifact structure. |
| R014 | differentiator | active | M003/provisional | M001-ncx5an/S03, M002/provisional | unmapped |
| R015 | integration | deferred | M003/provisional | none | unmapped |
| R016 | operability | deferred | M003/provisional | none | unmapped |
| R017 | differentiator | deferred | M003/provisional | none | unmapped |
| R018 | differentiator | deferred | none | none | unmapped |
| R019 | anti-feature | out-of-scope | none | none | n/a |
| R020 | anti-feature | out-of-scope | none | none | n/a |
| R021 | anti-feature | out-of-scope | none | none | n/a |
| R022 | anti-feature | out-of-scope | none | none | n/a |
| R023 | anti-feature | out-of-scope | none | none | n/a |
| R024 | constraint | out-of-scope | none | none | n/a |

## Coverage Summary

- Active requirements: 13
- Mapped to slices: 12
- Validated: 1 (R013)
- Unmapped active requirements: 0
