# M002: First Event+IMU Odometry Backend

**Status:** Draft for later discussion
**Depends on:** M001-ncx5an

## Seed Intent

M002 adds the first simple but real Event+IMU relative odometry backend after M001 has established the benchmark harness. The goal is not to implement a state-of-the-art event VIO backend yet. The goal is to produce a real estimated trajectory through the M001 backend interface, using event-camera data together with IMU propagation or correction, and to reuse the exact same artifact schema and evaluator that `imu_only` used in M001.

## Provisional Scope

### In Scope

- Implement `event_imu` behind the M001 odometry backend contract.
- Use MVSEC event stream and IMU data through the M001 sequence/synchronization contracts.
- Convert events into a simple deterministic representation if needed, such as event packets, event frames, or time surfaces.
- Combine event-derived motion cues with IMU propagation or correction to produce a relative trajectory.
- Export the same artifact set/schema as `imu_only`:
  - `estimated_trajectory.csv`
  - `estimated_trajectory_tum.txt`
  - `ground_truth_aligned.csv`
  - `metrics.json`
  - `error_vs_time.csv`
  - `error_vs_distance.csv`
  - `trajectory_plot.png`
  - `drift_over_distance.png`
  - `run.log`
  - `failure_notes.md`
  - `run_manifest.json`
- Preserve invalid/degraded intervals in benchmark artifacts.
- Evaluate drift growth versus distance travelled using the M001 evaluator.

### Out of Scope / Likely Deferred

- UltimateSLAM or ESVO production wrappers; likely M003.
- Full ensemble learning.
- RL/PPO fusion.
- Map/orthophoto anchoring or satellite matching.
- Embedded optimization or hard real-time deployment.
- Claiming drift-bounded navigation; M002 should still report measured drift honestly.

## Provisional Architecture Notes

- Consume the M001 common sequence object and synchronization outputs.
- Reuse the M001 minimal odometry backend interface and `OdometryResult` shape.
- Reuse the M001 export/evaluation/plot/manifest/failure-note pipeline unchanged.
- Keep the first Event+IMU backend inspectable and deterministic rather than state-of-the-art.
- Prefer simple event representations that can be tested with synthetic event packets before depending on full MVSEC data.

## Key Risks / Unknowns

- Event representation choice may dominate complexity; event packets, event frames, and time surfaces need comparison during M002 planning.
- A simple Event+IMU backend may produce weak accuracy, but the proof target is real trajectory generation and measurable drift, not benchmark-leading performance.
- Synchronization between event windows and IMU integration intervals must not silently discard data.
- Frame and timestamp assumptions from M001 must remain valid once event-derived motion cues are added.
- Synthetic tests must verify backend wiring without pretending to validate real odometry accuracy.

## Open Questions for Full M002 Discussion

- Which simple event representation should be the first implementation target: packets, fixed-time event frames, fixed-count event frames, or time surfaces?
- What minimal event-derived motion cue is acceptable for the first real backend?
- How should IMU propagation and event correction be combined without overbuilding a full filter?
- What synthetic motion fixture can prove Event+IMU wiring without claiming real MVSEC accuracy?
- Should M002 require one documented/manual MVSEC run, or only synthetic proof plus documented manual instructions?
- What failure states should be specific to Event+IMU, such as low event rate, feature/motion cue failure, poor event/IMU overlap, or divergence?

## Draft Acceptance Direction

M002 should be considered complete only when `event_imu` produces the same content-valid artifact set and trajectory schema as `imu_only`, and the evaluator can report drift growth versus distance travelled without changing M001 contracts.
