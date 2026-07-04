---

# M002: First Event+IMU Odometry Backend

**Gathered:** 2026-06-28
**Status:** Ready for planning

## Project Description

This repository is an MVSEC-based event-camera navigation benchmark for GPS-denied visual-inertial navigation. M002 adds the first simple but real `event_imu` odometry backend after M001 established the benchmark harness, trajectory schema, artifact layout, health labeling, and evaluator.

The milestone is intentionally not a state-of-the-art event VIO implementation. It is a deterministic, inspectable Event+IMU backend that consumes MVSEC event-camera data and IMU data through the M001 contracts, produces a real relative trajectory through the existing odometry backend interface, and exports/evaluates the same artifact set as `imu_only`.

## Why This Milestone

M001 proves that the project can load sensor data, run an IMU-only backend, export standardized trajectories, and measure drift. M002 is the next necessary proof: the harness must support a non-IMU-only backend that actually uses event-camera data without breaking synchronization, export, health, plotting, or evaluation contracts.

This solves the gap between a benchmark harness and the project mission of comparing multimodal navigation approaches. It also forces the event data path, event/IMU alignment, Event+IMU failure visibility, and artifact compatibility to become real before stronger baselines or ensemble work begin.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Run an `event_imu` method through the existing benchmark entrypoint against synthetic fixtures and local MVSEC data.
- Inspect the same artifact set produced by `imu_only`, including trajectory CSV/TUM files, metrics, error series, plots, manifest, logs, and failure notes.
- Compare measured drift growth versus distance travelled for `event_imu` using the M001 evaluator without changing M001 contracts.
- See Event+IMU-specific DEGRADED/LOST behavior for low event activity, poor event/IMU overlap, invalid event frames, and failed/low-confidence image-like shift estimates.

### Entry point / environment

- Entry point: `python -m nav_benchmark.run run --method event_imu ...`, matching the M001 CLI style established for `imu_only`.
- Environment: local development and CI for synthetic tests; local development with manually available MVSEC files for dataset-dependent proof.
- Live dependencies involved: none. The backend depends on local dataset files, Python dependencies from `pyproject.toml`, and the existing M001 loader/synchronization/export/evaluation pipeline.

## Completion Class

- Contract complete means: `event_imu` implements the M001 odometry backend interface, accepts the common sequence/synchronization outputs, and emits the required trajectory schema and artifact set with content-valid files rather than placeholders.
- Integration complete means: the CLI can run `event_imu` through loader → backend → exporters → evaluator → plots/manifest/failure notes without changing M001 contracts.
- Operational complete means: synthetic checks run deterministically in CI, and a documented/manual MVSEC run can be performed locally without committing raw data or bulky generated artifacts.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- A deterministic synthetic Event+IMU fixture can run end-to-end through `event_imu` and produce `estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, `ground_truth_aligned.csv`, `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, `trajectory_plot.png`, `drift_over_distance.png`, `run.log`, `failure_notes.md`, and `run_manifest.json`.
- The evaluator reports drift growth versus distance travelled for `event_imu` using the same association, alignment, health, and artifact policies used for `imu_only`.
- Event-specific failure cases are observable: poor event/IMU overlap, low or zero event activity, invalid event-frame data, and failed or low-confidence shift estimates produce explicit health/failure outputs rather than silent data loss.
- A manual MVSEC run is documented, preferably for `outdoor_day1` with `indoor_flying1` as the easier debug fallback when needed. The run may be documented rather than committed; raw MVSEC data and bulky generated artifacts remain untracked.
- What cannot be simulated if this milestone is truly done: at least one real MVSEC execution path must be exercised manually enough to confirm the backend can consume real event and IMU streams through the M001 loader/synchronization contracts.

## Architectural Decisions

### Fixed-Time Event Frames for the First Backend

**Decision:** Use fixed-time event frames as the first implementation target for `event_imu`.

**Rationale:** Fixed-time frames preserve clear timestamp-window semantics, align naturally with IMU propagation intervals and latency accounting, and are straightforward to test with synthetic event packets before relying on full MVSEC data. They also make low-event windows and poor event/IMU overlap easy to surface as health states.

