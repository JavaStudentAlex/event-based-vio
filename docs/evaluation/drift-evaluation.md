# Drift Evaluation and Plotting

This guide documents the S04 evaluation workflow for run artifacts produced by
`nav_benchmark.run`. It is written for benchmark users who need to evaluate a
completed estimator run without reading the evaluator implementation.

The evaluator consumes the fixed project trajectory export contract documented
in [`docs/trajectory/export-contract.md`](../trajectory/export-contract.md). Do
not duplicate or reinterpret that schema in evaluation code or downstream tools;
S04 depends on the fixed columns, including `timestamp`, pose, velocity,
`confidence`, `health`, and `latency_ms`, and preserves those health labels in
its diagnostics and artifact coverage. This supports requirement R003 by making
all evaluated methods use the same exported columns while retaining
machine-readable `OK`, `DEGRADED`, `LOST`, and `INVALID` status information.

## Running Evaluation

Evaluate a specific run directory:

```bash
python -m nav_benchmark.run eval \
  --run-dir runs/20260628_120000_imu_only_outdoor_day1 \
  --ground-truth path/to/outdoor_day1.h5
```

Evaluate the newest eligible run under an output root:

```bash
python -m nav_benchmark.run eval \
  --latest \
  --output-root runs \
  --method imu_only \
  --sequence outdoor_day1 \
  --ground-truth path/to/outdoor_day1.h5
```

Useful synthetic smoke-test invocation:

```bash
python -m nav_benchmark.run eval \
  --run-dir runs/20260628_120000_imu_only_synthetic_seq \
  --ground-truth path/to/generated_sequence
```

When `--ground-truth` names a generated synthetic sequence directory, the
evaluator reads `ground_truth/trajectory.csv` inside that directory. When it
names an MVSEC `.h5` or `.hdf5` file, the evaluator loads MVSEC ground-truth
poses through the dataset loader. When it names a CSV, the evaluator reads the
same project trajectory CSV columns used by estimator outputs.

If `--ground-truth` is omitted, the evaluator attempts to resolve the source
recorded in `run_manifest.json`. For generated synthetic runs this means the
manifest `input` directory is mapped to `ground_truth/trajectory.csv`.

## Alignment and Association Policy

Default evaluation is intentionally deterministic and explicit:

- **Association:** nearest-neighbor timestamp association with
  `--association-tolerance-sec` seconds of tolerance. The default is `0.1`.
- **Alignment:** global SE(3) alignment when `--alignment-policy se3` is used.
  This is the default and aligns the estimated trajectory to associated ground
  truth once before metric calculation.
- **No alignment:** `--alignment-policy none` skips global SE(3) alignment and
  evaluates the estimate in its original frame.
- **Scale:** scale correction is not enabled by the CLI default.
- **Time offset:** no time-offset search is performed. Input timestamps must
  already be in the same time base.
- **Outliers:** no outlier rejection is performed. Invalid, missing, or poor
  estimator output is represented through health coverage and errors rather than
  silently removed after association.

The selected policy is written to `metrics.json` under the `config` block so
that a result can be interpreted without recovering the command line.

## Health Filtering and Coverage

The evaluator separates numeric metric eligibility from observability:

- Rows with health `OK` or `DEGRADED` are eligible for numeric trajectory error
  and drift metrics when their pose values are finite.
- Rows with health `LOST` or `INVALID` are not used for numeric trajectory error
  calculations, but they are counted in coverage and failure diagnostics.
- The original health labels remain visible in the estimator trajectory and are
  summarized in `metrics.json` so missing or invalid poses remain benchmark data
  instead of disappearing from the run.

Coverage fields report how much of the exported estimate could participate in
metric calculation after health and timestamp association constraints.

## Metrics

`metrics.json` is the primary machine-readable output. Successful evaluations
write `status: "OK"` and include:

- `config`: alignment policy, association tolerance, RPE distance, drift-bin
  width, scale-correction setting, time-offset-search setting, and
  outlier-rejection setting.
- `diagnostics`: counts and timestamp ranges for estimate rows, ground-truth
  rows, health labels, associated pose pairs, and coverage.
- `ate`: absolute trajectory error summary after the selected alignment policy.
- `rpe`: relative pose error over `--rpe-delta-m` meters.
- `drift`: final drift, total drift, and per-distance-bin drift summaries using
  `--drift-bin-width-m` meters.
- `runtime`: latency and odometry-frequency summaries derived from exported
  timestamps and `latency_ms`.
- `coverage`: valid, associated, invalid, and failure proportions so consumers
  can distinguish accurate-but-sparse output from complete output.

Metric definitions:

- **ATE:** Euclidean translation error between each associated estimate pose and
  the aligned ground-truth pose at the same associated timestamp.
- **RPE:** relative translation error over the configured distance delta,
  measuring local drift rather than global offset.
- **Final drift:** translation error at the final associated pose.
- **Total drift:** accumulated drift over the associated trajectory.
- **Drift bins:** drift summarized over fixed traveled-distance bins, defaulting
  to 20 meters per bin for slice-level benchmark comparability.

## Artifact Outputs

Evaluation writes the following files into the run directory:

| Artifact | Meaning |
|---|---|
| `metrics.json` | Status, config, diagnostics, summary metrics, coverage, and runtime statistics. |
| `error_vs_time.csv` | Per-estimate-timestamp time series preserving health labels and associated translational error when available. |
| `error_vs_distance.csv` | Per-associated-sample distance series used by drift plots and bin summaries. |
| `ground_truth_aligned.csv` | Associated ground truth after the selected alignment policy, exported in project trajectory format for inspection. |
| `trajectory_plot.png` / `trajectory_plot.svg` | XY trajectory comparison between estimate and aligned ground truth. |
| `drift_plot.png` / `drift_plot.svg` | Drift/error over traveled distance. |

### Error CSV Columns

`error_vs_time.csv` provides one row for every exported estimate timestamp. Rows
that were associated to ground truth include aligned ground-truth coordinates,
XYZ error, error magnitude, and association residual; rows that were not eligible
or not associated keep those fields blank while preserving the estimate position
and health label. Columns are:

```text
timestamp,est_x,est_y,est_z,gt_aligned_x,gt_aligned_y,gt_aligned_z,error_x,error_y,error_z,error_magnitude,health,association_residual
```

`error_vs_distance.csv` provides one row per associated OK/DEGRADED pose pair
and includes the traveled-distance coordinate plus drift/error fields. Use it
when comparing fixed-distance drift behavior across methods or sequences.
Columns are:

```text
cumulative_distance,error_magnitude,health,association_residual,bin_start,bin_end
```

Both CSVs are deterministic for a fixed input run directory, ground truth,
alignment policy, association tolerance, and drift/RPE configuration.

## Failure Behavior

The eval command is designed to fail loudly while still leaving inspectable
artifacts:

- Missing `estimated_trajectory.csv`, missing ground truth, malformed CSV
  schemas, invalid timestamps, empty eligible pose sets, insufficient associated
  pairs, and degenerate SE(3) alignment inputs produce nonzero CLI exits.
- On failure, `metrics.json` is still written with `status: "failed"`, `reason`,
  and `error_message` fields.
- CSV outputs are initialized with headers when possible so downstream tooling
  can distinguish “evaluation failed before rows existed” from “no file was
  produced”.
- Plot files are only meaningful when evaluation succeeds; missing plots should
  be interpreted through the failure fields in `metrics.json` first.

## Dataset-Dependent Checks

Synthetic tests verify the artifact contract without downloading MVSEC. The
following checks remain dataset-dependent and should be performed when MVSEC data
is available:

- Load `outdoor_day1` or the selected MVSEC sequence and verify ground-truth pose
  extraction from the HDF5 file.
- Confirm sequence-specific timestamps share a time base with estimator outputs;
  the evaluator does not perform time-offset search.
- Compare trajectory and drift plots against known sequence geometry for obvious
  frame or axis mistakes.
- Confirm runtime and coverage statistics are plausible for the selected sensor
  rate and method.

## Failure Modes

- **Filesystem dependency:** the evaluator reads `estimated_trajectory.csv`,
  `run_manifest.json`, optional ground-truth CSVs, synthetic sequence
  directories, and MVSEC HDF5 files, and writes artifacts into the run directory.
  Missing files, malformed schemas, and unwritable output paths surface as
  nonzero eval failures with `metrics.json` failure diagnostics when the run
  directory can be written.
- **Dataset parser dependency:** synthetic CSV and MVSEC HDF5 loaders can reject
  missing streams, incompatible layouts, or malformed numeric values. These
  errors intentionally bubble to the eval command and are recorded in the
  failure status path rather than being silently converted to partial metrics.
- **Numerical dependency:** SE(3) alignment can fail for insufficient or
  degenerate associated pose geometry. The evaluator reports this as an
  evaluation failure; users can inspect the config block and retry with
  `--alignment-policy none` only when that policy is valid for the benchmark.
- **Subprocess dependency for users:** verification commands run through `uv`,
  Ruff, and pytest. Missing toolchain dependencies fail before artifact claims
  and are not masked by documentation.

## Load Profile

Evaluation is an offline batch workflow. The resource that saturates first at
10x expected load is memory for in-process trajectory arrays and plotting data,
followed by CPU for nearest-neighbor association, metric calculation, and PNG/SVG
rendering. The current protection is deterministic single-run processing: the
CLI evaluates one run directory at a time, writes bounded summary metrics plus
CSV series, and exposes `--latest`, `--method`, and `--sequence` filters to avoid
accidental bulk evaluation. There is no server, request pool, pagination layer,
or rate limiter in this task.

## Negative Tests

Synthetic tests protect the meaningful negative surface for this documentation
contract:

- `tests/cli/test_eval_cli_synthetic.py` covers successful CLI artifact writing
  and failure diagnostics for missing, malformed, mismatched, or insufficient
  evaluation inputs.
- `tests/evaluation/test_eval_artifact_contract_synthetic.py` covers the
  required artifact contract, including `metrics.json`, error-series CSVs,
  aligned ground-truth export, and plot outputs.
- `tests/evaluation/test_metrics_synthetic.py` covers deterministic metric math,
  association, coverage, health filtering, and edge conditions such as invalid
  poses or insufficient associated samples.
- `tests/evaluation/test_plots_synthetic.py` covers plot generation and plotting
  precondition failures using synthetic trajectories.

## Observability Impact

S04 makes evaluation observable by meaning, not only by file presence. The
config and diagnostics blocks explain how a run was evaluated, the error-series
CSVs show where drift happened, `ground_truth_aligned.csv` makes the alignment
inspectable, and failure-mode fields give downstream agents enough information
to diagnose missing data, mismatched timestamps, malformed inputs, or degenerate
alignment without reading Python internals.
