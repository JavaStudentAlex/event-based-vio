---
id: S06
milestone: M001-ncx5an
status: ready
---

# S06: Remediate validation string mismatch and run validation verification — Context

<!-- Slice-scoped context. Milestone-only sections (acceptance criteria, completion class,
     milestone sequence) do not belong here — those live in the milestone context. -->

## Goal

Fix the validation string mismatch so the `validate` subcommand succeeds on a synthetic M001 run after evaluation, without weakening the benchmark artifact contract.

## Why this Slice

S06 exists because S05 added validation coverage but left a user-visible mismatch that prevents validation from cleanly confirming an otherwise complete run. This slice is the final M001 closure step: it unblocks treating the benchmark artifact set as self-verifying and gives M002 a reusable validation gate for future `event_imu` outputs.

## Scope

### In Scope

- Remediate the known validation string mismatch by aligning producer and consumer behavior to one canonical string representation.
- Keep validation strict after canonicalization; new outputs should use the canonical string rather than relying on broad fuzzy matching.
- Preserve the existing `validate` subcommand contract: success returns exit code 0 and failure returns nonzero.
- Make successful validation feel quiet and trustworthy: a concise pass summary is preferred over noisy artifact-by-artifact output.
- Verify the fix using a synthetic `run → eval → validate` path, proving the validate subcommand passes successfully without requiring MVSEC downloads.
- Add or adjust regression coverage only as needed to prevent the mismatch from returning.

### Out of Scope

- Accepting a broad set of legacy or informal aliases for validation strings.
- Redesigning the validation framework, CLI UX, artifact schema, or run directory layout.
- Introducing learned backends, Event+IMU behavior, ensemble logic, map anchoring, or other M002/M003 work.
- Requiring real MVSEC datasets or manual full-dataset execution for ordinary completion proof.
- Turning validation output into a verbose checklist unless explicitly requested later.

## Constraints

- M001 remains a deterministic, synthetic-CI-friendly benchmark foundation; no ordinary verification step may require large MVSEC downloads.
- Existing fixed artifact contracts from S02-S05 remain authoritative, including project CSV schema, TUM export expectations, metrics artifacts, manifest, logs, and always-present `failure_notes.md`.
- Invalid, degraded, lost, and missing intervals must remain visible benchmark data and must not be hidden by the remediation.
- The validation fix should be narrow: canonical strict strings are preferred over compatibility aliases or speculative schema expansion.
- The proof target is the complete synthetic `run → eval → validate` path, because the user priority is that the validate subcommand passes successfully in normal usage.

## Integration Points

### Consumes

- `src/nav_benchmark/validation.py` — Existing artifact validator and likely location of the strict string comparison that currently mismatches produced artifacts.
- `src/nav_benchmark/run.py` — CLI wiring for `run`, `eval`, and `validate`, including validate exit behavior and concise terminal reporting.
- M001 synthetic fixture/run path — Used to create a complete run directory without requiring MVSEC data.
- Existing S03-S05 artifacts — `estimated_trajectory.csv`, `estimated_trajectory_tum.txt`, `ground_truth_aligned.csv`, `metrics.json`, `error_vs_time.csv`, `error_vs_distance.csv`, plots, `run_manifest.json`, `failure_notes.md`, and `run.log` must remain valid under validation.

### Produces

- Canonicalized validation string behavior — Producer and validator agree on the same string value, eliminating the mismatch error.
- Passing validation proof — A synthetic `run → eval → validate` execution exits successfully and demonstrates the full M001 artifact set is accepted.
- Regression coverage or targeted test adjustment — Prevents the same mismatch from reappearing while preserving strict validation.

## Open Questions

- Which exact string pair is mismatched — Current thinking: identify the failing expected-versus-actual value during implementation and fix the canonical source of truth rather than adding broad aliases.
- Whether a targeted regression test is needed in addition to the synthetic full-path proof — Current thinking: add or adjust a narrow test if the mismatch is easy to isolate, but do not expand S06 into a broad validation rewrite.
