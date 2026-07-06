"""Agentic PPO training harness for the RL-gated ensemble (CLI: ``train-rl``).

"Agentic" means the harness supervises its own run instead of blindly looping:

- it holds out every Nth episode window and, on a fixed cadence, evaluates the
  deterministic policy against the deterministic weighted-EKF baseline
  (all-ones trust) on clean *and* perturbed variants of those windows;
- it escalates the perturbation curriculum only after the policy clears an
  improvement bar on the current severity;
- it keeps the best checkpoint by held-out improvement, stops early when
  evaluation stagnates, and journals every decision to ``training_log.jsonl``.

Everything is seeded: episodes, perturbations, exploration noise, and
minibatch order derive from ``spec.seed``, so a training run is reproducible
on CPU. Rewards need ground truth, hence training inputs must carry GT poses;
benchmark inference does not.
"""

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

from nav_benchmark.datasets.loading import default_gravity, load_sequence
from nav_benchmark.ensemble.ekf import EkfConfig
from nav_benchmark.ensemble.fusion import EkfFusionConfig
from nav_benchmark.ensemble.rl_gated import RlGatedFusionConfig
from nav_benchmark.rl.env import EnsembleFusionEnv, EnvConfig
from nav_benchmark.rl.episodes import FusionEpisode, build_episodes, compute_ensemble_inputs
from nav_benchmark.rl.features import FeatureConfig, observation_dim
from nav_benchmark.rl.perturb import sample_episode_perturbations
from nav_benchmark.rl.ppo import PpoAgent, PpoConfig, RolloutBuffer

EVAL_SEVERITY = 2


@dataclass
class TrainRlSpec:
    """Inputs, environment shape, and optimisation settings for one training run."""

    dataset: str
    inputs: list[Path]
    output_dir: Path
    jepa_checkpoint: Path | None = None
    window_sec: float = 8.0
    stride_sec: float = 4.0
    control_period_sec: float = 0.10
    min_trust_to_apply: float = 0.05
    eval_holdout: int = 4
    iterations: int = 60
    steps_per_iteration: int = 2048
    eval_every: int = 5
    initial_severity: int = 1
    max_severity: int = 3
    promote_improvement: float = 0.05
    patience_evals: int = 4
    seed: int = 0
    device: str = "auto"
    event_window_ms: float = 50.0
    lr: float = 3e-4
    entropy_coef: float = 1e-3
    hidden: tuple[int, ...] = (64, 64)
    jitter_penalty: float = 0.05
    sequence_names: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.inputs:
            raise ValueError("At least one --input sequence is required")
        if self.eval_holdout < 2:
            raise ValueError("eval_holdout must be at least 2 (need both train and eval windows)")


@dataclass
class _EvalCase:
    """One held-out episode variant with its cached deterministic baseline error."""

    episode: FusionEpisode
    perturbed: bool
    env: EnsembleFusionEnv
    baseline_error_m: float


def _episode_rng(seed: int, episode_index: int, severity: int) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence((seed, episode_index, severity))))


def _rollout_final_error(env: EnsembleFusionEnv, policy=None) -> float:
    """Run one episode (all-ones trust when ``policy`` is None) and return the final error."""
    observation = env.reset()
    done = False
    while not done:
        action = np.ones(env.action_dim) if policy is None else policy(observation)
        observation, _reward, done, _info = env.step(action)
    return env.final_position_error_m()


