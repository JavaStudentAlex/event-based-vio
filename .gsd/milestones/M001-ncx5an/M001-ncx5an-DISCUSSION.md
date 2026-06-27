# M001-ncx5an Discussion Log

## Exchange — 2026-06-27T15:39:55.551Z

### Scope

For Milestone 1, which baseline set should be treated as required rather than stretch?

- **IMU plus Event+IMU (Recommended)** — Makes IMU-only and a deterministic Event+IMU path required, while event-only and UltimateSLAM remain optional/stretch.
- **All three baselines** — Requires IMU-only, event-only/event-frame VO, and Event+IMU, increasing scope and integration risk.
- **Include UltimateSLAM** — Adds external baseline wrapper work to Milestone 1, useful but riskier than a deterministic in-repo baseline.

**Selected:** IMU plus Event+IMU (Recommended)
---

## Exchange — 2026-06-27T15:41:01.216Z

### Scope Gate

Does this capture the scope? Adjust anything before we move on.

- **Yes, scope fits (Recommended)** — Proceed to architecture questions using this scope boundary.
- **Needs adjustment** — Pause here so you can clarify what is included, excluded, or deferred.

**Selected:** Needs adjustment
---

## Exchange — 2026-06-27T15:41:55.713Z

### Scope Gate

Does this updated scope capture Milestone 1? Adjust anything before we move on.

- **Yes, scope fits (Recommended)** — Proceed to architecture questions using this full benchmark scope.
- **Needs adjustment** — Pause here so you can clarify what is included, excluded, or deferred.

**Selected:** Needs adjustment
---

## Exchange — 2026-06-27T15:43:41.317Z

### Scope Gate

Does this capture the scope? Adjust anything before we move on.

- **Yes, scope fits (Recommended)** — Proceed to architecture questions with this tightened milestone contract.
- **Needs adjustment** — Pause here so you can clarify remaining scope issues.

**Selected:** Needs adjustment
---

## Exchange — 2026-06-27T15:52:35.327Z

### Split

How should we split the scope from milestone_1_event_imu_vio.md?

- **Two milestones (Recommended)** — Keep M001 focused on deterministic MVSEC pipeline, IMU baseline, simple Event+IMU baseline, exports, evaluation, CLI, and synthetic tests; defer stronger wrappers/comparison hardening.
- **One milestone** — Treat the whole file as M001, including wrapper, runtime/failure reports, and all benchmark artifacts, but execution risk is higher.
- **Three milestones** — Split more aggressively so each milestone has a smaller proof target and fewer coupled risks.

**Selected:** Three milestones
---

## Exchange — 2026-06-27T15:54:02.949Z

### Scope Gate

Does this capture the full scope split before we move to architecture?

- **Yes, scope fits (Recommended)** — Proceed to architecture decisions for the three-milestone plan.
- **Needs adjustment** — Pause here so you can clarify milestone boundaries, dependencies, or deferred work.

**Selected:** Yes, scope fits (Recommended)
---

## Exchange — 2026-06-27T15:56:37.242Z

### Modules

What module shape should we plan for the benchmark code?

- **nav_benchmark package (Recommended)** — Create a real Python package with dataset, sync, trajectory, baseline, evaluation, plotting, and CLI modules.
- **Top-level folders** — Use folders like data_tools, baselines, evaluation, and scripts, matching the source note but with looser package boundaries.
- **Single CLI first** — Start with one command module and split later, fastest initially but risks creating a script blob.

**Selected:** nav_benchmark package (Recommended)

### Alignment

For M001 evaluation, what trajectory alignment policy should be the default?

- **Explicit SE3 align (Recommended)** — Synchronize timestamps, align estimated trajectory to ground truth with a declared SE3 policy, and report that policy in metrics metadata.
- **Origin-only relative** — Start both trajectories at a common origin and compare relative drift without full spatial alignment.
- **Support both modes** — Implement both SE3 alignment and origin-relative evaluation in M001, increasing evaluator scope but making comparisons richer.

**Selected:** Explicit SE3 align (Recommended)
---

## Exchange — 2026-06-27T15:57:20.913Z

### Backend

How much of the odometry backend contract should M001 define before M002 adds Event+IMU?

