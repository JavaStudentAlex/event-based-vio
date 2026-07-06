"""JEPA-lite: joint-embedding predictive architecture over frame patches (torch).

An online patch encoder produces frame embeddings; an EMA target encoder
provides stable prediction targets; a predictor conditioned on IMU-derived
ego-motion maps the current embedding to the next frame's target embedding.
Training minimises cosine distance between prediction and target plus a
variance hinge that prevents representation collapse (VICReg-style). The
prediction error at inference is the "surprise" signal consumed by the RL
gating policy.
"""

import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import torch
from torch import nn

from nav_benchmark.jepa.frames import EGO_DIM, NUM_PATCHES, PATCH_DIM
from nav_benchmark.learn.torch_utils import resolve_device

CHECKPOINT_VERSION = 1


@dataclass
class JepaConfig:
    """Architecture and optimisation settings for the JEPA-lite model."""

    patch_dim: int = PATCH_DIM
    num_patches: int = NUM_PATCHES
    ego_dim: int = EGO_DIM
    embed_dim: int = 32
    hidden_dim: int = 64
    ema_tau: float = 0.995
    lr: float = 1e-3
    batch_size: int = 32
    steps: int = 300
    variance_floor: float = 0.5
    variance_coef: float = 1.0
    seed: int = 0


class _PatchEncoder(nn.Module):
    """Per-patch MLP followed by mean pooling into one frame embedding."""

    def __init__(self, config: JepaConfig) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(config.patch_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.embed_dim),
        )

    def forward(self, patches: torch.Tensor) -> torch.Tensor:
        return self.net(patches).mean(dim=-2)


class _Predictor(nn.Module):
    """Predicts the next frame's target embedding from (embedding, ego-motion)."""

    def __init__(self, config: JepaConfig) -> None:
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(config.embed_dim + config.ego_dim, config.hidden_dim),
            nn.GELU(),
            nn.Linear(config.hidden_dim, config.embed_dim),
        )

    def forward(self, embedding: torch.Tensor, ego: torch.Tensor) -> torch.Tensor:
        return self.net(torch.cat([embedding, ego], dim=-1))


def _cosine_distance(a: torch.Tensor, b: torch.Tensor) -> torch.Tensor:
    return 1.0 - nn.functional.cosine_similarity(a, b, dim=-1)


class JepaModel(nn.Module):
    """Online encoder, EMA target encoder, and ego-conditioned predictor."""

    def __init__(self, config: JepaConfig) -> None:
        super().__init__()
        self.config = config
        torch.manual_seed(config.seed)
        self.encoder = _PatchEncoder(config)
        self.target_encoder = _PatchEncoder(config)
        self.predictor = _Predictor(config)
        self.target_encoder.load_state_dict(self.encoder.state_dict())
        for parameter in self.target_encoder.parameters():
            parameter.requires_grad_(False)

    @torch.no_grad()
    def update_target(self) -> None:
        tau = self.config.ema_tau
        for online, target in zip(self.encoder.parameters(), self.target_encoder.parameters(), strict=True):
            target.mul_(tau).add_(online, alpha=1.0 - tau)

    @torch.no_grad()
    def embed(self, patches: torch.Tensor) -> torch.Tensor:
        """Stable (target-encoder) frame embeddings for inference features."""
        return self.target_encoder(patches)

    def training_loss(self, patches_now: torch.Tensor, patches_next: torch.Tensor, ego: torch.Tensor) -> torch.Tensor:
        context = self.encoder(patches_now)
        with torch.no_grad():
            target = self.target_encoder(patches_next)
        predicted = self.predictor(context, ego)
        prediction_loss = _cosine_distance(predicted, target).mean()
        std = context.std(dim=0)
        variance_loss = torch.clamp(self.config.variance_floor - std, min=0.0).pow(2).mean()
        return prediction_loss + self.config.variance_coef * variance_loss

    def save(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": CHECKPOINT_VERSION,
            "config": asdict(self.config),
            "state": {key: tensor.cpu() for key, tensor in self.state_dict().items()},
        }
        torch.save(payload, path)

    @staticmethod
    def load(path: str | Path, *, device: str = "cpu") -> "JepaModel":
        payload = torch.load(Path(path), map_location="cpu", weights_only=True)
        if payload.get("version") != CHECKPOINT_VERSION:
            raise ValueError(f"Unsupported JEPA checkpoint version: {payload.get('version')!r}")
        model = JepaModel(JepaConfig(**payload["config"]))
        model.load_state_dict(payload["state"])
        model.to(resolve_device(device))
        model.eval()
        return model


