# GSD Plan: MVSEC-Based Ensemble for GPS-Denied Visual-Inertial Navigation

## 1. Project Goal

The goal is to implement and benchmark an ensemble navigation pipeline for GPS-denied drone flight using:

- IMU
- grayscale/RGB-like camera frames
- event camera stream
- optional map anchoring later

The system should estimate the drone's relative trajectory in real time and keep drift bounded. The final ensemble should be compared against individual baselines, not only against IMU-only odometry.

The challenge target is event-camera + IMU odometry for GPS-denied navigation, with optional absolute correction by matching accumulated event edges to an orthophoto or satellite map.

---

## 2. Dataset Choice

### Selected first dataset

**MVSEC** will be used as the first benchmark dataset.

MVSEC is suitable because it contains the main sensor types needed for the first version of the ensemble:

- event camera data
- grayscale image frames
- IMU measurements
- ground-truth trajectory

For our purposes, the grayscale image frames can be treated as the image input for RGB-IMU visual-inertial baselines, because most VIO methods work with grayscale images.

### First sequence

Start with one sequence only, for example:

```text
MVSEC outdoor_day1
```

or, if we want an easier first debugging sequence:

```text
MVSEC indoor_flying1
```

Recommended first sequence:

```text
MVSEC outdoor_day1
```

Reason: it is more relevant to the outdoor drone-navigation scenario.

---

## 3. Milestone 0: Benchmark Contract

Milestone 0 does **not** implement the navigation algorithm yet.

It defines the rules that all future baselines and ensemble methods must follow.

### Milestone 0 output

At the end of Milestone 0, we should have:

1. Selected dataset and sequence
2. Selected sensor streams
3. Selected baselines
4. Selected metrics
5. Common output format for every method
6. Evaluation protocol

This becomes the fixed benchmark contract used in all later milestones.

---

## 4. Sensor Streams Used

For the first implementation, use the following MVSEC streams:

```text
IMU measurements
Event camera stream
Grayscale image frames
Ground-truth poses
```

The system should support the following sensor combinations:

```text
IMU only
Image + IMU
Event camera + IMU
Image + event camera + IMU
```

---

## 5. Baselines to Include

The ensemble must be compared against individual methods. The goal is to show that fusion improves robustness and/or drift compared with the best single branch.

### B0: IMU-only baseline

**Sensors:**

```text
IMU only
```

**Purpose:**

This is the weakest baseline. It shows how fast pure inertial dead reckoning drifts without visual correction.

**Expected output:**

```text
pose trajectory
velocity estimate
orientation estimate
optional covariance
```

---

### B1: RGB/grayscale + IMU baseline

**Sensors:**

```text
grayscale image frames + IMU
```

**Main baselines:**

```text
OpenVINS
VINS-Mono
```

**Optional baseline:**

```text
ORB-SLAM3 mono-inertial
```

**Purpose:**

This branch shows how normal visual-inertial odometry performs without using events.

---

### B2: Event camera + IMU baseline

**Sensors:**

```text
event camera + IMU
```

**Candidate baselines:**

```text
EVIO / event-based VIO
DEIO, if practical
UltimateSLAM event+IMU ablation, if practical
```

**Reference-only baselines:**

```text
ESVO
ESVIO
ESVO2
```

Important note: ESVO, ESVIO, and ESVO2 are mainly useful if we have stereo event data. If our first setup uses a single event camera branch, these should be treated as reference baselines rather than the first implementation target.

**Purpose:**

This branch should be stronger than image-only VIO in conditions such as:

```text
fast motion
motion blur
low light
high dynamic range
```

---

### B3: Image + event camera + IMU multimodal baseline

**Sensors:**

```text
grayscale/image frames + event camera + IMU
```

**Main baseline:**

```text
UltimateSLAM
```

**Optional baseline:**

```text
PL-EVIO
```

**Purpose:**

This is the strongest direct multimodal baseline. It uses all available onboard sensing modalities before we add our own ensemble fusion layer.

---

### B4: Final ensemble

**Sensors:**

```text
IMU + image frames + event camera
```

**Inputs to the ensemble:**

```text
IMU-only propagation
RGB/grayscale + IMU VIO output
Event + IMU VIO output
UltimateSLAM / multimodal VIO output
method confidence and health scores
```

**Purpose:**

The ensemble should combine the strengths of all branches and reject branches that become unreliable.

The ensemble should beat the best single baseline in at least one important dimension:

```text
lower drift
lower ATE
lower RPE
fewer tracking failures
better recovery after failure
better robustness across different conditions
```

---

## 6. Metrics

The same metrics must be used for every baseline and for the final ensemble.

### Core trajectory metrics

```text
ATE: Absolute Trajectory Error
RPE: Relative Pose Error
drift per meter travelled
total drift after full sequence
position error every 20 meters
orientation error
```

### Robustness metrics

```text
number of tracking failures
time until failure
recovery after failure
number of invalid poses
outlier rate
```

### Runtime metrics

```text
latency per update, in ms
odometry frequency, in Hz
CPU usage
GPU usage
RAM usage
```

### Most important metrics for the first demo

```text
ATE
RPE
drift every 20 m
total drift
tracking failure rate
latency
```

---

## 7. Common Output Format

Every method must export its result in the same format so that the evaluator and ensemble can consume all outputs consistently.

Recommended CSV format:

```text
timestamp,method,x,y,z,qx,qy,qz,qw,vx,vy,vz,confidence,health,latency_ms
```

Where:

```text
timestamp    time in seconds
method       name of the method, e.g. imu_only, openvins, event_vio, ultimate_slam, ensemble
x,y,z        estimated position
qx,qy,qz,qw  estimated orientation quaternion
vx,vy,vz     optional velocity estimate
confidence   optional confidence score or inverse covariance proxy
health       tracking status, e.g. OK, DEGRADED, LOST
latency_ms   processing latency
```

Example:

```csv
0.000,imu_only,0.0,0.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,1.0,OK,1.2
0.000,openvins,0.0,0.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,0.9,OK,18.5
0.000,ultimate_slam,0.0,0.0,0.0,0.0,0.0,0.0,1.0,0.0,0.0,0.0,0.95,OK,24.1
```

---

## 8. Evaluation Protocol

For every method:

1. Run the method on the same MVSEC sequence.
2. Export trajectory in the common format.
3. Align estimated trajectory with ground truth.
4. Compute ATE and RPE.
5. Compute position error every 20 meters.
6. Compute total drift after the full sequence.
7. Record failures and invalid-pose intervals.
8. Record latency and runtime frequency.
9. Compare against all other baselines.

The key comparison is:

```text
IMU-only
vs OpenVINS / VINS-Mono
vs Event+IMU VIO
vs UltimateSLAM
vs Final Ensemble
```

The ensemble should not only beat IMU-only. It should be compared against the best individual method.

---

## 9. Forward Milestone Plan

### M0: Benchmark contract

Define dataset, sequence, metrics, baselines, and output format.

### M1: Data replay and synchronization

Implement a loader/replay pipeline for:

```text
IMU
image frames
events
ground truth
```

### M2: IMU-only baseline

Implement inertial dead reckoning / IMU preintegration.

### M3: RGB/grayscale + IMU baseline

Run OpenVINS and/or VINS-Mono on MVSEC image frames + IMU.

### M4: Event + IMU baseline

Run one event-inertial baseline or an UltimateSLAM event+IMU ablation.

### M5: Full multimodal baseline

Run UltimateSLAM with image frames + events + IMU.

### M6: Common output interface

Make all methods export the same trajectory format.

### M7: Ensemble v1

Implement deterministic fusion using confidence weighting, EKF fusion, factor-graph fusion, or method switching.

### M8: Health scoring

Add confidence and failure detection for every branch.

### M9: Optional map anchoring

Accumulate event edges and attempt matching against orthophoto/satellite map tiles.

### M10: Embedded deployment

Profile and optimize on embedded compute.

### M11: Optional learned gating / RL

Train a learned policy only after enough baseline outputs and failure cases are logged.

---

## 10. First Practical Demo Target

The first demo should show the following comparison on one MVSEC sequence:

```text
IMU-only
OpenVINS or VINS-Mono
Event+IMU baseline
UltimateSLAM
Final ensemble v1
```

With plots:

```text
trajectory overlay
ATE over time
RPE over time
position error every 20 m
latency per method
failure intervals
```

The first success criterion is:

```text
The ensemble produces a valid trajectory and performs at least as well as the best single baseline on the selected MVSEC sequence, while showing better robustness or failure recovery.
```

---

## 11. Key Principle

Do not start from the full RL ensemble.

Start with:

```text
one dataset
one sequence
fixed metrics
fixed output format
individual baselines
simple deterministic fusion
```

Only after this works should we add:

```text
more sequences
map anchoring
embedded optimization
learned/RL gating
```
