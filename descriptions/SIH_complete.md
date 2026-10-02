# SIH26055 — Reconstructed Project History

## 0. The project in one sentence

The project evolved from a simple learned frequency-scanning prototype into a **closed-loop, PRI-aware, persistence-enhanced, scan-aware, adaptive scheduler for an EW/ESM receiver**, with progressively more realistic receiver constraints and finally validation against a real TSRD `.h5` recording.

The central idea remained:

> Instead of blindly sweeping frequencies, maintain beliefs about emitters, learn their temporal behavior, predict when they will transmit, and choose the next receiver band accordingly.

---

# Phase 1 — Birth of the prototype

### September 6, 2026 — ~01:09 to 20:34

## 1. Problem statement → computational formulation

The project started from **DRDO SIH26055: Smart Scan Strategy for Electronic Warfare**.

The problem was interpreted as a sequential decision problem:

* receiver can only observe a limited instantaneous bandwidth;
* the overall spectrum is much larger;
* emitters may be intermittent or periodic;
* previous intelligence may be unavailable/unreliable;
* every scan decision affects what can be learned next.

The initial conceptual framing was essentially:

**restless multi-armed bandit / POMDP-like adaptive sensing.**

The receiver maintains beliefs about which bands are useful and repeatedly chooses where to look.

---

## 2. First working scheduler

The first major implementation was:

`scan_scheduler_prototype.py`

It introduced:

* an environment;
* simulated emitters;
* band states;
* a basic belief-tracking scheduler;
* interception metrics;
* comparison against Round Robin.

Initial headline result:

* learned `BeliefScheduler`: **49.4% interception**
* Round Robin: **26.0%**

This established that the basic closed-loop idea could work in simulation.

---

# Phase 2 — From belief tracking to UCB + PRI awareness

## 3. Turing/TSRD data path introduced

The project then started targeting the **Alan Turing Institute Synthetic Radar Dataset / Turing Deinterleaving Challenge**.

The data architecture became:

```text
PDW source
   ↓
pdw_loader.py
   ↓
pdw_environment.py
   ↓
scheduler
   ↓
run_on_turing_dataset.py
```

The actual large dataset could not initially be downloaded inside Claude's environment, so a **schema-faithful synthetic stand-in** was used for development.

This distinction became important later: many early "PDW" results were actually synthetic-schema tests, not real TSRD measurements.

---

## 4. `scan_scheduler_v2.py`

The next major version introduced:

* UCB exploration;
* multi-channel scanning;
* `k` simultaneous/selected bands;
* exploration versus exploitation.

The problem became more realistic:

> Don't permanently exploit the currently best-looking band; deliberately explore uncertain bands.

---

# Phase 3 — PRI-aware scheduling

## 5. `scan_scheduler_v3_pri.py`

The next major step was temporal prediction.

The scheduler learned from pulse/intercept gaps and attempted to estimate a **Pulse Repetition Interval (PRI)**.

The PRI layer used ideas including:

* pairwise gap histograms;
* candidate generation;
* GCD-style candidate reasoning;
* least-squares refinement;
* periodicity scoring;
* warm-up scanning;
* priority-weighted scoring.

This produced the project's first dramatic synthetic result:

### Sparse fixed-PRI radar

PRI-aware scheduling reached approximately:

**100% radar capture**

where the plain belief scheduler essentially failed.

This was a major conceptual milestone:

> The scheduler was no longer merely learning *which frequency* was interesting; it was learning *when* that emitter should be observed.

---

## 6. The first major reality check: the 100% result was misleading

The project immediately subjected that result to multi-seed testing.

`multi_seed_robustness.py` showed that the apparent 100% success was not robust.

Across seeds, the sparse-radar result was roughly:

**30.0% ± 48.3%**

The distribution was essentially bimodal.

Some seeds locked onto the radar.

Others never did.

This led to one of the project's most important discoveries.

---

# Phase 4 — The sample-starvation / warm-up problem

## 7. Why PRIAware sometimes worked and sometimes didn't

The warm-up phase provided roughly the number of radar observations needed to cross an **8-hit lock threshold**.

The scheduler therefore behaved almost like:

```text
enough hits during warmup → lock
not enough hits → never lock
```

There was no sufficiently strong recovery mechanism after warm-up.

This was identified as a **sample-starvation coin flip**, rather than genuine robust learning.

---

# Phase 5 — Persistent PRI scheduler

## 8. `scan_scheduler_v4_persistent.py`

The solution was a persistent characterization mechanism.

`PersistentPRIAwareScheduler` introduced:

* persistent characterization bonus;
* scan limits/caps;
* continued pressure to characterize insufficiently observed bands.

The result became:

**93.5% ± 0.7% over 20 seeds**

instead of the previous bimodal behavior.

This was the first major example of the project's recurring methodology:

> Don't trust a spectacular single-seed result. Find the mechanism, fix it, then validate over many seeds.

---

# Phase 6 — Realistic beacon behavior and the plateau problem

## 9. The multi-step beacon exposed a different modeling error

The sparse radar was effectively modeled as point-like periodic events.

But the beacon scenario produced **multi-step bursts**.

The periodicity model treated them too much like instantaneous spikes.

That caused a **point-vs-plateau mismatch**.

The fix introduced persistent information about the maximum observed run / jitter floor so that a multi-step transmission occupied a wider temporal region.

Multi-seed testing showed an important nuance:

* the plateau fix helped some configurations, particularly `k=2`;
* it could slightly hurt `k=1`.

So again, it was not treated as a free improvement.

---

# Phase 7 — Harmonic lock-on

## 10. A serious PRI estimation bug appeared

The scheduler sometimes estimated:

**65 steps**

when the actual PRI was approximately:

**32.5 steps**

This was a harmonic-selection problem.

The fix used least-squares refinement / candidate scoring to distinguish the true fundamental from harmonics.

Later testing showed that this wasn't merely a synthetic curiosity; analogous issues appeared in real data.

---

# Phase 8 — Experimental methodology itself gets fixed

## 11. The seeding confound

During comparison of fixes, another important problem was discovered.

The validation harness sometimes seeded once for an entire comparison block.

Because the environment used randomness, scheduler A, B, C, etc. could consequently experience **different environment trajectories**.

That contaminated comparisons.

The methodology was corrected so that:

```text
seed
 ↓
scheduler A gets environment realization X

same seed
 ↓
scheduler B gets environment realization X

same seed
 ↓
scheduler C gets environment realization X
```

This became a recurring rule throughout the project:

> Never compare scheduler behavior using different random environments when a paired comparison is intended.

Later, the same issue reappeared when comparing v4 and v5 by interleaving `env.step()` calls, and was caught again.

---

# Phase 9 — Confidence tuning and off-by-one correction

## 12. `confidence_scale`

A sweep of the periodicity-confidence contribution showed a genuine trade-off.

There was no magic value that simultaneously maximized every scenario.

This became a recurring project conclusion:

> Several apparent "fixes" are actually Pareto trade-offs between sparse periodic emitters, dense Markov emitters, and different scanning regimes.

`confidence_scale` was therefore exposed as a parameter rather than pretending there was a universally optimal value.

---

## 13. The ±1 candidate-generation bug

A real bug was found in PRI candidate generation.

A candidate neighborhood failed to include the appropriate neighboring values.

The correction expanded candidate consideration around the estimate.

It produced broader improvements, including better performance on some bands, without materially damaging the beacon scenario.

This became one of the cleaner fixes in the project.

---

# Phase 10 — Band collision discovered

## 14. Band 1 failure wasn't actually a scheduler bug

One emitter appeared to be completely unlearnable.

Investigation showed two different emitters were being mapped into the same coarse frequency bin.

The issue was therefore:

**frequency-resolution collision**, not PRI learning.

Increasing channelization separated them.

This was an important conceptual result:

> A scheduler cannot distinguish two emitters that the receiver's frequency discretization has already merged.

---

# Phase 11 — Receiver switching cost changes everything

## 15. `switch_cost_steps`

The project then introduced a realistic receiver constraint:

> Changing frequency isn't instantaneous.

A switch incurs settling time during which the receiver cannot meaningfully observe the new band.

This exposed a huge vulnerability.

### Round Robin

With a nonzero switching cost:

**Round Robin collapsed to 0% interception.**

Every scan was effectively another switch.

This strongly demonstrated why an intelligent scheduler that **stays/camps on useful bands** is fundamentally different from a blind sweep when retuning has a real cost.

---

# Phase 12 — The sparse-radar result also collapsed

The more surprising discovery was that the famous:

**100% sparse-radar capture**

also collapsed, to roughly:

**1.5%**

under `switch_cost=1`.

Why?

The PRI scheduler was doing something seemingly intelligent:

```text
predict pulse arrival
→ switch to that band
→ pulse arrives
```

But the switch itself took time.

So the receiver was often:

```text
cold switch
     ↓
settling
     ↓
pulse arrives
     ↓
miss
```

The scheduler was predicting the pulse correctly but scheduling the **receiver transition too late**.

---

# Phase 13 — `switch_lead_steps`

## 16. First attempt: naive time shifting

Simply moving the prediction earlier didn't properly solve the problem.

It merely moved the scoring peak.

The successful mechanism instead created a **plateau / lead region**, allowing the scheduler to switch early enough and remain ready for the predicted pulse.

`switch_lead_steps` was introduced.

This restored the sparse-radar behavior under switching cost, but at a communication-band coverage cost.

Again:

> Better radar interception came at the cost of other-band coverage.

---

# Phase 14 — Warm-up itself was now broken

## 17. A new problem emerged

Even though the post-lock scheduler could now handle switching cost, the **warm-up sweep** still changed bands too frequently.

So:

```text
warm-up
→ switch
→ settle
→ switch
→ settle
→ switch
```

could prevent the scheduler from collecting enough samples to lock in the first place.

This produced the next major fix.

---

# Phase 15 — Warm-up dwell + jitter

## 18. `warmup_dwell_steps`

The scheduler began dwelling on each warm-up band instead of switching every step.

But dwell alone failed.

Why?

Because increasing dwell reduced the number of warm-up visits.

Scaling the warm-up budget helped, but another structural problem remained.

---

## 19. Fixed-parity aliasing

With fixed dwell lengths, some pulse phases consistently landed on the "wasted" settling positions.

Thus the receiver could remain permanently out of phase with a periodic emitter.

The solution was:

**dwell + jitter**

rather than fixed dwell.

The jitter broke the deterministic phase relationship.

---

## 20. The 30-seed ablation

The decisive ablation was:

