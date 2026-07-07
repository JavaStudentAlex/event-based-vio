# S02 Context Draft — Interview Notes

## Confirmed Decisions

1. **Structural identity scope:** Core file set (trajectory.csv, tum.txt, run_manifest.json, run.log) + CSV column name and order match. Method-specific diagnostics in manifests are allowed to differ.
2. **Optional artifacts:** Only mandatory artifacts must match. Extra files (failure_notes.md, diagnostic plots) are ignored.
3. **Synthetic sequence:** Single minimal deterministic fixture (5–10 timestamps) with IMU, events, and grayscale data, shared across all three backends.
4. **Row count policy:** Columns + non-empty, row counts may differ across methods.
5. **Validation approach:** Re-use validate_run_directory(expect_eval=False) on each method's output; all three must pass.
6. **Evaluation scope:** Run-phase artifacts only. Evaluation artifacts (metrics.json, plots, error CSVs) are S03's concern.

## Open Questions
- Health label handling across methods (are all health values valid across all backends?)
- Whether the test should check run_manifest.json is valid JSON beyond existence
