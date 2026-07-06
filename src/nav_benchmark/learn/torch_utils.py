"""Device resolution and deterministic seeding for the torch-based components.

The benchmark contract requires reproducible runs: inference always happens on
CPU with seeded weights, while training may use CUDA when a GPU node is
available (``--device auto``). CUDA kernels are not bit-deterministic across
hardware, so checkpoints record enough metadata for CPU re-evaluation.
"""

import torch


def resolve_device(device: str = "auto") -> torch.device:
    """Map a CLI device string to a torch device, validating CUDA availability."""
    if device == "auto":
        return torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    resolved = torch.device(device)
    if resolved.type == "cuda" and not torch.cuda.is_available():
        raise ValueError("CUDA was requested but no usable GPU is available; use --device cpu or auto")
    return resolved


def seed_torch(seed: int) -> None:
    """Seed torch RNGs (CPU and, when present, CUDA) for reproducible runs."""
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def module_parameter_count(module: torch.nn.Module) -> int:
    return sum(int(p.numel()) for p in module.parameters())