| Variant                           |    Radar lock-on |
| --------------------------------- | ---------------: |
| Original dwell=1                  |     3.8% ± 11.7% |
| Dwell only                        |               0% |
| Dwell + scaled warm-up, no jitter |               0% |
| Dwell + jitter + scaled warm-up   |    76.7% ± 42.3% |
| Above + v4 persistent bonus       | **93.2% ± 0.4%** |

The experiment established two things very clearly:

1. **Jitter was load-bearing**, not cosmetic.
2. **Dwell+jitter still benefited from v4's persistent characterization mechanism.**

With cost=2, the full combination reached approximately:

**92.0% ± 0.2%**

---

# Phase 16 — The fix did NOT generalize to the beacon

## 21. Negative result

The same dwell/jitter/lead/v4 combination that helped sparse radar was tested on the beacon.

It made the beacon worse.

At `k=1`, `cost=1` approximately:

* existing PRIAware: **17.3% ± 2.3%**
* dwell/jitter/lead fix: **13.6% ± 2.3%**
* persistent version: **13.8% ± 2.6%**

This was not treated as a failure of testing.

It was treated as a **real negative scientific result**.

The mechanism was traced:

* sparse radar benefits from long-term camping and anticipation;
* the beacon's multi-step/burst structure interacts differently with dwell and switching;
* therefore the fix is **scenario-specific**.

---

# Phase 17 — Spatially scanning emitters

## 22. The project then encountered a deeper physical modeling problem

A beam-scanning radar isn't simply:

```text
PRI → pulse → PRI → pulse
```

It has two temporal scales:

```text
slow beam/scan rotation
        +
fast intra-burst PRI
```

A new architecture was therefore created:

`ScanAwarePRIScheduler`

with:

`spatial_scan_emitter.py`

and:

`demo_spatial_scan_emitter.py`

The scheduler attempted to distinguish:

* beam dwell;
* beam revisit / scan period;
* intra-burst PRI.

---

# Phase 18 — Four real bugs in ScanAware

## 23. Mega-burst pollution

A merged group of multiple beam passes could corrupt:

* beam dwell estimate;
* PRI estimate.

Both were fixed by rejecting atypical burst sizes before updating these estimates.

---

## 24. Bad-lock self-reinforcement

A false periodicity estimate could reinforce itself.

This was fixed at more than one level.

---

## 25. Multiplier sweep runaway

The scan-period inference used a set of split multipliers.

Very large multipliers caused separated beam passes to be merged.

Attempts to patch this with period-based exclusion bounds actually produced new deadlocks and sub-harmonic errors.

The eventual solution was simpler:

remove the overly wide multipliers.

The sweep became:

```text
(2.0, 2.5, 3.0, 4.0, 6.0)
```

instead of including `9.0` and `13.0`.

---

# Phase 19 — Cold-start / exploration failure

## 26. Seed 11 exposed another distinct failure

One seed didn't have a fundamentally wrong lock.

Instead, after an early false start, the scheduler simply stopped returning to the important radar band.

It had only scanned it 63 times in 8000 steps.

This was classified as:

**exploration/cold-start starvation**

rather than a periodicity-estimation bug.

Two fixes followed:

### Fix A — confidence synchronization

`scan_confidence` was updated but `self.confidence`, which the selection logic actually used, could remain stale.

That could cause a band's score to effectively become zero.

### Fix B — priority-weighted exploration

Before a reliable periodic lock existed, the UCB exploration bonus was weighted by band priority.

This prevented rare/high-value bands from being starved before they had enough samples to establish a model.

---

## 27. Final ScanAware validation

After those fixes:

| Metric               |        Before |             After |
| -------------------- | ------------: | ----------------: |
| Overall interception |  19.4% ± 1.5% |  **27.7% ± 1.6%** |
| Radar-band capture   | 53.8% ± 24.6% | **51.1% ± 17.9%** |
| Starved seeds        |             1 |             **0** |

The radar capture average didn't increase, but the distribution became much more reliable:

* minimum radar capture increased dramatically;
* seed variability decreased;
* the overall interception gap versus PRIAware shrank considerably.

This closed what was being called **Gap #2: spatial/scan-period modeling**.

---

# Phase 20 — Real `config_169.h5` finally enters the picture

## 28. September 18–20

A real TSRD/config file became available:

`config_169.h5`

It contained:

* **6,668 PDWs**
* **5 transmitters**

This was the point where the project started distinguishing very carefully between:

### synthetic validation

and

### real-file validation.

---

# Phase 21 — The old PDW loader was replaced

## 29. `pdw_source.py`

The data path was cleaned up.

The project discovered that an old dependency on the gated Turing package could cause an import failure, after which the system could silently continue using synthetic data.

That was unacceptable for real-data validation.

The new approach:

```text
h5py
 ↓
data / labels / metadata
 ↓
direct PDW reader
```

And importantly:

> `--h5` became fatal if the real file could not be loaded.

No silent fallback to synthetic data.

---

# Phase 22 — Truth is now derived from the file

The project stopped relying entirely on hardcoded truths such as:

```text
band 1 → 700 us
```

Instead it examined the actual metadata.

This produced:

### Band 0

Real PRI:

**1693.244 µs**

Recovered estimate:

**~1693.2 µs**

with approximately **0.003% error**.

### Band 1

Metadata showed:

```text
100 / 120 / 140 / 160 / 180 µs
```

which corresponds to:

```text
5 / 6 / 7 / 8 / 9 steps
```

and a complete cycle of:

**35 steps = 700 µs**

---

# Phase 23 — The existing PRI estimator fundamentally could not handle stagger

## 30. This was not a tuning problem

The old estimator assumed approximately:

```text
t_i = a + b*n_i
```

i.e. one pulse per period.

A staggered emitter instead does:

```text
5, 6, 7, 8, 9 steps
```

repeatedly.

Therefore the old model had no candidate that represented the actual structure correctly.

This was identified as a **structural limitation**.

---

# Phase 24 — Staggered PRI estimator

## 31. A fallback stagger model was added

The new fallback activates only if the ordinary uniform-PRI estimator cannot lock.

Several bugs appeared while building it.

### Bug 1 — anomaly ceiling

A `4× median` gap threshold was too permissive.

It allowed missed-pulse gaps into the stagger pattern.

Reduced to:

**2× median**

---

### Bug 2 — phase resolution

The first implementation required an almost perfectly contiguous run.

Real data contains missed/irregular pulses.

A new `_resolve_stagger_phase` approach instead compared observed timestamps against candidate repeating grids and chose the phase with the best residual.

---

### Bug 3 — insufficient history

`history_len=30` was adequate for uniform PRI but insufficient for correctly identifying the stagger cycle.

A separate persistent history was introduced.

---

## 32. Result

The real AEGIS staggered emitter was recovered as:

**35.0 steps = 700.0 µs**

with:

**confidence = 1.00**

This was a major milestone because the truth came from the **actual file metadata**, not a synthetic scenario's hardcoded value.

---

# Phase 25 — Full-file validation changed earlier conclusions

## 33. A previous conclusion about v4 was corrected

Earlier, the project had concluded that plain PRIAware couldn't lock band 0 and that persistent PRIAware was required.

That turned out to be an artifact of using a short evaluation window.

At the natural full-file scale:

**plain PRIAware also locked band 0 successfully.**

So this earlier claim was explicitly corrected.

---

# Phase 26 — Full-file narrow-spike problem

## 34. A new important real-data limitation

On the real file:

* BeliefUCB: approximately **97.1%**
* PRIAware / PersistentPRIAware: approximately **67.7%**

The periodicity-aware scheduler could actually become *worse* after finding a highly confident periodic pattern.

Why?

Because its periodicity score produced very narrow temporal spikes.

For a high-duty emitter, ordinary belief tracking already works extremely well.

The periodicity mechanism could therefore overrule a good belief score with a narrow prediction window.

This became one of the project's most important design tensions:

> A periodicity model can be extremely accurate yet still reduce interception if its confidence is converted into an excessively narrow action window.

---

# Phase 27 — `max_blend_confidence`

## 35. Fixed global blending was investigated

A global cap was introduced on how strongly periodicity confidence could dominate the belief component.

Later full-file testing produced:

| `max_blend_confidence` | Band-1 interception |
| ---------------------: | ------------------: |
|                    1.0 |               69.7% |
|                    0.8 |               85.2% |
|                    0.5 |               90.0% |
|                    0.1 |               98.6% |

This made the problem sharper rather than eliminating it.

The synthetic sparse-radar scenario wanted strong periodicity.

The real high-duty band wanted much less periodicity dominance.

Thus:

**one global coefficient cannot optimally represent both regimes.**

That directly motivated the next architectural step.

---

# Phase 28 — Hedge / adaptive expert blending

## 36. `scan_scheduler_v5_hedge.py`

A new scheduler was designed:

`HedgeBlendedPRIAwareScheduler`

Instead of:

```text
fixed belief weight
+
fixed PRI weight
```

each band learns how much to trust two experts:

### Expert A

Belief / Markov model

### Expert B

PRI / periodicity model

Conceptually:

```text
score =
    w_belief × belief_expert
  + w_pri × periodicity_expert
  + exploration
```

with per-band adaptive weights.

The weights use a multiplicative/Hedge-style update.

This was specifically motivated by the fact that:

* some bands are better represented by Markov belief;
* some are genuinely periodic;
* some change behavior;
* a global fixed cap cannot handle all of them.

---

# Phase 29 — An inheritance mistake temporarily resurrected an old bug

## 37. First v5 implementation inherited from v3

The first v5 implementation subclassed:

`PRIAwareScheduler`

instead of:

`PersistentPRIAwareScheduler`.

Multi-seed testing immediately exposed the consequence.

Sparse radar returned to roughly:

**50.0% ± 50.9%**

The exact bimodal signature of the old sample-starvation problem.

This was not a new algorithmic failure.

It was the **old v3 bug accidentally reintroduced by inheritance**.

---

# Phase 30 — v5 rebased onto v4

## 38. v5 was changed to inherit the persistent mechanism

The v5 architecture was rebased so that it retained v4's characterization bonus while adding Hedge blending.

That restored the persistence mechanism.

This was another useful lesson from the project:

> Version numbers were not independent algorithms; each newer version had to preserve the mechanisms that previous validation had established as load-bearing.

---

# Phase 31 — `class_balance_alpha`

## 39. Harmonizing band behavior

A class-balance coefficient was introduced to control how aggressively the learned expert weights moved between the competing behaviors.

The sweep found a sharp threshold.

The chosen value became:

**α = 0.1**

