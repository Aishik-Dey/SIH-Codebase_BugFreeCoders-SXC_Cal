"""
noise_model.py
================
Gap #1: probability of detection (Pd), probability of false alarm (Pfa),
and sensitivity -- three of the figures of merit the problem statement
names explicitly ("probability of detection, probability of false
alarm, sensitivity, ...") and the only ones this project hadn't built
yet. Every prior scheduler/episode runner in this codebase assumes a
scanned, transmitting band is ALWAYS correctly observed and a scanned,
silent band NEVER falsely reports a hit -- i.e. Pd=1, Pfa=0 always.
That's the simplifying assumption every other file in this project
still makes; this file is what removes it, as an OPT-IN layer.

MODEL, STATED HONESTLY: a simple coherent/linear Gaussian detector --
noise-only samples ~ N(0, sigma^2); signal+noise samples ~ N(A, sigma^2)
where SNR_linear (power ratio) = (A/sigma)^2, so the mean shift in the
detector statistic is sqrt(SNR_linear)*sigma. A fixed threshold
T = threshold_std * sigma (in units of noise std-devs) gives:

    Pfa = Q(threshold_std)                          -- independent of SNR
    Pd(snr_db)  = Q(threshold_std - sqrt(SNR_linear))

where Q is the standard-normal upper-tail probability (1 - CDF). This
is the standard introductory linear-detector model (see e.g. Skolnik,
"Introduction to Radar Systems", ch. 2) -- NOT the full non-coherent
Marcum-Q/Swerling envelope-detector model real radar receivers use,
which needs numerically-evaluated Bessel/Marcum-Q functions and is a
substantially bigger lift. Stated as a real simplification, not
fabricated precision: Pd/Pfa numbers from this model are directionally
and structurally correct (right shape, right monotonicity, right
sensitivity-vs-threshold tradeoff) but not radar-engineering-grade
absolute figures. Upgrading to Marcum-Q is a clearly scoped, separate
next step if that precision is ever needed.

`sensitivity_db(target_pd)` answers the PS's literal "sensitivity"
figure of merit: the minimum SNR (dB) needed to reach a given Pd at
this model's fixed Pfa -- closed-form via the inverse-normal-CDF
(`statistics.NormalDist`, stdlib, no scipy needed).

Everything here is opt-in and additive: `run_episode_noisy` mirrors
`scan_scheduler_v2.run_episode`'s loop line-for-line (same
on_since/credited/intercept-delay bookkeeping) so results are directly
comparable, and reproduces run_episode's EXACT output when
`noise_model=None` (verified in noise_model_demo.py) -- nothing in
scan_scheduler_v2.py itself is touched.
"""

import math
import random
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_NORMAL = statistics.NormalDist()


def _q(x: float) -> float:
    """Standard-normal upper-tail probability P(Z > x), i.e. 1 - CDF(x)."""
    return 1.0 - _NORMAL.cdf(x)


def _q_inv(p: float) -> float:
    """Inverse of _q: the x such that P(Z > x) = p."""
    return _NORMAL.inv_cdf(1.0 - p)


@dataclass
class ReceiverNoiseModel:
    """A fixed detection threshold, expressed in noise standard-deviations.

    threshold_std directly sets Pfa (see module docstring); typical
    radar-engineering threshold choices land in the 4-6 sigma range for
    a low (~1e-5 to 1e-9) false-alarm rate per detection attempt --
    default 4.0 here (Pfa ~= 3.2e-5) is a reasonable, commonly-cited
    middle ground, not tuned against anything in this project.
    """
    threshold_std: float = 4.0

    @property
    def pfa(self) -> float:
        return _q(self.threshold_std)

    def pd(self, snr_db: float) -> float:
        if snr_db is None or snr_db == float("inf"):
            return 1.0
        snr_linear = 10 ** (snr_db / 10.0)
        return _q(self.threshold_std - math.sqrt(snr_linear))

    def sensitivity_db(self, target_pd: float) -> float:
        """Minimum SNR (dB) for this model's Pd to reach target_pd, at
        this model's fixed Pfa. Closed-form inversion of pd(): solves
        threshold_std - sqrt(snr_linear) = _q_inv(target_pd) for snr_linear."""
        if not 0.0 < target_pd < 1.0:
            raise ValueError("target_pd must be strictly between 0 and 1")
        sqrt_snr = self.threshold_std - _q_inv(target_pd)
        if sqrt_snr <= 0:
            return float("-inf")  # target_pd already met at SNR -> -inf (below Pfa floor)
        snr_linear = sqrt_snr ** 2
        return 10 * math.log10(snr_linear)

    def detect(self, true_on: bool, snr_db: Optional[float]) -> bool:
        """One stochastic detection trial. Draws from Python's `random`
        module (seed it the same way every other scheduler/episode
        comparison in this project does, for reproducibility)."""
        p = self.pd(snr_db) if true_on else self.pfa
        return random.random() < p


