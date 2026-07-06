# Learned Ensemble: RL-Gated Fusion + JEPA Perception Signals

The learned ensemble keeps the deterministic error-state EKF as the estimator
and adds two learned components on top of the existing deterministic ensemble:

- a **PPO gating policy** (torch) that outputs a per-backend *trust* value in
  `[0, 1]` every control period, learning when to rely on each sensor option —
  `image_imu` (IMU+RGB), `event_imu` (IMU+event), `multimodal_vio`
  (IMU+RGB+event), plus the pure `rgb_vo`/`event_vo` streams;
- a **JEPA-style self-supervised scene model** whose prediction error
  ("surprise") and embedding dynamics feed the policy as perception-quality
  features, with an adapter for embeddings precomputed by large open-source
  pretrained JEPA models.

So the fusion stack is: **EKF** (state estimation) + **RL policy** (trust
gating) + **JEPA** (perception prior) = the `rl_gated` ensemble fusion mode.

## Design guarantees

- **Exact parity fallback.** Trust = 1 for every backend reproduces
  `--fusion weighted_ekf` bit-for-bit (`tests/ensemble/test_rl_gated_core.py`).
  The policy modulates a proven filter; it does not replace it.
- **Hard safety gates stay on.** Health, raw-confidence, timestamp, motion
  sanity, and chi-square gates always apply. A policy cannot force a
  physically inconsistent update into the filter; trust below a floor only
  *excludes* measurements (logged with the explicit reason `policy_gate`).
- **No train/inference skew.** Training episodes and benchmark runs step the
  same `GatedEkfFusionCore` (`src/nav_benchmark/ensemble/rl_gated.py`).
- **Layout-bound checkpoints.** Policy checkpoints embed the observation
  layout (method order, JEPA on/off, control period). Inference validates it
  and refuses mismatched runs instead of silently degrading.
- **Deterministic.** Episodes, perturbations, exploration noise, and minibatch
  order all derive from `--seed`. Benchmark inference uses the deterministic
  policy mode on CPU.

## Training data and rewards

Rewards need ground truth: the per-control-step reward is the reduction of
absolute position error against GT, minus a small trust-jitter penalty (the
return telescopes to initial-minus-final error). Training inputs are generated
synthetic sequence directories or MVSEC HDF5 slices *with GT poses*; inference
needs no GT.

Because the deterministic backends rarely fail on clean data, the trainer
injects **seeded perturbations** into backend measurement streams: dropouts,
noisy bursts, honest bias ramps (confidence drops), and *confident bias* — a
backend that drifts while still reporting high confidence. That last case is
what static confidence weighting cannot handle and the policy must detect from
innovation/agreement features.

## The agentic training harness

`train-rl` supervises its own run (`src/nav_benchmark/rl/train.py`):

1. builds an episode bank (windowed, GT-rebased) and holds out every Nth
   window;
2. on a fixed cadence, evaluates the deterministic policy on clean and
   perturbed held-out windows against the deterministic weighted-EKF baseline
   (all-ones trust) and the best single backend;
3. escalates the perturbation curriculum only after the policy clears an
   improvement bar at the current severity;
4. keeps `policy_best.pt` by held-out improvement, stops early on stagnation,
   and journals every decision to `training_log.jsonl`; the final comparison
   lands in `report.json`.

## Commands

Pretrain JEPA on a sequence (self-supervised, no GT needed):

```bash
PYTHONPATH=src uv run python -m nav_benchmark train-jepa \
  --dataset synthetic --input outputs/route_a \
  --output models/jepa.pt --steps 500 --device auto
```

Train the gating policy (JEPA features optional but recommended):

```bash
PYTHONPATH=src uv run python -m nav_benchmark train-rl \
  --dataset synthetic --input outputs/route_a --input outputs/route_b \
  --output-dir models/rl_gate --jepa models/jepa.pt \
  --window-sec 8 --stride-sec 4 --iterations 60 --device auto
```

Benchmark with the learned ensemble (standard artifact contract plus
`rl_trust_log.csv` and the usual `ensemble_updates.csv`/`rejected_updates.csv`):

```bash
PYTHONPATH=src uv run python -m nav_benchmark run \
  --method ensemble --fusion rl_gated \
  --dataset mvsec --sequence indoor_flying1 --input data/indoor_flying1.h5 \
  --policy models/rl_gate/policy_best.pt --jepa models/jepa.pt \
  --output-root runs --evaluate
```

## Using open-source pretrained JEPA models

Large pretrained JEPA releases (I-JEPA, V-JEPA 2) are hundreds of millions of
parameters; run them **offline** on a GPU node and export per-frame embeddings
to a simple file (HDF5 datasets `/times` (N, seconds) and `/embeddings`
(N, D), or an NPZ with the same keys). Then:

```bash
PYTHONPATH=src uv run python -m nav_benchmark run \
  --method ensemble --fusion rl_gated --policy models/rl_gate/policy_best.pt \
  --jepa-embeddings-rgb embeddings/vjepa_rgb.h5 \
  --dataset mvsec --sequence outdoor_day1 --input data/outdoor_day1.h5
```

Without the paired predictor, surprise is approximated by the cosine change
rate of consecutive embeddings (`src/nav_benchmark/jepa/external.py`). The
built-in JEPA-lite (`train-jepa`) is the default, fully local path.

## Devices

All training accepts `--device auto|cpu|cuda`; `auto` selects CUDA when a GPU
is usable and falls back to CPU. The installed torch build is `+cu130`; if the
future GPU node runs a CUDA 12.x driver, install the matching wheel variant
instead: `uv pip install torch --index-url https://download.pytorch.org/whl/cu126`.
Benchmark inference always runs the policy on CPU for reproducibility.

## File map

| Path | Role |
| --- | --- |
| `src/nav_benchmark/ensemble/rl_gated.py` | Trust-gated EKF fusion core (shared train/inference) |
| `src/nav_benchmark/rl/features.py` | Observation layout (causal, bounded, checkpoint-bound) |
| `src/nav_benchmark/rl/episodes.py` | Backend precomputation, windowing, GT rebase |
| `src/nav_benchmark/rl/perturb.py` | Seeded backend degradations (incl. confident-bias liar) |
| `src/nav_benchmark/rl/env.py` | Episodic environment (reset/step, reward shaping) |
| `src/nav_benchmark/rl/ppo.py` | Torch PPO, sigmoid-squashed Gaussian, checkpoint IO |
| `src/nav_benchmark/rl/train.py` | Agentic training harness (curriculum, eval gates, journal) |
| `src/nav_benchmark/rl/runner.py` | Benchmark inference + trust log export |
| `src/nav_benchmark/jepa/` | JEPA-lite model, signals, trainer, external-embedding adapter |
| `src/nav_benchmark/learn/torch_utils.py` | Device resolution, seeding |