At that setting, the four major reference scenarios were approximately:

| Scenario             | BeliefUCB |  PRIAware |      Hedge v5 |
| -------------------- | --------: | --------: | ------------: |
| Sparse radar         |        0% |    100.0% |     **99.6%** |
| Beacon k=1           |     28.2% |     27.5% |     **28.4%** |
| Beacon k=2           |     54.8% |     53.4% |     **54.0%** |
| Synthetic PDW band 4 |   no lock | 0.79 conf | **0.89 conf** |
| Real band 1          |     99.7% |     69.7% |     **98.0%** |

The result was particularly important because v5 could now retain the sparse-radar behavior while recovering much of the real-data band-1 performance.

---

# Phase 32 — Beacon regression investigated properly

## 40. Another methodological correction

At one point, a difference between v4 and v5 was suspected to be a new v5 regression.

The investigation first found a divergence at a particular time.

But interleaved scheduler execution again contaminated the comparison because both environments shared a global random stream.

The schedulers were then run **separately on identical seeded environments**.

The result showed:

```text
PRIAware v3:              27.5 / 53.4
PersistentPRIAware v4:   25.0 / 45.5
Hedge v5:                 25.0 / 49.0
```

for beacon k=1/k=2.

Therefore:

> v5 did not introduce the main beacon degradation.

v4 itself had already introduced that trade-off relative to v3.

In fact, v5 partially recovered v4's k=2 loss.

This was explicitly corrected in the project history.

---

# Phase 33 — η sweep

## 41. Hedge learning-rate sweep

`eta` was swept over:

```text
1, 2, 4, 6, 8, 12
```

Results:

|     η | Band-4 locks | Real band-1 |
| ----: | -----------: | ----------: |
|     1 |          3/5 |        94.6 |
|     2 |          4/5 |        94.7 |
| **4** |      **5/5** |    **98.0** |
|     6 |          3/5 |        99.6 |
|     8 |          3/5 |        99.6 |
|    12 |          3/5 |        99.6 |

The project retained:

**η = 4**

because it gave the most reliable synthetic band-4 lock behavior while maintaining strong real-data performance.

---

# Phase 34 — Driver integration

## 42. v5 finally became part of the real pipeline

`run_on_turing_dataset.py` was updated so that HedgeBlended could be selected from the CLI.

New parameters included:

```text
--eta
--class-balance-alpha
```

alongside the existing PRI-related configuration.

During this integration, another reproducibility issue was found:

### `--seed` wasn't seeding Python's global `random`

The synthetic environment used NumPy's seeded generator, but scheduler warm-up used Python's global `random`.

Therefore identical invocations could produce different scheduler warm-up orders.

The driver was fixed to seed both appropriately.

Repeated invocations became byte-identical.

---

# Phase 35 — Hedge on the actual real file

## 43. Final real-file result

When the newly integrated Hedge scheduler was actually run through the real-data driver:

**HedgeBlended aggregate interception: ~94.6%**

versus approximately:

**67.7% for PRIAware/PersistentPRIAware**

on the relevant full-file evaluation.

This agreed with the standalone real-band result:

**~98.0% on real band 1**

The difference between 94.6% and 98.0% was explained by the aggregate metric including the other bands / overall file weighting.

---

# Phase 36 — Argparse / real-data infrastructure cleanup

The latest work also substantially cleaned up the real-data infrastructure.

Important changes included:

### `--h5`

Real-file mode became explicit and non-fallback.

### Truth derivation

Truth is derived from metadata where possible instead of blindly using synthetic constants.

### Seed semantics

For real data, multiple seeds represent different scheduler randomness on the **same fixed recording**, not different environments.

### `t0_us`

The replay environment can avoid counting huge pre-recording empty periods as if they were meaningful scheduler observations.

### Window selection

Windows can now be selected from actual active regions of the file.

For example:

```text
band 1:
start ≈ 2.5000 s
duration ≈ 0.2499 s
pulses = 3103
cycles ≈ 357

band 0:
start ≈ 13.0041 s
duration ≈ 0.1422 s
pulses = 42
cycles ≈ 84
```

This made PRI validation much more meaningful.

---

# Phase 37 — Important real-data caveat

## 44. The real recording is itself a scanning receiver recording

One of the latest analyses discovered something subtle.

The file isn't simply:

```text
continuous staring receiver
```

The emitter pulses occur in bursts separated by long gaps.

For band 0:

* actual emitter PRI ≈ **1693 µs**
* but bursts are separated by roughly **2.15 seconds**
* those gaps align with the receiver's own sweep behavior.

This explains why naive prediction metrics can report a huge average error even though the PRI estimate itself is correct.

The scheduler can correctly predict:

```text
pulse within the current burst
```

but:

```text
last pulse of burst
→ predicted next pulse using PRI
```

can be wrong by roughly **2 seconds** because the receiver/emitter observation process has moved into a different scan interval.

This was verified from the raw pulse timing rather than merely inferred.

---

# Phase 38 — Final stagger validation

## 45. The latest staggered-PRI implementation was tested against the real file

The stagger fallback now:

* correctly identifies the repeating stagger pattern;
* tolerates missed pulses;
* resolves phase without requiring an uninterrupted sequence;
* maintains enough history to avoid short-window false patterns.

It recovers the real band-1 pattern as:

```text
5, 6, 7, 8, 9 steps
```

with:

```text
sum = 35 steps
```

and:

```text
35 × 20 µs = 700 µs
```

matching the metadata.

A false-positive protection was also added because dense Markov bands could otherwise look like:

```text
[1, 1]
```

and be incorrectly interpreted as a periodic pattern.

---

# Current architecture

As reconstructed, the project has evolved approximately like this:

```text
                    ┌────────────────────────┐
                    │     PDW Source         │
                    │ synthetic / real H5    │
                    └───────────┬────────────┘
                                │
                                ▼
                       PDW Replay Environment
                                │
                                ▼
                    ┌────────────────────────┐
                    │   Belief / UCB layer   │
                    └───────────┬────────────┘
                                │
                     ┌──────────┴──────────┐
                     │                     │
                     ▼                     ▼
              Markov belief          PRI estimator
                                           │
                                  ┌────────┴────────┐
                                  │                 │
                                  ▼                 ▼
                              Uniform PRI      Staggered PRI
                                  │                 │
                                  └────────┬────────┘
                                           │
                                           ▼
                                  Periodicity model
                                           │
                                           ▼
                              Scan/spatial awareness
                                           │
                                           ▼
                              Adaptive expert blend
                              (Hedge / v5)
                                           │
                                           ▼
                                  Band selection
                                           │
                              ┌────────────┴────────────┐
                              │                         │
                         switch cost                dwell/jitter
                              │                         │
                              └────────────┬────────────┘
                                           ▼
                                      Next scan
```

---

# What is genuinely completed

By the end of the exported history, these are no longer merely ideas:

### Core scheduler

* Belief/UCB scheduler
* PRI-aware scheduler
* Persistent characterization scheduler
* Scan-aware PRI scheduler
* Hedge-blended scheduler

### Receiver realism

* multi-band scanning
* switching cost
* switch lead time
* warm-up dwell
* dwell jitter
* scan-period modeling

### PRI processing

* ordinary PRI estimation
* harmonic correction
* ±1 candidate correction
* staggered PRI estimation
* phase resolution
* missed-pulse tolerance
* false-positive guards

### Robustness

* multi-seed validation
* paired environment comparisons
* seed methodology correction
* reproducibility correction
* multiple ablation studies
* parameter sweeps

### Real-data pipeline

* direct HDF5 reading
* fatal `--h5` failure behavior
* metadata-derived truth
* real-file window selection
* real PRI recovery
* real staggered PRI recovery
* CLI integration

### Documentation / presentation

* project documentation
* presentation material
* talk track
* technical code explanations
* validation scripts
* result CSVs

### Code packaging

The final Claude session reported a package containing:

**36 project files**

consisting of Python scripts and result CSVs, excluding your original `config_169.h5`.

---

# What is still genuinely open

This is where it's important to distinguish **unfinished work** from things that were repeatedly investigated and actually closed.

## 1. Pfa / sensitivity / noise-floor model

Still fundamentally unfinished.

The project does not yet have a realistic:

```text
Pfa
↓
noise floor
↓
detection threshold
↓
Pd / false alarm behavior
```

model.

This is arguably the largest missing piece relative to the actual EW/ESM problem statement.

---

## 2. Full receiver/interception realism

The real `config_169.h5` validation is valuable, but the project discovered that it is itself a **scanning observation**, not a clean stare-mode ground truth environment.

So a true:

> receiver stares at selected band → detects or misses emitter

evaluation dataset would be cleaner for evaluating scheduler interception.

The project repeatedly identified obtaining/creating a **stare-mode recording** as the next useful step.

---

## 3. `prediction_accuracy_metrics.py`

The prediction metrics infrastructure exists, but the real-data integration was still being completed/refined.

The important metrics are:

* `% correct predictions`
* average intercept-time error

and the real-file analysis already showed why naive average prediction error can be misleading when scan gaps are present.

---

## 4. Larger theoretical upgrades

Still not fully implemented:

* **Whittle-index policy**
* **real RL agent**

  * contextual bandit / DQN / PPO type approaches
* **V-measure / HDBSCAN comparison**

  * especially relevant to TSRD's deinterleaving-oriented evaluation

These are larger research extensions rather than basic missing pieces.

---

# The biggest lessons the project discovered

These are arguably more important than the raw list of files.

### 1. Single-seed results are dangerous

The original 100% result looked spectacular.

Multi-seed testing revealed it was a coin flip.

This drove much of the project's validation philosophy.

---

### 2. Fixes can create different failures

Examples:

* dwell fixed switching but introduced parity aliasing;
* jitter fixed parity aliasing;
* persistent characterization fixed sample starvation but cost beacon performance;
* periodicity fixed sparse radar but hurt dense/high-duty bands;
* scan awareness improved radar understanding but initially reduced overall interception;
* Hedge recovered some of those conflicts.

---

### 3. Some "algorithm failures" are actually resolution failures

The band-collision case demonstrated:

```text
two emitters
      ↓
same coarse frequency bin
      ↓
scheduler cannot separate them
```

No amount of smarter scheduling solves that particular problem.

---

### 4. Prediction accuracy isn't the same as interception accuracy

A scheduler can estimate the PRI correctly while still missing pulses because:

```text
prediction
     ≠
receiver readiness
```

The switch-cost experiment demonstrated this directly.

---

### 5. Real data changed the conclusions

The real `.h5` data exposed things the synthetic environment didn't:

* staggered PRI;
* receiver scan structure;
* missed pulses;
* frequency-agile emitters;
* dead bands;
* narrow-spike scoring problems;
* burst boundaries;
* different meanings of seed variation.

That is why the project eventually became much more than "UCB + PRI."

---

# Current state — September 24, 2026

The latest state represented by these exports is approximately:

```text
                         PROJECT
                            │
                            ▼
                 ┌────────────────────┐
                 │ HedgeBlended v5    │
                 │ + persistent v4    │
                 └─────────┬──────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
          UCB/belief      PRI         scan-aware
             │             │             │
             │       ┌─────┴─────┐       │
             │       ▼           ▼       │
             │    fixed PRI   stagger    │
             │                           │
             └────────────┬──────────────┘
                          ▼
                    adaptive blend
                          │
                          ▼
                 receiver constraints
                 ├─ switch cost
                 ├─ switch lead
                 ├─ dwell
                 └─ jitter
                          │
                          ▼
                    real H5 path
                          │
                          ▼
                  config_169.h5
```

And the most significant validated real-data result in the latest history is:

**HedgeBlended ≈94.6% aggregate interception through the real-data driver**, with **≈98.0% on the real band-1-specific measurement**, while the earlier PRIAware/PersistentPRIAware aggregate was around **67.7%**.

But that should **not** be presented as "the project is finished." The real-data analysis simultaneously uncovered the remaining modeling gaps, especially Pfa/noise modeling and the distinction between a scanning recording and a true stare-mode receiver evaluation.

---

## The actual project progression, compressed to one line

**Belief scheduler → UCB exploration → PRI prediction → persistent characterization → robust multi-seed validation → beacon/plateau modeling → harmonic correction → switch-cost modeling → anticipatory switching → dwell+jitter warm-up → scan/spatial awareness → real H5 validation → staggered PRI → adaptive Hedge blending → real-data integration.**

# SIH26055 — Chronology Addendum from the New Markdown

## 46. Sept. 21 — Alternative scheduling ideas were evaluated

The project briefly considered **partitioned round-robin** and **bipartite/assignment scheduling** combined with the existing Markov confidence strategy.

The conclusion was:

* Markov confidence was **not actually new** because `BeliefUCBScheduler` already provided the 2-state per-band Markov belief model.
* Partitioned round-robin could improve exploration/warm-up allocation, but the project had already encountered the fundamental periodicity problem: a rigid schedule can become permanently blind because of the relationship between scan period and emitter period.
* Therefore, if partitioned RR were ever used, **jitter would be essential** rather than optional.
* Bipartite/Hungarian assignment only becomes genuinely useful if retuning cost depends on **which frequency a channel moves to**, rather than the existing flat `switch_cost_steps`.

So neither was immediately adopted. 

---

## 47. Sept. 21 — New algorithmic ideas were brainstormed

Several possible extensions were identified:

1. **Hidden Semi-Markov Model (HSMM)**
   Replace the memoryless 2-state Markov model with explicit state-duration modeling.

2. **Hedge/exponential-weights expert blending**
   Replace several hand-tuned constants with adaptive per-band trust between belief and PRI experts.

3. **AoA/amplitude co-band separation**
   Use previously unused PDW fields to distinguish emitters that fall into the same coarse frequency bin.

4. **CUSUM/Bayesian changepoint detection**
   Detect when a previously learned PRI becomes stale.

5. **Explicit intercept-time-error optimization**
   Make the scheduler directly optimize one of the PS's stated figures of merit rather than only measuring it afterward.

6. **Kalman PRI/phase tracking**
   Track periodicity dynamically rather than relying on static jitter estimates.

Of these, Hedge blending was selected as the most realistic high-value addition within the available time. 

---

# 48. Sept. 21 — The remaining codebase debt was closed

A review of the codebase showed that most of the supposedly unfinished work was **already implemented**.

The actual remaining CLI gap was:

* `min_cycles`
* `max_blend_confidence`

Both existed internally in the PRI schedulers but were not exposed through `run_on_turing_dataset.py`.

They were wired into the CLI and verified to have real behavioral effects rather than merely being accepted arguments.

A separate existing bug was also discovered: an unescaped `%` in an argparse help string caused `--help` itself to crash. That was fixed. 

This is an important addition to the earlier reconstruction because it establishes that, by Sept. 21, the codebase was already much further along than some of the older notes suggested.

---

# 49. Sept. 21 — Real-data regression became the next major target

The full `config_169.h5` run showed:

* **BeliefUCB: 97.1%**
* **PRIAware: 67.7%**
* **PersistentPRIAware: 67.7%**

The problem was traced almost entirely to **Band 1**, which contained 6,521 of the 6,668 PDWs.

BeliefUCB captured approximately **99.7%** of Band 1, while PRIAware/PersistentPRIAware captured only **69.7%**.

An important clarification emerged:

> v4's persistent-characterization mechanism was not helping on this file.

That was **not a v4 bug**. Band 1 was already massively characterized, so the mechanism designed to rescue sample-starved bands simply had nothing to do.

The real problem was the PRI layer's narrow scoring spike overriding a very strong Markov belief signal. 

---

# 50. Sept. 21 — The `max_blend_confidence` trade-off was quantified

The real-file experiment showed:

| `max_blend_confidence` | Band-1 interception |
| ---------------------: | ------------------: |
|                    1.0 |               69.7% |
|                    0.8 |               85.2% |
|                    0.5 |               90.0% |
|                    0.1 |               98.6% |

This produced a much sharper version of an existing project lesson:

**A perfectly correct periodicity prediction can still produce a worse scheduling decision.**

The PRI estimator could be correct to the microsecond, yet the resulting narrow action window could hurt a high-duty emitter whose Markov belief already provided an excellent estimate.

The conflict became:

* sparse periodic emitters want stronger PRI trust;
* dense/high-duty emitters want belief to dominate.

A single global coefficient could not cleanly satisfy both.

That motivated the Hedge architecture. 

---

# 51. Sept. 21–22 — Hedge v5 was designed

The new scheduler was named:

**`HedgeBlendedPRIAwareScheduler`**

in:

`scan_scheduler_v5_hedge.py`

The intended structure was:

* Expert A = existing Markov belief score
* Expert B = periodicity/PRI score
* each band receives its own trust weights
* weights are updated online using multiplicative/exponential weighting
* a floor prevents an expert from being permanently eliminated
* `max_blend_confidence` is no longer the main mechanism controlling PRI trust

The conceptual goal was significant:

> Replace several global hand-tuned constants with a learned, per-band trust relationship.

The initial implementation used squared-error expert losses. 

---

# 52. Sept. 22 — First Hedge implementation failed two major references

The initial single-seed results were:

| Reference    |        PRIAware |       Hedge v5 |
| ------------ | --------------: | -------------: |
| Sparse radar |    100.0% radar |    99.6% radar |
| Beacon k=1   |           27.5% |          16.3% |
| Beacon k=2   |           53.4% |          26.7% |
| PDW Band 4   | 0.79 confidence | failed to lock |
| Real Band 1  |           69.7% |          75.6% |

The real-data case improved, but the synthetic references exposed a fundamental problem with the loss function.

---

# 53. Sept. 22 — First Hedge bug: class imbalance before PRI lock

When the PRI expert had **not locked**, its prediction was exactly zero.

With squared-error loss:

* most observations are OFF;
* predicting zero therefore looks extremely good;
* the uninformative "always predict zero" expert accumulated less loss than the calibrated belief expert.

This was the classic **class-imbalance / majority-predictor problem**.

The immediate fix was to prevent an **unlocked PRI expert** from participating in Hedge weight updates.

That recovered:

* sparse radar: ~99.6%
* beacon k=1: 28.4%
* beacon k=2: 54.0%
* real Band 1: 99.6%

But synthetic PDW Band 4 still failed to lock.  

---

# 54. Sept. 22 — Second Hedge bug: class imbalance after PRI lock

Further instrumentation revealed a subtler version of the same problem.

Even after a periodic emitter was correctly locked:

* OFF observations vastly outnumbered ON observations;
* belief and PRI experts were both penalized on those OFF observations;
* the small advantage of belief on OFF predictions accumulated over many more samples than the PRI expert's rare ON wins.

This caused Hedge to gradually suppress a legitimately useful PRI expert.

The resulting redistribution indirectly affected another band's scan timing.

The conclusion was that the problem was not simply "starvation"; it was the **loss function itself**.

---

# 55. Sept. 22 — Class-balanced Hedge loss fixed Band 4

The next patch introduced inverse-frequency class balancing.

Results:

| Reference    | PRIAware | Hedge v5 patched |
| ------------ | -------: | ---------------: |
| Sparse radar |   100.0% |            99.6% |
| Beacon k=1   |    27.5% |            28.6% |
| Beacon k=2   |    53.4% |            54.2% |
| PDW Band 4   |     0.79 |         **0.89** |
| Real Band 1  |    69.7% |        **94.7%** |

So all four references were brought back to at least the v3 level.

But Band 1 had fallen from the unpatched Hedge result of 99.6% to 94.7%.

That created the next optimization problem. 

---

# 56. Sept. 22 — `class_balance_alpha` harmonized the two regimes

Instead of choosing between:

* no class balancing (`α = 0`)
* full class balancing (`α = 1`)

a linear interpolation parameter was introduced:

**`class_balance_alpha`**

The sweep revealed a sharp nonlinear threshold:

* α = 0.02 → Band 4 failed
* α = 0.05 → Band 4 fully recovered
* α = 0.10 → Band 4 remained fixed while preserving most of Band 1 performance
* α = 1.0 → unnecessary cost to Band 1

The default was therefore changed to:

**`class_balance_alpha = 0.1`**

Final single-seed harmonized result:

| Reference    |  Hedge v5 α=0.1 |
| ------------ | --------------: |
| Sparse radar |           99.6% |
| Beacon k=1   |           28.4% |
| Beacon k=2   |           54.0% |
| PDW Band 4   | 0.89 confidence |
| Real Band 1  |           98.0% |

This was an important methodological result:

> The useful correction did not require full balancing; a small coefficient crossed a threshold that fixed the low-duty case while imposing only a small cost on the high-duty case. 

---

# 57. Sept. 23 — Multi-seed testing exposed a hidden v5 inheritance bug

This was one of the most important additions from the new Markdown.

The α=0.1 result had initially been tested primarily with **one seed**.

A 30-seed run showed:

```text
PRIAware v3:       50.0% ± 50.9%
Hedge v5:          50.0% ± 50.8%
```