**Alternatives Considered:**
- Fixed-count event frames — stabilizes event density but creates variable timing and latency semantics, making synchronization and odometry frequency harder to reason about.
- Time surfaces — closer to event-camera practice and potentially richer for motion estimation, but introduces more parameters and implementation complexity than M002 needs.
- Raw event packets only — useful as an intermediate representation, but too weak by itself as the first user-visible odometry representation.

---

### Image-Like Shift as the Minimal Event Motion Cue

**Decision:** Estimate an image-like 2D shift between fixed-time event frames as the minimal event-derived motion cue.

**Rationale:** This makes the backend genuinely use event-camera data while staying inspectable and deterministic. The cue is simple enough for synthetic tests, can expose confidence/failure states, and avoids prematurely building a full feature tracker or production event VIO system.

**Alternatives Considered:**
- Feature tracks — more VIO-like, but larger in scope and more tune-sensitive for M002.
- Event rate health only — useful diagnostics, but too weak to satisfy the milestone goal of producing a real Event+IMU trajectory.
- Full residual/update estimator — more faithful to a future backend, but expands M002 toward later strong-baseline work.

---

### Conservative Event Correction with IMU Propagation as Backbone

**Decision:** Keep IMU propagation as the backbone and apply the event-frame shift as a conservative bounded correction or motion cue, not as a full VIO filter.

**Rationale:** The project needs a first real Event+IMU backend, not a state-of-the-art estimator. A bounded deterministic correction gives the event stream a real effect on the estimated trajectory while preserving traceability, testability, and honest reporting of weak accuracy.

**Alternatives Considered:**
- Diagnostic-only event cue — safer but may not meet the intent of an Event+IMU backend.
- A full estimator prototype — technically interesting but introduces too many irreversible architecture and tuning decisions for M002.

---

### Reuse M001 Artifact and Evaluation Contracts Unchanged

**Decision:** Reuse the M001 backend interface, trajectory schema, artifact set, health labeling philosophy, export rules, and evaluator behavior for `event_imu`.

**Rationale:** The point of M002 is to prove that a new backend can plug into the established benchmark harness. Changing artifact or evaluation contracts would blur whether the milestone improved odometry capability or merely changed measurement behavior.

**Alternatives Considered:**
- Event-specific output schema — could expose more backend internals, but would fragment benchmark comparisons.
- Separate event-only evaluator — would make drift results less comparable to `imu_only` and later backends.

---

### Manual MVSEC Proof Plus Synthetic CI Fixtures

**Decision:** Require deterministic synthetic fixtures for CI and documented/manual MVSEC proof for real-data execution.

**Rationale:** Synthetic fixtures are necessary for reliable automated verification and failure-state coverage. A manual MVSEC run is also required because event/IMU synchronization, data-shape assumptions, and real event activity cannot be fully proven with synthetic data alone.

**Alternatives Considered:**
- Synthetic only — easier for CI, but risks deferring real MVSEC integration issues to later milestones.
- Checked-in tiny MVSEC-derived fixture — useful if provenance and size are acceptable, but not required to satisfy M002 if manual proof is documented.

---

> See `.gsd/DECISIONS.md` for the full append-only register of all project decisions.

## Error Handling Strategy

M002 should preserve M001's no-silent-data-loss principle. Rows should remain in the project CSV with stable health labels; TUM export should continue to include only valid OK/DEGRADED poses according to the established policy. Event+IMU-specific failures should be explicit in health labels, diagnostics, `failure_notes.md`, and run logs.

Expected failure handling:

- Poor event/IMU overlap: mark affected intervals DEGRADED or LOST depending on severity; record overlap diagnostics.
- Low or zero event activity: mark windows DEGRADED when usable but weak, LOST when no meaningful event cue can be computed for required intervals.
- Invalid event frames or non-finite values: mark affected output LOST or INVALID according to initialization/propagation state; do not drop rows silently.
- Shift-confidence failure: skip or bound the correction, label the interval DEGRADED/LOST, and record the failure reason.
- Divergence or non-finite propagation: follow M001 health semantics and preserve failure visibility in artifacts.

No retry policy is needed for local file processing. User-facing errors should name the missing/invalid input, sequence, method, output directory, and the specific stage that failed.

