# SIH 2026 — Smart Scan Strategy for Electronic Warfare (SIH26055)
### Full Project Compilation — Idea, Plan, Progress, and Remaining Work
*Compiled from all chat sessions, uploaded markdown transcripts, and code up to 20 September 2026.*

---

## a. The Idea Behind This Project

**Problem statement:** DRDO, SIH26055, "Smart Scan Strategy for Electronic Warfare," category Software, theme Robotics and Drones.

The problem statement asks for an ML-based scheduler for an Electronic Support Measures (ESM) receiver operating **without prior intelligence** on enemy emitters. An ESM receiver has high sensitivity but much lower instantaneous bandwidth than the full spectrum it must watch, so it must sweep across frequency bands rather than see everything at once. Traditional "open-loop" strategies sweep the whole band as fast as possible using pre-mission data, but this wastes dwell time on non-threatening/empty bands while potentially missing new or threatening emitters, especially short-lived, rare, or frequency-agile ones.

The problem statement explicitly asks for:
- A simulated RF environment with ground truth of emitter transmission status per band, per time-step.
- A **learned, closed-loop scheduler** trained on hits/misses that decides where to look next in real time (instead of following a fixed rotation).
- Figures of merit: probability of detection, probability of false alarm, sensitivity, average intercept rate, average reward/cost, percentage of correct predictions, average intercept time error.
- Specific handling of **periodic scan receivers/emitters** — i.e., predicting and exploiting periodicity, not just reacting to hits.

