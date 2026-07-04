---
depends_on: [M001-ncx5an, M002]
---

# M003: Strong Baselines and Benchmark Reporting

**Gathered:** 2026-06-27
**Status:** Ready for planning

## Project Description

M003 integrates at least one stronger external Event/IMU baseline (default target: UltimateSLAM; fallback: ESVO or reporting-only if integration blocks) and adds richer benchmark reporting without changing the artifact contract or backend interface established in M001 and extended in M002. The milestone keeps outputs comparable by reusing the same trajectory CSV/TUM schema, evaluator, plots, manifest metadata, and failure-visibility rules.

## Why This Milestone

With the benchmark harness (M001) and first Event+IMU backend (M002) in place, the project can now integrate a stronger external reference method and improve benchmark reporting. This helps quantify how much headroom exists between simple baselines and state-of-the-art event-based methods, and establishes reliability/runtimes as first-class reporting surfaces.

## User-Visible Outcome

### When this milestone is complete, the user can:

- Run the CLI to execute at least one external baseline (e.g., UltimateSLAM) on a documented MVSEC sequence and obtain the same content-valid artifact set/schema as `imu_only` and `event_imu`.
- Compare `imu_only`, `event_imu`, and the external method side-by-side via shared metrics and plots.
- Review richer runtime/failure reporting including latency summaries, approximate real-time factor, and aggregated failure intervals.

### Entry point / environment

- Entry point: `python -m nav_benchmark.run`
- Environment: local dev; external method may require a container or environment setup guide. Ordinary CI remains synthetic-only and must not attempt external runs.
- Live dependencies involved: local MVSEC HDF5 files for manual runs; external baseline binaries/containers when used.

## Completion Class

- Contract complete means: external baseline adapter produces the identical artifact schema without modifying core exporters/evaluator.
- Integration complete means: one documented external method runs on one documented MVSEC sequence and its outputs are evaluated and compared via the same evaluator/plots.
- Operational complete means: manifests capture external tool version/config, and failure intervals and runtimes are reported without over-instrumentation.

## Final Integrated Acceptance

To call this milestone complete, we must prove:

- At least one stronger external baseline (UltimateSLAM preferred; ESVO acceptable) runs on a documented MVSEC sequence and produces the same content-valid artifact set and schema.
- Reporting additions include runtime summaries (latency, approximate real-time factor where measurable) and aggregated failure intervals across methods.
- Multi-method comparison plots are generated (estimated vs ground truth overlays and comparative drift-over-distance).
- The project-owned CSV/TUM/metrics/plots/manifest/failure-notes contracts remain unchanged.

## Architectural Decisions

### External baseline adapter policy

**Decision:** Integrate external methods via adapters that run a subprocess or container and translate their outputs into the project artifact schema without modifying core exporters.

**Rationale:** Keeps the core harness stable and allows multiple external baselines with different environments.

**Alternatives Considered:**
- Vendor/inline upstream code — rejected for license/maintenance complexity.
- Rewrite external outputs directly in Python — rejected when upstream pipelines are complex; adaptation at the artifact boundary is safer.

### Environment and reproducibility

**Decision:** Prefer containerized execution or a pinned environment guide for the external baseline; record tool/version/config in `run_manifest.json`.

**Rationale:** External baselines often require specific OS/CUDA/compiler stacks.

### Dataset conversion boundaries

**Decision:** If an external method expects a different dataset layout, provide a conversion stage that reads the M001 sequence object and writes its expected input, without mutating the core artifact schema or internal contracts.

**Rationale:** Prevents leakage of external layout assumptions into the project’s stable interfaces.

## Error Handling Strategy

- External setup missing: fail fast with a clear message and a link/path to setup instructions.
- External run failure: capture return code, stderr summary, and adapter-stage artifacts; still write `run_manifest.json` and `failure_notes.md`.
- Conversion failures: name the missing inputs or shape mismatches and stop; do not generate partial artifacts that could be mistaken for success.
- Timeouts: terminate the external run with a recorded status and partial diagnostics.

## Risks and Unknowns

- External environment/cuda/toolchain complexity may block integration.
- Dataset conversion correctness can be brittle; conversion and adapter steps need deterministic tests.
- Runtime comparability across different stacks may be noisy; keep scope to basic latency/RTF summaries.
- License restrictions can limit redistribution; avoid bundling weights/binaries.

## Existing Codebase / Prior Art

- M001-ncx5an: package structure, backend contract, CSV/TUM exporters, evaluator, plots, manifests, and failure-visibility rules.
- M002: `event_imu` implementation behind the same backend contract.
- Upstream projects: UltimateSLAM/ESVO documentation for expected inputs/outputs (referenced during adapter design).

## Relevant Requirements

- R014 — Strong external baseline wrapper path.
- R016 — Rich runtime and resource profiling (to a basic extent appropriate for this milestone).
- R017 — Multi-method comparison and robustness reporting.
- R013 — Shared artifact schema across methods (reaffirmed).

## Scope

### In Scope

- One external baseline adapter (UltimateSLAM preferred; ESVO acceptable).
- Optional dataset conversion stage for the adapter without changing core contracts.
- Runtime summaries (latency, approximate real-time factor where supported).
- Aggregated failure-interval reporting across methods.
- Comparative plots for multiple methods.

### Out of Scope / Non-Goals

- Changing project CSV/TUM/metrics/plots/manifest/failure-notes contracts.
- Ensemble/fusion logic.
- RL/PPO.
- Map/orthophoto anchoring.
- Embedded hard real-time deployment.

## Technical Constraints

- Preserve stable artifact and backend contracts from M001/M002.
- Keep adapter execution optional and clearly documented.
- CI remains synthetic-only; no external adapter runs in ordinary CI.

## Integration Points

- External baseline binary/container via adapter.
- MVSEC HDF5 via M001 sequence object and optional conversion stage.
- Existing evaluator/plotting and artifact validation.

## Testing Requirements

- Unit tests for adapter argument building, environment checks, and error reporting.
- Deterministic tests for dataset conversion inputs/outputs (synthetic fixtures).
- Artifact validation tests that confirm adapter outputs meet the unchanged contract.
- Mark external/integration tests separately; do not run in ordinary CI.

## Acceptance Criteria

M003 is complete when:

- One external baseline adapter runs on a documented MVSEC sequence and produces the identical artifact set/schema as existing methods.
- Runtime summaries and failure-interval aggregation are added to reporting without changing artifact contracts.
- Comparative plots across multiple methods are generated.
- Setup instructions/container references exist and the `run_manifest.json` records external tool/version/config.
- External failures are diagnosable through `run.log`, adapter stderr summary, manifest status, and `failure_notes.md`.

## Open Questions

- Which external method integrates more smoothly given environment constraints: UltimateSLAM or ESVO?
- Which dataset conversion is least invasive and best documented by upstream?
- Should we provide a reference container or step-by-step setup only?
- What minimal runtime fields are reliable across external methods (e.g., latency per frame/update, approximate real-time factor)?
