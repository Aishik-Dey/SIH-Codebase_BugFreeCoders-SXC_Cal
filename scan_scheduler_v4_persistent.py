"""
scan_scheduler_v4_persistent.py
=================================
Fixes the seed-sensitive lock-on bug diagnosed in diagnose_pri_lockon.py:

  PRIAwareScheduler requires >= 8 confirmed hits on a band before it will
  even attempt a PRI estimate. The fixed 800-step warmup sweep gives the
  sparse fixed-PRI radar band an EXPECTED ~8.3 confirmed hits (100 warmup
  scans / 12-step period) -- right on top of that threshold, so whether a
  given seed crosses it is close to a coin flip (Binomial noise on ~100
  trials at p=1/12). Worse: once warmup ends, a band that came up short
  gets almost no further scans (its UCB exploration credit is already
  spent from the 100 warmup visits, and its Markov belief is near-zero
  since it's off ~92% of the time) -- so a seed that didn't cross the
  threshold during warmup is locked out FOREVER. That combination turns
  ordinary sampling noise into a permanent, binary 0%-or-100% outcome
  (measured: 30.0% +/- 48.3% capture across 10 seeds).

The fix: track TOTAL confirmed hits per band (total_hits, never
truncated -- separate from the sliding hit_times window used for PRI
estimation itself), and give a band that HASN'T YET ACCUMULATED ENOUGH
HITS TO EVEN ATTEMPT A PRI ESTIMATE (total_hits < required_hits, the
same threshold _update_pri_model itself uses) a PERSISTENT
characterization bonus that decays with its OWN HIT COUNT rather than
with total scan count:

    char_bonus(b) = char_bonus_c * sqrt(log(t+2) / (total_hits[b] + 1))

This targets the actual scarce resource -- confirmed ON samples, not
scans in general -- so a band that was scanned 100 times during warmup
but only produced 6 hits still looks "worth probing" after warmup,
unlike the existing UCB term (which sees scan_count=100 and treats the
band as thoroughly explored).

TWO bounds were needed, found by testing each in turn -- a single
gate wasn't enough:

  1. Gate on total_hits < required_hits, NOT on "confidence still
     below threshold." Gating on confidence alone means a genuinely
     aperiodic band (e.g. the frequency-agile threat, split across 4
     bands so none of them individually rack up many hits) NEVER
     earns periodicity confidence, so it gets chased forever,
     permanently stealing scan budget from everything else --
     confirmed by a first test tanking comm-1 capture from ~85% to
     ~21%.

  2. ALSO cap total scan attempts per band (give_up_after_scans),
     independent of hit count. A band with a total_hits gate alone
     still fails catastrophically for a band that is simply NEVER on
     (e.g. an unassigned band with no emitter at all): total_hits
     stays 0 forever, so 1/(total_hits+1) never decays, and that one
     band absorbed ~85% of the ENTIRE post-warmup budget in testing
     (3300 of 4000 total scans went to a single always-silent band).
     Capping scan attempts means the scheduler gives up on a band
     that isn't paying off within a bounded number of tries, exactly
     like the original UCB term already does for confidence in
     general -- this bonus just gets its own, hit-count-aware version
     of that same discipline.

Run:  python3 scan_scheduler_v4_persistent.py
"""

import math
from typing import List

from scan_scheduler_v3_pri import PRIAwareScheduler


class PersistentPRIAwareScheduler(PRIAwareScheduler):
    def __init__(self, n_bands, char_bonus_c: float = 1.5,
                 required_hits: int = 8, give_up_after_scans: int = 300,
                 **kwargs):
        super().__init__(n_bands, **kwargs)
        self.char_bonus_c = char_bonus_c
        # Must match the >= 8 threshold _update_pri_model uses internally
        # -- the bonus exists purely to help bands REACH that sample
        # size, not to chase periodicity confidence indefinitely.
        self.required_hits = required_hits
        # Bound on total scans (warmup + post-warmup) a band gets while
        # still under required_hits, before the scheduler gives up on
        # ever characterizing it. Needed for bands with duty cycle ~0
        # (or literally no emitter) where total_hits never climbs no
        # matter how many times it's scanned -- without this, such a
        # band's bonus never decays and it can consume most of the
        # remaining run (observed: one always-silent band absorbed 3300
        # of 4000 total scans without this cap).
        self.give_up_after_scans = give_up_after_scans
        # Total confirmed hits ever seen on this band -- unlike
        # hit_times (capped at history_len for the PRI estimator itself),
        # this never shrinks, so it's a clean signal of "how much ON
        # evidence have we actually accumulated," independent of how
        # long ago the sliding window discarded it.
        self.total_hits: List[int] = [0] * n_bands

    def update(self, band, observed_on):
        super().update(band, observed_on)
        if observed_on:
            self.total_hits[band] += 1

    def choose_bands(self, k):
        self.t += 1
        if self.t <= self.warmup_steps:
            for b in range(self.n_bands):
                self._propagate(b)
            return self._warmup_bands(k)
        for b in range(self.n_bands):
            self._propagate(b)
        scores = []
        for b in range(self.n_bands):
            ucb_bonus = self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
            conf = min(self.confidence[b], self.max_blend_confidence)
            periodic = self._periodicity_score(b, self.t)
            blended = (1 - conf) * self.belief[b] + conf * self.periodicity_weight * periodic

            char_bonus = 0.0
            if (self.total_hits[b] < self.required_hits
                    and self.scan_count[b] < self.give_up_after_scans):
                char_bonus = self.char_bonus_c * math.sqrt(
                    math.log(self.t + 2) / (self.total_hits[b] + 1))

            scores.append(self.priority[b] * blended + ucb_bonus + char_bonus)
        order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
        return order[:k]


if __name__ == "__main__":
    import random
    from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
    from scan_scheduler_v3_pri import make_sparse_scenario

    n_bands = 36
    n_steps = 4000
    warmup = 800
    scenario = make_sparse_scenario(n_bands)
    random.seed(11)
    print("Quick single-seed sanity check (seed=11, matches earlier reports):\n")
    schedulers = {
        "BeliefUCB (Markov-only)": BeliefUCBScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
        "PRIAware (original)": PRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
        "PRIAware (persistent, fixed)": PersistentPRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
    }
    header = (f"{'Scheduler':32s} | {'Interception %':>15s} | {'Avg Reward/step':>16s}")
    print(header)
    print("-" * len(header))
    for name, sched in schedulers.items():
        random.seed(11)
        stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=1)
        r = stats.report()
        print(f"{name:32s} | {r['interception_ratio']*100:14.1f}% | {r['avg_reward_per_step']:16.3f}")
