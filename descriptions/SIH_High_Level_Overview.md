## High-level overview

This is a research/experimentation codebase for **intelligent electronic-support-measurement (ESM) spectrum scanning**.

The core loop is:

1. An environment produces ON/OFF activity for multiple frequency bands.
2. A scheduler chooses one or more bands to scan.
3. The scheduler receives the scan result and updates its model.
4. The run reports interception, delay, prediction, and robustness metrics.

The project evolves several schedulers:

```
Prototype
  └─ BeliefScheduler
      └─ BeliefUCBScheduler
          └─ PRIAwareScheduler
              ├─ PersistentPRIAwareScheduler
              │   └─ HedgeBlendedPRIAwareScheduler
              └─ ScanAwarePRIScheduler

BeliefUCBScheduler
  └─ WhittleIndexScheduler
```

It also contains:

- Synthetic emitter simulations
- PDW/TSRD data loading and replay
- Real-data experiment runners
- Noise/Pd/Pfa modeling
- Whittle-index optimization
- Many diagnostic, validation, and parameter-sweep scripts

I extracted the ZIP and ran `compileall`; all 44 Python files compile successfully.

---

# 1. Core simulation and scheduler files

### `scan_scheduler_prototype.py`

The original baseline implementation.

It defines:

- `Emitter`: base emitter abstraction
- `MarkovEmitter`: bursty fixed-band traffic
- `PeriodicEmitter`: cyclic beacon that moves between bands
- `AgileEmitter`: randomly hopping emitter
- `Environment`: combines emitter activity into per-band ON/OFF status
- `RoundRobinScheduler`: deterministic baseline
- `RandomScheduler`: random baseline
- `BeliefScheduler`: learns a two-state Markov model for every band
- `RunStats`: interception and delay metrics
- `run_episode()`: main simulation loop
- `make_scenario()`: standard mixed emitter scenario

The `BeliefScheduler` maintains a probability that each band is currently active. It updates that belief when a band is observed and propagates it forward when the band is not scanned.

This file establishes the basic architecture used by almost every later module.

---

### `scan_scheduler_v2.py`

The first major upgrade over the prototype.

Main changes:

- Replaces epsilon-greedy exploration with a UCB-style exploration bonus.
- Supports scanning multiple bands per step through `choose_bands(k)`.
- Adds optional receiver switching cost.
- Adds warm-up scanning.
- Adds warm-up dwell and jitter to avoid scan-period aliasing.

Important classes/functions:

- `BeliefUCBScheduler`
- `RoundRobinScheduler`
- `RandomScheduler`
- `run_episode()`
- `recommended_warmup_dwell()`

The scheduler score is approximately:

```
priority × belief + UCB exploration bonus
```

`run_episode()` also models hardware settling time. A band that has just been selected may be temporarily unobservable while the receiver retunes.

---

### `scan_scheduler_v3_pri.py`

Adds explicit **Pulse Repetition Interval (PRI)** modeling.

`PRIAwareScheduler` extends `BeliefUCBScheduler` and learns:

- Recent hit times per band
- Estimated PRI
- Timing jitter
- Confidence in the PRI estimate
- Whether a band appears to use staggered PRI
- Burst width for multi-step transmissions

The scheduler combines:

```
Markov belief
+ periodic phase prediction
+ UCB exploration
```

The PRI estimation logic:

1. Collects pairwise hit-time differences.
2. Generates candidate periods using GCDs, modes, divisors, and neighboring integer candidates.
3. Refines each candidate using least-squares fitting.
4. Selects the best relative RMSE fit.
5. Requires enough cycles and sufficient confidence before locking on.

It also supports staggered PRI patterns, where the sequence of pulse gaps repeats but individual gaps differ.

This file also defines:

- `SparsePeriodicEmitter`
- `make_sparse_scenario()`
- `run_comparison()`
- `run_sparse_comparison()`

The sparse scenario is designed to test a radar that emits only one short pulse every several steps.

---

### `scan_scheduler_v4_persistent.py`

Defines `PersistentPRIAwareScheduler`.

It fixes a seed-sensitive lock-on problem in v3. A band could receive many warm-up scans but too few positive hits to reach the PRI estimator's threshold. After warm-up, normal UCB exploration might never revisit it sufficiently.

v4 adds:

- `total_hits`: lifetime confirmed hits per band
- A persistent characterization bonus
- A maximum number of scans before giving up on a band

The characterization bonus favors bands that have not yet accumulated enough positive observations, but eventually stops rewarding bands that remain silent.

---

### `scan_scheduler_v5_hedge.py`

