# Notebooks — hexacopter (MVSEC `indoor_flying1`) walkthroughs

These notebooks showcase the project's odometry **algorithms** and **ensembles**
on the "hexacopter" part of the dataset: MVSEC's `indoor_flying` sequences were
recorded with a DAVIS346 event-camera + IMU + grayscale rig flown on a
hexacopter, with motion-capture ground truth. We use a 15-second slice
(5 s → 20 s) of `indoor_flying1`.

They call the **same code the CLI runs** (`python -m nav_benchmark …`) — the
loader, the six backends, the fusion functions, and the evaluator — so the
numbers match a real benchmark run.

| Notebook | What it shows |
| --- | --- |
| [`01_explore_hexacopter_dataset.ipynb`](01_explore_hexacopter_dataset.ipynb) | The four sensor streams: IMU, events (edge frames + time surface), grayscale APS frames, and the ground-truth flight path. |
| [`02_odometry_baselines_hexacopter.ipynb`](02_odometry_baselines_hexacopter.ipynb) | Runs all six baselines (`imu_only`, `rgb_vo`, `event_vo`, `event_imu`, `image_imu`, `multimodal_vio`), scores each against ground truth (ATE/RPE/drift/failures/latency), and plots estimated paths + drift-over-distance. |
| [`03_ensembles_hexacopter.ipynb`](03_ensembles_hexacopter.ipynb) | The fusion layer: `confidence_weighted`, `weighted_ekf` (with gate accept/reject analysis), `winner_takes_healthy`, a head-to-head vs. the best baseline, and how to invoke the learned `rl_gated` ensemble. |
| [`04_ensemble_merging_explained.ipynb`](04_ensemble_merging_explained.ipynb) | Deep-dive on **how the mergers combine the backends**: the blend-weight recipe, the EKF gate cascade + confidence→σ, and the RL trust gate (drives the fusion core directly, proves the trust≡1 parity, demos the confident-bias case). JEPA is summarized here and detailed in notebook 05. |
| [`05_jepa_perception.ipynb`](05_jepa_perception.ipynb) | Standalone **JEPA** deep-dive: builds JEPA-lite end to end (frames → patches → IMU ego-motion conditioning → self-supervised training → `surprise`/`embedding_speed` signals), shows how the signals feed the RL policy, and exercises the pretrained-embedding (I-JEPA/V-JEPA) adapter path. |

> **All five notebooks are committed already executed, with every output saved
> inline.** Each was run once, top to bottom, on the `indoor_flying1_5s20s_img.h5`
> slice — 20 figures, 6 tables, every `print`, **0 errors**, execution counts in
> clean `1…N` order. So the plots, metric tables and printed values render
> straight from the `.ipynb` files: you can read the complete results **without a
> running kernel or even the dataset**. Re-running is optional (see *Running*
> below); a *Restart & Run All* would recompute against your local data.

## Prerequisites

**Environment** (from the repo root):

```bash
uv sync --group dev
```

**Data.** The notebooks look for a converted HDF5 slice under `data/`, preferring
the image-inclusive one and falling back to events + IMU only:

1. `data/indoor_flying1_5s20s_img.h5`  *(events + IMU + grayscale + GT — enables all six baselines)*
2. `data/indoor_flying1_5s20s.h5`  *(events + IMU + GT — image-based methods are skipped)*

`data/` is git-ignored, so these files are local. To (re)generate the
image-inclusive slice from the MVSEC bags (see the root `README.md` for the
download helper):

```bash
uv run python scripts/convert_mvsec_bag_to_h5.py \
    --data-bag data/indoor_flying1_data.bag \
    --gt-bag   data/indoor_flying1_gt.bag \
    --output   data/indoor_flying1_5s20s_img.h5 \
    --start-sec 5 --duration-sec 15 --include-images
```

## Running

```bash
uv run jupyter lab            # then open a notebook, or:
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/02_odometry_baselines_hexacopter.ipynb
```

Notebooks 02 and 03 run all six backends over the slice (~30–40 s on CPU) before
plotting.

## Notes

- **Honest results.** This is real, un-tuned MVSEC data. The GT-scaled feature-VO
  baselines track best on this clean slice; open-loop `imu_only` drifts tens of
  metres; the IMU-fused variants and the deterministic ensembles do **not** beat
  the best single baseline here. The notebooks report this plainly — faithful
  benchmarking is the project's contract (see `AGENTS.md`).
- **Learned ensemble.** `rl_gated` needs a trained PPO policy; training campaigns
  (GPU) are deferred, so notebook 03 shows the commands and runs the policy only
  if a checkpoint is present. See `docs/rl-ensemble.md`.
- **Tooling.** `notebooks/` is excluded from the repo's lint/type/test gates
  (ruff, mypy, bandit, coverage, mutmut, pre-commit, CI), so committed notebook
  outputs don't trip the checks. Keep rendered outputs modest.