## Risks and Unknowns

- Event-frame window size and alignment policy may dominate backend behavior — these should be planned explicitly per slice and tested with synthetic fixtures.
- The image-like shift cue may be weak or noisy on real MVSEC sequences — M002 should report measured drift honestly rather than claiming bounded navigation.
- Conservative correction thresholds may be hard to tune — they must be deterministic, documented, and revisable.
- Synchronization between event windows and IMU integration intervals must not silently discard data.
- Frame, timestamp, quaternion-order, and alignment assumptions from M001 must remain valid once event-derived corrections are added.
- Synthetic tests can prove wiring and failure behavior, but cannot validate real odometry accuracy.
- Manual MVSEC proof may expose dataset availability or runtime issues that CI cannot reproduce.

## Existing Codebase / Prior Art

- `src/nav_benchmark/baselines/base.py` — M001 backend interface expected to be reused by `event_imu`.
- `src/nav_benchmark/baselines/imu.py` — existing `imu_only` backend and health-labeling precedent.
- `src/nav_benchmark/run.py` or `python -m nav_benchmark.run` entrypoint — existing CLI orchestration path to extend with `--method event_imu`.
- M001 loader/synchronization modules — source of MVSEC sequence objects, event/IMU streams, timestamp validation, and calibration/frame assumptions.
- M001 exporters — required CSV/TUM trajectory schema and artifact writing behavior.
- M001 evaluator and plotting utilities — required drift, ATE/RPE, error series, and plot generation behavior.
- `.gsd/DECISIONS.md` D001-D007 — prior decisions on synchronization, export policy, CLI shape, health labeling, backend interface, evaluation alignment, and error-series schema.

## Relevant Requirements

- R001 — Advances MVSEC sensor ingestion by exercising event-camera and IMU streams in a real backend, not just the loader path.
- R002 — Advances timestamp synchronization and calibration handling by adding event-window to IMU-interval alignment and explicit overlap diagnostics.
- R003 — Advances the fixed trajectory output contract by proving a second backend can produce the same CSV/TUM schema, health labels, and artifact set.
- Core benchmark requirements from the project instructions — preserves required metrics: ATE, RPE, drift every 20 m, total drift, tracking failure rate, invalid-pose intervals, outlier rate, latency per update, and odometry frequency.

## Scope

### In Scope

- Implement `event_imu` behind the M001 odometry backend contract.
- Consume MVSEC event stream and IMU data through existing sequence/synchronization contracts.
- Build fixed-time event frames from event packets.
- Estimate an image-like shift between event frames as the minimal event-derived motion cue.
- Apply the event cue as a conservative bounded correction or motion cue while IMU propagation remains the backbone.
- Preserve and expose Event+IMU-specific health/failure states.
- Export the same artifact set and trajectory schema as `imu_only`.
- Evaluate drift growth versus distance travelled using the M001 evaluator.
- Add deterministic synthetic tests for wiring, artifacts, and failure states.
- Document and perform at least one manual MVSEC run, with generated artifacts kept out of git.

### Out of Scope / Non-Goals

- UltimateSLAM, ESVO, or other production wrapper integrations.
- Full ensemble learning, learned gating, or RL/PPO fusion.
- Full state-of-the-art event VIO or drift-bounded navigation claims.
- Map/orthophoto anchoring or satellite matching.
- Embedded optimization or hard real-time deployment.
- Changing M001 trajectory, artifact, evaluator, association, alignment, or health-label contracts unless a blocking defect is found and explicitly documented.
- Committing raw MVSEC archives, extracted large datasets, generated trajectories, plots, caches, or virtual environments.

## Technical Constraints

- Use Python 3.13 and `uv`; `pyproject.toml` remains the dependency/tooling source of truth.
- Keep dataset IO, synchronization, backend execution, evaluation, and plotting in separate modules.
- Preserve the required trajectory CSV schema: `timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms`.
- Use method name `event_imu`.
- Timestamps are seconds; quaternions are `qx,qy,qz,qw` in project CSVs.
- Maintain M001 nearest-neighbor association/alignment/export assumptions unless explicitly superseded by a new decision.
- Preserve invalid/degraded intervals in benchmark artifacts; do not silently drop missing or invalid poses.
- Synthetic tests must not pretend to validate real odometry accuracy.
- MVSEC proof must avoid committing raw datasets or bulky generated outputs.