Defines `HedgeBlendedPRIAwareScheduler`.

Instead of using a fixed confidence-based mixture between Markov belief and PRI periodicity, it treats them as two competing prediction experts:

- Belief expert
- Periodicity expert

Each band has learned weights:

```
w_belief + w_pri = 1
```

The weights are updated using multiplicative-weights/Hedge logic based on squared prediction error.

It also contains two safeguards:

- A pre-lock gate so the periodicity expert cannot win by predicting zero before it has a valid PRI lock.
- Class-balanced loss weighting to prevent frequent OFF observations from overwhelming rarer but important ON observations.

Important parameters:

- `eta`: Hedge learning rate
- `initial_weight_belief`
- `weight_floor`
- `class_balance_alpha`

This is the latest heuristic scheduler in the main evolution chain.

---

### `spatial_scan_emitter.py`

Defines `SpatiallyScanningEmitter`.

This is a decorator around an existing emitter. It models an emitter whose antenna scans or rotates, so the emitter is only visible during a beam window.

It introduces a second periodic structure:

```
Fast periodicity: pulse repetition interval
Slow periodicity: antenna rotation / beam revisit period
```

Optional sidelobe leakage can create occasional detections outside the main beam.

---

### `scan_aware_scheduler.py`

Defines `ScanAwarePRIScheduler`.

It extends `PRIAwareScheduler` to handle spatially scanning emitters that produce nested periodicity:

- Intra-burst PRI
- Inter-burst scan period

It separately tracks:

- `scan_period_estimate`
- `scan_confidence`
- `pri_estimate`
- `pri_confidence`
- Burst start times
- Beam dwell width

Its logic includes:

- Robust PRI seeding
- Burst segmentation
- Fixed-threshold and ratio-based segmentation
- Period candidate search
- Burst-size consistency checks
- Scan-period stability gating
- Combined burst and intra-burst periodicity scoring

This is the most specialized scheduler in the project.

---

# 2. Whittle-index files

### `whittle_index.py`

Implements a numerical Whittle-index solver for the two-state Markov channel model.

The model assumes each band is a restless bandit:

- Active state: band is transmitting
- Passive state: band is not scanned
- Active action: scan the band and observe its state
- Reward: 1 when the scanned band is ON

The file:

1. Builds the reachable belief-state chain.
2. Solves a subsidized single-band MDP using relative value iteration.
3. Sweeps possible passive subsidies.
4. Records the subsidy where each belief state switches from active to passive.

It includes a self-test for:

- Known index behavior at `p11`
- Monotonicity of the index with respect to belief

---

### `whittle_index_optimized_v2.py`

A faster, drop-in implementation of the Whittle solver.

It preserves the original API and numerical method but:

- Uses optimized NumPy operations.
- Uses Numba when available.
- Optimizes belief-chain construction.
- Accelerates the subsidy sweep.

Important observation: this optimized module is **not currently wired into the main scheduler**. `scan_scheduler_whittle.py` still imports `solve_whittle_indices` from `whittle_index.py`.

---

### `scan_scheduler_whittle.py`

Defines the main `WhittleIndexScheduler`.

It extends `BeliefUCBScheduler` but replaces the exploitation score:

```
belief score
```

with:

```
Whittle index for the current belief
```

Features:

- Periodic index-table recomputation
- Linear interpolation between belief states
- Exact table memoization
- Optional approximate parameter quantization
- NumPy-vectorized band scoring
- Retained UCB exploration and priority behavior

This is the theoretically motivated alternative to the heuristic schedulers.

---

### `scan_scheduler_whittle_scalar.py`

A scalar/reference implementation of `WhittleIndexScheduler`.

It performs the same calculations with ordinary Python loops instead of the vectorized NumPy path.

Its main purpose is equivalence testing and debugging.

---

### `whittle_equiv_test.py`

Randomized numerical test for `whittle_index.py`.

It compares:

```python
solve_whittle_indices(fast=True)
```

against:

```python
solve_whittle_indices(fast=False)
```

The goal is to verify that the optimized solver path produces the same results as the full reference sweep.

---

### `scan_scheduler_whittle_equiv_test.py`

Compares:

- Vectorized `scan_scheduler_whittle.WhittleIndexScheduler`
- Scalar `scan_scheduler_whittle_scalar.WhittleIndexScheduler`

It runs randomized environments and checks that both implementations choose the same bands.

---

# 3. PDW and real-data pipeline

### `pdw_loader.py`

Provides PDW loading and synthetic PDW generation.

PDW fields are:

