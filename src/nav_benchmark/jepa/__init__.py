"""JEPA-style self-supervised scene representation for the learned ensemble.

A small joint-embedding predictive architecture (context encoder, EMA target
encoder, ego-motion-conditioned predictor) is trained on a sequence's RGB and
event frames. Its prediction error ("surprise") and embedding dynamics feed
the RL gating policy as perception-quality signals. Precomputed embeddings
from large open-source pretrained JEPA models (e.g. V-JEPA) can be plugged in
through :mod:`nav_benchmark.jepa.external` without importing their code.
"""
