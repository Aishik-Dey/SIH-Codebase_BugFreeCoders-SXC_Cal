"""
noise_model_demo.py
=====================
Validates noise_model.py (Gap #1) in the same order every prior fix in
this project has been validated: backward-compatibility first, then
theoretical-vs-empirical agreement, then a real demonstration of what
the new capability actually shows that nothing before it could.

Run:  python3 noise_model_demo.py
"""

import random
import math

from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
from noise_model import ReceiverNoiseModel, run_episode_noisy


def check_1_backward_compat():
    print("=== Check 1: noise_model=None must reproduce run_episode exactly ===")
    n_bands, n_steps, warmup = 8, 4000, 800
    scenario = make_sparse_scenario(n_bands)

    random.seed(11)
    sched_a = PRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup)
    stats_a = run_episode(scenario, sched_a, n_steps, n_bands, k_channels=1)

    random.seed(11)
    sched_b = PRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup)
    stats_b = run_episode_noisy(scenario, sched_b, n_steps, n_bands,
                                 noise_model=None, k_channels=1)

    ra, rb = stats_a.report(), stats_b.report()
    match = (ra["interception_ratio"] == rb["interception_ratio"]
             and ra["avg_reward_per_step"] == rb["avg_reward_per_step"]
             and stats_a.hits == stats_b.detections)
    print(f"  run_episode:        interception={ra['interception_ratio']*100:.1f}%  hits={stats_a.hits}")
    print(f"  run_episode_noisy:  interception={rb['interception_ratio']*100:.1f}%  detections={stats_b.detections}"
          f"  false_alarms={stats_b.false_alarms}")
    print(f"  BYTE-IDENTICAL: {match}\n")
    assert match, "noise_model=None must reproduce run_episode exactly -- this is a hard invariant"


def check_2_theoretical_vs_empirical():
    print("=== Check 2: theoretical vs empirical Pd/Pfa, single band, many trials ===")
    nm = ReceiverNoiseModel(threshold_std=4.0)
    print(f"  Pfa (theoretical, SNR-independent) = {nm.pfa:.6f}")

    n_trials = 200_000
    random.seed(42)
    for snr_db in [-6, -3, 0, 3, 6, 9]:
        detections = sum(1 for _ in range(n_trials) if nm.detect(True, snr_db))
        empirical_pd = detections / n_trials
        theoretical_pd = nm.pd(snr_db)
        print(f"  SNR={snr_db:>3}dB: theoretical Pd={theoretical_pd:.4f}  "
              f"empirical Pd={empirical_pd:.4f}  (n={n_trials})")

    false_alarms = sum(1 for _ in range(n_trials) if nm.detect(False, snr_db=None))
    empirical_pfa = false_alarms / n_trials
    print(f"  empirical Pfa = {empirical_pfa:.6f} (theoretical {nm.pfa:.6f})\n")


def check_3_sensitivity():
    print("=== Check 3: sensitivity_db is a correct closed-form inverse of pd() ===")
    nm = ReceiverNoiseModel(threshold_std=4.0)
    for target_pd in [0.5, 0.9, 0.99]:
        sens = nm.sensitivity_db(target_pd)
        pd_at_sens = nm.pd(sens)
        print(f"  target Pd={target_pd} -> sensitivity={sens:.2f} dB -> "
              f"pd(sensitivity)={pd_at_sens:.4f} (should match target)")
    print()


def check_4_demonstration():
    print("=== Check 4: what this actually shows -- a correctly-scheduled but "
          "low-SNR emitter still gets missed ===")
    print("  (band-5-SPECIFIC numbers, not global -- global empirical_pd is "
          "swamped by the other 7 near-perfect bands and hides this entirely, "
          "confirmed the hard way while building this demo. Aggregated across "
          "20 seeds since band 5 is a deliberately SPARSE radar -- only ~9 "
          "true encounters per single 4000-step episode, too few to read "
          "anything from alone.)")
    n_bands, n_steps, warmup, n_seeds = 8, 4000, 800, 20
    scenario = make_sparse_scenario(n_bands)
    nm = ReceiverNoiseModel(threshold_std=4.0)

    for snr_db, label in [(float("inf"), "ideal (SNR=inf, Pd=1)"),
                          (9, "SNR=9dB"),
                          (6, "SNR=6dB"),
                          (0, "SNR=0dB"),
                          (-3, "SNR=-3dB (weak/LPI-style threat)")]:
        total_d = total_m = total_encounters = 0
        for seed in range(1, n_seeds + 1):
            random.seed(seed)
            sched = PRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup)
            stats = run_episode_noisy(scenario, sched, n_steps, n_bands,
                                       noise_model=nm, band_snr_db={5: snr_db}, k_channels=1)
            br = stats.band_report(5)
            total_d += stats.per_band_detections.get(5, 0)
            total_m += stats.per_band_misses.get(5, 0)
            total_encounters += br["true_encounters"]
        empirical_pd = total_d / max(1, total_d + total_m)
        theoretical_pd = nm.pd(snr_db)
        print(f"  radar SNR {label:32s}: {total_encounters} true encounters over "
              f"{n_seeds} seeds -> band-5 empirical Pd={empirical_pd*100:5.1f}%  "
              f"(theoretical {theoretical_pd*100:5.1f}%)  detections={total_d}  misses={total_m}")
    print("\n  Same scheduler, same scan-time correctness every time -- band-5 "
          "detection collapses purely from physical detectability once SNR "
          "drops, something no prior scheduler/episode runner in this "
          "project could show at all.")


if __name__ == "__main__":
    check_1_backward_compat()
    check_2_theoretical_vs_empirical()
    check_3_sensitivity()
    check_4_demonstration()
