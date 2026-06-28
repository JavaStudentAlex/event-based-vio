"""Synthetic sequence generation pipeline.

Turns the Google Earth Pro drone simulator (or a built-in synthetic frame source)
into a drone-like sensor dataset: raw RGB, ground-truth trajectory, synthetic IMU,
synthetic events, visualizations, calibration, and metadata.

No odometry is implemented here; this only produces clean, synchronized input data
for later baselines (see :func:`nav_benchmark.data.sequence_loader.load_sequence`).
"""