@dataclass
class NoisyRunStats:
    total_steps: int = 0
    total_band_transmissions: int = 0
    detections: int = 0        # true_on AND correctly detected
    misses: int = 0            # true_on AND NOT detected (noise-caused miss)
    false_alarms: int = 0      # NOT true_on AND falsely detected
    true_negatives: int = 0    # NOT true_on AND correctly not-detected
    intercept_delays: List[int] = field(default_factory=list)
    step_hit_rewards: List[int] = field(default_factory=list)
    switches: int = 0
    # Per-band breakdown of the same four counts. A global empirical_pd
    # is close to meaningless whenever only some bands have reduced SNR
    # (the many near-perfect bands swamp the one you actually reduced
    # SNR on in the aggregate) -- confirmed the hard way while building
    # this file's own demo: a global "99.3% empirical Pd" at SNR=6dB
    # completely hid that band 5 itself, in isolation, had only 9 true
    # encounters and 8 misses (~11% empirical Pd) at that same SNR.
    # Same "report per-emitter, not one blended number" lesson this
    # project has hit before (the original sparse-radar headline, Gap
    # #2's radar-band-%) -- report per_band[b], not the global numbers,
    # whenever band_snr_db varies by band.
    per_band_detections: Dict[int, int] = field(default_factory=dict)
    per_band_misses: Dict[int, int] = field(default_factory=dict)
    per_band_false_alarms: Dict[int, int] = field(default_factory=dict)
    per_band_true_negatives: Dict[int, int] = field(default_factory=dict)

    def band_report(self, band: int):
        d = self.per_band_detections.get(band, 0)
        m = self.per_band_misses.get(band, 0)
        fa = self.per_band_false_alarms.get(band, 0)
        tn = self.per_band_true_negatives.get(band, 0)
        return {
            "true_encounters": d + m,
            "empirical_pd": round(d / max(1, d + m), 4),
            "false_alarms": fa,
            "empirical_pfa": round(fa / max(1, fa + tn), 5),
        }

    def report(self):
        interception_ratio = self.detections / max(1, self.total_band_transmissions)
        empirical_pd = self.detections / max(1, self.detections + self.misses)
        empirical_pfa = self.false_alarms / max(1, self.false_alarms + self.true_negatives)
        avg_reward = statistics.mean(self.step_hit_rewards) if self.step_hit_rewards else 0.0
        avg_delay = statistics.mean(self.intercept_delays) if self.intercept_delays else None
        return {
            "interception_ratio": round(interception_ratio, 3),
            "empirical_pd": round(empirical_pd, 4),
            "empirical_pfa": round(empirical_pfa, 5),
            "false_alarms": self.false_alarms,
            "avg_reward_per_step": round(avg_reward, 3),
            "avg_intercept_delay": round(avg_delay, 2) if avg_delay is not None else "n/a",
        }


def run_episode_noisy(env_factory, scheduler, n_steps: int, n_bands: int,
                       noise_model: Optional[ReceiverNoiseModel] = None,
                       band_snr_db: Optional[Dict[int, float]] = None,
                       k_channels: int = 1) -> NoisyRunStats:
    """Mirrors scan_scheduler_v2.run_episode's loop exactly, with one
    addition: when noise_model is not None, each SCANNED band's true
    on/off state is passed through a stochastic Pd/Pfa detection trial
    before the scheduler ever sees it -- the scheduler updates on the
    (possibly wrong) OBSERVED value, exactly like a real receiver that
    can miss a real signal or report a phantom one. Un-scanned bands
    are unaffected either way (never observed, same as run_episode).

    noise_model=None (the default) skips detection entirely -- observed
    == true always, reproducing run_episode's behavior exactly. This is
    verified directly in noise_model_demo.py against the sparse-radar
    headline invariant.

    band_snr_db maps band index -> SNR in dB for that band's emitter
    (bands with no entry default to SNR=+inf, i.e. Pd=1 for them --
    only bands you explicitly give a finite SNR are affected)."""
    band_snr_db = band_snr_db or {}
    env = env_factory()
    stats = NoisyRunStats()
    on_since = [None] * n_bands
    credited = [False] * n_bands
    prev_bands = set()

    for t in range(n_steps):
        status: Dict[int, bool] = env.step()

        for b in range(n_bands):
            if status[b]:
                stats.total_band_transmissions += 1
                if on_since[b] is None:
                    on_since[b] = t
                    credited[b] = False
            else:
                on_since[b] = None
                credited[b] = False

        bands = scheduler.choose_bands(k_channels)
        step_hit = False
        for band in bands:
            true_on = status[band]
            if noise_model is None:
                observed_on = true_on
            else:
                snr = band_snr_db.get(band, float("inf"))
                observed_on = noise_model.detect(true_on, snr)

            scheduler.update(band, observed_on)

            if true_on and observed_on:
                stats.detections += 1
                stats.per_band_detections[band] = stats.per_band_detections.get(band, 0) + 1
                step_hit = True
                if on_since[band] is not None and not credited[band]:
                    stats.intercept_delays.append(t - on_since[band])
                    credited[band] = True
            elif true_on and not observed_on:
                stats.misses += 1
                stats.per_band_misses[band] = stats.per_band_misses.get(band, 0) + 1
            elif not true_on and observed_on:
                stats.false_alarms += 1
                stats.per_band_false_alarms[band] = stats.per_band_false_alarms.get(band, 0) + 1
            else:
                stats.true_negatives += 1
                stats.per_band_true_negatives[band] = stats.per_band_true_negatives.get(band, 0) + 1

        stats.step_hit_rewards.append(1 if step_hit else 0)
        stats.total_steps += 1
        prev_bands = set(bands)

    return stats