def build_pair_dataset(segments: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Assemble (now, next, ego) pair arrays from contiguous (patches, ego) segments.

    Pairs never cross segment boundaries, so multiple streams and sequences can
    be mixed into one training set safely.
    """
    now_parts: list[np.ndarray] = []
    next_parts: list[np.ndarray] = []
    ego_parts: list[np.ndarray] = []
    for patches, ego in segments:
        if len(patches) < 2:
            continue
        if len(ego) != len(patches) - 1:
            raise ValueError("Ego-motion feature count must be frame count - 1 per segment")
        now_parts.append(patches[:-1])
        next_parts.append(patches[1:])
        ego_parts.append(ego)
    if not now_parts:
        raise ValueError("JEPA training needs at least one segment with two or more frames")
    return (
        np.concatenate(now_parts, axis=0),
        np.concatenate(next_parts, axis=0),
        np.concatenate(ego_parts, axis=0),
    )


def train_jepa(
    model: JepaModel,
    patches_now: np.ndarray,
    patches_next: np.ndarray,
    ego: np.ndarray,
    *,
    device: str = "cpu",
    log=None,
) -> list[float]:
    """Self-supervised training over frame pairs; returns the loss history."""
    if len(patches_now) == 0 or len(patches_now) != len(patches_next) or len(patches_now) != len(ego):
        raise ValueError("Pair arrays must be non-empty and of equal length")
    config = model.config
    resolved = resolve_device(device)
    model.to(resolved)
    model.train()
    now_tensor = torch.as_tensor(patches_now, dtype=torch.float32, device=resolved)
    next_tensor = torch.as_tensor(patches_next, dtype=torch.float32, device=resolved)
    ego_tensor = torch.as_tensor(ego, dtype=torch.float32, device=resolved)
    optimizer = torch.optim.Adam([p for p in model.parameters() if p.requires_grad], lr=config.lr)
    rng = np.random.Generator(np.random.PCG64(config.seed))
    pair_count = len(patches_now)

    history: list[float] = []
    for step in range(config.steps):
        indices = rng.integers(0, pair_count, size=min(config.batch_size, pair_count))
        idx = torch.as_tensor(np.asarray(indices), dtype=torch.long, device=resolved)
        loss = model.training_loss(now_tensor[idx], next_tensor[idx], ego_tensor[idx])
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        model.update_target()
        history.append(float(loss.item()))
        if log is not None and (step + 1) % max(config.steps // 10, 1) == 0:
            recent = history[-max(config.steps // 10, 1) :]
            log(f"JEPA step {step + 1}/{config.steps}: loss {sum(recent) / len(recent):.4f}")
    model.eval()
    return history


@torch.no_grad()
def surprise_scores(model: JepaModel, patches: np.ndarray, ego: np.ndarray, *, device: str = "cpu") -> np.ndarray:
    """Per-frame prediction error aligned to frames: index k = error predicting frame k.

    The first frame has no prediction, so its surprise is 0.
    """
    resolved = resolve_device(device)
    model.to(resolved)
    model.eval()
    count = len(patches)
    scores = np.zeros(count, dtype=np.float64)
    if count < 2:
        return scores
    patches_tensor = torch.as_tensor(patches, dtype=torch.float32, device=resolved)
    ego_tensor = torch.as_tensor(ego, dtype=torch.float32, device=resolved)
    context = model.embed(patches_tensor[:-1])
    target = model.embed(patches_tensor[1:])
    predicted = model.predictor(context, ego_tensor)
    scores[1:] = _cosine_distance(predicted, target).cpu().numpy().astype(np.float64)
    return scores


@torch.no_grad()
def embedding_speeds(model: JepaModel, patches: np.ndarray, *, device: str = "cpu") -> np.ndarray:
    """L2 step size of consecutive frame embeddings (first frame is 0)."""
    resolved = resolve_device(device)
    model.to(resolved)
    model.eval()
    count = len(patches)
    speeds = np.zeros(count, dtype=np.float64)
    if count < 2:
        return speeds
    embeddings = model.embed(torch.as_tensor(patches, dtype=torch.float32, device=resolved))
    deltas = embeddings[1:] - embeddings[:-1]
    scale = math.sqrt(model.config.embed_dim)
    speeds[1:] = (torch.linalg.norm(deltas, dim=-1) / scale).cpu().numpy().astype(np.float64)
    return speeds