**Our framing:** This is a **restless multi-armed bandit / POMDP problem** — each frequency band is an "arm" whose hidden state (transmitting or not) evolves on its own even when unobserved, and you only learn a band's state when you're tuned to it. The chosen approach combines:
- A **belief-state online learner** (per-band Markov transition model) with **UCB1-style exploration** for the general bandit problem.
- A **PRI (Pulse Repetition Interval) estimator** — classical ESM/EW technique (pairwise-difference histogramming, GCD-of-diffs, least-squares fractional-period refinement, and later staggered-PRI deinterleaving) — layered on top, specifically to solve the problem statement's "intercept a periodic scan receiver" requirement.
- Honest framing (documented in the project's own learnings): this is a **competent integration of established restless-bandit theory (Whittle-index-adjacent myopic policy, UCB1) with classical PRI deinterleaving (CDIF/SDIF family)**, not a novel algorithm — the competitive strengths are execution rigor, direct fit to the problem statement's language, and defensible multi-seed statistical validation, rather than algorithmic novelty.

The project is validated against the **Alan Turing Institute's Turing Synthetic Radar Dataset (TSRD)** — real Pulse Descriptor Word (PDW) data (ToA, Centre Frequency, Pulse Width, Angle of Arrival, Amplitude) from `.h5` files, originally built for a *pulse deinterleaving* challenge but reused here as realistic ground truth for scan scheduling.

---

## b. What We Had Planned

From the earliest sessions, the roadmap (beyond the initial working prototype) was laid out as:

1. **UCB-style exploration** to replace naive fixed-epsilon exploration.
2. **Multi-channel scanning** (k bands per step instead of 1).
3. **PRI-aware prediction** for periodic emitters (the problem statement's explicit periodic-scan-receiver ask).
4. **Real-data integration** with the Turing Synthetic Radar Dataset via a loader/adapter so the same scheduler code runs on real or synthetic PDW streams.
5. **Priority-weighted scoring** so rare/high-value threats can be dialed up against loud, easy comm channels.
6. **Multi-seed robustness validation** — a standing discipline that every claimed result must be checked across many random seeds (30 seeds became the project's own minimum standard) rather than trusted from a single run, after an early single-seed "headline" result (100% radar capture) turned out to be a coin flip.
7. **Retune/switch-cost modeling** — real receiver hardware cannot re-tune instantly; band hops should carry a delay cost.
8. **A proper Whittle-index policy** — the theoretically optimal restless-bandit solution, as a more rigorous alternative to the myopic belief/UCB heuristic.
9. **Real Pfa (probability of false alarm) / noise-floor / SNR modeling** — deliberately deferred since it needs a legitimate noise model, not just numbers.
10. **V-measure/HDBSCAN comparison** against TSRD's own published leaderboard metric (pulse deinterleaving), as a judge-facing benchmark.
11. **A real RL agent** (contextual bandit or small DQN/PPO) as an eventual replacement for the heuristic scheduler, once justified by data/complexity.
12. Later, a **precise gap analysis against the literal problem-statement text** identified three specific remaining gaps to close before submission:
    - **Gap #1:** Pfa/sensitivity modeling (needs an SNR/noise model) — deferred.
    - **Gap #2:** Spatial/mechanically-scanning emitter modeling (separating an emitter's own scan period from its intra-burst PRI) — the real TSRD emitters turned out to all be circular-scanning radars, not simple always-broadcasting ones.
    - **Gap #3:** Standalone reporting of "percentage of correct predictions" and "average intercept time error" as their own figures of merit (as literally worded in the problem statement).
13. Presentation deliverables: a submission-format PPTX and a presenter's talk track.

---

## c. Everything We've Completed

### 1. Core scheduler evolution
- **`scan_scheduler_prototype.py`** — first working prototype: simulated RF `Environment` with `MarkovEmitter` (bursty comms), `PeriodicEmitter` (cyclic beacon), `AgileEmitter` (frequency-hopping threat); `BeliefScheduler` (online per-band 2-state Markov model, ε-greedy). Result: **49.4% vs 26.0%** interception vs round-robin — nearly doubled.
- **`scan_scheduler_v2.py`** — added **UCB-style exploration** (optimism bonus shrinking with scan count, no epsilon to tune) and **multi-channel scanning** (k bands/step). Confirmed compounding gains: k=1 ~2.1x, k=2 ~2.2x, k=3 ~1.8x over round-robin.
- **`scan_scheduler_v3_pri.py`** — added the **PRI-aware periodicity estimator** (`PRIAwareScheduler`): pairwise-difference histogramming, GCD-of-diffs candidate generation, least-squares fractional-period refinement, chance-adjusted candidate scoring, a warm-up sweep (with shuffled band order to avoid a real `gcd(scan_period, emitter_period)` aliasing blind spot), and **priority-weighted scoring** (an explicit per-band priority dial). Headline synthetic result: sparse fixed-PRI radar caught **100%** (vs 0% for plain belief-tracking) at a comm-channel cost (79% vs 87% comm-1 coverage).
- **`scan_scheduler_v4_persistent.py`** (`PersistentPRIAwareScheduler`) — fixes a genuine **coin-flip lock-on bug**: warm-up gave an *expected* hit count (~8.3) sitting right on the algorithm's hard 8-hit lock threshold, with no recovery mechanism after warm-up, producing a binary 0%/100% outcome across seeds (measured: 30.0% ± 48.3% over 10 seeds). Fixed with a persistent, hit-count-based characterization bonus plus a scan-attempt cap (to stop chasing bands with zero emitters forever). Validated: **93.5% ± 0.7%** radar capture across 20 seeds (20/20 locking on), up from a bimodal 50.0% ± 51.3% (10/20 locking).

### 2. Real-data (Turing Synthetic Radar Dataset) integration
- **`pdw_loader.py`** — wraps the dataset's own `PulseTrain.load` API for real `.h5` files.
- **`pdw_environment.py`** — `PDWReplayEnvironment`, bins raw PDW frequency/ToA into the same band/dwell-step interface the scheduler expects, so scheduler code runs unmodified on real or synthetic PDW data. Later gained `t0_us` (real recordings don't start at ToA 0) and `next_transmission_after` (for prediction-accuracy metrics).
- **`run_on_turing_dataset.py`** — driver script; repeatedly repointed to the current best scheduler stack as it evolved, and later gained CLI flags for `--k-channels`, `--warmup-steps`, `--ucb-c`, `--priority`, `--dwell-us`, `--confidence-scale`, switch-cost/lead/warmup-dwell parameters, and `--h5`/window flags.
- Found and fixed a **dwell-resolution bug**: default 200µs dwell was too coarse vs. real PRIs (650–1500µs), giving only 3–8 scan-steps/period — indistinguishable from burst noise. Fixed with a finer 20µs dwell.
- Found and fixed a **fractional-PRI drift bug**: true PRI (650µs) wasn't an integer multiple of the dwell (32.5 steps), so a fixed-integer-tolerance model degraded. Fixed with a least-squares arithmetic-progression fit recovering the exact fractional period (32.5048 vs true 32.5, ~0.005% error).
- Found and fixed a **chance-level bias**: small candidate periods trivially scored well by chance; fixed by scoring candidates against their own chance baseline.
- **Real `.h5` files acquired (Sept 18):** six real TSRD files (`Test/config_{1,57,169}.h5`, `Validation/config_{1,57,169}.h5`). `Validation/config_169.h5` (6,668 PDWs) chosen as the working development dataset.
- New **`pdw_source.py`** — centralizes real-data access (h5py, no gated dependency), derives ground truth from file metadata, refuses to emit truth for collided/hopping/no-single-period bands, adds provenance/seed-semantics tracking, sub-window replay (`--window-start-s`/`--window-s`), and `suggest_windows()` (evidence-based window selection).
- **First genuine real-data PRI recovery:** on a real band-0 burst window, `PersistentPRIAwareScheduler` recovered 84.66226 scan-steps = 1693.2µs against the file's metadata-declared 1693.24404µs (SMART-L EWC Long Range radar) at confidence 0.98 (~0.003% error) — direct real-data confirmation that v4's sample-starvation fix matters on real data (correcting an earlier, incomplete "v4 doesn't help on PDW data" conclusion).
- **Found a structural insight about scan-mode TSRD files:** the recording receiver is itself a fixed open-loop scanner (36×500MHz dwells, 2.15s full sweep), so every emitter's burst-start spacing in the file reflects the *recording receiver's* revisit period, not the transmitters' own scan periods — meaning scan-mode files measure re-capture efficiency on a pre-filtered stream, and stare-mode files would be the true oracle for honestly scoring scan scheduling.

### 3. File-integrity and workflow discipline
- Caught (by actually *running* the code, not just reading imports) that an early "v1/v2 are obsolete" call was wrong — v3 subclasses v2, which subclasses v1; all three are load-bearing dependencies, not superseded drafts.
- Established a running discipline: every zip/markdown handoff is re-verified by actually executing the code against fixed reference numbers ("invariants") that must never silently move.
- `run_all.py` restructured (Sept 19–20) to include the four scripts it was missing (`scan_aware_scheduler.py`, `demo_spatial_scan_emitter.py`, `validate_scan_aware_mixed.py`, `prediction_accuracy_metrics.py`) and to correctly pass `--h5` only to the five h5-capable scripts, leaving controlled synthetic-regression suites untouched.

### 4. Multi-seed robustness auditing
- **`multi_seed_robustness.py`** — reruns every scheduler comparison across many seeds with mean ± stdev, min/max, paired win-counts. Revealed that BeliefUCB-vs-RoundRobin wins were rock-solid (10/10 to 30/30 seeds everywhere), but the original "100% sparse-radar capture" headline was a seed lottery.
- **`diagnose_pri_lockon.py`** — root-caused the coin-flip mechanism described above (Section 1, v4).
- Fixed suite-E CSV-writer bug: it mislabelled every suite's rows with real-data provenance whenever `--h5` was passed, even for hardcoded-synthetic suites; also fixed a header/column-count mismatch. Fixed to only stamp real-data provenance on the suite that actually used it.

### 5. Beacon-scenario (multi-step burst) regression, diagnosed and fixed
- Found a **point-vs-plateau bug**: `PRIAwareScheduler` modeled every periodic occurrence as an instantaneous spike (jitter floored at 0.5) — correct for a sparse single-pulse radar, wrong for a multi-step burst emitter (a beacon on for 4 consecutive steps/cycle); once locked on, it abandoned the burst after step 1, actively worse than plain belief. Fixed with a persistent `max_run_ever` tracker widening the jitter floor to plateau across the real burst width — validated to leave the single-pulse case completely untouched.
- Found a **harmonic-lock-on bug**: candidate-period selection could pick a harmonic (e.g. 65 instead of the true 32.5) when GCD-of-diffs collapsed to 1 under real jitter. Fixed by refining every candidate via least-squares and picking the best actual fit quality rather than a coarse tolerance score.
- **Multi-seed isolated both fixes properly** (30 seeds, reconstructing pre-fix `Original`/`PlateauOnly` scheduler states): plateau fix helps at k=2 (+1.6pp, 20/30) but slightly costs k=1 (-1.5pp) — a real trade-off invisible to a single-seed spot check.
- **Caught and fixed a real methodology confound** in the fix-interaction investigation: sequential seeding gave sequential schedulers *different* underlying environments, not the same one. Fixed by verifying that resetting the RNG seed immediately before each scheduler run produces byte-identical environment trajectories, then re-ran the comparison properly. Confirmed mechanism: the harmonic-selection fix makes lock-on more eager/confident (correct for real fractional-PRI PDW data), which costs a small, real, now-quantified amount on the multi-step beacon by over-trusting an imperfect periodicity bump over well-calibrated belief.

### 6. Off-by-one candidate bug (PDW seed-5 failure), and two structural findings
- Traced and fixed a genuine **off-by-one bug**: the candidate generator never tried mode±1, and a real PDW seed's true period (32) differed from the detected mode (33) by exactly 1, causing a rounding collision that made the correct candidate look bad and the wrong one look good. Fixed by testing each candidate's ±1 integer neighbors too. This incidentally also improved lock-on broadly on other bands. Multi-seed confirmed (30 seeds): essentially a free win with no beacon-scenario cost.
- **Band-1 "total failure" diagnosed as NOT a bug**: band 1 in the PDW stand-in structurally contains two independent emitters (a fixed-PRI radar and a frequency-agile hopper landing in the same coarse 8-band bin). Confirmed by finer channelization (n_bands=20) immediately recovering the true period. This connects directly to the still-open V-measure/HDBSCAN (pulse deinterleaving) item.
- **v4's band-6 (sparser-signal) advantage confirmed real at scale**: 14/20 vs plain PRIAware's 8/20 correct lock-on, at a real, honest cost to band-4 reliability (16/20 vs 19/20) — a genuine trade-off, not a one-sided win.

### 7. Confidence-eagerness threshold tuning
- Swept `confidence_scale` (added as a parameter, default 0.25) against both the beacon regression and PDW fractional-PRI lock-on reliability. **Finding: a genuine Pareto trade-off** — every value that helps the beacon scenario costs real PDW lock-on reliability, monotonically, with no free win. Kept the default (favoring real-dataset reliability), exposed as a CLI flag.

### 8. Switch/retune-cost modeling
- Added `switch_cost_steps` to `run_episode()` (default 0, fully backward-compatible) — a channel moved to a new band is "blind" (no observation/credit) for the configured number of steps.
- **Finding 1:** RoundRobin is not just suboptimal but non-functional under any real switch cost (switches every step by construction; collapses to 0% at cost=1 and cost=2). BeliefUCB degrades gracefully (28.2% → 15.9% → 11.1%). A strong argument for the whole project's premise.
- **Finding 2:** the sparse-radar headline result also collapsed (100% → 1.5% at cost=1) because the phase-locked scheduler always switches in cold exactly at the predicted pulse instant, so it's still settling exactly when the pulse arrives.
- **Fix — `switch_lead_steps`** (anticipatory early switching): the periodicity score plateaus across `[predicted-lead, predicted]` instead of spiking at a single point. Took two attempts (a naive time-shift just moved the peak rather than widening it — traced and fixed to floor the distance-to-predicted instead). Fully recovers 100% radar capture at every tested switch cost, with an honest, quantified, growing comm-1 coverage cost as lead widens. Roughly neutral on the beacon (dense bursts already tolerate a modest switch cost).
- **Found a further, distinct, real problem this way:** the warm-up sweep itself switches bands every step, so it suffers the *same* devastation under switch cost that RoundRobin does — the scheduler may never even accumulate enough hits to lock on in the first place.
- **Fixed that too — `warmup_dwell_steps` + `warmup_dwell_jitter`**: repeats each warm-up band visit to survive settling delay, scaled proportionally with warm-up length, and **jittered** (dwell length randomized) to break a second, newly-discovered aliasing bug (fixed dwell width creates a fixed parity between "wasted"/settling and "valid"/observing steps, which can make a seed's true pulse phase permanently unreachable). This exact fix was independently, convergently reached in two parallel chat sessions at the same point — properly tested and validated (rather than left as an untested edit) by combining dwell+jitter+scaled-warmup: **76.7% ± 42.3% → still not fully reliable alone.**
- **Combined all three fixes** (dwell+jitter warm-up survival, `switch_lead_steps` re-acquisition, and v4's persistent characterization bonus): closes the residual gap completely — **30/30 seeds locking at both cost=1 and cost=2**, variance collapsing from ±42pp to ±0.4pp, with an honest, real comm-1 coverage cost.
- **Beacon-scenario generalization check found the fix does NOT generalize** — and this is reported as a real, mechanistically-explained negative finding: the same dwell+jitter+lead+v4 combo that rescued the sparse radar actively *hurts* the beacon (13.6–17.9% band interception drops, lock-on confidence collapses from 0.72 to ~0.03–0.06). Isolated the mechanism: the artificial warm-up phase itself is the entire cost (the beacon is dense/high-duty-cycle enough that ordinary online belief+UCB learning already visits it plenty, even under switch cost, with zero explicit warm-up). **Conclusion, stated for the writeup:** apply the dwell/jitter/lead/v4 combo only to genuinely sample-starved, low-duty-cycle signals (e.g. a real sparse-PRI radar); leave dense/frequent periodic signals on the existing zero-warm-up default.

### 9. Staggered-PRI deinterleaving (a real gap found only on real data)
- Discovered that the existing PRI model (`t_i = a + b*n_i`, one pulse per period) structurally cannot represent a **staggered emitter** (multiple distinct PRIs repeating in a cycle — a standard radar ECCM technique). Three of five transmitters in the real dataset file used exactly this (AEGIS SPY-1D, Staggered PRIs 100/120/140/160/180µs).
- Built a staggered-PRI fallback (`_try_stagger_model`, `_resolve_stagger_phase`), tried only after the uniform-period model fails — strictly additive, zero cost when the uniform model already succeeds.
- Iteratively fixed: detection via longest clean-gap run split into L position-buckets (L=2..9), tightened the gap ceiling to avoid pollution from real missed-pulse gaps; separated phase resolution from pattern discovery (an unbroken-contiguity requirement almost never held on real, imperfect data — replaced with a nearest-grid-point residual fit tolerant of missed pulses); fixed a small-window bug where `history_len=30` picked the wrong stagger length L on real data (needed ~50+ hits) by adding a separate, longer-retention `stagger_hit_times` side-channel.
- **End-to-end validated on real data:** exact recovery of the declared 700.0µs cycle (35 scan-steps) at confidence 1.00, matching the file's metadata to the microsecond.
- **Found a further, genuinely interesting scoring-policy limitation:** locking the staggered PRI at full confidence actually made interception *worse* (44.3% vs BeliefUCB's 93.7%) because narrow per-pulse spikes only cover ~43% of the cycle, and full confidence zeroes belief's weight in the score blend, so the scheduler "looks away" between spikes. Diagnosed as a scoring-policy gap (not a detection bug) — the PRI is exact — and connected explicitly to the still-open Whittle-index item as the theoretically correct fix. Added `max_blend_confidence` (default 1.0, exact backward compatibility) to cap blend-confidence separately from the lock decision; swept and found another genuine Pareto trade-off (no value both fixes band-1 and preserves the sparse-radar headline); kept default, documented as a deployment dial.
- Found and fixed a **regression this introduced in the synthetic scenario**: the stagger fallback was falsely locking onto a degenerate `pattern=[1,1]` on the densely-scanned synthetic comm-1 band, regressing the beacon-scenario numbers substantially. Fixed with a stagger-specific minimum-pattern-value floor derived from the longest run of literally-adjacent hits, mirroring the guard the uniform model already had. Re-verified all synthetic invariants restored.

### 10. Precise problem-statement gap analysis and Gap #3 build
- Ran a literal gap analysis against the problem statement's exact wording, identifying three concrete remaining gaps (Pfa/sensitivity modeling, spatial/mechanical-scan modeling, standalone prediction-accuracy metrics — see Section b, item 12).
- **Gap #3 completed**: added `next_transmission_after` to `pdw_environment.py` and built `prediction_accuracy_metrics.py`, reporting "percentage of correct predictions" and "average intercept time error" as standalone figures of merit exactly as worded in the problem statement.
- **Gap #2 (spatial/mechanical scan modeling) substantially built**, found necessary once real TSRD metadata showed every real emitter is a mechanically circular-scanning radar (not an always-broadcasting emitter): `spatial_scan_emitter.py` (decorator adding beam-illumination gating + sidelobe leak probability to any existing Emitter), `scan_aware_scheduler.py` (two-tier scheduler separating outer scan-period from inner intra-burst PRI), `validate_scan_aware_mixed.py` (competitive mixed scenario). Debugged through several real failure modes (a false-lock bug, burst-segmentation fragility, a naive adjacent-gap statistic failure, `beam_dwell_estimate` pollution, and a structural issue where the inner PRI is an exact algebraic divisor of every burst-onset time) — the last fix applied (`min_candidate` derived from `min_scan_to_pri_ratio`) had not yet been confirmed by the time this thread of work paused.

### 11. Real-data validation at full scale (Sept 19–20)
Ran the four `--h5`-capable scripts against `config_169.h5` at real (not smoke-test) seed counts:
- `validate_pdw_multiseed --h5` (band-1 window): 20/20 seeds lock CORRECT at exactly 700.0µs for both PRIAware and PersistentPRIAware; the pre-stagger-fix reconstruction locks 0/20 — confirms the stagger fix is genuinely load-bearing.
- `multi_seed_robustness` suite E `--h5` (band-1 window): BeliefUCB 93.7% vs RoundRobin 12.8% (+80.9pp, 10/10 seeds); PRIAware 44.3% (−49.4pp vs BeliefUCB) — confirms the narrow-spike scoring limitation at scale, not a single-seed fluke.
- `tune_confidence_threshold --h5` (band-0 window): confirms plain PRIAware locks 0/15 on a ~0.6%-duty band (needs v4's characterization bonus) — consistent with the established sample-starvation finding. Sweep only partially completed (0.25/0.20/0.17 of 6 planned values) before a call timeout.
- `prediction_accuracy_metrics` finished `--h5` wiring (the last of the four PDW-capable harnesses to get it) — truth derived from file metadata, predictions for staggered locks correctly use the scheduler's own per-pulse `stagger_pattern`/`stagger_phase` rather than the flat-PRI formula.

### 12. Presentation and documentation deliverables
- **SIH2026 IDEA submission PPTX built** in the official template format: Title, Idea Title (proposed solution/how it addresses PS/innovation), Technical Approach, Feasibility and Viability, Impact and Benefits, Research and References — pulled from a genuine read of the 16-script codebase and chat history, including honest caveats (seed-sensitive PRI lock-on, unfixed-at-the-time warm-up-under-switch-cost issue) rather than only headline wins. File-integrity and visual QA both passed; "Important Instructions" template slide removed.
- **A full presenter talk track** written for the deck (timed, ~4–4.5 min at normal pace), including guidance on how to handle a judge probing the seed-sensitivity bug (treated as a credibility strength, not something to hide).

---

## d. Everything That Still Remains

### Carried from the very beginning, still open
1. **Proper Whittle-index policy** — the theoretically optimal restless-bandit solution, to replace/augment the current myopic belief/UCB heuristic. Now has a concrete, demonstrated motivation: it's the correct fix for the staggered-PRI scoring-policy limitation found in Section c.9 (full-confidence lock currently *hurts* interception because it can't represent "spend attention across the whole cycle, weighted").
2. **Real Pfa / noise-floor / SNR modeling** (Gap #1) — explicitly deferred; needs a legitimate noise model or the numbers would be fabricated.
3. **V-measure/HDBSCAN comparison** against TSRD's own published leaderboard metric (pulse deinterleaving) — nothing has been benchmarked against the dataset's actual scoring criterion yet. Now doubly motivated: by judge-facing credibility, and by the band-1 collision finding (a co-banded pair of emitters is exactly what pulse deinterleaving is built to separate).
4. **A real RL agent** (contextual bandit or small DQN/PPO) as an eventual replacement for the heuristic — only worth it once there's a concrete case the heuristics fall short (the staggered-PRI scoring gap is one candidate justification).

### Directly in progress when work last paused
5. **Retest `scan_aware_scheduler.py`** (Gap #2 — spatial/mechanical-scan modeling) with the final `min_candidate` fix applied, and confirm the mixed competitive scenario (scanning radar vs. Markov comms vs. AgileEmitter, k=1) runs cleanly and produces sane numbers. This is the single most concrete "next step."
6. **Finish the `tune_confidence_threshold --h5` sweep** — only 3 of 6 planned `confidence_scale` values were confirmed against real data before a call timed out.

### Concrete, smaller loose ends
7. **`prediction_accuracy_metrics.py` real-data validation at scale** — `--h5` wiring is done, but it hasn't yet been run at full multi-seed scale against real data the way the other three PDW-capable harnesses were.
8. **Full CLI wiring completeness check** — `run_on_turing_dataset.py` has accumulated many flags over time (`--k-channels`, `--warmup-steps`, `--ucb-c`, `--priority`, `--dwell-us`, `--confidence-scale`, switch-cost/lead/warmup-dwell, `--h5`/window args); worth a final pass to confirm every scheduler-level parameter added across the project is actually reachable from this one driver's CLI, not just from standalone scripts.
9. **Whether the dwell+jitter+lead+v4 switch-cost combo should be conditionally applied** (based on measured duty cycle) rather than a manual per-scenario choice — currently the project's own conclusion is "apply it only to sample-starved signals," which is a judgment call made by the operator/writeup, not an automatic decision in the code.

### Larger, acknowledged, deliberately deferred items (good candidates for "acknowledged next steps" in the writeup rather than build targets under time pressure)
10. Pfa/noise-floor modeling (#2 above, repeated for completeness of this list).
11. Whittle-index policy (#1 above).
12. V-measure/HDBSCAN leaderboard comparison (#3 above).
13. Real RL agent (#4 above).

### Presentation/submission housekeeping
14. **Team ID and Team Name** still need to be filled into the title slide of the PPTX (left blank deliberately, since they're specific to the SIH portal registration).
15. **Export the final PPTX to PDF** before uploading — the SIH portal instructions require a PDF, not PPT/Word.
16. The PPTX and talk track were built from an earlier project snapshot (pre real-data validation, pre staggered-PRI work, pre Gap #2/#3); **both should be refreshed** to reflect the real-`.h5`-validated results (e.g. the exact 700.0µs staggered-PRI recovery, the real-data multi-seed numbers from Section c.11) before final submission, since they currently describe an earlier, less-complete state of the project.

---

*This document reflects the state of the project as of 20 September 2026. Later sessions (code changes, new zips/transcripts) will move some of these items from "remaining" to "completed" — re-verify before treating any single number here as still current, consistent with the project's own established discipline of re-running code rather than trusting a write-up.*