That enormous variance was the familiar sample-starvation coin flip.

The reason:

**v5 inherited from `PRIAwareScheduler` (v3), not `PersistentPRIAwareScheduler` (v4).**

Therefore, v5 had accidentally reintroduced a problem that v4 had already solved.

The single seed used throughout the earlier v5 development happened to be a "lucky" seed and hid the problem.

This is a major chronology correction: **single-seed validation had been insufficient to establish v5's robustness.** 

---

# 58. Sept. 23 — v5 was rebased onto v4

The Hedge scheduler was modified to inherit the persistent-characterization mechanism from v4.

After the rebase:

* sparse radar became **93.4% ± 0.6%**
* the coin-flip disappeared
* PDW Band 4 remained healthy, with **17/20** locks and ~0.88 mean confidence

However, the rebase brought back v4's known characterization trade-off on the beacon scenario.

The key later correction was important:

**The beacon cost was not actually a new v5 regression.**

Direct isolated testing showed:

```text
                 k=1     k=2
PRIAware v3      27.5%   53.4%
Persistent v4    25.0%   45.5%
Hedge v5         25.0%   49.0%
```

Thus:

* v4 itself already paid this beacon cost;
* v5 inherited it;
* v5 actually recovered part of v4's k=2 loss.

The earlier claim that v5 had introduced the beacon regression was explicitly corrected. 

---

# 59. Sept. 23 — `eta` was finally swept

The Hedge learning rate was tested at:

**1, 2, 4, 6, 8, 12**

Results included:

|     η | Band-4 locks | Real Band 1 |
| ----: | -----------: | ----------: |
|     1 |          3/5 |       94.6% |
|     2 |          4/5 |       94.7% |
| **4** |      **5/5** |       98.0% |
|     6 |          3/5 |       99.6% |
|     8 |          3/5 |       99.6% |
|    12 |          3/5 |       99.6% |

The project retained:

**η = 4**

because it provided the most reliable Band-4 locking while maintaining strong real-data performance.

This also demonstrated another recurring project pattern: increasing a parameter could improve one metric while reducing reliability elsewhere. 

---

# 60. Sept. 23–24 — Hedge was integrated into the main driver

`run_on_turing_dataset.py` was updated to expose:

* `--eta`
* `--class-balance-alpha`

and to run HedgeBlended alongside the established schedulers.

During this process another reproducibility bug was found:

**`--seed` did not seed Python's global `random` module.**

The synthetic environment was deterministic, but scheduler warm-up used `random.shuffle()`, which was still drawing from OS entropy.

That caused identical invocations to produce different results.

The fix seeded Python's `random` as well.

Repeated invocations subsequently became **byte-identical**.

The integrated real-file result was approximately:

**HedgeBlended = 94.6% aggregate interception**

versus:

* BeliefUCB = 97.1%
* PRIAware/Persistent = 67.7%

The 98.0% Band-1 result remained the more specific per-band figure. 

---

# 61. Sept. 24–25 — Codebase consolidated

The working codebase was eventually consolidated into a much more accurate map.

The old record of:

> 18 files / ~3,930 lines

was found to be stale.

The actual codebase at that point was:

**32 files / ~7,848 lines**

and later the delivered package contained **36 files plus 4 CSVs**.

The project history was also deliberately compressed into a more reliable structural record instead of retaining every debugging step. 

---

# 62. Sept. 25 — Beacon received proper 30-seed validation

The earlier single-seed beacon conclusions were finally subjected to the project's established multi-seed discipline.

The important findings:

* v4's beacon cost was real, not a single-seed artifact.
* v4 lost to v3 on **24/30 seeds for k=1** and **26/30 seeds for k=2**.
* v5 generally tracked v4 and matched or beat it on most seeds.
* v5 beat v4 on **22/30 seeds for k=1** and **21/30 for k=2**.
* Mean differences between v4 and v5 were small, ≤ ~0.3 percentage points.
* However, v4/v5 showed roughly **double the variance** of v3.

So the earlier correction became much stronger:

**the beacon cost belongs to v4's characterization mechanism, not to Hedge itself.**

---

# 63. Sept. 25 — Gap #2: spatial scan awareness was re-verified

The old `scan_aware_scheduler.py` work from around Sept. 14 was revisited.

The validation initially looked slow because:

* 4 schedulers
* 10 seeds
* 2 full 8,000-step episodes

meant roughly 80 runs.

The team therefore isolated `ScanAwarePRIScheduler` and smaller runs before interpreting the behavior.

This closed the loop on the previously "mid-debug" spatial-scan work.

---

# 64. Sept. 26 — Gap #1: Pfa/noise/sensitivity modeling was finally implemented

A separate `noise_model.py` layer was built to add:

* receiver noise
* SNR
* Pd
* Pfa
* sensitivity

without modifying the shared scheduler implementation.

An initial validation exposed a serious bug:

SNR values of 6 dB, 0 dB and −3 dB were producing identical empirical results despite theoretical Pd values being radically different.

That inconsistency was caught rather than silently accepted.

This eventually became part of the project's closure of the original PS gaps.

---

# 65. Sept. 27 — Whittle-index work began

The project then tackled one of the major theoretical extensions:

**Whittle-index scheduling**

The goal was to compare the heuristic stack against a theoretically motivated restless-bandit policy.

The existing 2-state Markov belief model was mapped to the known dynamic-channel restless-bandit formulation.

Rather than risk copying a complicated piecewise closed-form formula incorrectly, the implementation used a **numerical Whittle-index solver**.

The solver was validated against the known analytical anchor:

$$
W(p_{11}) = p_{11}
$$

and passed monotonicity/self-tests. 

---

# 66. Sept. 27–28 — WhittleIndexScheduler was implemented

`WhittleIndexScheduler` reused the existing `BeliefUCBScheduler` belief-learning machinery and replaced its myopic score with a periodically recomputed Whittle-index lookup.

The first results showed:

* good behavior on genuinely Markov channels;
* poor behavior on periodic emitters.

The team checked whether the problem was simply stale index recomputation.

It wasn't.

The deeper diagnosis showed that the scheduler was correctly valuing persistent Markov bands **but applying a Markov model to periodic emitters where the Markov assumption was false**.

The band-level scan counts demonstrated this directly:

| Band | Type           | BeliefUCB | Whittle |
| ---- | -------------- | --------: | ------: |
| 1    | Markov         |      1340 |    1661 |
| 4    | Markov         |       211 |     906 |
| 2    | Periodic       |       606 |      28 |
| 6    | Periodic/agile |      1025 |     484 |

So the result was not an implementation bug.

It was a **model-assumption limitation**:

> Whittle's optimality applies to the model it assumes; if the emitter violates the Markov assumption, the index can be optimal for the wrong model.

That is a particularly useful result for the project because it provides a principled comparison against the heuristic architecture rather than simply saying "Whittle performed worse." 

---

# 67. Sept. 28 — Final Whittle comparison

The four-reference comparison became:

| Reference    |   BeliefUCB |      PRIAware |     Hedge v5 |         Whittle |
| ------------ | ----------: | ------------: | -----------: | --------------: |
| Sparse radar | 0.0 / 87.2% | 100.0 / 79.4% | 99.6 / 79.2% | 0.0 / **88.6%** |
| Beacon k=1   |       28.2% |         27.5% |        26.4% |           24.2% |
| Beacon k=2   |       54.8% |         53.4% |        50.7% |           52.2% |
| Real Band 1  |       99.7% |         69.7% |        98.0% |           93.7% |

Whittle also took roughly **199 seconds** on the real file, compared with roughly 10–50 seconds for the other schedulers.

So the Whittle experiment produced two concrete findings:

1. It can exploit persistence very effectively on genuinely Markov emitters.
2. It is computationally heavier and structurally weaker when the environment contains periodic/staggered/agile emitters.

The Whittle implementation therefore became a **validated alternative/benchmark**, rather than replacing HedgeBlended. 

---

# 68. Sept. 28 — The project asked: "Have the heuristics actually plateaued?"

Instead of simply declaring them plateaued, a **genie/oracle ceiling** was implemented.

The oracle has perfect knowledge of the true transmitter state before selecting bands.

That establishes a defensible upper bound on what any scheduler could capture under the given environment.

For the real `config_169.h5`:

* oracle ceiling ≈ **100%**
* BeliefUCB = **97.1%**
* HedgeBlended = **94.6%**

So the remaining gap is only a few percentage points.

The synthetic sparse-radar/beacon cases had much larger gaps, but the oracle has perfect instantaneous knowledge, meaning part of those gaps may be fundamentally unreachable by any realistic online scheduler.

This resulted in a more careful conclusion:

**The heuristics appear close to a practical plateau on the real data, but the synthetic cases do not prove that all possible algorithmic headroom has disappeared.**

Held-out real files were identified as the best remaining test of generalization. 

---

# 69. Sept. 28–29 — `run_all.py` / `run_on_turing_dataset.py` became the final integration problem

This is the **latest chronology point in the new Markdown**.

The project discovered that the algorithmic work was largely complete, but the execution suite was not.

The issue was that several scripts:

* hardcoded `config_169.h5`;
* did not accept a common `--h5`;
* therefore could not reliably be driven by `run_all.py`.

The scripts were classified into three groups.

### Real-data scripts needing `--h5`

* `deinterleave_hdbscan.py`
* `diagnose_fullfile_regression.py`
* `oracle_ceiling.py`
* `sanity_check_hedge.py`
* `sweep_class_balance_alpha.py`
* `sweep_eta.py`
* `validate_hedge_blend.py`

### Scripts that only needed inclusion in `run_all.py`

* `whittle_index.py`
* `multiseed_alpha_default.py`
* `multiseed_beacon_v5.py`
* `noise_model_demo.py`

### Correctly excluded

* `scan_scheduler_whittle.py`
* `noise_model.py`

because they are library modules without standalone `__main__` execution.

The seven real-data scripts were patched, syntax-checked, and functionally tested. The renamed-HDF5 test confirmed that the new override actually loaded the supplied file and reproduced the established:

**97.1% / 67.7% / 94.6%**

real-file results.

`run_all.py` was then being updated to include the appropriate scripts and H5 mappings. The Markdown ends while that final integration work is still being completed. 

---

# The revised project progression

So, incorporating this Markdown, I would now represent the **full high-level evolution** as:

```text
Problem formulation
        ↓
BeliefScheduler
        ↓
BeliefUCB / v2
        ↓
PRI-aware scheduler / v3
        ↓
Multi-seed failures discovered
        ↓
Persistent characterization / v4
        ↓
Warm-up + dwell + jitter + switching fixes
        ↓
Spatial / ScanAware scheduler
        ↓
Real TSRD / config_169.h5 pipeline
        ↓
Staggered PRI detection
        ↓
Real-data narrow-spike failure discovered
        ↓
max_blend_confidence trade-off
        ↓
HedgeBlended / v5
        ↓
Class-imbalance bug #1
        ↓
Class-imbalance bug #2
        ↓
class_balance_alpha
        ↓
α = 0.1
        ↓
30-seed validation exposes v5 → v3 inheritance mistake
        ↓
v5 rebased onto v4
        ↓
Beacon trade-off correctly attributed to v4
        ↓
η sweep → η = 4
        ↓
Driver integration + reproducibility fix
        ↓
Noise / Pfa / Pd / sensitivity model
        ↓
Gap #2 spatial-scan re-verification
        ↓
Whittle-index numerical implementation
        ↓
Whittle model-mismatch diagnosis
        ↓
Genie/oracle ceiling analysis
        ↓
Practical heuristic plateau assessment
        ↓
FINAL INTEGRATION:
run_all.py + run_on_turing_dataset.py
```

## And the most important new lessons

The new Markdown adds several lessons that I think should become part of the **official reconstruction**, not just footnotes:

### 1. Single-seed validation repeatedly lied

The v5 seed-11 results looked excellent.

Thirty seeds revealed a **50/50 failure mode** that the single seed completely hid. 

This reinforces:

> **A single successful run is not evidence of robustness.**

### 2. Loss functions can create their own intelligence

The Hedge system wasn't merely learning which expert was better.

Its squared-error loss initially taught it that:

> "Always predict OFF" is an excellent expert.

That was mathematically reasonable under the loss but completely wrong for the scheduling objective.

So the project learned:

> **The learning objective itself has to reflect the operational decision problem.**

### 3. Fixing one failure can resurrect an older trade-off

Rebasing v5 onto v4 solved the sparse-radar coin flip but inherited v4's characterization cost on the beacon.

This is why the chronology should explicitly distinguish:

**new regression vs inherited historical trade-off.**

### 4. Better prediction ≠ better interception

The real Band-1 experiment is probably one of the strongest examples of this.

PRI prediction became extremely accurate, yet trusting that prediction too aggressively **reduced interception**.

This is the broader principle:

> **Prediction quality and action quality are separate optimization problems.**

### 5. "Optimal" algorithms are only optimal under their model

The Whittle experiment is particularly valuable here.

Whittle performed exactly as expected when the environment behaved like its assumed Markov model, but periodic/agile emitters violated that assumption.

Thus:

> **Model mismatch can defeat theoretical optimality.**

### 6. The project is now much more than "we built a scheduler"

The actual research story has evolved into:

> **We progressively discovered that EW scan scheduling is a problem of allocating limited observations under uncertainty, partial observability, emitter heterogeneity, periodic structure, receiver constraints, and model mismatch.**

And the architecture evolved in response to those failures rather than being a collection of arbitrary algorithms.

---

## One important correction to our previous reconstruction

The previous reconstruction stopped around the **Hedge v5 / class-balance / η / integrated real-data result**.

This new Markdown means the previous "current state" should now be updated to:

**Hedge v5 is no longer merely a proposed/partially validated scheduler.**

It went through:

* class-imbalance fixes,
* α sweep,
* multi-seed testing,
* v4 rebase,
* beacon validation,
* η sweep,
* driver integration,
* reproducibility repair,
* real-file validation,
* Whittle comparison,
* oracle-ceiling analysis.

And as of the end of this Markdown, the **remaining engineering task is primarily execution-suite integration** — making `run_all.py` and `run_on_turing_dataset.py` actually run the complete appropriate set of experiments consistently. 

So yes: **this Markdown materially extends the reconstruction, rather than merely duplicating what we already had.**


Yes. I went through the **three newly uploaded Markdown exports** and extracted the chronology that comes *after* the previous reconstruction. There is substantial new material, especially from **September 29 through October 2**, including the first serious held-out evaluation, the move from 8 → 36 bands, the realization that the PRI layer was not generalizing, and the Whittle optimization work.

Below is the **append-ready continuation**. I’m continuing the numbering from the previous chronology rather than rewriting the earlier sections.

---

# SIH26055 — Chronology Addendum

## 70. Sept. 29–30 — First complete codebase audit

The project reached a major consolidation point.

The final codebase snapshot contained approximately:

* **40 Python files**
* approximately **9,750 lines**
* 4 result CSVs

The complete codebase was syntax-checked.

The major components were exercised where the sandbox permitted:

* sparse-radar invariant
* synthetic PDW driver
* Whittle-index self-test
* noise-model demo
* HedgeBlended
* PRIAware
* PersistentPRIAware
* BeliefUCB

The synthetic headline at this stage was:

* PRIAware sparse radar: **267/267 pulses = 100%**
* PRI estimate: **12 steps**
* confidence: **1.00**
* synthetic driver:

  * BeliefUCB: **17.3%**
  * PRIAware: **22.4%**
  * PersistentPRIAware: **22.5%**
  * HedgeBlended: **24.9%**

Whittle's mathematical self-tests also passed:

* \(W(p_{11})=p_{11}\)
* monotonicity check passed.

The noise model likewise produced internally consistent theoretical/empirical \(P_d\) results.

However, the real HDF5 validation could not be rerun in that environment because the Turing `.h5` files and `h5py` were unavailable. 

---

## 71. Sept. 30 — The real-data results changed the interpretation

The first serious held-out evaluation exposed a major distinction between:

> **the scheduler architecture working**

and

> **the tuned advanced scheduler generalizing.**

The six real files showed:

* BeliefUCB beating RoundRobin across all six files.
* Rates roughly spanning **31–97%** versus approximately **8–13%** for RoundRobin under the earlier 8-band configuration.
* The tuned `config_169` Validation file was a major outlier:

  * BeliefUCB: **97.1%**
  * HedgeBlended: **94.6%**

Held-out Test results were much lower:

| Dataset  | BeliefUCB |  PRIAware |     Hedge |   Whittle | ScanAware |
| -------- | --------: | --------: | --------: | --------: | --------: |
| Test 169 |     56.8% |     56.8% |     56.8% |     50.6% |     54.4% |
| Test 57  |     60.4% |     56.5% |     71.1% |      8.9% |      4.9% |
| Test 1   |     60.0% |     61.3% |     59.0% |     61.2% |     51.6% |
| **Mean** | **59.1%** | **58.2%** | **62.3%** | **40.2%** | **37.0%** |

This changed the project's interpretation of the advanced layers.

Hedge's apparent +3 percentage-point advantage was largely attributable to **Test/config_57**, which contained only 761 pulses and one seed.

The `eta` and `class_balance_alpha` tuning performed on the development file therefore did not provide convincing evidence of generalization. 

---

## 72. Sept. 30 — “Prediction is not interception” became a generalization problem

The real-data results reinforced an earlier lesson.

The PRI machinery could recover a period accurately on the development file, but this did not translate into reliable interception on unseen files.

The situation became:

* development file:

  * staggered PRI recovered correctly
  * approximately **700 µs**
  * essentially zero reported period error
* Test/config_57:

  * plausible truths around **750 µs, 2200 µs and 120 µs**
  * no PRI lock
* other held-out files:

  * generally no useful PRI lock.

The likely structural explanation was **band collision**.

At 8 bands, multiple emitters could occupy the same band. A band-level PRI estimator is then being asked to infer a single periodic process from an interleaved mixture.

This was explicitly treated as a **hypothesis**, not a proven causal explanation. 

---

## 73. Sept. 30 — The “camp on the busiest band” problem was discovered

A more important evaluation issue emerged.

Overall interception percentage could be dominated by whichever band happened to contain the most pulses.

For example, on Validation/config_169, BeliefUCB could capture almost all activity from the dominant band while capturing essentially none of the actual rare radar bands.

Therefore:

> High aggregate interception does not necessarily mean good interception of every emitter.

This motivated the idea of reporting:

* per-band capture
* per-emitter capture
* mean capture over labeled emitters
* rather than relying only on aggregate interception.

This became one of the most important methodological corrections to the project. 

---

## 74. Sept. 30 — The real-data runner was made independent of synthetic experiments

A dedicated:

`run_real_data.py`

was created.

Its purpose was explicitly:

> **real HDF5 data only — no synthetic fallback.**

It accepted an array such as:

```python
H5_FILES = [
    "Datasets/Turing datasets/Validation/config_169.h5",
    # ...
]
```

and processed the files sequentially.

For each file it could run:

* RoundRobin
* Random
* BeliefUCB
* PRIAware
* PersistentPRIAware
* ScanAwarePRI
* HedgeBlended
* WhittleIndex
* genie/oracle ceiling

It also produced:

* overall results
* oracle gap
* per-band capture
* PRI-lock diagnostics
* HDBSCAN/V-measure information
* CSV summaries.

Failures were deliberately recorded rather than silently ignored. 

---

## 75. Sept. 30 — Multi-file `run_all.py` was repaired

`run_all.py` was upgraded to accept multiple HDF5 files:

```text
--h5 file1.h5 file2.h5 ...
```

It could also:

* run H5-only suites
* select subsets of scripts
* create per-file logs
* distinguish failed files from skipped files.

During this work, two previously unnoticed bugs were found.

### Bug 1 — `oracle_ceiling.py`

`import sys` had accidentally been placed inside the module docstring.

Therefore:

```python
sys
```

was never actually imported.

This was fixed.

### Bug 2 — `sanity_check_hedge.py`

An explicit failed `--h5` load could silently become:

```text
SKIPPED
```

while still returning exit code 0.

That meant a runner could incorrectly report the test as successful.

The behavior was changed so an explicitly requested real-data test fails loudly when the HDF5 input cannot be loaded.

This was an important reproducibility/evaluation-harness correction. 

---

## 76. Sept. 30 — Receiver/channel count was made explicit

The user asked how many receivers were actually listening simultaneously.

The answer was:

> **One channel.**

At the original configuration:

```text
K_CHANNELS = 1
N_BANDS = 8
```

every algorithm selected exactly one band per step.

That established the meaning of the earlier RoundRobin ≈12.5% result:

$$
\frac{1}{8}=12.5\%
$$

The oracle was therefore also a **k=1 oracle** rather than an unrestricted omniscient receiver.

The codebase supported multiple simultaneous channels, motivating a controlled:

```text
k = 1
k = 2
k = 4
```

experiment. 

---

