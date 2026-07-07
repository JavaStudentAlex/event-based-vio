# S03 Context Draft — Interview Notes

## Confirmed Decisions

1. **ATE assertion:** Strict less-than (`event_imu.ate_rmse < imu_only.ate_rmse`), no percentage margin. Synthetic sequence designed so gap is unambiguous.
2. **Evaluation pipeline:** Full end-to-end: backend.run → export → evaluate → compare_runs → write_comparison_artifacts. No shortcuts or mocking.
3. **Comparison artifact depth:** Existence + non-empty checks only (metrics_comparison.json, comparison_table.csv, plot). No deep schema validation.
4. **Synthetic sequence design:** Event-rich motion pattern with clear drift advantage for event_imu. IMU has realistic noise; events encode clean displacement signal. Large deterministic ATE gap.
5. **Scope:** Test-only (pytest). No CLI changes, no new subcommands, no scripts.
6. **image_imu role:** Included in comparison pipeline, artifacts checked for existence, no ATE assertion. Present for completeness and 3-method comparison table.

## Open Questions
- Test file location (tests/test_benchmark_comparison.py?)
- Whether S03 fixture can be shared with S02 or needs its own
- Ground truth alignment policy (reuse D006 global SE3?)
