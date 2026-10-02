"""
multiseed_alpha_default.py
============================
Multi-seeds the class_balance_alpha=0.1 default (scan_scheduler_v5_hedge.py)
across the three references whose environment is randomly generated --
sparse-radar headline, beacon k=1/k=2, and the synthetic PDW band-4
fractional-PRI stand-in. Real config_169.h5 is deliberately excluded: it
is a fixed file and HedgeBlendedPRIAwareScheduler makes zero calls to
`random` anywhere in its own code (confirmed by grep), and the real-band1
reference always runs with warmup_steps=0 so no inherited warmup
randomness fires either -- its 98.0% result is exact and reproducible,
not a single lucky seed, so there is nothing to average there.

This directly answers the question the single-seed alpha sweep left
open: was alpha=0.1's margin above the observed 0.02/0.05 lock threshold
(measured on ONE synthetic PDW seed) actually safe, or did seed=1 happen
to be easy? PDW band-4 lock RATE across seeds is the critical number;
sparse-radar and beacon are re-checked for completeness since they were
flat across alpha in the original sweep but were also never multi-seeded
for HedgeBlended specifically.

Uses reset-seed-immediately-before-each-scheduler's-run (not sequential
shared-stream) so every scheduler sees an identical environment per seed
-- the same discipline settle_fix_interaction.py established after
finding the sequential-seeding confound earlier in this project.

Run:  python3 multiseed_alpha_default.py
"""

import random
import statistics

from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
from scan_scheduler_prototype import make_scenario
from scan_scheduler_v5_hedge import HedgeBlendedPRIAwareScheduler
from pdw_source import PDWSource
from pdw_environment import PDWReplayEnvironment

N_BANDS = 36
N_SEEDS = 30
SCHEDULERS = [
    ("BeliefUCB", BeliefUCBScheduler, {}),
    ("PRIAware (v3)", PRIAwareScheduler, {}),
    ("HedgeBlended (v5, alpha=0.1)", HedgeBlendedPRIAwareScheduler, {}),
]


def sparse_radar_seed(seed):
    n_steps, warmup = 4000, 800
    scenario = make_sparse_scenario(N_BANDS)
    out = {}
    for name, cls, kw in SCHEDULERS:
        random.seed(seed)
        env = scenario()
        sched = cls(N_BANDS, ucb_c=0.5, warmup_steps=warmup, **kw)
        radar_p = radar_c = comm1_on = comm1_c = 0
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for b in bands:
                sched.update(b, status[b])
            if t > warmup:
                if status[5]:
                    radar_p += 1
                    if 5 in bands:
                        radar_c += 1
                if status[1]:
                    comm1_on += 1
                    if 1 in bands:
                        comm1_c += 1
        out[name] = (100 * radar_c / radar_p if radar_p else 0.0,
                     100 * comm1_c / comm1_on if comm1_on else 0.0)
    return out


def beacon_seed(seed, k):
    n_steps = 4000
    scenario = make_scenario(N_BANDS)
    out = {}
    for name, cls, kw in SCHEDULERS:
        random.seed(seed)
        sched = cls(N_BANDS, ucb_c=0.5, **kw)
        stats = run_episode(scenario, sched, n_steps, N_BANDS, k_channels=k)
        out[name] = stats.report()["interception_ratio"] * 100
    return out


def pdw_band4_seed(seed):
    dwell_us, warmup = 20.0, 800
    source = PDWSource(h5_path=None, n_bands=N_BANDS, window_s=None)
    pdw = source.for_seed(seed)
    def env_factory():
        return PDWReplayEnvironment(pdw, n_bands=N_BANDS, dwell_us=dwell_us,
                                     freq_range_mhz=source.freq_range_mhz, t0_us=source.t0_us)
    probe = env_factory()
    n_steps = probe.n_steps
    out = {}
    for name, cls, kw in SCHEDULERS:
        random.seed(seed)
        env = env_factory()
        sched = cls(N_BANDS, ucb_c=0.5, warmup_steps=warmup, **kw)
        for t in range(n_steps):
            status = env.step()
            bands = sched.choose_bands(1)
            for b in bands:
                sched.update(b, status[b])
        conf4 = getattr(sched, "confidence", [0.0] * N_BANDS)[4]
        out[name] = conf4
    return out


def summarize(label, values):
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return f"{mean:6.1f} +/- {std:5.1f}"


if __name__ == "__main__":
    print(f"=== Sparse-radar headline, {N_SEEDS} seeds ===")
    radar_by_sched = {name: [] for name, _, _ in SCHEDULERS}
    comm1_by_sched = {name: [] for name, _, _ in SCHEDULERS}
    for s in range(1, N_SEEDS + 1):
        r = sparse_radar_seed(s)
        for name in radar_by_sched:
            radar_by_sched[name].append(r[name][0])
            comm1_by_sched[name].append(r[name][1])
    for name, _, _ in SCHEDULERS:
        print(f"  {name:30s}: radar {summarize('', radar_by_sched[name])}   "
              f"comm-1 {summarize('', comm1_by_sched[name])}")

    for k in (1, 2):
        print(f"\n=== Beacon scenario, k={k}, {N_SEEDS} seeds ===")
        by_sched = {name: [] for name, _, _ in SCHEDULERS}
        for s in range(1, N_SEEDS + 1):
            r = beacon_seed(s, k)
            for name in by_sched:
                by_sched[name].append(r[name])
        for name, _, _ in SCHEDULERS:
            print(f"  {name:30s}: {summarize('', by_sched[name])}")

    print(f"\n=== PDW band-4 fractional-PRI, {N_SEEDS} seeds (LOCK RATE is the key number) ===")
    conf_by_sched = {name: [] for name, _, _ in SCHEDULERS}
    for s in range(1, N_SEEDS + 1):
        r = pdw_band4_seed(s)
        for name in conf_by_sched:
            conf_by_sched[name].append(r[name])
    for name, _, _ in SCHEDULERS:
        confs = conf_by_sched[name]
        locked = sum(1 for c in confs if c > 0)
        print(f"  {name:30s}: locked {locked}/{N_SEEDS}   mean conf when locked: "
              f"{statistics.mean([c for c in confs if c > 0]):.2f}" if locked else
              f"  {name:30s}: locked 0/{N_SEEDS}")