## 77. Sept. 30 — k=1 / k=2 / k=4 sweep introduced

`run_real_data.py` was rewired so every file could be evaluated sequentially at:

```python
K_VALUES = [1, 2, 4]
```

For each \(k\), the runner calculated:

* scheduler performance
* oracle ceiling
* oracle gap
* per-band capture
* PRI diagnostics
* aggregate summaries.

CSV outputs gained a `k` column.

This made the receiver-resource trade-off explicit instead of mixing hardware capability with algorithmic performance. 

A critical methodological rule was established:

> Increasing \(k\) naturally raises raw interception, so improvement in raw percentage cannot automatically be interpreted as algorithmic improvement.

For example, RoundRobin itself improves as more simultaneous channels are allowed.

Therefore future comparisons should include:

* gain over RoundRobin
* gap to oracle
* performance at the same \(k\)

rather than raw interception alone.

---

## 78. Sept. 30 — 8 bands was reconsidered

The original 8-band configuration became questionable.

The real recording reportedly used a **36-dwell sweep**.

At 8 bands, the modeled frequency width was roughly:

$$
\frac{17.5\text{ GHz}}{8}\approx2.19\text{ GHz}
$$

per band.

That was considered a generous instantaneous-bandwidth assumption.

Using 36 bands instead gives roughly:

$$
\frac{17.5\text{ GHz}}{36}\approx486\text{ MHz}
$$

per band.

The project therefore moved toward **36 bands as the most defensible real-data configuration**, because it matched the recorded receiver's sweep channelization rather than being chosen purely for performance. 

---

## 79. Sept. 30 — 36-band configuration introduced

The real-data entry points were changed to use:

```text
N_BANDS = 36
```

while synthetic scenarios remained at 8 bands because their hard-coded invariants were defined around the 8-band synthetic setup.

Specifically:

* `run_real_data.py` → 36
* `deinterleave_hdbscan.py` → 36
* H5 mode of `run_on_turing_dataset.py` → 36
* H5 mode of `prediction_accuracy_metrics.py` → 36

The synthetic/regression suites remained at 8.

This distinction was important because blindly changing every script to 36 would invalidate synthetic expectations such as:

* radar being on a specific band
* known synthetic PRI bands
* existing expected percentages.

The 36-band runner was tested end-to-end using a synthetic stand-in. 

---

## 80. Sept. 30 — Evaluation at 36 bands changed the interpretation again

With 36 bands:

* RoundRobin becomes approximately:

$$
\frac{1}{36}\approx2.8\%
$$

for \(k=1\),

and approximately:

$$
\frac{4}{36}\approx11.1\%
$$

for \(k=4\).

Therefore the old 8-band numbers could **not** be compared directly to the new 36-band results.

The project adopted the rule:

> Every reported percentage must state both \(N_{\text{bands}}\) and \(k\).

This prevented a later 36-band result from being accidentally compared with an earlier 8-band result as though the hardware assumptions were identical.

---

# October 1 — Held-out evaluation becomes the central question

## 81. Oct. 1 — The six-file, 36-band report was critically reviewed

The new 36-band report changed the evaluation framing again.

The test harness itself appeared internally consistent:

* RoundRobin ≈ \(k/36\)
* Random ≈ \(k/36\)
* oracle approached saturation at \(k\ge2\).

But the data were identified as **open-loop scanning-receiver recordings**.

Therefore the metric should be described as something closer to:

> **re-capture efficiency on a pre-filtered recording**

rather than literal interception against a continuously observable RF environment.

That distinction became important for the final scientific interpretation. 

---

## 82. Oct. 1 — The PRI layer failed to demonstrate generalization at 36 bands

The 36-band report showed that:

* BeliefUCB remained competitive or best at \(k=2\) and \(k=4\).
* At \(k=1\), Hedge was only about 1–2 percentage points apart from BeliefUCB.
* No convincing PRI locks were appearing for PRIAware/Persistent/Hedge.
* ScanAware's apparent locks were often at round dwell-grid values such as:

  * 60 µs
  * 80 µs
  * 100 µs
  * 120 µs

with low confidence.

This raised the possibility that some apparent “PRI recovery” was actually **grid fitting rather than recovery of physical periodicity**.

The earlier 1693 µs Band-1 truth was especially important because the new 36-band results were not recovering it.

---

## 83. Oct. 1 — Aggregate interception was confirmed to be misleading

A particularly revealing result was:

> BeliefUCB could achieve a strong aggregate score while essentially ignoring the labeled radar.

For example, on Validation/config_169 at \(k=1\):

* BeliefUCB captured approximately **99.3%** of one dominant band.
* Yet it captured **0%** of Band 1, the labeled SMART-L radar.
* It also captured **0%** of Band 6.

Thus the aggregate percentage was heavily influenced by the busiest band.

This made **per-emitter capture** a much more meaningful metric for the actual EW objective. 

---

## 84. Oct. 1 — ScanAware became a confirmed weak branch

ScanAwarePRI had originally been developed to address the spatial/scan-awareness gap.

The new 36-band report showed:

* mean approximately **20.7% at k=1**
* **24.5% at k=2**
* **52.4% at k=4**

It collapsed to roughly **7–13%** on four of six files at \(k=1\).

On Validation/config_169, an especially strange behavior appeared:

* Band 6 capture: **27.1% at k=1**
* Band 6 capture: **2.9% at k=2**

So adding a second receiver channel actually reduced capture of that emitter.

The cause was not yet established.

---

## 85. Oct. 1 — WhittleIndex was identified as fragile and computationally expensive

WhittleIndex showed a particularly severe failure on:

`Test/config_57`

which contained only:

* **761 pulses**
* approximately **28.9 seconds**

Whittle results:

| k | Whittle | RoundRobin |
| - | ------: | ---------: |
| 1 |    2.6% |       2.8% |
| 2 |    4.1% |       4.1% |
| 4 |    8.8% |       9.1% |

Thus it effectively collapsed to RoundRobin.

Elsewhere it was substantially better, so this was not a universal failure.

The implementation was also extremely slow:

* roughly **800–2400 seconds** per run in some configurations
* versus roughly **50–150 seconds** for other schedulers.

This made Whittle both a scientific curiosity and an engineering problem. 

---

# October 2 — WhittleIndex investigation and optimization

## 86. Oct. 2 — Whittle collapse investigated

The investigation focused first on whether Whittle's subsidy grid was too coarse for sparse bands.

The original grid was approximately:

```python
linspace(-0.5, 1.5, 120)
```

with a step of roughly:

$$
0.0168
$$

Sparse bands could have \(p_{01}\) around \(10^{-3}\) or smaller.

This meant many low-index states could quantize to the same subsidy value.

The investigation found:

* roughly **2.5 distinct index values** across 36 bands in the sparse replay
* a modified log-spaced low-end grid raised this to roughly **3.6**.

However, the synthetic reconstruction did **not** reproduce the real Test/config_57 collapse.

Therefore:

> The coarse subsidy grid was confirmed as a real implementation defect, but it was **not proven to be the cause** of the 2.6% real-data collapse.

This distinction was explicitly retained.

---

## 87. Oct. 2 — The Whittle grid was patched

The patched grid used:

* a log-spaced low range around \(10^{-6}\) to \(10^{-2}\)
* followed by the original linear tail.

The mathematical anchor and monotonicity checks still passed.

The patch was therefore treated as:

> a correctness improvement,

not:

> a confirmed fix for Test/config_57.

The real file itself was still required to determine the actual failure mechanism.

---

## 88. Oct. 2 — Whittle collapse isolated to Test/config_57

A file-by-file comparison established that **only Test/config_57 completely collapsed**.

| File                 | Whittle k=4 | BeliefUCB k=4 |
| -------------------- | ----------: | ------------: |
| Validation/config_57 |       45.3% |         72.0% |
| Test/config_169      |       48.2% |         92.9% |
| Validation/config_1  |       59.4% |         75.0% |
| Test/config_1        |       58.7% |         88.6% |

The sparse Test/config_57 case therefore became the specific Whittle failure case to investigate.

The report still did **not** establish the exact cause. 

---

## 89. Oct. 2 — Exact-key Whittle caching produced the first major speedup

Profiling finally showed where the runtime was going.

Approximately:

* **94% of runtime** was inside `solve_whittle_indices`.
* The Python scheduling loop was comparatively small.

The key observation was that many bands had exactly the same estimated:

$$
(p_{01},p_{11})
$$

because those estimates came from integer transition counts.

Therefore the same Whittle table did not need to be solved repeatedly.

An exact-key cache was introduced.

### 14k-step replay

| Configuration    | Solves |   Time | Interception |
| ---------------- | -----: | -----: | -----------: |
| k=1, no cache    |  2,484 | 60.8 s |        56.5% |
| k=1, exact cache |    204 |  4.7 s |        56.5% |
| k=4, no cache    |  2,484 | 85.0 s |        67.0% |
| k=4, exact cache |    237 |  6.8 s |        67.0% |

The output was identical.

So the cache achieved roughly:

> **13× fewer Whittle solves**

without changing the scheduler's behavior.

This became the primary Whittle optimization. 

---

## 90. Oct. 2 — Several proposed Whittle optimizations were rejected

A number of optimization ideas were tested rather than blindly merged.

### Early exit + trimmed subsidy sweep

Exact and safe, but only about:

> **1.1× faster**

because the existing sweep was already substantially trimmed.

### Policy-stability stopping

Potentially **2–3× faster per solve**, but not exact.

Across 293 cases:

* **13–32 cases differed**
* worst index difference around **0.25**

Therefore it was left disabled.

### Approximate parameter-bucket caching

This produced unstable behavior:

> interception varied dramatically with bucket width.

Therefore approximate caching was rejected.

The project retained **exact-key caching** because it produced the desired speedup without changing outputs. 

---

## 91. Oct. 2 — A second Whittle implementation had better asymptotic chain construction

Another submitted `whittle_index_optimized.py` was compared against the project's version.

Its main improvement was:

* vectorized `searchsorted`
* binary-search nearest-state lookup.

This reduced belief-chain construction from approximately:

$$
O(n^2)
$$

to:

$$
O(n\log n).
$$

Measured chain construction improvements were substantial at large \(n\), but chain construction was only a tiny fraction of total Whittle solve time.

The actual bottleneck remained:

$$
O(G\cdot I\cdot n)
$$

value iteration over the subsidy grid.

Therefore the conclusion was:

> The alternative implementation is asymptotically better in one component, but the exact-key scheduler cache produces the much larger practical speedup.

---

## 92. Oct. 2 — Whittle v2 attacked the real bottleneck