## Integration Points

- MVSEC local HDF5 files — source of event-camera, IMU, calibration, timestamp, and ground-truth streams.
- M001 sequence/synchronization layer — provides validated sensor streams and overlap behavior to the backend.
- Odometry backend interface — `event_imu` plugs in alongside `imu_only`.
- CLI runner — dispatches `--method event_imu` and writes run directories with the established artifact skeleton.
- Exporters — write project CSV, TUM trajectory, manifest, logs, and failure notes.
- Evaluator and plotting utilities — compute metrics and generate error/trajectory/drift artifacts.
- CI — runs deterministic synthetic tests without requiring MVSEC downloads.

## Testing Requirements

M002 requires unit, integration, and command-level tests that prove contract behavior without depending on full MVSEC data in CI.

Required test coverage:

- Unit tests for fixed-time event-frame construction, including empty windows, low-activity windows, polarity handling if represented, deterministic binning, and timestamp/window boundaries.
- Unit tests for image-like shift estimation, including known synthetic shifts, low-confidence/no-shift cases, invalid/non-finite inputs, and deterministic confidence outputs.
- Unit tests for conservative correction behavior, including bounded correction, skipped correction on low confidence, and preservation of IMU propagation when event cues are unavailable.
- Health/failure tests for poor event/IMU overlap, low event activity, invalid event frames, and shift-confidence failure.
- Integration tests showing `event_imu` produces the required trajectory schema and artifact set from a tiny synthetic sequence.
- CLI smoke test for `python -m nav_benchmark.run run --method event_imu ...` on synthetic data.
- Evaluator smoke test proving `event_imu` artifacts can produce drift/error outputs using the existing M001 evaluator.
- Manual MVSEC run instructions and recorded notes for at least one real sequence; dataset-dependent output artifacts should remain untracked.

Before claiming completion, run the smallest relevant checks first and then broader checks where available:

```bash
rtk uv run --only-dev ruff check .
rtk uv run --only-dev ruff format --check .
rtk uv run pytest tests -q
```

## Acceptance Criteria

M002 acceptance should be decomposed into slices, but the milestone-level criteria are:

- `event_imu` is available as a backend method and is reachable from the existing CLI.
- `event_imu` consumes both event-camera data and IMU data through the M001 contracts.
- Fixed-time event frames are generated deterministically and tested with synthetic event packets.
- Image-like event-frame shift is computed deterministically and has confidence/failure behavior.
- IMU propagation remains the backbone while event shifts apply conservative bounded corrections or motion cues.
- Poor event/IMU overlap, low event activity, invalid event frames, and shift-confidence failures are surfaced through health labels, logs, diagnostics, and failure notes.
- The backend writes content-valid versions of all required artifacts: `estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, `ground_truth_aligned.csv`, `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, `trajectory_plot.png`, `drift_over_distance.png`, `run.log`, `failure_notes.md`, and `run_manifest.json`.
- The evaluator reports drift growth versus distance travelled for `event_imu` without changing M001 evaluator contracts.
- Synthetic tests pass in CI-compatible conditions.
- A manual MVSEC run is documented for `outdoor_day1` when available, with `indoor_flying1` as an easier debug fallback.

## Open Questions

- What fixed-time window size should be the default for event frames? Current thinking: choose during planning with synthetic tests and expose it as configuration.
- How exactly should image-plane shift map to a bounded pose, velocity, or heading correction? Current thinking: keep it deliberately conservative and deterministic for M002.
- What confidence thresholds should separate OK, DEGRADED, and LOST for event-shift behavior? Current thinking: define simple thresholds in the M002 plan and make them revisable.
- Should a tiny MVSEC-shaped fixture be added later for stronger CI proof? Current thinking: not required for M002 if synthetic tests and manual MVSEC proof are both present.
- Which manual MVSEC run should be documented first if dataset availability is limited? Current thinking: target `outdoor_day1`, use `indoor_flying1` as fallback.