```
toa    Time of arrival
cf     Centre frequency
pw     Pulse width
aoa    Angle of arrival
amp    Amplitude
label  Emitter label
```

Functions:

- `load_real_pulse_train()`: delegates real HDF5 loading to `pdw_source.py`
- `generate_synthetic_pdw_stream()`: creates a schema-compatible synthetic stream

The synthetic stream contains:

- Three fixed-frequency, approximately constant-PRI emitters
- Two frequency-agile emitters

The synthetic data is explicitly not the real TSRD dataset.

---

### `pdw_source.py`

Centralizes source handling and ground truth.

This is one of the most important utility files.

It defines:

- `PDWSource`
- `PDWSourceError`
- `read_h5_pulse_train()`
- `derive_true_periodic_bands()`
- `empirical_period_check()`
- CLI helpers for HDF5 files and time windows
- `suggest_windows()`

Responsibilities:

- Load real TSRD-style `.h5` files directly with `h5py`
- Load synthetic data when no HDF5 file is supplied
- Derive periodic-band truth from metadata
- Detect collisions and frequency-agile emitters
- Track whether seeds alter the environment or only scheduler randomness
- Handle absolute ToA offsets
- Print source/provenance banners
- Suggest useful sub-windows in long real recordings

It deliberately fails when an explicitly requested real file cannot be loaded instead of silently falling back to synthetic data.

---

### `pdw_environment.py`

Defines `PDWReplayEnvironment`.

It converts a PDW stream into the same interface used by the synthetic `Environment`:

```python
env.step() -> {band: True/False}
```

It:

- Bins frequency into `n_bands`
- Bins time into fixed `dwell_us` intervals
- Marks a band ON if at least one pulse occurs in that time/frequency cell
- Exposes per-band occupancy
- Provides `next_transmission_after()` for offline prediction evaluation

Schedulers do not access the future truth grid; only evaluation code does.

---

### `prediction_accuracy_metrics.py`

Computes prediction-specific metrics that are distinct from simple interception delay.

It reports:

1. Percentage of correct PRI locks
2. Average error between the scheduler's predicted next transmission and the true next transmission

It supports:

- `PRIAwareScheduler`
- `PersistentPRIAwareScheduler`
- `ScanAwarePRIScheduler`

The scan-aware scheduler gets a separate prediction path because it predicts burst starts rather than simply predicting `t + pri_estimate`.

---

### `deinterleave_hdbscan.py`

Evaluates unsupervised pulse deinterleaving.

It clusters PDWs using features such as:

- Centre frequency
- Pulse width
- Angle of arrival

It then compares predicted clusters with emitter labels using:

- V-measure
- Homogeneity
- Completeness
- Confusion breakdowns

It also compares:

- Agile versus fixed emitters
- Full data versus selected subsets
- Raw coarse-band grouping versus clustering

The purpose is to investigate band collisions that cannot be resolved by frequency binning alone.

---

# 4. Noise and detection modeling

### `noise_model.py`

Adds an optional receiver detection model.

Earlier schedulers assumed:

```
Pd = 1
Pfa = 0
```

This file models:

- Probability of detection, `Pd`
- Probability of false alarm, `Pfa`
- Sensitivity in dB
- Per-band SNR
- Stochastic detection outcomes

`ReceiverNoiseModel` uses a simple Gaussian threshold detector:

```
Pfa = Q(threshold)
Pd  = Q(threshold - sqrt(SNR))
```

`run_episode_noisy()` mirrors the ordinary episode loop but inserts stochastic detection between the true environment state and the scheduler's observation.

`NoisyRunStats` reports:

- Detections
- Misses
- False alarms
- True negatives
- Empirical Pd/Pfa
- Per-band statistics

The noise model is opt-in; existing scheduler behavior is unchanged unless it is explicitly used.

---

### `noise_model_demo.py`

Validation/demo script for `noise_model.py`.

It checks:

1. Backward compatibility with the noiseless runner
2. Theoretical versus empirical Pd/Pfa
3. Sensitivity calculations
4. A practical scheduler demonstration under noisy observations

---

# 5. Experiment runners

### `run_all.py`

Orchestrates the project's scripts as subprocesses.

It:

- Defines the experiment script list
- Adds common arguments to HDF5-capable scripts
- Resolves HDF5 paths
- Runs scripts sequentially
- Optionally writes logs
- Reports elapsed time and failures

This is the closest thing to a project-wide entry point.

---

### `run_on_turing_dataset.py`

Runs the scheduler stack against either:

- The synthetic PDW stand-in
- A real TSRD-style HDF5 file supplied with `--h5`

It evaluates:

- Round robin
- Random
- Belief UCB
- PRI-aware
- Persistent PRI-aware
- Hedge-blended
- Whittle-index

It supports:

- Multiple channels
- Warm-up periods
- Priority weights
- Dwell time
- Time-window selection
- Optional scheduler comparison priorities

Despite its name, it can use synthetic data unless `--h5` is explicitly provided.

---

### `run_real_data.py`

The most complete real-data experiment runner.

It is explicitly configured to use real `.h5` data only.

It runs:

- Round robin
- Random
- Belief UCB
- PRIAware
- Persistent PRIAware
- Scan-aware PRI
- Hedge-blended
- Whittle-index
- Genie/oracle ceiling

It additionally supports:

- Multiple seeds
- Multiple channel counts
- Per-band capture statistics
- PRI diagnostics
- Optional HDBSCAN deinterleaving
- CSV reports
- Text reports
- File failure tracking
- Window suggestions

Outputs are written under a timestamped `real_results/` directory.

The default HDF5 path referenced by this script is not included in the ZIP, so the script will require external dataset files.

---

### `oracle_ceiling.py`

Computes an upper bound using a “genie” scheduler.

The oracle sees the true ON/OFF status of all bands before choosing the best `k` bands.

It compares:

- Oracle performance
- Belief UCB
- PRIAware
- Hedge-blended
- Whittle-index

This estimates how much room remains for scheduler improvement.

---

# 6. Robustness, diagnosis, and validation scripts

### `multi_seed_robustness.py`

The main multi-seed evaluation harness.

It reruns multiple experiment suites and reports:

- Mean
- Standard deviation
- Minimum
- Maximum
- Paired per-seed deltas
- Win counts

Suites cover:

- Prototype scenario
- Multi-channel scanning
- Beacon scenario
- Sparse radar
- Persistent-characterization fix
- PDW/Turing scenario
- Scan-aware mixed scenario

This file exists because many earlier results were based on a single random seed.

---

### `diagnose_pri_lockon.py`

Investigates why v3 PRI lock-on is seed-sensitive for the sparse fixed-PRI radar.

It instruments:

- Scan counts
- Hit counts
- PRI-update calls
- Candidate periods
- Confidence values
- Lock/no-lock outcomes

This diagnosis motivated the persistent characterization mechanism in v4.

---

### `diagnose_beacon_regression.py`

Investigates why PRI awareness helps at one channel count but hurts at another in the beacon scenario.

It records:

- Per-band capture
- Whether multiple simultaneous channels help or hurt
- Scheduler-specific behavior

This led to fixes for multi-step burst plateau handling.

---

### `diagnose_fullfile_regression.py`

Investigates a real-file performance gap where Belief UCB outperformed PRI-aware schedulers.

It:

- Reproduces per-band captures
- Compares band occupancy
- Examines PRI confidence and estimates
- Sweeps blending behavior
- Focuses on a dominant staggered-PRI band

---

### `settle_fix_interaction.py`

Examines interactions between scheduler fixes under different random-seeding conventions.

It compares scheduler variants on identical or differently generated environments and highlights the difference between:

- Shared random streams
- Resetting the random seed per scheduler
- Fresh environment construction

This is important because environment randomness can otherwise be confused with scheduler performance.

---

### `validate_offbyone_fix.py`

Compares the current PRI candidate search with a reconstructed pre-fix version.

The fix under test is the inclusion of each candidate period's immediate `±1` integer neighbors.

This is important for fractional-PRI cases where the best coarse candidate may be one scan step away from the true value.

---

### `validate_plateau_fix.py`

Validates the burst-plateau fix in `PRIAwareScheduler`.

It compares:

- `OriginalPRIAware`
- `PlateauOnlyPRIAware`
- Current scheduler behavior

The issue was that a multi-step beacon burst could have nearly zero onset jitter. A narrow periodicity bump would then make the scheduler abandon the band after the first ON step.

The fix uses a persistent estimate of the longest ON run to widen the periodicity score.

---

### `validate_pdw_multiseed.py`

Runs multi-seed validation on the synthetic PDW dataset.

It classifies PRI estimates as:

- `CORRECT`
- `HARMONIC`
- `WRONG`
- `NO LOCK`

It focuses on harmonic-lock and fractional-PRI behavior.

---

### `validate_warmup_dwell_fix.py`

Validates warm-up behavior when receiver switching has nonzero cost.

It compares:

- No dwell
- Dwell without jitter
- Dwell with jitter
- Recommended warm-up configurations

The goal is to prevent every warm-up scan from being wasted on receiver settling.

---

### `validate_beacon_switchcost_dwell.py`

