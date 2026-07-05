# External Baseline Adapters

Strong external Event/IMU baselines (UltimateSLAM preferred, ESVO as the
fallback) are integrated at the artifact boundary: the external tool runs in
its own environment, produces a trajectory file, and the adapter normalizes
that file into the project's backend contract. Core exporters, the evaluator,
and the artifact schema are never modified by an adapter.

## Two integration modes

### A. Import an offline result

Run the tool however its upstream documentation prescribes (container, ROS
workspace, another machine), export its trajectory as TUM (`t x y z qx qy qz qw`)
or project CSV, then import it:

```bash
python -m nav_benchmark.run run --method external --dataset mvsec \
  --sequence outdoor_day1 --input data/outdoor_day1.h5 \
  --external-trajectory results/ultimateslam_outdoor_day1.tum
```

### B. Run the tool as a subprocess

When the tool (or a wrapper script for it) is invocable locally, let the
benchmark run it, capture its exit status/stderr, and record tool version and
timing in `run_manifest.json`:

```bash
python -m nav_benchmark.run run --method external --dataset mvsec \
  --sequence outdoor_day1 --input data/outdoor_day1.h5 \
  --external-command "./wrappers/run_ultimateslam.sh data/converted/outdoor_day1 /tmp/us.tum" \
  --external-trajectory /tmp/us.tum \
  --external-tool-name ultimateslam \
  --external-version-command "./wrappers/run_ultimateslam.sh --version" \
  --external-timeout-sec 7200
```

Behavior:

- The command runs via subprocess (shell-style quoting, `--external-workdir`
  optional) with a timeout (default 3600 s).
- On success, the trajectory written to `--external-trajectory` flows through
  the same export → evaluation → validation pipeline as native methods.
- `run_manifest.json → config.execution` records the command, tool name,
  version (first line of `--external-version-command` output), return code,
  duration, and stdout/stderr tails.
- On failure (missing binary, non-zero exit, timeout, missing output file) the
  run directory still gets `run_manifest.json` with `status: "failed"`, an
  `external_execution` record with the stderr tail, `failure_notes.md`, and
  `run.log` — external failures stay diagnosable, and no partial trajectory
  artifacts are produced.

## Dataset conversion

If the external tool cannot read MVSEC HDF5 directly, export the sequence
streams to a plain layout and re-pack from there in your wrapper:

```bash
python -m nav_benchmark.run convert --dataset mvsec --sequence outdoor_day1 \
  --input data/outdoor_day1.h5 --output-dir data/converted/outdoor_day1
```

Layout (streams the sequence lacks are omitted; `conversion_manifest.json`
records what was written, with times in seconds and quaternions as xyzw):

```text
events.csv              t,x,y,p
imu.csv                 t,ax,ay,az,gx,gy,gz
ground_truth.csv        t,x,y,z,qx,qy,qz,qw
images/frame_NNNNNN.png
image_timestamps.csv    frame_id,t,path
conversion_manifest.json
```

For tools that want the original rosbags (UltimateSLAM and ESVO both consume
MVSEC's bag distribution directly), skip conversion and point the wrapper at
`data/<sequence>_data.bag` — that is the least invasive path.

## Tool setup notes

Neither tool is bundled; both need their own environment. CI never runs
external adapters (`tests` use stub subprocess commands only).

### UltimateSLAM (preferred)

- Upstream: <https://github.com/uzh-rpg/rpg_ultimate_slam_open>. ROS1
  (Noetic/Melodic) catkin workspace; build per upstream instructions, ideally
  inside a container so the version is pinned.
- It consumes events + IMU (+ optional frames) from rosbags and publishes a
  pose track; record/export it and convert to TUM (`evo_traj` or a small
  script) for `--external-trajectory`.
- Wrap the launch + export in one script so `--external-command` is a single
  reproducible entry point, and give the same script a `--version` flag (e.g.
  print the git SHA of the workspace) for `--external-version-command`.

### ESVO (fallback)

- Upstream: <https://github.com/HKUST-Aerial-Robotics/ESVO> — stereo
  event-based VO, also ROS1, also consumes MVSEC bags.
- Same wrapper pattern: launch, record the pose topic, export TUM, exit
  non-zero on tracking failure so the adapter records it.

## Verifying the adapter without the external tool

The adapter path itself is exercised in CI with stub commands
(`tests/baselines/test_external_tool.py`). To smoke-test locally end to end,
any command that writes a TUM file works, e.g.:

```bash
python -m nav_benchmark.run run --method external --dataset synthetic \
  --sequence adapter_smoke \
  --external-command "python -c \"open('/tmp/fake.tum','w').write('0 0 0 0 0 0 0 1\n1 1 0 0 0 0 0 1\n')\"" \
  --external-trajectory /tmp/fake.tum --external-tool-name fake_tool
```