- **Stable minimal contract (Recommended)** — Define a small backend interface now so IMU-only, Event+IMU, and future wrappers all produce the same trajectory/run metadata.
- **IMU-only first** — Keep M001 focused on IMU-only code and introduce the backend contract in M002 when Event+IMU exists.
- **Rich plugin contract** — Design a fuller plugin API in M001 for external wrappers like UltimateSLAM and ESVO.

**Selected:** Stable minimal contract (Recommended)

### Artifacts

Where should benchmark run artifacts live by default?

- **runs/ benchmark outputs (Recommended)** — Use `runs/` for generated benchmark outputs and keep them untracked; this matches your earlier command example.
- **experiments/ outputs** — Use `experiments/`, matching the source file, but this can blur generated outputs with reusable experiment docs/configs.
- **Configurable only** — Require every run to specify an output directory and avoid a default convention.

**Selected:** runs/ benchmark outputs (Recommended)
---

## Exchange — 2026-06-27T15:59:49.542Z

### Errors

We can go deep on error handling and failure modes, or I can apply sensible defaults based on the architecture decisions above. Which do you prefer?

- **Use sensible defaults (Recommended)** — Apply explicit, benchmark-focused defaults for dataset, sync, odometry, export, and evaluation failures.
- **Go deep** — Spend another round detailing failure behavior, retries, invalid data policy, and user-facing diagnostics.
- **Other / let me explain** — Use your own framing if neither option matches how you want failures handled.

**Selected:** Use sensible defaults (Recommended)
---

## Exchange — 2026-06-27T16:16:06.331Z

### Quality

Does this capture the quality bar before we move on to requirements and roadmap?

- **Yes, quality fits (Recommended)** — Proceed to depth verification and then requirements/roadmap preview.
- **Needs adjustment** — Pause here so you can clarify acceptance criteria, tests, or unacceptable outcomes.

**Selected:** Needs adjustment
---

## Exchange — 2026-06-27T16:21:22.335Z

### Quality

Does the quality bar fit with these additions: required run_manifest.json, always-present failure_notes.md, content-valid artifacts, and explicit invalid/degraded intervals in benchmark artifacts?

- **Yes, quality fits (Recommended)** — Proceed to depth verification and then requirements/roadmap preview.
- **Needs adjustment** — Pause here so you can clarify acceptance criteria, tests, or unacceptable outcomes.

**Selected:** Yes, quality fits (Recommended)
---

## Exchange — 2026-06-27T16:26:45.513Z

### Depth Check

Did I capture the depth right?

- **Yes, you got it (Recommended)** — Proceed to requirements and roadmap preview using the locked depth summary.
- **Not quite — let me clarify** — Pause so you can correct the depth summary before planning artifacts are written.

**Selected:** Yes, you got it (Recommended)
---

## Exchange — 2026-06-27T16:30:32.732Z

### Roadmap

Ready to write, or want to adjust?

- **Ready to write (Recommended)** — Write project, requirements, M001 context, and the M001 roadmap artifacts.
- **Want to adjust** — Pause here so you can revise slices, dependencies, demos, or definition of done.

**Selected:** Ready to write (Recommended)
---

## Exchange — 2026-06-27T16:37:50.943Z

### M002 Gate

For M002 — First Event+IMU Odometry Backend, how should we handle its context now?

- **Write draft for later (Recommended)** — Save a concise seed context with provisional scope and open questions, then move to the M003 gate without spending more discussion time now.
- **Discuss now** — Do a focused M002 planning discussion now, including technical assumption verification before writing full context.
- **Just queue it** — Create no M002 context now; future auto-mode will pause and start full discussion from scratch when it reaches M002.

**Selected:** Write draft for later (Recommended)
---

## Exchange — 2026-06-27T16:44:12.412Z

### Depth Check — M003

Did I capture the depth for M003: Strong Baselines and Benchmark Reporting?

- **Yes, you got it (Recommended)** — Proceed to write M003 full CONTEXT.md and finalize gates.
- **Not quite — let me clarify** — Pause so you can correct the M003 scope, risks, or acceptance before I write.

**Selected:** Yes, you got it (Recommended)
---