class TrainingHarness:
    """Owns the episode bank, the PPO loop, evaluation gates, and the journal."""

    def __init__(self, spec: TrainRlSpec, log=print) -> None:
        self.spec = spec
        self.log = log
        self.output_dir = Path(spec.output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._journal_path = self.output_dir / "training_log.jsonl"
        self._journal_path.write_text("", encoding="utf-8")

        self._fusion_config_template = self._fusion_config()
        self._train_episodes, self._eval_episodes = self._load_episode_bank()
        methods = tuple(sorted(self._train_episodes[0].backend_trajectories))
        self.feature_config = FeatureConfig(methods=methods, include_jepa=spec.jepa_checkpoint is not None)
        self.severity = spec.initial_severity
        self._train_envs = self._build_train_envs(self.severity)
        self._eval_cases = self._build_eval_cases()
        self._action_rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence((spec.seed, 1))))
        self._update_rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence((spec.seed, 2))))
        self.agent = self._build_agent()

    # ---------------------------------------------------------------- setup

    def _fusion_config(self) -> RlGatedFusionConfig:
        gravity = default_gravity(self.spec.dataset)
        return RlGatedFusionConfig(
            base=EkfFusionConfig(ekf=EkfConfig(gravity=gravity)),
            control_period_sec=self.spec.control_period_sec,
            min_trust_to_apply=self.spec.min_trust_to_apply,
        )

    def _jepa_series_for(self, sequence):
        if self.spec.jepa_checkpoint is None:
            return None
        from nav_benchmark.jepa.model import JepaModel
        from nav_benchmark.jepa.signals import obs_series_for_sequence

        model = JepaModel.load(self.spec.jepa_checkpoint, device=self.spec.device)
        return obs_series_for_sequence(
            model, sequence, gravity=default_gravity(self.spec.dataset), device=self.spec.device
        )

    def _load_episode_bank(self) -> tuple[list[FusionEpisode], list[FusionEpisode]]:
        episodes: list[FusionEpisode] = []
        for index, input_path in enumerate(self.spec.inputs):
            name = self.spec.sequence_names[index] if index < len(self.spec.sequence_names) else Path(input_path).name
            self.log(f"Loading sequence {name} from {input_path}")
            sequence = load_sequence(self.spec.dataset, input_path, sequence_name=name)
            inputs = compute_ensemble_inputs(
                sequence,
                event_window_sec=self.spec.event_window_ms / 1000.0,
                gravity=default_gravity(self.spec.dataset),
            )
            jepa_series = self._jepa_series_for(sequence)
            built = build_episodes(
                inputs,
                window_sec=self.spec.window_sec,
                stride_sec=self.spec.stride_sec,
                name_prefix=name,
                jepa_series=jepa_series,
            )
            self.log(f"Sequence {name}: {len(built)} episode windows")
            episodes.extend(built)
        if not episodes:
            raise ValueError("No training episodes could be built from the given inputs")

        train = [ep for i, ep in enumerate(episodes) if (i + 1) % self.spec.eval_holdout != 0]
        eval_ = [ep for i, ep in enumerate(episodes) if (i + 1) % self.spec.eval_holdout == 0]
        if not eval_:
            eval_ = [episodes[-1]]
        if not train:
            train = list(episodes)
        self.log(f"Episode bank: {len(train)} train / {len(eval_)} eval windows")
        return train, eval_

    def _env_for(self, episode: FusionEpisode, perturbations) -> EnsembleFusionEnv:
        config = EnvConfig(fusion=self._fusion_config_template, jitter_penalty=self.spec.jitter_penalty)
        return EnsembleFusionEnv(episode, self.feature_config, config=config, perturbations=perturbations)

    def _build_train_envs(self, severity: int) -> list[EnsembleFusionEnv]:
        envs = []
        methods = tuple(sorted(self._train_episodes[0].backend_trajectories))
        for index, episode in enumerate(self._train_episodes):
            rng = _episode_rng(self.spec.seed, index, severity)
            perturbations = sample_episode_perturbations(rng, methods, episode.t_start, episode.t_end, severity)
            envs.append(self._env_for(episode, perturbations))
        return envs

    def _build_eval_cases(self) -> list[_EvalCase]:
        cases: list[_EvalCase] = []
        methods = tuple(sorted(self._eval_episodes[0].backend_trajectories))
        for index, episode in enumerate(self._eval_episodes):
            clean_env = self._env_for(episode, [])
            cases.append(_EvalCase(episode, False, clean_env, _rollout_final_error(clean_env)))
            rng = _episode_rng(self.spec.seed, 10_000 + index, EVAL_SEVERITY)
            perturbations = sample_episode_perturbations(rng, methods, episode.t_start, episode.t_end, EVAL_SEVERITY)
            perturbed_env = self._env_for(episode, perturbations)
            cases.append(_EvalCase(episode, True, perturbed_env, _rollout_final_error(perturbed_env)))
        return cases

    def _build_agent(self) -> PpoAgent:
        from nav_benchmark.rl.runner import policy_feature_metadata

        config = PpoConfig(
            obs_dim=observation_dim(self.feature_config),
            act_dim=len(self.feature_config.methods),
            hidden=self.spec.hidden,
            lr=self.spec.lr,
            entropy_coef=self.spec.entropy_coef,
            seed=self.spec.seed,
        )
        return PpoAgent(
            config,
            feature_metadata=policy_feature_metadata(self.feature_config, self._fusion_config_template),
            device=self.spec.device,
        )

    # ------------------------------------------------------------- training

    def _journal(self, record: dict) -> None:
        with open(self._journal_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    def _collect(self) -> tuple[RolloutBuffer, float]:
        buffer = RolloutBuffer()
        episode_returns: list[float] = []
        env_index = 0
        while len(buffer) < self.spec.steps_per_iteration:
            env = self._train_envs[env_index % len(self._train_envs)]
            env_index += 1
            observation = env.reset()
            episode_return = 0.0
            done = False
            while not done:
                action, obs_normalized, pre_squash, log_prob, value = self.agent.act(observation, self._action_rng)
                observation, reward, done, _info = env.step(action)
                buffer.add(obs_normalized, pre_squash, log_prob, value, reward, done)
                episode_return += reward
            episode_returns.append(episode_return)
        return buffer, float(np.mean(episode_returns))

    def _evaluate(self) -> dict:
        policy = self.agent.act_deterministic
        details = []
        improvements_all: list[float] = []
        improvements_perturbed: list[float] = []
        for case in self._eval_cases:
            error = _rollout_final_error(case.env, policy)
            improvement = (case.baseline_error_m - error) / max(case.baseline_error_m, 1e-6)
            details.append(
                {
                    "episode": case.episode.name,
                    "perturbed": case.perturbed,
                    "baseline_error_m": case.baseline_error_m,
                    "policy_error_m": error,
                    "improvement": improvement,
                }
            )
            improvements_all.append(improvement)
            if case.perturbed:
                improvements_perturbed.append(improvement)
        return {
            "mean_improvement": float(np.mean(improvements_all)),
            "mean_improvement_perturbed": float(np.mean(improvements_perturbed)) if improvements_perturbed else 0.0,
            "cases": details,
        }

    def _maybe_promote_curriculum(self, evaluation: dict, iteration: int) -> None:
        if self.severity >= self.spec.max_severity:
            return
        if evaluation["mean_improvement_perturbed"] < self.spec.promote_improvement:
            return
        self.severity += 1
        self._train_envs = self._build_train_envs(self.severity)
        self.log(f"Curriculum promoted to severity {self.severity} at iteration {iteration}")
        self._journal({"type": "curriculum", "iteration": iteration, "severity": self.severity})

    def _best_single_backend_errors(self) -> dict[str, float]:
        """Final-window error of each raw backend on clean eval episodes (benchmark rule:
        the ensemble must be compared against the best individual baseline)."""
        errors: dict[str, list[float]] = {}
        for episode in self._eval_episodes:
            gt_end = episode.gt_positions[-1]
            for method, trajectory in episode.backend_trajectories.items():
                if len(trajectory.timestamps) == 0:
                    continue
                end_position = np.array(
                    [
                        np.interp(episode.t_end, trajectory.timestamps, trajectory.positions[:, axis])
                        for axis in range(3)
                    ]
                )
                errors.setdefault(method, []).append(float(np.linalg.norm(end_position - gt_end)))
        return {method: float(np.mean(values)) for method, values in errors.items()}

    def run(self) -> dict:
        spec = self.spec
        best_improvement = -np.inf
        best_iteration = -1
        evals_since_best = 0
        started = time.perf_counter()

        for iteration in range(1, spec.iterations + 1):
            buffer, mean_return = self._collect()
            stats = self.agent.update(buffer, self._update_rng)
            self._journal(
                {"type": "iteration", "iteration": iteration, "mean_return": mean_return, "steps": len(buffer), **stats}
            )
            self.log(
                f"iter {iteration:>3}/{spec.iterations} return {mean_return:+.4f} "
                f"kl {stats['approx_kl']:.4f} entropy {stats['entropy']:.2f}"
            )

            if iteration % spec.eval_every != 0 and iteration != spec.iterations:
                continue
            evaluation = self._evaluate()
            self._journal({"type": "eval", "iteration": iteration, **evaluation})
            self.log(
                f"eval @ iter {iteration}: improvement {evaluation['mean_improvement']:+.3f} "
                f"(perturbed {evaluation['mean_improvement_perturbed']:+.3f})"
            )
            self.agent.save(self.output_dir / "policy_last.pt", extra_metadata={"iteration": iteration})
            if evaluation["mean_improvement"] > best_improvement:
                best_improvement = evaluation["mean_improvement"]
                best_iteration = iteration
                evals_since_best = 0
                self.agent.save(
                    self.output_dir / "policy_best.pt",
                    extra_metadata={"iteration": iteration, "mean_improvement": best_improvement},
                )
                self._journal({"type": "best", "iteration": iteration, "mean_improvement": best_improvement})
            else:
                evals_since_best += 1
            self._maybe_promote_curriculum(evaluation, iteration)
            if evals_since_best >= spec.patience_evals:
                self.log(f"Early stop: no eval improvement for {evals_since_best} evaluations")
                self._journal({"type": "early_stop", "iteration": iteration})
                break

        report = {
            "spec": self._spec_json(),
            "train_episodes": len(self._train_episodes),
            "eval_episodes": len(self._eval_episodes),
            "final_severity": self.severity,
            "best_improvement": float(best_improvement),
            "best_iteration": best_iteration,
            "elapsed_sec": time.perf_counter() - started,
            "final_evaluation": self._evaluate(),
            "best_single_backend_mean_final_error_m": self._best_single_backend_errors(),
            "checkpoints": {
                "best": str(self.output_dir / "policy_best.pt"),
                "last": str(self.output_dir / "policy_last.pt"),
            },
        }
        with open(self.output_dir / "report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        self.log(f"Training report written to {self.output_dir / 'report.json'}")
        return report

    def _spec_json(self) -> dict:
        data = asdict(self.spec)
        data["inputs"] = [str(p) for p in self.spec.inputs]
        data["output_dir"] = str(self.spec.output_dir)
        data["jepa_checkpoint"] = str(self.spec.jepa_checkpoint) if self.spec.jepa_checkpoint else None
        data["hidden"] = list(self.spec.hidden)
        return data


def run_training(spec: TrainRlSpec, log=print) -> dict:
    """Build the harness and run the full training loop; returns the report."""
    return TrainingHarness(spec, log=log).run()
