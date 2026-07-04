# M002: First Event+IMU Odometry Backend

**Gathered:** 2026-06-28
**Status:** Draft in discussion

## Discussion Notes So Far

M002 is intended to add the first simple but real `event_imu` odometry backend after M001's benchmark harness, while preserving M001's backend interface, trajectory schema, artifact set, evaluator, health labeling philosophy, and no-silent-data-loss contract.

User choices captured so far:

- First event representation: fixed-time event frames.
- Minimal event-derived motion cue: image-like shift between event frames.
- Proof beyond synthetic fixtures: documented/manual MVSEC run, with generated artifacts not committed.
- Fusion boundary: conservative correction; IMU propagation remains the backbone and event-frame shift provides a bounded deterministic correction or velocity/heading cue.
- Event+IMU-specific failures: poor event/IMU overlap, low event activity, invalid event frames, and shift-confidence failure should be first-class DEGRADED/LOST acceptance criteria.

## Remaining Depth To Verify

Need confirm the integrated framing, user-visible outcome, final acceptance proof, and remaining uncertainty before writing final context.