Applies switch-cost and dwell validation to the multi-step beacon scenario.

It checks whether the sparse-radar warm-up fix generalizes to a beacon that remains ON for several consecutive steps.

It also includes an `isolate_mechanism()` helper to determine which part of the fix is responsible for improvements.

---

### `validate_scan_aware_mixed.py`

Tests `ScanAwarePRIScheduler` in a mixed environment where other bands compete for scan time.

This is more realistic than testing a scanning emitter alone, because the scheduler must decide whether to:

- Camp on the current band
- Leave during the beam's dead time
- Return near the predicted next burst

---

### `validate_hedge_blend.py`

First-pass single-seed validation for the Hedge scheduler.

It checks four reference situations:

- Sparse radar
- Beacon
- Synthetic PDW
- Real file band

It is intended as a gate before running the more expensive multi-seed tests.

---

### `sanity_check_hedge.py`

Another initial Hedge validation script.

It compares Hedge against established reference schedulers on:

- Sparse radar
- Beacon
- Synthetic PDW
- Real data

It is a fast directional sanity check, not a statistical validation.

---

### `multiseed_alpha_default.py`

Runs 30-seed tests for the default Hedge `class_balance_alpha=0.1`.

It checks:

- Sparse radar
- Beacon with one and two channels
- Synthetic PDW band 4

Real-file testing is excluded because the real recording is fixed and the Hedge scheduler itself does not introduce meaningful random variation in that configuration.

---

### `multiseed_beacon_v5.py`

Runs a full 30-seed beacon comparison for:

- Belief UCB
- PRIAware
- Persistent PRIAware
- Hedge

It was created to verify that the single-seed Hedge result was not accidental.

---

### `sweep_class_balance_alpha.py`

Sweeps the Hedge class-balance parameter:

```
alpha = 0
```

means unweighted loss, while:

```
alpha = 1
```

means full inverse-frequency balancing.

It compares the trade-off between:

- Synthetic sparse/PDW performance
- Real-file performance

---

### `sweep_eta.py`

Sweeps the Hedge learning rate `eta`.

It evaluates whether the default value of `4.0` is robust across:

- Sparse radar
- Beacon
- Synthetic PDW
- Real data

The baseline schedulers are not rerun for every eta because eta only affects Hedge.

---

### `tune_confidence_threshold.py`

Sweeps the PRI confidence scale.

The scale controls how much relative fitting error is tolerated before a PRI is considered reliable.

It evaluates the trade-off between:

- Locking onto fractional PRI signals quickly
- Avoiding false locks on bursty or beacon-like signals

---

### `switch_cost_comparison.py`

Measures the impact of receiver retuning cost.

It sweeps several switch costs and compares:

- Round robin
- Random
- Belief UCB
- PRI-aware

It also reports switching frequency and analyzes whether exact-timing PRI predictions are harmful when the receiver needs time to settle.

---

# 7. Small demonstrations

### `demo_spatial_scan_emitter.py`

A minimal visualization/debug script for `SpatiallyScanningEmitter`.

It wraps a fast PRI emitter in a slow scanning beam and prints the resulting timeline, making the nested burst structure easy to inspect.

---

## Important project observations

### The project is experiment-oriented, not packaged as a library

There is:

- No `README`
- No `requirements.txt`
- No `pyproject.toml`
- No formal `tests/` directory
- No external HDF5 data in the ZIP

Most validation is implemented as standalone executable scripts.

### The real-data path needs external dependencies/data

Real runs require at least:

- NumPy
- `h5py`
- Recent scikit-learn for `HDBSCAN`
- Optional Numba for `whittle_index_optimized_v2.py`

The real `.h5` datasets are not included in `SIH.zip`.

### The project has two distinct meanings of “interception”

For synthetic environments, interception is measured against the simulated truth.

For a real scan-mode TSRD file, the recording may already be filtered by another scanning receiver. In that case, the result measures how efficiently this scheduler re-captures already-recorded pulses, not how many pulses the physical emitter actually transmitted.

### The optimized Whittle solver is currently unused

`whittle_index_optimized_v2.py` is a standalone optimized implementation. The active scheduler imports the original `whittle_index.py`.

### The codebase's main research progression is

```
Markov belief
  → UCB exploration and multi-channel scanning
  → PRI prediction
  → Persistent characterization
  → Hedge blending
  → Nested spatial-scan modeling
  → Whittle-index scheduling
```

In short, this is a progressively refined research prototype for learning which RF bands to scan under partial observation, periodic emitters, bursty emitters, receiver switching costs, noisy detection, and real PDW data.