A second optimized version used a compiled/Numba-style kernel to accelerate the Bellman sweep.

The sandbox could not run Numba itself, so a C transcription was used as a speed proxy.

Results:

|             | Original   | v1             | v2 proxy       |
| ----------- | ---------- | -------------- | -------------- |
| Chain build | \(O(n^2)\) | \(O(n\log n)\) | \(O(n\log n)\) |
| Sweep       | \(O(GIn)\) | same           | same           |
| Per solve   | ~55.5 ms   | ~same          | **1.43 ms**    |

The v2 kernel therefore produced roughly:

> **39× faster individual solves**

in the C proxy.

End-to-end 14k-step replay:

| Configuration                 |          Time |
| ----------------------------- | ------------: |
| v1 + original scheduler       |       113.5 s |
| original + cache              |         8.8 s |
| v2 proxy + original scheduler |         4.0 s |
| v2 proxy + cache              | **1.9–2.0 s** |

At \(k=4\):

$$
11.7s \rightarrow 1.7s
$$

when moving to the v2 proxy plus cache.

The pick hashes remained identical.

Important caveat:

> These were C-proxy timings, not direct Numba timings.

So the v2 speedup still needed confirmation in the user's actual environment. 

---

## 93. Oct. 2 — Monotone passive-set divide-and-conquer was investigated

The user proposed exploiting the monotonicity of the Whittle passive set instead of sweeping the whole subsidy grid.

A divide-and-conquer threshold solver was implemented.

It recursively searched only regions where state thresholds remained unresolved.

Results over 150 random parameter sets:

|                    | Linear sweep | Divide & conquer |
| ------------------ | -----------: | ---------------: |
| Solves/case        |         42.2 |             31.1 |
| VI iterations/case |        3,468 |            2,519 |
| Wall time          |        7.7 s |            5.8 s |

So:

* **1.35× fewer solves**
* **1.38× fewer iterations**
* **1.34× faster**

But it was **not merged**.

Reasons:

1. The existing sweep was already heavily pruned.
2. Many cases had many distinct thresholds.
3. A large fraction of computation was still consumed by slow-converging capped Bellman solves.
4. Once the exact cache and compiled solver were used, the remaining bottleneck was the scheduler's per-step Python overhead.

There were also 10/150 cases with slightly different grid-cell outputs, so it was not considered clean enough to replace the existing method. 

---

# Final Whittle optimization stage

## 94. Oct. 2 — Whittle band selection was vectorized

The next bottleneck was:

```text
WhittleIndexScheduler.choose_bands()
```

It was rewritten to operate on arrays rather than looping over all 36 bands in Python.

Vectorization covered:

* belief propagation
* recomputation checks
* table interpolation
* score calculation
* top-k selection.

The inherited Python lists remained authoritative, so the external scheduler interface did not change.

The top-k selection used stable sorting to preserve the original tie-breaking behavior.

Most importantly:

> The vectorized and scalar versions were **bit-identical**.

Tests covered:

* sparse environments
* dense environments
* \(k=1\) through \(k=8\)
* random priorities
* warm-up phases
* bitwise score comparisons.

The pick hashes matched. 

---

## 95. Oct. 2 — Vectorization produced another 1.5–1.7× speedup

Measured results:

|                     |    Scalar | Vectorized |
| ------------------- | --------: | ---------: |
| `choose_bands`, k=1 | 91–103 µs |   52–56 µs |
| `choose_bands`, k=4 | 92–102 µs |   54–57 µs |
| 14k steps, k=1      |     1.9 s |      1.3 s |
| 14k steps, k=4      |     1.7 s |      1.5 s |
| 100k steps, k=1     |    13.9 s |      9.5 s |

The reason the gain was not larger was that there are only 36 bands:

> NumPy function-call overhead becomes comparable to the Python loop being removed.

The optimized path therefore became:

```text
compiled/optimized Whittle solve
        +
exact-key table cache
        +
vectorized band selection
```

rather than relying on a single optimization.

---

## 96. Oct. 2 — Band-count dependence of vectorization was measured

The vectorized implementation was then tested across band counts.

| Bands |  k | Scalar | Vectorized | Effect          |
| ----: | -: | -----: | ---------: | --------------- |
|     8 |  1 |  28 µs |      52 µs | slower          |
|     8 |  4 |  23 µs |      61 µs | slower          |
|    20 |  1 |  63 µs |      63 µs | equal           |
|    20 |  4 |  60 µs |      68 µs | slightly slower |
|    36 |  1 | 126 µs |      67 µs | faster          |
|    36 |  4 | 106 µs |      68 µs | faster          |
|   100 |  1 | 316 µs |      85 µs | much faster     |

The break-even point was approximately **20 bands**.

Since the real-data configuration had moved to **36 bands**, the vectorized implementation was retained.

No automatic scalar fallback was added for smaller band counts. 

---

# 97. Oct. 2 — The project's final state after the new chronology

At the end of the newly supplied chronology, the project had effectively split into three levels of maturity.

### Core scheduler

**BeliefUCB**

This is the most consistently supported real-data result.

It:

* beats RoundRobin across the real files examined
* generalizes better than the tuned PRI/Hedge layers
* remains computationally manageable.

### Advanced scheduler family

**PRIAware / PersistentPRIAware / HedgeBlended**

These remain valuable experimentally because they demonstrated:

* PRI recovery
* persistence
* adaptive expert blending
* class-balanced learning
* recovery from narrow PRI-score failures.

But the held-out 36-band data showed that their real-data generalization was not yet established.

### Alternative theoretical scheduler

**WhittleIndex**

This successfully demonstrated:

* mathematical formulation
* anchor correctness
* monotonicity
* model-mismatch behavior
* substantial optimization work.

But it also demonstrated:

* sensitivity to sparse conditions
* collapse on Test/config_57
* significant computational cost before optimization.

Its implementation was nevertheless heavily optimized by the end:

```text
original Whittle
→ exact-key cache
→ optimized/compiled Bellman solver
→ vectorized band selection
```

with correctness preserved in the available tests.

---

# 98. Oct. 2 — Final unresolved scientific questions

The new chronology leaves several questions explicitly unresolved rather than pretending they were solved.

### 1. Why does Whittle collapse on Test/config_57?

Known:

* it collapses at \(k=1,2,4\)
* the file is the sparsest tested file
* a subsidy-grid quantization defect exists
* fixing that defect did **not** reproduceably fix the collapse in the synthetic stand-in.

Therefore the actual cause remains unproven.

### 2. Why does ScanAware lose Band 6 when \(k\) increases?

Known:

* Band 6 capture falls from **27.1% → 2.9%**
* no PRI lock appears/disappears to explain it.

The exact mechanism remains unresolved.

### 3. Does the PRI/Hedge machinery genuinely improve unseen real data?

Current evidence says:

> **not demonstrated yet.**

The held-out data did not provide convincing evidence of a general improvement.

### 4. Is the real metric actually measuring interception?

Because the available real files are scanning-receiver recordings, not continuous stare-mode recordings, the metric is fundamentally constrained by what the recording contains.

A true stare-mode recording remains the cleanest test.

### 5. Does the scheduler capture individual emitters?

Aggregate interception is insufficient.

A per-emitter metric became a major recommended next step.

### 6. Does performance remain stable across seeds?

Many of the real-data tables were still:

```text
seed = 0
```

so small differences between schedulers should not yet be treated as statistically meaningful.

The project therefore moved toward:

* multiple seeds
* per-emitter metrics
* held-out data
* stare-mode recordings.

---

# 99. Final progression after incorporating all three new files

The previous progression can now be extended to:

```text
Problem formulation
→ BeliefScheduler
→ BeliefUCB / v2
→ PRI-aware / v3
→ multi-seed failure
→ persistent characterization / v4
→ warm-up / dwell / jitter / switching fixes
→ spatial / ScanAware
→ real config_169.h5 pipeline
→ staggered PRI
→ narrow PRI spike real-data failure
→ max_blend_confidence tradeoff
→ Hedge v5
→ class-imbalance bug #1
→ class-imbalance bug #2
→ class_balance_alpha
→ alpha = 0.1
→ 30-seed v5 inheritance bug
→ v5 rebased onto v4
→ beacon tradeoff correctly attributed to v4
→ eta sweep
→ eta = 4
→ driver integration
→ reproducibility fix
→ noise / Pfa / Pd / sensitivity model
→ spatial-scan re-verification
→ Whittle-index numerical implementation
→ Whittle model-mismatch diagnosis
→ genie/oracle ceiling
→ practical plateau analysis
→ run_all.py / real-data integration
→ dedicated real-data-only runner
→ held-out real-data evaluation
→ overfitting/generalization reassessment
→ per-band / per-emitter metric concern
→ k=1 / k=2 / k=4 sweep
→ 8 → 36 band channelization
→ 36-band held-out evaluation
→ PRI generalization failure exposed
→ “camp on busiest band” problem exposed
→ ScanAware fragility exposed
→ Whittle Test/config_57 collapse isolated
→ Whittle subsidy-grid defect discovered
→ exact-key Whittle cache
→ ~13× fewer Whittle solves
→ optimized Bellman kernel
→ ~39× per-solve proxy improvement
→ monotone passive-set divide-and-conquer experiment
→ rejected as insufficiently useful
→ vectorized Whittle band selection
→ 1.5–1.7× scheduler-step improvement
→ final Whittle optimization stack
→ remaining questions: real emitter-level generalization, ScanAware failure, Whittle sparse-file collapse, stare-mode validation
```

## The biggest change to the project's story

The chronology now makes the evolution much clearer.

The project **didn't simply progress from a bad scheduler to a better scheduler**.

It progressed through successive discoveries about what the problem actually was:

> **First:** adaptive scheduling beats open-loop sweeping.

> **Then:** periodicity can help, but only when the band actually represents a coherent emitter.

> **Then:** accurate prediction can still produce bad interception decisions.

> **Then:** expert blending can repair that locally.

> **Then:** held-out data showed that the apparent PRI/Hedge advantage was not yet general.

> **Then:** finer channelization became necessary because the original 8-band representation merged too many emitters.

> **Finally:** Whittle became a second theoretical branch whose model assumptions themselves became part of the experiment.

And the most important methodological progression was:

**single-seed synthetic success → multi-seed validation → real dev data → held-out real data → hardware/channelization correction → metric criticism.**

That is a much more complete project history than the earlier chronology alone. The new files materially change the **final interpretation**, especially because the held-out 36-band results prevent us from treating the earlier `config_169` results as representative of all real recordings.  
