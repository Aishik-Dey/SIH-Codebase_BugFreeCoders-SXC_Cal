# Smart Scan Scheduler — Technical Explanation Report

**Subject:** Consolidated code and algorithm explanations for the SIH Smart Scan Scheduler codebase (18 Python source files)

---

## Abstract

This report documents the design, evolution, and validation history of a spectrum-scanning
scheduler simulator built for DRDO's SIH problem statement (26055): a scheduler that decides,
moment-to-moment, which frequency band an ESM (Electronic Support Measures) receiver should
listen to, given that multiple emitters turn on and off independently across many bands and
the receiver can only tune to a narrow slice of spectrum at a time. This is mathematically a
**restless multi-armed bandit** (or POMDP — Partially Observable Markov Decision Process).

The codebase progresses from a baseline prototype through four scheduler generations (V1–V4),
a PDW (Pulse Descriptor Word) replay pipeline for real/synthetic radar data, and a series of
diagnostic and validation scripts that catch, isolate, and multi-seed-validate individual bugs
and fixes. Each file's section below states the problem that file solves, then walks through
its implementation line by line.

## Contents

1. `scan_scheduler_prototype.py` — the foundation
2. `scan_scheduler_v2.py` — UCB exploration and multi-channel scanning
3. `scan_scheduler_v3_pri.py` — the PRI-aware periodicity estimator
4. `scan_scheduler_v4_persistent.py` — fixing the coin-flip lock-on
5–6. `pdw_loader.py` and `pdw_environment.py` — bridging simulation to real data
7. `run_on_turing_dataset.py` — the driver script
8. `diagnose_pri_lockon.py` — proving the coin-flip
9. `multi_seed_robustness.py` — the general-purpose multi-seed validation harness
10. `diagnose_beacon_regression.py` — a hypothesis that turned out wrong
11. `validate_plateau_fix.py` — reconstructing intermediate states to isolate a fix
12. `settle_fix_interaction.py` — catching a confound in the validation methodology
13. `tune_confidence_threshold.py` — proving a trade-off is a genuine Pareto frontier
14. `validate_pdw_multiseed.py` — the multi-seed check on real PDW data
15. `validate_offbyone_fix.py` — closing the last flagged validation gap
16. `switch_cost_comparison.py` — real-world receiver constraints
17. `validate_warmup_dwell_fix.py` — the definitive 5-way ablation
18. `validate_beacon_switchcost_dwell.py` — the negative result that scopes the fix

---

## File 1 of 18: `scan_scheduler_prototype.py` --- the foundation

This is the very first file built in the project --- everything else in
the zip either imports from it directly or inherits from classes defined
here. Let me explain the problem framing, then walk through every line.

## The problem this file solves

DRDO's SIH problem statement (26055) asks for a scheduler that decides,
moment-to-moment, which frequency band an ESM (Electronic Support
Measures) receiver should listen to, given that: - The receiver can only
listen to a narrow slice of spectrum at a time (it has to "tune" to one
band) - Multiple emitters (radars, comms, jammers) exist across many
bands, each turning on and off independently - The old approach is "open
loop" --- sweep every band in a fixed rotation regardless of what's
actually happening

This is mathematically a **restless multi-armed bandit** (or POMDP ---
Partially Observable Markov Decision Process): each frequency band is an
"arm." Unlike a classic bandit, the arm's state (transmitting or not)
keeps changing even while you're *not* looking at it --- "restless." You
only get to observe (and get reward from) an arm when you choose to scan
it. The goal is a policy that decides which arm to pull each step to
maximize how much of the actual transmission activity you catch.

This file builds the smallest possible version of that whole pipeline: a
simulated RF world, three competing scheduling policies, and the
plumbing to score them.

## Line-by-line walkthrough

**Lines 1--27 --- module docstring.** This just states the four-stage
pipeline (Environment → Scheduler → Update → Metrics) and previews the
three schedulers being compared. Worth noting up front:
`BeliefScheduler` is explicitly described as "a practical/myopic
approximation of the Whittle index" --- i.e., this is *not* claiming to
be the textbook-optimal restless-bandit solution (that's the still-open
"Whittle index" item flagged repeatedly across the project), it's
a cheaper Bayesian heuristic that approximates it.

**Lines 29--32 --- imports.** `random` for all the stochastic emitter
behavior and exploration; `statistics` for `mean()` in the metrics;
`dataclass`/`field` from `dataclasses` for the lightweight data
containers (`Environment`, `RunStats`); `typing` imports purely for
readability/type hints.

**Lines 39--48 --- `Emitter` base class.** This is the abstract parent
for anything that can transmit. `self.band` tracks which frequency band
it's currently on (`-1` = unset --- subclasses always set this properly
before use). `self.on` is whether it's transmitting *right now*.
`step(t)` is the abstract method every subclass must implement --- given
the current timestep `t`, decide the new `(band, on)` state. Raising
`NotImplementedError` here is a guard rail: if someone forgets to
override `step`, they get a loud crash instead of silent wrong behavior.

**Lines 51--64 --- `MarkovEmitter`.** This models **bursty
communications traffic** --- think a radio channel that's sometimes
busy, sometimes quiet, with "stickiness" (if it was just on, it's likely
still on). The core mechanism is a **2-state Markov chain**: -
`p_on_given_off` (line 57, default 0.15): probability of turning ON,
given it was OFF last step - `p_on_given_on` (line 58, default 0.85):
probability of staying ON, given it was ON last step

Line 59 randomly initializes the starting state (30% chance of starting
ON) so different emitter instances don't all start in lockstep. The
actual dynamics are in `step()` (lines 61--64): look up the right
transition probability based on current state (`p_on_given_on` if
currently on, else `p_on_given_off`), then roll a random number against
it to decide the next state --- classic Markov chain simulation via
`random.random() < p`. Returns `(band, on)` --- band never changes for
this emitter type, since it's a fixed-frequency channel.

**Lines 67--80 --- `PeriodicEmitter`.** This models a **cyclic scanning
beacon or periodic radar** --- something that sweeps through a *fixed,
repeating sequence* of bands. `band_sequence` (line 70) is the ordered
list of bands it visits; `dwell` is how many timesteps it spends on each
band before moving to the next. The key line is 77:
`idx = (t // self.dwell) % len(self.band_sequence)` --- integer-divide
the current time by dwell length to get which "slot" you're in, then
modulo by the sequence length to wrap around. This is a completely
deterministic function of `t` --- no randomness at all, which is exactly
what makes it *learnable*: if a scheduler can reverse-engineer this
pattern, it can predict future activity perfectly. `self.on = True`
always (line 79) --- this emitter, unlike the Markov one, is *always*
transmitting somewhere, it just moves around. This is the ancestor of
what later becomes the "beacon" scenario that motivates the entire
PRI-aware line of work in v3.

**Lines 83--98 --- `AgileEmitter`.** This models a **frequency-agile
threat** --- an adversary deliberately hopping between bands
unpredictably to evade detection (the "LPI/LPD" --- Low Probability of
Intercept/Detection --- behavior mentioned in line 86). `bands` (line
87) is its *pool* of possible bands (not a fixed sequence); `dwell` is
how often it re-rolls; `duty` is its duty cycle (fraction of time
actually transmitting even while parked on a band). Line 92 picks an
initial random band. In `step()`: line 95 checks `t % self.dwell == 0`
--- every `dwell` steps, jump to a *uniformly random* new band via
`random.choice(self.bands)`. Line 97 independently rolls whether it's
actually transmitting this instant, using `duty` as the probability.
This emitter is the deliberate "unlearnable" control case in every
experiment throughout the whole project --- no scheduler should ever be
able to predict it, and it's used later (in v4) as the trap case that
reveals a real bug (a band with *no* real signal can still fool a naive
"keep trying" bonus into never giving up).

**Lines 101--116 --- `Environment` dataclass.** This is the world-state
container. `n_bands`: total number of frequency slots the receiver's
spectrum is divided into. `emitters`: the list of `Emitter` objects
populating this world. `t`: the internal clock, starts at 0. The
`step()` method (107--116) is the heart of "ground truth" generation:
line 110 initializes every band to `False` (silent) for this step; the
loop (111--114) advances *every* emitter one tick and, if it's
transmitting, marks its band `True`. Critically, line 113's
`if on: status[band] = True` is an **OR-combine** --- if two emitters
happen to share a band and only one is on, the band still reads as "on."
This OR-collision behavior becomes structurally important much later (in
the PDW/band-1-collision investigation described later, where
two real emitters landing in the same coarse band made periodicity
detection correctly fail). Line 115 increments the clock, line 116
returns the dict of per-band truth for this step.

**Lines 123--132 --- `Scheduler` base class.** The abstract interface
every scheduling policy must implement: `choose_band()` returns which
single band to scan this step; `update(band, observed_on)` is the
*feedback* hook --- called after scanning, telling the scheduler what it
actually saw, so it can learn. The base `update` is a no-op (`pass`) ---
dumb baselines don't need to learn anything.

**Lines 135--144 --- `RoundRobinScheduler`.** This is the **open-loop
baseline** the whole SIH problem statement explicitly wants to be beaten
--- literally "sweep the entire band with the best speed possible,"
described in the PS as the naive-but-standard current practice.
`self.ptr` (line 139) is a simple rotating pointer; `choose_band()`
returns the current pointer position then advances it modulo `n_bands`
(line 143) --- a plain deterministic cycle through every band in order,
blind to what's actually happening anywhere.

**Lines 147--150 --- `RandomScheduler`.** Even dumber baseline: pick a
uniformly random band every step, no memory, no pattern. Exists mainly
as a sanity floor --- if the "smart" scheduler can't beat even *this*,
something is badly wrong.

**Lines 153--209 --- `BeliefScheduler`, the actual "smart" part.** This
is the payload of the whole prototype. The docstring (154--168) explains
the design precisely: for each band, online-learn a 2-state Markov model
of its behavior (same structural idea as `MarkovEmitter`, but now the
*scheduler* is trying to infer it purely from its own scan history), and
maintain a **belief** --- a probability estimate of "is this band ON
right now" --- that's exact when you just scanned it, and decays/updates
via the learned model when you haven't.

Constructor (169--178): `epsilon` (default 0.08) is the exploration
rate. `off_on`/`off_tot` and `on_on`/`on_tot` are **Laplace-smoothed
counters** --- this is the standard trick for online probability
estimation from sparse data: initializing counts to `1.0`/`2.0` (lines
173--176) instead of `0`/`0` means a brand-new band starts with a sane
50% prior instead of undefined `0/0`, and each new observation just
nudges the ratio. `belief` (177) starts at a flat `0.3` per band (a mild
prior toward "probably off," matching the general sparsity of the
world). `last_scan_result` (178) remembers what state each band was in
the *last time it was actually scanned* --- needed because updating the
Markov counts requires knowing the transition (from-state → to-state),
and you only truly know the "from" state if you scanned it last time
too.

`_p_on_given_off` / `_p_on_given_on` (180--184): simple ratio lookups
--- confirmed hit count over total count, giving the current best
estimate of each transition probability for that band.

`_propagate` (186--188): this is the actual **HMM forward step**. If a
band wasn't scanned this turn, its belief still needs to evolve --- it
does so via the law of total probability:
`new_belief = old_belief × P(on|on) + (1 − old_belief) × P(on|off)`.
This is exactly how you propagate a hidden Markov chain's state
distribution forward one step without an observation --- weight the two
possible "were you on or off last step" scenarios by their current
belief, and apply the matching transition probability to each.

`choose_band` (190--195): line 191--192 propagates *every* band's belief
forward one step (since time passes for everyone, scanned or not). Line
193 rolls the epsilon-exploration dice --- with 8% probability, pick a
totally random band regardless of belief (this guarantees no band is
ever permanently ignored, which matters enormously later --- this exact
mechanism is what the whole "8-hit lock-on cliff" bug later
traces back to). Otherwise (line 195), greedily pick `argmax` belief ---
scan whichever band is *currently* believed most likely to be
transmitting.

`update` (197--209): called after the scan with ground truth. Lines
198--207: if this band was scanned before (`prev is not None`), use the
transition `prev → observed_on` to increment the right Laplace counters
--- `on_tot`/`on_on` if it was on last time, `off_tot`/`off_on` if it
was off. Line 208 remembers this observation as the new "last scan
result" for next time. Line 209 is the crucial belief reset: since we
just directly observed this band, belief snaps to exactly `1.0` or `0.0`
--- no more uncertainty about *this* band's *current* state, until the
next propagation step blurs it again.

**Lines 216--233 --- `RunStats` and `report()`.** A results accumulator
matching almost exactly the figures-of-merit the problem statement
explicitly demands: `total_transmissions` counts steps where *something*
was transmitting somewhere (the denominator for "did we catch it");
`hits` counts steps where the scanned band happened to be the one that
was on; `intercept_delays` records, per transmission event, how many
steps elapsed between it starting and the scheduler actually landing on
it; `rewards` is a simple per-step 0/1 hit indicator. `report()`
computes `interception_ratio = hits / total_transmissions` --- the
headline metric used throughout the rest of the project (this is the "49.4%
vs 26.0%" number, the "100%/79%" sparse-radar invariant, etc. --- all
descendants of this exact formula).

**Lines 236--269 --- `run_episode`, the simulation driver.** This is the
loop every later scheduler variant gets tested through, unmodified.
`env_factory` is a *function* that builds a fresh `Environment` (not the
environment itself) --- this matters because each call to `run_episode`
needs its own independent random realization, not a shared/mutated one
(this exact detail is what caused the "confounded seeding" bug
discovered later in the project, where sequential scheduler runs
off one continuous random stream accidentally gave different schedulers
different underlying worlds). `on_since` (239) and `credited` (240)
track, per band, when its *current* transmission burst started and
whether that burst has already been "credited" toward an intercept-delay
measurement (so a 4-step burst doesn't get counted 4 times).

The main loop (242--267): line 243 advances the environment one tick and
gets ground truth. Lines 245--252 maintain the "how long has this
transmission been running" bookkeeping --- if a band just started
transmitting, mark its start time and reset its credited flag; if it
went silent, clear both. Line 254 counts this step toward
`total_transmissions` if *any* band is active anywhere. Line 257 asks
the scheduler which band to scan --- this is the one call to the actual
policy under test. Line 258 looks up the ground truth for that specific
band. Line 259 feeds the result back to the scheduler for learning.
Lines 261--266: record the 0/1 reward, and if it was a hit, increment
`hits` and (if this is the first credit for the current burst) record
how many steps elapsed since the burst started as an intercept delay.

**Lines 272--283 --- `make_scenario`.** Builds the actual test world: 8
bands, two `MarkovEmitter`s simulating comms channels with different
chattiness (`comm-1` is loud/sticky at 90% stay-on, `comm-2` is
moderate), one `PeriodicEmitter` beacon cycling through bands
`[2, 5, 6]` with dwell 4, and one `AgileEmitter` threat hopping
unpredictably across bands `[0, 3, 6, 7]`. Note bands 6 and 7 overlap
between beacon/threat --- deliberate collision stress-testing.

**Lines 286--312 --- `main`.** Seeds randomness for reproducibility
(`random.seed(7)`), sets up 8 bands / 4000 steps, instantiates all three
schedulers, runs each through `run_episode`, and prints a formatted
comparison table. This is literally the script that produced the very
first headline result of the whole project: **49.4% vs 26.0%**
interception (BeliefScheduler vs RoundRobin) --- the number that kicked
off the entire nine-day, sixteen-fix arc that followed.

------------------------------------------------------------------------

## File 2 of 18: `scan_scheduler_v2.py`

## The problem this file solves

Two separate weaknesses in the prototype's `BeliefScheduler`:

1.  **Fixed epsilon-exploration is crude.** An 8%-forever exploration
    rate means the scheduler keeps randomly sampling bands it already
    understands perfectly well, wasting scan budget indefinitely --- and
    there's no principled way to pick "8%" versus any other number.
2.  **Single-channel scanning is unrealistic.** Real ESM receivers with
    digital channelizers can listen to several bands simultaneously.

Both get fixed here, and (as the project matured) this file became the
load-bearing parent class that `v3` and `v4` build on, so it absorbed a
lot of later fixes too.

## Line-by-line walkthrough

**Lines 1--18 --- docstring.** States the two headline upgrades (UCB
exploration, multi-channel scanning) that motivated the file's creation.

**Lines 20--28 --- imports.** Adds `math` (needed for `log`/`sqrt` in
the UCB formula) on top of the prototype's imports, and --- importantly
--- **imports directly from `scan_scheduler_prototype`** (line 26--28):
`MarkovEmitter`, `PeriodicEmitter`, `AgileEmitter`, `Environment`,
`make_scenario`. This is the exact dependency that caused the "missing
file" bug found later --- someone assumed v2 could stand
alone once v3 existed, but v2 itself needs v1's emitter classes and
scenario builder; it doesn't redefine them.

**Lines 35--65 --- `recommended_warmup_dwell()`.** This function did
**not** exist in the original v2 --- it was added on Sept 8 as the final
polish on the "warmup devastation under switch cost" fix (the very last
item chased down over several rounds of debugging). Its job: given a
real `switch_cost_steps` (how long re-tuning takes) and how long you'd
normally warm up for, compute two things --- the right per-band "dwell"
length during warmup, and a *scaled-up* warmup length to compensate for
the dwell eating into available laps. Line 61--62: if there's no switch
cost, dwell=1 and warmup length is untouched (pure backward
compatibility). Line 63: otherwise, dwell = cost + a 2-step safety
margin (empirically validated --- the docstring explicitly says `cost+1`
wasn't enough margin, `cost+2` was). Line 64: the warmup budget scales
up by the ratio `dwell / (dwell − switch_cost_steps)` --- the intuition
is, if each "visit" during warmup now wastes `switch_cost_steps` steps
just settling, you need proportionally more total warmup steps to get
the same number of *actually useful* looks at each band as you'd get
with instant switching.

**Lines 68--76 --- `Scheduler` base class (v2 version).** Same shape as
the prototype's, but `choose_band()` → `choose_bands(k)` --- the
interface upgrade to multi-channel.

**Lines 79--92 --- `RoundRobinScheduler` / `RandomScheduler`,
multi-channel versions.** RoundRobin's `choose_bands` (84--87) now
returns `k` consecutive bands from the current pointer position and
advances the pointer by `k`. Random's (91--92) uses `random.sample`
(sampling *without* replacement) to grab `k` distinct random bands,
capped at `n_bands` in case `k` exceeds the total band count.

**Lines 95--248 --- `BeliefUCBScheduler`, the core upgrade.** This is
the file's centerpiece.

The class docstring (96--111) states the UCB score formula directly:
`score(b) = priority(b) * belief(b) + c * sqrt(log(t+1) / (scans(b)+1))`.
This is a textbook **UCB1** exploration bonus (Auer, Cesa-Bianchi &
Fischer): the second
term grows with total elapsed time `t` (so exploration pressure never
fully disappears) but shrinks as an individual band's own scan count
grows (so a well-understood band stops attracting exploration bonus).
The `log(t+1)` growth is deliberately slow --- it's what gives UCB
algorithms their famous "logarithmic regret" guarantee in bandit theory:
you keep exploring forever, just at a vanishing rate. `priority` (also
explained here) is the dial added later that lets you weight *how much a
band's exploitation term counts*, independent of how eagerly you still
learn its true behavior (exploration stays unweighted) --- this is what
let the project trade off "catch the rare radar" against "keep the loud
comm channel" as an explicit, tunable choice instead of an accident.

Constructor (113--156): parameters accumulated across the whole
project's history --- `ucb_c` (exploration strength), `warmup_steps`
(forced open-loop sweep length before UCB scoring kicks in), `priority`
(per-band weight vector, defaulting to all-1.0 meaning "no preference,"
line 119), and then the Laplace-smoothed Markov counters (120--123,
identical mechanism to the prototype's `BeliefScheduler`), belief array
(124), scan-count tracking (126, needed for the UCB denominator), and
the warmup machinery (127--156) --- `_warmup_order`/`_warmup_idx` for
the shuffled sweep, and
`warmup_dwell_steps`/`warmup_dwell_jitter`/`_warmup_slots` for the
dwell-with-jitter mechanism, whose entire rationale is spelled out in
the long comment (130--153) --- I'll explain the mechanism itself when
we hit the methods below, since the comment previews exactly what those
methods do.

`_p_on_given_off`/`_p_on_given_on`/`_propagate` (158--166): identical
logic to the prototype's `BeliefScheduler` --- ratio lookups and the HMM
forward-propagation step.

`_next_warmup_band` (168--179): pulls the next band from a
**shuffled-per-lap** sweep order. Line 173: if we've exhausted the
current shuffled lap, build a fresh one (174: full band list, 175:
`random.shuffle` --- a *new* random order, not the same fixed rotation
repeated). This shuffle-per-lap design is the fix for a real bug found
early in the project: with a *fixed* rotation, if
`gcd(scan_period, emitter_period)` doesn't evenly divide the phase
offset between the scan cycle and a periodic emitter's cycle, the two
sequences can be mathematically guaranteed to *never* intersect, no
matter how long you run --- a permanent blind spot. Shuffling breaks
that fixed relationship every lap while still guaranteeing full coverage
each lap (since it's a shuffle of *all* bands, not a subsample).

`_warmup_bands` (181--217, docstring at 182--202): this is the
dwell+jitter mechanism. One "slot" per channel (line 203--206 lazily
grows `_warmup_slots` to size `k` if needed). For each slot: if its
remaining dwell time has expired (`remaining <= 0`, line 209), pull a
fresh band from the shuffled order (210) and set a new dwell duration
--- `warmup_dwell_steps` plus a random jitter amount between 0 and
`warmup_dwell_jitter` (211--214). Otherwise, keep the same band and just
decrement the remaining counter (216). With the default
`warmup_dwell_steps=1`, `remaining` always hits zero immediately, so
this collapses to "always pick a fresh band" --- byte-identical to the
pre-dwell behavior, which is exactly why this change was safe to make
without breaking every earlier validated result.

The *reason* dwell+jitter exists at all (explained in the docstring,
187--202, and worth restating because it's one of the most subtle bugs
in the whole project): under a real switch cost, if warmup switches
bands every single step (dwell=1), it suffers the exact same failure as
`RoundRobin` under switch cost --- always mid-retune, never actually
observing anything. Simply making dwell longer (camping on each band for
several steps) fixes *that* problem but creates a new, sneakier one:
with a *fixed* dwell width, the "wasted" (settling) steps and "valid"
(observing) steps fall on *fixed, predictable positions* relative to the
sweep's lap length --- so if a periodic emitter's true phase happens to
always coincide with the wasted parity, it becomes *permanently*
unobservable, structurally, no matter how many laps you run. This is
mathematically the same aliasing phenomenon as the fixed-rotation blind
spot that motivated shuffling in the first place, just recurring one
level deeper (in the dwell timing rather than the band order). Jitter
--- randomizing dwell length by a few extra steps --- breaks that fixed
parity the same way shuffling broke the fixed rotation.

`choose_bands` (219--233): line 220 advances the internal clock. Lines
221--224: if still within the warmup window, propagate every band's
belief (still learning passively) but return warmup bands rather than
UCB-scored ones. Lines 225--233 (the normal closed-loop path): propagate
all beliefs, compute the UCB score for every band per the formula in the
docstring (227--231), sort bands by score descending (232), and return
the top `k` (233).

`update` (235--248): identical Markov-counting logic to the prototype's
version, plus line 248 incrementing `scan_count[band]` --- the piece the
UCB formula's denominator depends on.

**Lines 255--275 --- `RunStats` (v2 version).** Expanded from the
prototype's version to track `switches` (how many times a scheduled band
differs from what was scanned last step) and `wasted_scans` (steps spent
settling after a switch, contributing zero observation) --- both of
which only become meaningful once `switch_cost_steps > 0`, added much
later. `total_band_transmissions` (258) replaces the prototype's
`total_transmissions` with a **per-band** count rather than "any band
transmitting" --- necessary once multi-channel scanning means you can
catch more than one transmission in a single step, so the old single
"did something happen this step" denominator would undercount
opportunity.

**Lines 278--345 --- `run_episode` (v2 version, with switch-cost
modeling).** The docstring (280--299) explains `switch_cost_steps`,
added later in the project: when a channel moves to a band it wasn't
parked on last step, that band is **blind** for `switch_cost_steps`
steps --- no `scheduler.update()` call happens (so its belief model
isn't corrupted with a fake observation, it just gets nothing, matching
a real receiver that isn't tuned in yet), and no interception credit is
awarded even if the band really was transmitting during that window.
Default `0` --- verified throughout the project to be a byte-for-byte
no-op, so every earlier validated result stays intact.

Mechanically: `prev_bands` (304) tracks which bands were scanned last
step; `settling_remaining` (305) is a per-band countdown of how much
settling time is left. Inside the loop, per selected band (322--339): if
switch-cost modeling is active and this band wasn't scanned last step
(324), it's a genuine switch --- start its settling countdown and
increment the switch counter (325--326). If it's still settling (327),
burn one settling step, count it as wasted, and `continue` --- skip
straight past observation for this band this step (330). Only once
settling has fully elapsed does the band actually get observed (332) and
fed to `scheduler.update()` (333), with hit/delay bookkeeping identical
in spirit to the prototype. Line 343 resets `prev_bands` to this step's
choices for next iteration's comparison --- and note the docstring's
explicit callout (296--298): a band that was scanned, then abandoned,
then re-scanned later pays the **full** switch cost again --- no "still
warm" credit, matching how a real local oscillator actually behaves once
it's been retuned elsewhere.

**Lines 348--377 --- `main`.** Runs the three-way comparison
(RoundRobin/Random/BeliefUCB) across `k_channels ∈ {1, 2, 3}`, reseeding
for each `k` so the comparisons are fair. This produced the "k=1: 12.8%
vs 27.4%, k=2: 25.1% vs 54.9%, k=3: 37.5% vs 68.2%" table from the
earliest multi-channel experiments --- showing the multi-channel and UCB
gains compound rather than substitute for each other.

------------------------------------------------------------------------

## File 3 of 18: `scan_scheduler_v3_pri.py` --- the PRI-aware periodicity estimator

This is the largest, most heavily-debugged file in the project ---
nearly every "found a bug, fixed a bug" episode across the whole
project's debugging history happened inside this one file. It's worth taking
slowly.

## The problem this file solves

`BeliefUCBScheduler` (v2) only knows first-order Markov structure: "this
band was recently on, so it's probably still on." That's a reasonable
model for bursty comms traffic, but it's a *terrible* model for a
**fixed-PRI radar** --- a radar that emits a brief pulse at a strictly
regular interval (its Pulse Repetition Interval), then goes silent for a
long stretch until the next pulse. Between pulses, a Markov model has
essentially nothing to go on --- "recently on → still on" has nothing to
say about a band that's been off for the last 11 steps and is about to
fire on step 12. This is also literally named in the DRDO problem
statement: *"approaches to intercept a periodic scan receiver optimally
should be outlined."*

The fix is to explicitly model periodicity: track the actual gaps
between confirmed hits, estimate the period (PRI) and its uncertainty,
and predict *exactly when* the next pulse is due --- then score that
predicted moment highly, instead of relying on a decaying "recently
seen" signal.

## Line-by-line walkthrough

**Lines 1--22 --- docstring.** States the motivation directly, and
importantly states the intended failure-safe design: "For bursty/agile
bands (no stable period), the gap variance stays high, confidence drops
to \~0, and the scheduler falls back to the plain belief+UCB score ---
so this is a strict upgrade, not a trade-off." (In practice, the
multi-step-burst regression discovered later showed this promise didn't
fully hold --- more on that below.)

**Lines 24--37 --- imports.** `Counter` from `collections` (for finding
the most common pairwise gap --- the "mode" in PRI histogramming);
`reduce` from `functools` (for folding `math.gcd` across a whole list of
differences to get their overall GCD). Lines 31--37 import from **both**
v2 and the original prototype --- v3 needs v2's `BeliefUCBScheduler` to
subclass, and the prototype's raw
`Emitter`/`MarkovEmitter`/`AgileEmitter`/`Environment`/`make_scenario`
to build its own test scenarios. This three-file dependency chain is
exactly what the "missing files" bug encountered earlier was about.

**Lines 40--58 --- `SparsePeriodicEmitter`.** A new emitter type,
distinct from the prototype's `PeriodicEmitter`: instead of a multi-step
beacon that hops through several bands, this is a **single instantaneous
pulse** on one fixed band every `pri` steps. Line 56:
`self.on = (t % self.pri == 0)` --- deceptively simple, but this is
exactly the shape of a real fixed-frequency radar and is the emitter
that motivated the whole PRI-estimator's existence: with a Markov model,
a band that's OFF 11/12 steps has near-zero belief right before the
pulse, so a Markov-only scheduler essentially never looks at it at the
right moment.

**Lines 60--71 --- `make_sparse_scenario`.** Builds the specific test
world used for the project's most-cited headline result: 2 Markov comms,
one `SparsePeriodicEmitter` on band 5 with period 12, and one
`AgileEmitter` threat. This is the scenario behind the "100% radar / 79%
comm-1" numbers referenced throughout the rest of the project.

**Lines 74--150 --- `PRIAwareScheduler.__init__` and class docstring.**
The docstring (75--98) is worth reading closely because it documents a
bug *in the class comment itself* --- a rare and useful practice. It
explains the periodicity-scoring mechanism (median gap → PRI, stdev →
jitter, a Gaussian bump around the predicted next occurrence), then
explicitly calls out the "beacon regression" bug: fitting jitter from
*onset* timing precision conflates "the start time is very predictable"
with "the event is instantaneous." A multi-step burst (on for 4
consecutive steps) has near-zero onset jitter too, which used to
collapse the phase-bump to a single-point spike --- meaning the
scheduler would confidently predict the burst's *start* and then abandon
it after one step, even though the burst was still ongoing. This was
strictly *worse* than the dumber Markov model, which --- via its learned
`P(on|on)` --- naturally stays elevated for the whole burst.
`max_run_ever` (explained at the end of the docstring) is the fix, which
we'll see in the update method.

Constructor parameters (100--104), each corresponding to a specific
historical addition: - `history_len=30`: how many recent confirmed hits
to remember per band (a sliding window) - `min_confidence=0.75`: the
threshold a periodicity estimate must clear before being trusted at
all - `periodicity_weight=1.5`: how strongly to weight the periodicity
signal once trusted, relative to plain belief - `confidence_scale=0.25`:
the eagerness/conservatism knob added during the "tune the harmonic fix"
work --- the comment (111--120) explicitly documents that this exact
value was chosen via a Pareto-trade-off sweep
(`tune_confidence_threshold.py`), not guessed - `switch_lead_steps=0`:
the anticipatory-switching fix, added to handle switch-cost
re-acquisition --- the comment (122--136) explains precisely why:
without lead time, the scheduler always arrives at a periodic band
exactly as the pulse starts, meaning under any real switch cost it's
*always* a cold switch, so it's always still settling exactly when the
pulse hits (empirically confirmed: 267/285 band-5 visits were fresh
switches) - `warmup_dwell_steps`/`warmup_dwell_jitter`: passed straight
through to the parent `BeliefUCBScheduler.__init__` (105--107)

State arrays (137--150): `hit_times` --- per-band list of confirmed hit
timestamps (the raw data the whole periodicity estimate is built from);
`pri_estimate`/`jitter_estimate`/`confidence` --- the model's current
belief about each band's periodicity; `max_run_ever` (150) --- the
persistent, never-shrinking burst-width tracker that fixes the
point-vs-plateau bug, explained in the trailing comment (141--149): it
has to be tracked *outside* the sliding `hit_times` window because once
the buggy point-spike behavior kicks in and starts abandoning bursts
early, the *evidence* of the true burst width (a long run of consecutive
hits) never even gets recorded in the first place --- a chicken-and-egg
problem that a merely-larger sliding window wouldn't fix.

**Lines 152--155 --- `_score_candidate` (static method).** A coarse
periodicity test: given a list of pairwise time-differences and a
candidate period, count what fraction of diffs are "close" (within
`tol`) to *some* integer multiple of the candidate. Line 154:
`round(d / candidate) * candidate` finds the nearest multiple of the
candidate to each diff, then checks if the diff is within `tol` of that
multiple. This method is now vestigial --- a comment further down (line
270--272) explains it was replaced as the primary selection criterion by
the least-squares refinement, but it's kept around ("harmless, might be
useful for diagnostics").

**Lines 157--188 --- `_refine_pri` (static method), the least-squares
fractional-period fit.** This is the fix for a genuinely elegant bug: if
the true period isn't an *exact integer* number of scan-steps (e.g., a
650µs-PRI radar sampled with a 20µs dwell has a period of exactly 32.5
steps), then consecutive gaps between hits **alternate** between 32 and
33 --- and naive integer-tolerance matching degrades badly as this
rounding error compounds over a long observation history, even though
the emitter is perfectly, mathematically periodic. The fix: treat this
as a linear regression problem. Each hit time `t_i` should fit the model
`t_i = a + b·n_i`, where `n_i` is that hit's inferred cycle index (line
176: `round((t - t0) / seed_candidate)`) and `b` is the *true,
possibly-fractional* period. Lines 179--187 are a textbook
ordinary-least-squares slope/intercept fit: `b = Σ(n-n̄)(t-t̄) / Σ(n-n̄)²`
(the standard covariance-over-variance slope formula), then `a` from the
mean residual, then RMSE of the fit as a quality measure. This recovers
a period like `32.5048` instead of oscillating between `32` and `33` ---
accurate to within 0.005% of the true 32.5 in the validated test case.

**Lines 190--314 --- `_update_pri_model`, the core estimator, called
after every confirmed hit.** This is where nearly every bug in the
project's history was found and fixed, layered on top of each other:

-   Lines 192--195: require at least 8 confirmed hits before attempting
    any estimate at all --- below that, there's not enough data to
    distinguish a real period from noise. (This exact threshold, "8
    hits," is what caused the notorious "coin-flip lock-on cliff" bug
    discovered via `diagnose_pri_lockon.py` --- the warmup sweep's
    *expected* hit count for a rare band landed right on top of this
    cutoff, making lock-on a near-50/50 seed lottery. That bug was fixed
    in a *different* file, `v4_persistent.py`, not here --- this file
    just defines the threshold that made the bug possible.)
-   Line 204: build **all pairwise time differences** between hits ---
    the classic PRI-histogramming technique real ESM systems use
    (mentioned explicitly in the comment) --- because the true period
    should be a common factor across *most* of these differences, not
    just the smallest gap (which is fragile to noise/missed cycles).
-   Lines 206--221: the "dense run" guard. If the scheduler recently
    scanned a band on several *consecutive* steps (e.g., because it's
    confidently locked onto a loud comm channel), the resulting run of
    back-to-back integer hit-times will trivially contain "multiples" of
    almost any small candidate purely by combinatorics --- the comment
    gives a concrete example (a run 100--110 contains diffs of 2 through
    10). The fix: track the longest observed run of consecutive-step
    hits (`max_run`, computed via a simple linear scan at 215--220 ---
    increment `run` while consecutive, reset to 1 otherwise, track the
    max), update `max_run_ever` to never shrink (221), and set a
    `min_candidate` floor (222) that rules out any candidate small
    enough to be a coincidental artifact of that densest run.
-   Lines 224--228: filter the diff pool to only differences at or above
    `min_candidate`; bail out with zero confidence if nothing qualifies.
-   Lines 239--248: **candidate generation**, from two complementary
    sources. Method 1 (240--242): the GCD of *all* diffs via
    `reduce(math.gcd, diffs)` --- exact and immediate when the diffs are
    clean integer multiples of the true period with no jitter, but
    useless (collapses to 1) under real noise. Method 2 (243--248): the
    statistical **mode** of the diff pool (the single most frequently
    occurring gap value) plus its small-integer divisors (dividing by 2
    through 8) --- this catches the case where the mode lands on a
    *harmonic* of the true period (e.g., 168 = 14×12) rather than the
    fundamental itself, since a true fundamental is often a divisor of a
    common harmonic.
-   Lines 250--268: the **off-by-one neighbor expansion** --- the last
    major bug fix in this file's history. The comment explains a real,
    concretely-traced failure: on one PDW seed, the true period was 32.5
    steps, but the pairwise-diff mode landed on **33**, not 32 --- and
    that single-step error wasn't just "slightly wrong," it caused a
    **rounding collision** in the least-squares fit (two genuinely
    distinct hits mapping to the same inferred cycle index `n_i` once
    the seed error compounded across enough cycles), which inflated 33's
    residual far more than a naive "off by one" error would suggest.
    Since neither GCD, mode, nor any submultiple of the mode ever
    generated the correct value (32) as a candidate at all, the fix
    (265--268) is to also test every candidate's immediate ±1 integer
    neighbors --- cheap to try, and it directly patches this exact
    failure mode.
-   Lines 270--295: **candidate selection via refinement quality**,
    replacing an earlier, cruder approach. For every candidate, run the
    least-squares refinement (284) and compute its *relative* error
    (`rmse / refined`, line 287) --- pick whichever candidate has the
    smallest relative error, i.e., the tightest actual fit, rather than
    whichever merely passes a coarse "close enough" tolerance test. The
    comment (270--281) explains why this mattered: when the true period
    is fractional and GCD collapses to 1 under jitter, a harmonic can
    sometimes score *better* than the true fundamental on the coarse
    binary in/out-of-tolerance test for a given noise draw --- but the
    refined fit's continuous residual is a much more sensitive
    discriminator.
-   Lines 297--314: final gating. If no candidate refined successfully,
    or the winning fit is too poor, report zero confidence (297--300).
    Otherwise compute confidence as
    `1 − rmse/(confidence_scale × refined_pri)` (302) --- a **relative**
    fit-quality score: perfect fit → confidence 1, fit error comparable
    to `confidence_scale` fraction of the period → confidence 0. Only if
    confidence clears `min_confidence` (0.75) is the estimate actually
    committed (303--311); crucially, line 310 is the **plateau-jitter
    fix**: `jitter_estimate = max(0.5, rmse, max_run_ever/2.0)` --- the
    floor is no longer just the fit residual or a flat 0.5 minimum, it
    also respects half the observed burst width, so a 4-step burst gets
    a jitter wide enough that the phase-bump doesn't collapse after one
    step, while a genuinely single-instant radar (max_run_ever=1) is
    untouched.

**Lines 316--341 --- `_periodicity_score`, the Gaussian phase bump.**
Given a band and current time `t`: find the phase offset from the last
known hit modulo the estimated PRI (320--321), take the distance to the
*nearest* predicted occurrence --- wrapping around, so being one step
early or late are symmetric (322: `min(phase, pri - phase)`). Lines
323--339 are the **switch-lead plateau fix**, explained in detail in the
inline comment: rather than shifting the whole score curve forward in
time (which was tried first and failed --- it just relocates the peak
rather than widening it, so the scheduler switches in early, gets stuck
settling, and then abandons the band on the very step the real pulse
arrives, having moved the "peak" earlier without protecting the actual
arrival time), the fix floors the distance itself at
`dist − switch_lead_steps` (339) --- creating a flat maximum-score
*plateau* spanning the whole window from `predicted − lead` to
`predicted`, so arriving early and then staying through the real arrival
is what actually gets rewarded. Line 341 turns the (possibly plateaued)
distance into a score via a Gaussian: `exp(−dist²/(2σ²))`, where σ is
the jitter estimate --- this is what gives the "phase bump" its bell
shape, sharp for a confident/narrow estimate, wide for an
uncertain/burst one.

**Lines 343--359 --- `choose_bands`.** Same warmup-gating structure as
v2 (344--348). Once past warmup, for every band: compute the UCB
exploration bonus exactly as in v2 (353), get the current periodicity
confidence and phase-bump score (354--355), and **blend** plain Markov
belief with the periodicity signal weighted by confidence (356):
`(1−conf)×belief + conf×periodicity_weight×periodic`. This is the
"strict upgrade, not trade-off" design promised in the docstring --- a
band with zero periodicity confidence contributes zero periodicity term
and falls back entirely to Markov belief, exactly like v2's
`BeliefUCBScheduler`. Line 357 applies the priority multiplier and adds
the (unweighted) UCB bonus, matching v2's design philosophy.

**Lines 361--368 --- `update`.** Calls the parent's Markov-counting
update (362) first, then --- only on an actual hit (363) --- appends
this timestamp to `hit_times` (364--365), trims the sliding window to
`history_len` (366--367), and re-runs the full PRI model update (368).
Note the PRI model is *only* re-estimated on a confirmed hit, never on a
miss --- misses don't add information about periodicity.

**Lines 371--489 --- the demo/comparison functions.** `run_comparison()`
(371--415) runs the standard multi-step beacon scenario at k=1,2 and
prints a PRI diagnostic confirming the beacon's true 12-step period is
(or isn't) correctly recovered on the right bands.
`run_sparse_comparison()` (418--483) is the file's headline
demonstration: runs the sparse single-pulse-radar scenario, then breaks
down **per-emitter** capture (455--475, the `per_emitter_capture`
helper) rather than one blended interception number --- this function is
literally what produces the "radar caught X/Y (100%), comm-1 caught X/Y
(79%)" invariant number quoted as the fixed reference point throughout
every later validation script in the project.

------------------------------------------------------------------------

## File 4 of 18: `scan_scheduler_v4_persistent.py` --- fixing the coin-flip lock-on

This is a short file (149 lines) but it fixes one of the most
consequential bugs found in the whole project --- one measured, not just
suspected: a headline "100% capture" result that was actually a
near-coin-flip across random seeds.

## The problem this file solves

`PRIAwareScheduler` (v3) refuses to even attempt a PRI estimate below 8
confirmed hits (line 192 of v3, `if len(times) < 8`). The problem:
during an 800-step warmup sweep, a rare band (like the sparse radar,
pulsing 1-in-12 steps) gets scanned roughly 100 times, so its *expected*
hit count is `100/12 ≈ 8.3` --- landing right on top of the 8-hit
cutoff. Whether any given random seed happens to cross that threshold is
essentially a coin flip (binomial noise around a mean of 8.3). Worse,
once warmup ends, a band that fell just short gets essentially no
further scans --- its UCB exploration credit is already spent from 100
warmup visits, and its Markov belief sits near zero (since it's off
\~92% of the time). So missing the threshold during warmup means being
locked out **permanently**, not just delayed. This is what produced the
measured "30.0% ± 48.3% capture across 10 seeds" bimodal result
measured directly --- half the seeds locked on and got 100%,
half never crossed the threshold and got \~0%.

## The algorithm: a persistent, hit-count-gated exploration bonus

## Line-by-line walkthrough

**Lines 1--61 --- docstring.** This is unusually thorough and worth
reading as-is since it documents the exact debugging process: the root
cause (lines 4--17), the fix's mechanism (19--33), and --- importantly
--- **two separate bugs found while building the fix itself**, both
explained with concrete numbers (35--58). I'll expand on both when we
hit the relevant code.

**Lines 63--66 --- imports.** Just `math` and `PRIAwareScheduler` from
v3 --- this class is a direct subclass, adding one new mechanism on top.

**Lines 69--93 --- `PersistentPRIAwareScheduler.__init__`.** Three new
parameters beyond what v3 already has: - `char_bonus_c=1.5` (70):
strength of the new "characterization bonus" - `required_hits=8` (71):
**must match** v3's internal 8-hit gate exactly --- the comment (75--77)
is explicit that this bonus exists purely to help a band *reach* that
sample size, not to chase periodicity confidence indefinitely once it's
already past the gate - `give_up_after_scans=300` (71): the second bug's
fix, explained below - `**kwargs` (72): forwards any other parameters
straight through to `PRIAwareScheduler.__init__` via
`super().__init__(n_bands, **kwargs)` (73) --- this is a deliberate
design choice that paid off later: because v4 uses `**kwargs` rather
than explicitly naming every v3 parameter, when `confidence_scale`,
`switch_lead_steps`, `warmup_dwell_steps`, etc. were added to v3 in
*later* revisions, v4 needed **zero code changes** to automatically
support them --- confirmed directly ("v4 needs no code changes, confirmed
via `**kwargs`"). - `self.total_hits`
(93): the actual new state --- a per-band counter of confirmed hits
that, unlike v3's `hit_times`, is **never truncated**. This distinction
matters: v3's `hit_times` is a sliding window capped at `history_len`
(30) for the PRI *estimator's* purposes, but that's the wrong signal for
"has this band accumulated enough evidence yet" --- a band could have
had 8 confirmed hits total but have some of them fall outside the
current window. `total_hits` is a clean, monotonically-increasing count
of all-time evidence.

**Lines 95--98 --- `update`.** Calls the parent's full update logic (96,
which itself calls v3's, which calls v2's Markov-counting logic and PRI
re-estimation) --- then, if this was a real hit, increments `total_hits`
(98). This is the only state change added at update-time; the actual
scoring behavior change happens in `choose_bands`.

**Lines 100--123 --- `choose_bands`, the actual fix.** Same
warmup-gating and belief-propagation structure as v3 (100--107). The
scoring loop (108--121) computes everything v3 does --- UCB bonus (110),
blended belief/periodicity score (111--113) --- and then adds the new
**characterization bonus** term (115--121):

    char_bonus(b) = char_bonus_c * sqrt(log(t+2) / (total_hits[b] + 1))

This has the exact same *mathematical shape* as a UCB bonus, but with a
critical substitution: the denominator uses `total_hits[b]` (confirmed
ON evidence) instead of `scan_count[b]` (total scans of any outcome).
This targets the genuinely scarce resource --- this is the whole point
of the fix. A band scanned 100 times during warmup but yielding only 6
hits still has a *low* `total_hits`, so this bonus stays high even
though the ordinary UCB term (which sees `scan_count=100`) has already
mostly decayed --- giving the band a "second chance" post-warmup that
plain UCB exploration wouldn't provide.

But the bonus is only applied under a **two-part gate** (116--117), and
this gate is exactly where the two bugs documented in the docstring
live:

**Bug 1 (documented at 38--45): the gate must be on `total_hits`, not on
"confidence still below threshold."** The first implementation attempt
gated the bonus on whether the band had achieved periodicity confidence
yet. That's subtly wrong: a genuinely aperiodic band (like the
frequency-agile threat, whose activity is split unpredictably across 4
different bands, so no single band ever racks up much evidence) will
*never* earn periodicity confidence --- not because it needs more
samples, but because there's genuinely no period to find. Gating on
"confidence still low" means the scheduler chases that band **forever**,
since the bonus condition can never resolve to false. The docstring
reports the measured damage: comm-1 capture tanked from \~85% to \~21%
under this first version. Line 116's actual gate ---
`total_hits[b] < self.required_hits` --- fixes this by asking a bounded,
resolvable question ("have we hit 8 confirmed samples yet") instead of
an open-ended one ("has periodicity confidence emerged yet").

**Bug 2 (documented at 47--58): even the hit-count gate alone isn't
sufficient --- you also need a hard scan-attempt cap.** Consider a band
with *no emitter at all* (always silent, duty cycle exactly zero) ---
this actually exists in the test scenarios as a deliberate stress case.
Its `total_hits` stays at 0 forever, no matter how many times it's
scanned, since it structurally can never produce a hit. That means
`1/(total_hits+1) = 1` forever --- the bonus term never decays, and in
testing, this single always-silent band ended up absorbing **3,300 of
4,000 total post-warmup scans** --- nearly the entire simulation budget,
chasing a band that mathematically could never pay off. Line 117's
second gate condition, `scan_count[b] < give_up_after_scans` (default
300), caps how many total attempts a band gets while still under the
hit-count requirement, independent of whether it ever accumulates hits
--- giving the scheduler a principled way to eventually give up on a
genuinely dead band, mirroring the discipline the ordinary UCB term
already applies to confidence-in-general, just re-applied specifically
to this new hit-count-aware bonus.

Line 121: the final score sums the priority-weighted blended
belief/periodicity term, the ordinary UCB bonus, and (when the gate is
open) this new characterization bonus.

**Lines 126--150 --- demo/sanity-check block.** A three-way comparison
(plain `BeliefUCB`, original `PRIAware`, and the new
`PersistentPRIAware`) on the sparse-radar scenario at a single fixed
seed (11) --- a quick spot-check, not the full multi-seed validation
(that lives in `multi_seed_robustness.py`, coming up soon in this
walkthrough). The validated headline result from the full 20-seed run
(from the full validation run, not reproduced by this quick script)
was: radar capture went from a bimodal `50.0% ± 51.3%` (10/20 seeds
locking on) to a reliable `93.5% ± 0.7%` (20/20 seeds locking on) ---
the coin-flip fully eliminated, at a modest, honest cost of roughly 6
percentage points of comm-1 coverage (the price of the extra
characterization-chasing).

------------------------------------------------------------------------

## Files 5 & 6 of 18: `pdw_loader.py` and `pdw_environment.py` --- bridging simulation to real data

These two files exist to answer one question: does any of this scheduler
machinery actually work on *real* radar signal data, not just the
hand-built toy scenarios? I'll cover both together since they're a
tightly coupled pair (loader → adapter).

## The problem these files solve

Every scheduler so far has only ever been tested against `Environment`
from the prototype --- a purely synthetic world built directly out of
`Emitter` subclasses. That's useful for controlled experiments, but it
says nothing about whether the approach generalizes to real, messy radar
data. The project's chosen real-world benchmark is the **Alan Turing
Institute's Turing Synthetic Radar Dataset (TSRD)** --- a published
dataset of realistic Pulse Descriptor Words (PDWs), the standard
low-level representation radar receivers actually output (each detected
pulse gets a Time of Arrival, Centre Frequency, Pulse Width, Angle of
Arrival, and Amplitude, plus a ground-truth emitter label for
evaluation).

The problem: the scheduler stack expects a very specific interface ---
"which bands are transmitting *this scan step*" --- but a PDW stream is
a flat, irregular list of individual pulse events with continuous-valued
timestamps and frequencies. Something has to translate between the two
representations without touching any scheduler code.

## `pdw_loader.py` --- getting PDW data (real or synthetic stand-in)

**Lines 1--28 --- docstring.** States the PDW schema explicitly (ToA in
µs, Centre Frequency in MHz, Pulse Width in µs, Angle of Arrival in
degrees, Amplitude in dB, plus a ground-truth label) and is upfront
about a real limitation: this sandbox can't reach `huggingface.co`
(outside the network allowlist) and the dataset requires a license/token
anyway --- so the real data was never actually downloaded or tested
against during development. This is disclosed honestly rather
than glossed over.

**Lines 33--46 --- `load_real_pulse_train`.** This function is written
to call the TSRD's own documented API ---
`turing_deinterleaving_challenge.PulseTrain.load(h5_path)` --- and was
never run, only written to match the published interface exactly (line
41's import is deliberately *inside* the function, so importing this
whole module doesn't fail just because that external package isn't
installed --- it only errors if you actually try to call this specific
function). Returns three things straight from the dataset's own object
model: `pt.data` (the actual PDW array), `pt.labels` (ground-truth
emitter assignment per pulse, for scoring), `pt.metadata` (receiver
configuration --- scan-mode vs. stare-mode, etc.).

**Lines 49--94 --- `generate_synthetic_pdw_stream`, the schema-faithful
stand-in.** Since the real data was unreachable, this function generates
*fake* data that matches the *shape* of real TSRD data closely enough to
build and validate the whole downstream pipeline. Line 61: seeds a NumPy
random generator for reproducibility. Two emitter categories get
generated, matching the real dataset's described mix:

-   **Fixed-frequency, near-constant-PRI emitters** (lines 66--76):
    three hardcoded radars, each defined by
    `(centre_frequency, pri, pulse_width, angle_of_arrival)` --- e.g.,
    `(9200, 650, 1.2, 140)` means a 9.2 GHz radar pulsing every 650µs.
    Line 71 picks a random phase offset (`rng.uniform(0, pri)`) so
    different emitters don't all start in lockstep. The generation loop
    (72--75) walks forward in time, emitting one pulse per PRI cycle,
    with **realistic noise added at every level**: the actual centre
    frequency wobbles by `rng.normal(0, 0.5)` MHz (73), the angle of
    arrival wobbles similarly, amplitude is drawn uniformly in a
    plausible dB range, and --- critically --- line 75 adds **PRI
    jitter**: `t += pri * (1 + rng.normal(0, 0.02))`, meaning each
    inter-pulse gap is randomly perturbed by about 2%. This small jitter
    is exactly what makes the fractional-PRI-recovery problem in v3
    nontrivial --- a real radar's PRI isn't a perfectly noiseless clock
    tick.
-   **Frequency-agile emitters** (lines 79--89): two hoppers, each
    defined by a *list* of candidate centre frequencies it can hop
    between (e.g., `[500, 3300, 6100, 11800, 16200]` MHz) plus a nominal
    PRI. Line 85 picks a random frequency from the hop-list for each
    pulse --- this is the PDW-data equivalent of the `AgileEmitter`
    class from the prototype, deliberately unpredictable.

Line 91 sorts all generated pulses by arrival time (since two
independent emitter generation loops produce pulses in separate
time-order, they need to be merged/sorted before use). Lines 92--94 pack
everything into a NumPy **structured array** with named fields (`toa`,
`cf`, `pw`, `aoa`, `amp`, `label`) --- this is what lets downstream code
access `pdw["toa"]` or `pdw["cf"]` like dictionary keys while still
getting the memory efficiency of a typed array.

## `pdw_environment.py` --- the adapter that makes it all compatible

**Lines 1--19 --- docstring.** States the design goal explicitly: bin a
raw PDW stream into the exact same "band status per step" dictionary
interface the original `Environment.step()` produces, so that **every
scheduler and every metric written so far runs completely unmodified**
against this new data source --- only the environment object changes.
This is a deliberate architectural choice that paid off across the whole
project: because the interface boundary was drawn correctly here on day
one, every later scheduler improvement (UCB, multi-channel,
PRI-awareness, persistent bonus) automatically became testable against
PDW data with zero adapter changes.

**Lines 24--45 --- `PDWReplayEnvironment.__init__`.** This is where the
actual binning happens, and it's the crux of the whole adapter. Two axes
need discretizing:

-   **Frequency → band index.** Line 30:
    `np.linspace(lo, hi, n_bands+1)` creates `n_bands` equal-width
    frequency bins spanning the given range (default 0--18 GHz, matching
    the real dataset's oracle "stare" receiver's full coverage). Line
    38: `np.digitize(cf, self.band_edges) - 1` maps every pulse's centre
    frequency to a bin index (NumPy's `digitize` returns 1-indexed bin
    numbers by default, hence the `-1`), and
    `np.clip(..., 0, n_bands-1)` guards against any pulse landing
    exactly on the upper boundary and getting bumped one bin too high.
-   **Time → scan-step index.** Line 39:
    `(toa // dwell_us).astype(np.int64)` --- integer-divide each pulse's
    arrival time by the dwell length to figure out which discrete "scan
    step" it falls into. This is precisely the parameter that caused the
    dwell-resolution bug found early in the PDW integration work: the
    default 200µs dwell was far coarser than the dataset's actual radar
    PRIs (650--1500µs), giving only 3--8 scan-steps per period --- too
    close to noise to reliably distinguish a real periodic pattern from
    a coincidentally-dense burst. Dropping to a 20µs dwell (used
    throughout later validation) fixed the resolution, but then exposed
    the fractional-PRI problem that `_refine_pri` in v3 was built to
    solve (650µs / 20µs = 32.5, not a whole number).

Lines 41--43: build a dense boolean matrix `self._status` of shape
`(n_steps, n_bands)`, then use NumPy's fancy indexing ---
`self._status[step_idx, band_idx] = True` --- to mark every
`(step, band)` cell that had at least one pulse land in it, in a single
vectorized operation rather than a Python loop over every pulse. This is
also where the **OR-collision** behavior from the original
`Environment.step()` gets naturally reproduced: if two different pulses
(possibly from two different emitters) land in the same band during the
same step, that cell is still just marked `True` once ---
indistinguishable from a single emitter. This is exactly the mechanism
behind the later "band 1 collision" finding, where a fixed-PRI radar and
a frequency-agile hopper happened to land in the same coarse 8-band bin,
making the combined signal genuinely non-periodic (correctly, not a
bug).

**Lines 47--53 --- `step()`.** Mimics the original `Environment.step()`
interface exactly: return a dict `{band: bool}` for the current step,
advance the internal clock, and --- if the clock runs past the end of
the actual data (line 48--49) --- just return an all-`False` row
(silence) rather than erroring, so a scheduler can keep running past the
end of a finite PDW recording without crashing.

------------------------------------------------------------------------

## File 7 of 18: `run_on_turing_dataset.py` --- the driver script

This file is the CLI entry point that ties every scheduler and both PDW
files together into something runnable end-to-end. It's also, in a real
sense, a *historical record*: its docstring and argument list
accumulated a new flag for nearly every fix discovered across the whole
project, and it explicitly documents which of those fixes are validated
versus merely wired-in-but-untested on real data.

## The problem this file solves

Everything up to this point is a library. Someone needs to actually run
it against PDW data with configurable parameters, print results in a
comparable format, and --- since this script kept getting "repointed"
across the project as new scheduler classes were built --- always
reflect the *current best* scheduler stack, not a stale one. Failing to
do this was a repeatedly-caught bug: "the driver is still stuck on the
old plain `BeliefScheduler`."

## Line-by-line walkthrough

**Lines 1--56 --- docstring.** This is unusually candid as documentation
goes, and worth reading closely rather than skimming, because it does
something most code comments don't: it tells you exactly what's been
validated and what hasn't. Lines 11--20 explain why this specific script
mattered as a fix target --- the same 8-hit lock-on threshold that made
the *toy* sparse-radar scenario a coin flip applies equally to real PDW
data's low-duty fixed-PRI emitters, but nothing confirmed the
persistent-bonus fix actually helped there rather than just on the toy
case it was diagnosed on. Lines 22--38 are even more pointed:
`switch_cost_steps`/`switch_lead_steps`/`warmup_dwell_steps` are wired
through, but explicitly flagged as **untested against real PDW data**
--- validated only on the toy scenarios, and even there found to be
*scenario-specific* (helps a sample-starved sparse radar, actively hurts
a dense beacon). This kind of "here's what this code does, and here's
specifically what I have NOT verified about it" documentation is a
pattern that shows up throughout this whole project's fix history.

Lines 40--56 give concrete usage examples, including the `--auto-dwell`
flag that auto-derives the dwell/warmup-scaling parameters via
`recommended_warmup_dwell()` (the function we saw in v2) rather than
requiring you to hand-compute them.

**Lines 58--67 --- imports.** Pulls from every layer of the stack built
so far: `scan_scheduler_v2` (the base schedulers, `run_episode`, and the
dwell-scaling helper), `scan_scheduler_v3_pri` (`PRIAwareScheduler`),
`scan_scheduler_v4_persistent` (`PersistentPRIAwareScheduler`), and both
PDW files. This is the file with the deepest import chain in the whole
project --- it transitively depends on all six of the "core" files.

**Lines 70--87 --- `load_pdw`.** Tries the real path first: if `--h5`
was given, attempt `load_real_pulse_train` (73). Two specific failure
modes are caught and handled gracefully rather than crashing:
`ImportError` (76--80) --- the `turing_deinterleaving_challenge` package
isn't installed, so print the exact pip-install command needed and fall
through; `FileNotFoundError` (81--82) --- the given path doesn't exist,
fall through with a clear message. Either way, or if `--h5` was never
given at all, it falls back (84--87) to the local synthetic stand-in
from `pdw_loader.generate_synthetic_pdw_stream`, seeded by `args.seed`
for reproducibility. This means the script is **always runnable**, even
with zero setup --- it just tells you honestly which data source it
actually used.

**Lines 90--96 --- `parse_priority`.** Parses a comma-separated CLI
string like `"1,1,1,1,5,1,1,1"` into a list of floats, validating the
count matches `n_bands` exactly (94--95) --- a defensive check against a
common CLI-typo failure mode (forgetting a value or adding an extra
one).

**Lines 99--156 --- `main`, argument parsing.** Each `argparse` argument
corresponds to a specific, traceable point in the project's history: -
`--h5`, `--n-bands`, `--dwell-us`: basic data-source and binning
controls (101--104) - `--k-channels`, `--warmup-steps`, `--ucb-c`: the
v2-era multi-channel and UCB parameters (105--110) -
`--confidence-scale` (111--118): the PRI eagerness dial, with its help
text explicitly stating the exact trade-off found by
`tune_confidence_threshold.py` --- smaller values are more conservative
and help the beacon toy scenario slightly but cost real fractional-PRI
reliability on this actual PDW path, which is why the default (0.25) was
*kept* rather than changed, prioritizing the real-data use case this
script exists for - `--priority` (119--122): the per-band weighting dial
from the priority-scoring work - `--seed` (123): controls only the
*synthetic stand-in's* randomness - `--switch-cost-steps`,
`--switch-lead-steps`, `--warmup-dwell-steps`, `--warmup-dwell-jitter`,
`--auto-dwell` (124--155): the entire switch-cost-modeling fix chain,
each with help text that explicitly states its default preserves prior
behavior exactly and (for the switch-cost path specifically) that it's
untested against real data at this integration point

**Lines 158--173 --- wiring up the auto-dwell convenience path.** If
`--switch-cost-steps > 0` and `--auto-dwell` was passed, this overrides
the manually-specified dwell/warmup/lead values by calling
`recommended_warmup_dwell()` (166--167) --- the same helper defined back
in v2 --- and setting `switch_lead_steps` equal to the switch cost (169)
as a sensible default starting point, then prints exactly what was
auto-derived (170--173) so the user isn't left guessing what values
actually got used.

**Lines 175--181 --- building the environment and step count.**
`env_factory` (175--176) is a closure --- a function that builds a fresh
`PDWReplayEnvironment` each time it's called, matching the `env_factory`
pattern `run_episode` expects from every earlier file. Line 178 builds
one throwaway instance just to read off `n_steps` (the effective length
of the recording). Lines 179--181: if there's no data at all (an empty
PDW stream), bail out cleanly rather than running a zero-length
simulation and printing meaningless results.

**Lines 183--190 --- status printing.** Reports the configuration
actually being used (step count, band count, dwell, channels, warmup,
switch cost), and --- importantly --- if `switch_cost_steps > 0`,
reprints the "this path is unvalidated against real data" warning right
at the point of use, not just buried in the module docstring (187--190),
so it's impossible to miss in the actual run output.

**Lines 192--206 --- building the four schedulers.** All four ---
`RoundRobin`, `Random`, `BeliefUCB`, `PRIAware`, `PersistentPRIAware`
--- get instantiated with the *same* resolved parameters (whether
manually specified or auto-derived), ensuring a fair, apples-to-apples
comparison. Note that `RoundRobin` and `Random` don't take most of these
parameters at all (they're dumb baselines), while the three learned
schedulers all get the full parameter set forwarded --- this is
`PersistentPRIAwareScheduler`'s `**kwargs` design paying off directly,
since `confidence_scale`, `switch_lead_steps`, etc. reach it without v4
ever needing to name them explicitly.

**Lines 208--222 --- running the comparison and printing results.** For
each scheduler, calls `run_episode` (215--216) with the switch-cost
parameter threaded through, then prints a formatted row including the
newer `switches`/`wasted_scans` columns from `RunStats` (only meaningful
once switch-cost modeling is active --- they'll be zero otherwise).
Lines 221--222: track any scheduler that's a `PRIAwareScheduler` (or
subclass, since `PersistentPRIAwareScheduler` inherits from it) in a
separate dict, for the diagnostic printout that follows.

**Lines 224--236 --- the PRI diagnostic.** For every PRI-capable
scheduler that was run, print which bands ended up with a
confidently-detected period, converting the estimate from scan-steps
back into real microseconds (`pri * dwell_us`, line 233) --- this is
exactly the printout that produced the project's other major headline
invariant:
`"estimated PRI = 32.5... scan-steps (~650.1 us), confidence = 0.90"`,
matching the true 650µs radar almost exactly. If nothing locked on at
all, line 234--236 prints a helpful nudge rather than silent emptiness.

------------------------------------------------------------------------

## File 8 of 18: `diagnose_pri_lockon.py` --- proving the coin-flip

This is the diagnostic script that turned a suspicious multi-seed
statistic into a mechanistically-understood, root-caused bug --- the
investigation that directly led to `scan_scheduler_v4_persistent.py`.

## The problem this file solves

`multi_seed_robustness.py` (which we'll get to shortly) had already
revealed something alarming: the sparse-radar "100% capture" headline
result --- the single most-quoted number in the whole project --- was
actually `30.0% ± 48.3%` across 10 seeds, essentially bimodal (either
locks on completely, or barely captures anything). That statistic tells
you *something is wrong*, but not *why*. This file exists purely to
answer "why" --- by instrumenting the scheduler's internals directly
rather than just re-running the black-box comparison.

## The approach: instrument, don't guess

## Line-by-line walkthrough

**Lines 1--14 --- docstring.** States the exact number being
investigated (30.0% ± 48.3%) and the method: instrument scheduler
internals across many seeds and look at what actually differs between
the seeds that lock on and the seeds that don't.

**Lines 16--28 --- imports and constants.** `RADAR_BAND = 5`,
`TRUE_PRI = 12`, `WARMUP = 800`, `N_SEEDS = 40` --- this file uses 40
seeds, more than the original robustness check's 10, for a more
statistically solid characterization once the investigation is already
targeted rather than exploratory.

**Lines 31--48 --- `InstrumentedPRIAware`, a debug subclass.** This is a
clean, minimal-footprint way to add logging without touching the actual
scheduler logic: subclass `PRIAwareScheduler`, override
`_update_pri_model` to call the real parent implementation (line 41) and
then, *only* for the specific band under investigation (line 42,
`if band == RADAR_BAND`), append a snapshot dict recording the
timestamp, how many hits had accumulated *before* this call (40), and
the resulting PRI estimate and confidence (43--48). This means every
single PRI-model update for band 5, across the whole simulated run, gets
a permanent trace --- letting you reconstruct the exact moment (if any)
confidence crossed the lock-on threshold.

**Lines 51--99 --- `run_one(seed)`, the per-seed instrumented run.**
Sets up a fresh scenario and scheduler (52--55), then tracks six
separate counters split by warmup-vs-post-warmup phase (57--62): scans
on band 5, hits on band 5, and *actual pulses* on band 5 (ground truth,
whether observed or not) --- each tracked separately for the warmup
window and the post-warmup window. The main loop (64--84) is a
manually-unrolled version of `run_episode` --- done this way (rather
than reusing `run_episode`) specifically so the extra bookkeeping (which
counters to increment, and whether we're still in warmup) can be
interleaved cleanly. Line 98 computes `radar_capture_pct` --- hits
divided by actual pulses, *restricted to the post-warmup phase* ---
which is the real metric of interest: did the scheduler actually catch
the radar once it mattered, not during the deliberately-suboptimal
warmup phase.

**Lines 102--114 --- `main`, the theoretical prediction.** Before even
looking at simulation results, this prints out the *predicted* mechanism
in plain arithmetic: with a shuffled full 8-band sweep during an
800-step warmup, band 5 gets scanned roughly `800/8 = 100` times (once
per lap). The radar is on for exactly `1/12` of all steps. So the
*expected* number of confirmed hits during warmup is `100/12 ≈ 8.3` ---
and since `_update_pri_model` requires at least 8 hits before attempting
anything, that expected value sits almost exactly on top of the
threshold. This is a deliberately falsifiable prediction stated up
front, before the data is examined --- good diagnostic practice.

**Lines 116--126 --- confirming the prediction statistically.** Runs all
40 seeds (116), then computes mean/stdev/min/max of hits-during-warmup
across all of them (120--122): the actual measured mean and spread
confirm the theoretical \~8.3 prediction closely, and --- critically ---
line 125--126 counts how many seeds fell *below* 8 hits by the end of
warmup: this is the direct, seed-by-seed confirmation that a large
fraction genuinely never crossed the cliff during the window that
mattered.

**Lines 128--131 --- final lock-on tally.** Splits seeds into `locked`
(final confidence ≥ 0.75) versus `not_locked`, and reports the count ---
the direct evidence for the bimodal 30%/100% split.

**Lines 133--139 --- the full per-seed table.** Prints every seed's
hits-at-warmup-end, final hit count, final PRI estimate, final
confidence, and radar-capture percentage --- the raw data anyone could
independently re-derive the aggregate statistics from.

**Lines 141--152 --- timing analysis for the seeds that DID lock on.**
This answers a follow-up question: for seeds that succeeded, *when* did
they cross the threshold --- during warmup, or only afterward via lucky
post-warmup scans? Line 148 finds the first log entry where confidence
crossed 0.75; line 151 reports whether that happened during or after
warmup. This check exists to rule out an alternative hypothesis --- that
the 800-step warmup budget just wasn't long enough in general, and
post-warmup scanning was doing the real work --- which would point to a
different fix (lengthen warmup) than the one actually pursued (give
under-sampled bands a persistent post-warmup bonus).

**Lines 154--165 --- post-mortem for the seeds that failed.** For each
non-locked seed, distinguishes two failure sub-modes: never accumulating
8 hits at all (158--160, the pure sample-starvation case), versus
reaching 8 hits but never getting a confident-enough fit (161--165,
showing the best attempt's confidence/PRI/timestamp) --- a useful
distinction, since the former points toward "needs more samples" while
the latter would point toward "the estimator itself is unreliable," and
the actual finding was overwhelmingly
the former.

------------------------------------------------------------------------

## File 9 of 18: `multi_seed_robustness.py` --- the general-purpose "is this real or a seed lottery" harness

This is the largest utility script in the project (412 lines) and
arguably the most methodologically important, since it's the tool that
first proved a headline result wasn't robust --- before this script
existed, every number quoted in the project was a single seeded run.

## The problem this file solves

Every scheduler comparison up to this point ran exactly once, with one
fixed random seed. A single run can't distinguish "the scheduler is
genuinely better" from "this particular random draw of comms bursts and
threat hops happened to favor it." Given how many subtle bugs had
already turned up purely by code inspection, the project needed a way to
statistically validate --- not just assert --- that a win was real.

## Line-by-line walkthrough

**Lines 1--28 --- docstring.** States the purpose directly and ---
importantly --- documents a specific methodological design decision
(18--23): this harness deliberately **replicates the existing
convention** of calling `random.seed(seed)` once per comparison, then
running every scheduler in sequence off the same continuously-advancing
global stream, exactly like the original scripts do. This choice is
explicitly a trade-off: it makes results directly comparable to the
single-seed numbers already reported, but (as later validation
revealed) it also means different schedulers in the same comparison see
*different* underlying environment realizations, not identical ones ---
a confound that later validation scripts (`settle_fix_interaction.py`)
had to specifically work around when they needed a truly
apples-to-apples comparison.

**Lines 30--51 --- imports.** Pulls schedulers from every generation:
`scan_scheduler_prototype` aliased with a `V1` prefix (36--41, to
disambiguate from v2's classes of the same name), `scan_scheduler_v2`,
`scan_scheduler_v3_pri`, `scan_scheduler_v4_persistent`, plus both PDW
files --- this file tests literally the entire scheduler lineage in one
run.

**Lines 58--66 --- `summarize`.** A small statistics helper: given a
list of values, returns mean, stdev (guarded against `n<=1` to avoid a
`statistics` library error on a single value), min, and max as a dict.

**Lines 69--78 --- `print_summary_table`.** Formats a summary dict per
scheduler into an aligned table, converting to percentage by default
(`scale=100.0`).

**Lines 81--88 --- `paired_delta`, the key statistical tool.** Given two
lists of values from the *same* seed sequence (85--86: this is a
**paired** comparison, not an independent-samples one --- critical,
since paired comparisons have much more statistical power when the same
random noise source affects both arms), computes per-seed differences
(`a - b` for each seed), then counts how many seeds had a strictly
positive difference (`wins`, line 84). This win-count is arguably more
informative than the raw mean/stdev --- "won in 8/10 seeds" tells you
about consistency in a way a single averaged number can hide.

**Lines 91--94 --- `print_delta`.** Formats a delta dict, including the
win count, into a single readable line --- this is the format behind
every `"+X.Xpp ± Y.Ypp, won Z/N seeds"` line quoted throughout the rest of this report.

**Lines 97--120 --- Suite A: the original prototype, re-tested.** For
each seed, seeds the global RNG once, then runs
`RoundRobin`/`Random`/`BeliefScheduler` (the *v1* classes) through
`run_episode_v1`, collecting the interception ratio from each. Reports
the summary table and --- the actual headline check ---
`BeliefScheduler vs RoundRobin`'s paired delta. This is what confirmed
the original 49.4%-vs-26.0% headline was a *robust* effect (10/10 win
rate confirmed by the multi-seed run), not the fragile kind of result
found elsewhere.

**Lines 123--148 --- Suite B: multi-channel comparison.** Same pattern,
but looped across `k ∈ {1,2,3}` (line 130), reseeding for each `k`
(137--138) --- testing whether the UCB/multi-channel gains from v2 hold
up across seeds at every channel count, not just k=1.

**Lines 151--176 --- Suite C: the beacon scenario.** Tests
`PRIAware vs BeliefUCB` on the standard multi-step beacon scenario
across `k ∈ {1,2}`. This is the suite that first statistically confirmed
the "beacon regression is real, not a single-seed artifact" --- PRIAware
losing in 9/10 seeds at k=2, matching what was found and eventually
root-caused (the point-vs-plateau jitter bug) later in the project.

**Lines 179--249 --- Suite D: the sparse radar scenario, both blended
and per-emitter.** Lines 183--204: the blended-interception-ratio
comparison, same pattern as before. But lines 205--249 do something more
careful, matching what the single-seed analysis had already shown
mattered: a **per-emitter capture breakdown**, not just one blended
number. The `per_emitter_capture` helper (208--230) is essentially a
manually-unrolled simulation (like the one in `diagnose_pri_lockon.py`)
that separately tracks radar-band and comm-1-band capture rates,
restricted to post-warmup steps (`if t > warmup`, line 219). This is the
exact function whose output --- run across 10 seeds instead of 1 ---
produced the `30.0% ± 48.3%` bimodal radar-capture statistic that
motivated the entire v4 investigation. Lines 240--246 print both the
summary tables and the paired deltas for radar and comm-1 capture
separately.

**Lines 252--303 --- Suite F: validating the v4 fix itself.** Nearly
identical structure to Suite D's per-emitter check, but comparing
`PRIAwareScheduler` (original) against `PersistentPRIAwareScheduler`
(the v4 fix) directly. Lines 299--302 add a specific "locked on" tally
--- counting how many seeds achieved radar capture above 50% for each
variant --- which is exactly the statistic that demonstrated the fix's
core claim: original `10/20` seeds locking on, fixed `20/20`.

**Lines 306--341 --- Suite E: the Turing PDW stand-in, tested across
seeds.** Notably, line 319--322's comment flags an important
methodological detail: each seed here generates a **different synthetic
PDW stream** (via `generate_synthetic_pdw_stream(seed=seed)`) in
addition to seeding the schedulers' own randomness --- so this suite
checks robustness to *both* the underlying data realization and
exploration noise, a stronger test than the other suites (which reuse
the same fixed scenario every seed and only vary scheduler randomness).

**Lines 344--358 --- `write_csv`.** Appends raw per-seed values to a CSV
file for anyone who wants to dig into the numbers independently rather
than trust the printed summary --- this produced
`multi_seed_results.csv`, one of the three data files sitting alongside
the code in the zip.

**Lines 361--408 --- `main`.** Parses `--seeds`/`--seed-start`/`--csv`
CLI args, builds the seed list, and runs every suite in sequence (A
through F), writing each suite's raw results to the shared CSV with a
distinguishing label. The closing print (405--408) states the
interpretive principle behind the whole file plainly: a delta whose mean
is well clear of zero relative to its own stdev, and that wins in most
or all seeds, is a robust effect --- anything else is closer to noise
than to a real finding.

------------------------------------------------------------------------

## File 10 of 18: `diagnose_beacon_regression.py` --- chasing a hypothesis that turned out wrong (which is itself a useful finding)

This file is a good example of honest diagnostic work: it tests a
specific, plausible hypothesis, and the data doesn't clearly support it
--- which is exactly the kind of finding worth keeping in the record,
since it's what redirected the investigation toward the real bug (found
via a follow-up periodicity-score inspection not fully captured in this
saved file, but referenced in its results).

## The problem this file investigates

`multi_seed_robustness.py`'s Suite C had already statistically confirmed
something odd: `PRIAware` beats `BeliefUCB` on the beacon scenario at
k=1 (+1.5pp, 8/10 seeds), but *loses* at k=2 (−1.5pp, 1/10 seeds) ---
same scheduler, same scenario, opposite sign, purely from adding a
second scan channel. The docstring (lines 8--14) states this precisely
and rules out one easy explanation up front: if periodicity-checking
simply had a fixed computational/bookkeeping cost, that cost would show
up at k=1 too, not just k=2. Something about *having two channels
available* specifically is what flips the sign.

## The hypothesis under test: "double beacon betting"

## Line-by-line walkthrough

**Lines 1--38 --- docstring, hypothesis statement.** Two structural
facts about this scenario are noted (16--25) that don't exist in the
simpler sparse-radar scenario already diagnosed: (1) the beacon isn't
one band, it's **three** bands (`2 → 5 → 6 → 2 → ...`, hopping every 4
steps), each independently learning its own confidence/PRI estimate for
what's really a single physical phenomenon; (2) band 6 is **shared**
with the frequency-agile threat --- a genuine collision injecting random
noise specifically into band 6's periodicity signal. The hypothesis
(27--35): with only one channel (k=1), the scheduler must make a single
best bet, so it naturally only ever chases the *one* beacon band
currently due. With two channels available, if the periodicity term
inflates more than one beacon band's score simultaneously (plausible
near a burst transition, where both the ending burst's tail and the next
burst's approaching phase bump could be elevated), `PRIAware` could
spend **both** of its k=2 slots on beacon-adjacent bands in a single
step --- at the direct cost of a slot `BeliefUCB` would have instead
spent on an always-productive comm band.

**Lines 40--51 --- imports and constants.** `BEACON_BANDS = {2, 5, 6}`,
`COMM_BANDS = {1, 4}` --- the specific bands under investigation, and
`N_SEEDS = 10` for the multi-seed check.

**Lines 54--107 --- `per_band_capture`, the instrumented simulation.**
Beyond the standard per-band pulse/capture tracking (64--65, 72--79 ---
familiar from earlier files), this adds specific instrumentation for the
hypothesis under test (81--89): whenever `k=2` and *both* scanned bands
fall in `BEACON_BANDS` simultaneously, count it as a "double beacon bet"
(84), then check whether at least one of the two bets actually landed a
hit (85--89) --- distinguishing a *productive* double-bet (at least one
hit) from a *fully wasted* one (both slots missed). Lines 91--107
aggregate: `beacon_capture`/`comm_capture` as blended rates across all
three beacon bands / both comm bands respectively, plus the double-bet
counters and a `per_band_capture` breakdown for each individual beacon
band (useful for testing the "band 6's collision suppresses its
confidence" sub-hypothesis).

**Lines 110--111 --- `summarize`.** A compact one-liner formatter for
mean±stdev (or just the single value if only one seed).

**Lines 114--150 --- `main`, the multi-seed hypothesis test.** For both
`k=1` and `k=2`, runs 10 seeds of both `BeliefUCBScheduler` and
`PRIAwareScheduler`, collecting beacon and comm capture rates for each
(126--137). Prints the summary comparison (139--140), and --- only at
k=2, where the hypothesis predicts the effect should appear --- reports
the double-bet statistics: what fraction of steps were double-beacon
bets, and of those, what fraction actually landed at least one hit
(141--149).

This is the part where the hypothesis test comes back
**inconclusive-to-negative**, per the actual numbers referenced in the
project's history: double-beacon bets occurred on roughly a third of
steps (33.8%) with an 81.4% hit rate --- not an obviously wasteful
pattern, since an 81% success rate on a "bet" isn't the signature of a
scheduler throwing away scan budget. This is exactly the kind of result
that should prompt distrust of the hypothesis itself rather than
force-fitting the data to confirm it --- and this is precisely
what happened: the investigation pivoted away from "double betting" and
toward directly inspecting the *shape* of the periodicity score curve
across a full beacon cycle, which is where the real bug (the jitter
floor collapsing the phase bump to a near-instant spike, one to two
steps after a multi-step burst's onset) was actually found. That
follow-up inspection was done as an ad-hoc check and
isn't fully preserved as its own standalone script in this file --- but
its finding is exactly what `max_run_ever` (which we already saw added
to `PRIAwareScheduler` in v3) was built to fix.

**Lines 152--169 --- single-seed detailed confidence trace.** As a
secondary check (testing the "band 6's agile-threat collision suppresses
its confidence relative to bands 2 and 5" sub-hypothesis), this runs one
fully-detailed episode (seed=1, k=2) and prints each beacon band's final
PRI estimate and confidence, tagging band 6 specifically as "(also hosts
agile threat)" (168) so you can visually compare whether its confidence
really does come out lower than its two uncontaminated siblings.

------------------------------------------------------------------------

## File 11 of 18: `validate_plateau_fix.py` --- a scientific technique: reconstructing intermediate states to isolate a single fix

This file solves a real methodological problem that's easy to overlook:
two separate bug fixes (the burst-plateau jitter fix, and a
harmonic-lock-on fix) landed in `scan_scheduler_v3_pri.py` back-to-back,
both touching the same function
(`_update_pri_model`). A naive "before vs. after" comparison --- running
only the *original* shipped code against the *current* shipped code ---
can't tell you which fix caused which part of the change, since you're
really measuring their combined effect.

## The problem this file solves

Isolating fix 1's contribution requires a version of the code
that has fix 1 applied but *not* fix 2. That version was never actually
shipped anywhere --- it only ever existed transiently, mid-development,
before fix 2 landed on top of it a few minutes later. This file's
solution: **reconstruct** that intermediate state as a frozen,
hand-written copy of the old method, purely for comparison purposes.

## Line-by-line walkthrough

**Lines 1--41 --- docstring.** States the problem precisely (9--22):
both fixes touch `_update_pri_model`, so isolating fix 1 requires a
`PlateauOnly` variant (fix 1 applied, fix 2 not) alongside `Original`
(neither) and `Current` (both). Lines 29--37 state the specific
methodological choice: reuse the *exact same seeding convention* as
`multi_seed_robustness.py`'s Suite C (one seed per full comparison
block, schedulers run sequentially off one continuously-advancing
stream), so this validation's results are directly comparable to the
already-reported pre-fix numbers
(`k=1: +1.5pp, 8/10; k=2: −1.5pp, 1/10`) --- this becomes a built-in
sanity check later, since reproducing those exact numbers confirms the
reconstruction is faithful.

**Lines 59--120 --- `OriginalPRIAware`, a frozen copy of the pre-fix
`_update_pri_model`.** This is a hand-transcribed snapshot of exactly
what `_update_pri_model` looked like *before either fix* --- the class
docstring (60--63) says so explicitly: "old single-seed 'excess over
chance' candidate selection, AND the narrow rmse-only jitter floor."
Comparing this method line-by-line against the current v3 file we
already covered reveals the two differences precisely:

-   Line 79's `min_candidate` computation doesn't update
    `self.max_run_ever` (compare to current v3's line 221, which does)
    --- the persistent burst-width tracker didn't exist yet in this
    version.
-   Lines 99--104: candidate selection uses `_excess_over_chance` ---
    the *old*, coarse selection method (score against a fixed-tolerance
    test, penalized by the chance level of a small candidate explaining
    data by coincidence) --- rather than the refined-fit-quality
    comparison the current version uses.
-   Line 115: `self.jitter_estimate[band] = max(0.5, rmse)` --- the
    **narrow** floor, with no burst-width term at all. This is the exact
    line whose absence *is* the bug being fixed.

**Lines 122--184 --- `PlateauOnlyPRIAware`, the reconstructed
intermediate state.** Nearly identical to `OriginalPRIAware`, but with
two surgical differences, both flagged with inline `# NEW` comments for
easy visual diffing: line 142 *does* update `self.max_run_ever`, and
line 180 *does* use the widened floor:
`max(0.5, rmse, self.max_run_ever[band]/2.0)`. Critically, the
candidate-selection method (lines 163--168, `_excess_over_chance`) is
**left unchanged** from `OriginalPRIAware` --- this class deliberately
keeps fix 2 absent, so any statistical difference between `PlateauOnly`
and `Original` can only be attributed to the jitter-floor change,
nothing else.

**Lines 191--226 --- harness helpers.** Identical in structure to
`multi_seed_robustness.py`'s
`summarize`/`print_summary_table`/`paired_delta`/`print_delta` ---
deliberately reusing the same statistical machinery and output format so
results are visually and numerically comparable across scripts.

**Lines 235--270 --- `suite_plateau_validation`, the actual four-way
comparison.** For each `k ∈ {1,2}`, builds **five** schedulers per seed:
`RoundRobin`, `BeliefUCB`, `Original`, `PlateauOnly`, and `Current`
(240--246) --- running all five off the same seeded stream per seed.
This gives four separate, meaningful deltas (258--265): -
`Original vs BeliefUCB`: the pre-fix baseline, expected to reproduce the
already-documented numbers exactly (this is the built-in sanity check) -
`PlateauOnly vs BeliefUCB`: how the plateau-fix-only variant compares to
plain belief - `PlateauOnly vs Original`: **fix 1's own isolated
contribution** --- the number this whole file exists to compute -
`Current vs BeliefUCB`: the fully-shipped state's comparison to plain
belief, for context

Line 268--269: if a CSV path is given, write the raw per-seed data ---
this produced `plateau_validation_results.csv`, one of the three CSV
files in the zip.

**Lines 273--283 --- `write_csv`.** Identical structure to the CSV
writer in `multi_seed_robustness.py`.

**Lines 286--301 --- `main`.** Defaults to 20 seeds (more than the
original 10-seed Suite C, for extra statistical power once this became a
targeted, higher-stakes check), and runs the validation.

## What this file actually found (from the full run, not printed by the code itself)

At 30 seeds (an even larger run than this script's own default), the
sanity check confirmed the reconstruction was faithful ---
`Original vs BeliefUCB` reproduced the documented `+1.2pp (19/30)` at
k=1 and `−2.6pp (3/30)` at k=2, matching the earlier numbers closely
(small differences purely from the larger sample). Fix 1's isolated
contribution (`PlateauOnly vs Original`) turned out to be genuinely
two-sided: **+1.6pp (20/30 wins) at k=2** --- a real, majority win
exactly where the burst-abandonment bug was diagnosed and demonstrated
--- but **−1.5pp (8/30 wins) at k=1**, where the wider plateau caused
some over-lingering that cost part of what the original sharp
point-spike used to buy cleanly. This is exactly the kind of nuanced,
seed-level finding a single-seed spot-check could never have surfaced
--- and it's what motivated the next file in the pipeline.

------------------------------------------------------------------------

## File 12 of 18: `settle_fix_interaction.py` --- catching a real confound in the project's own methodology

This is a short but methodologically important file: it caught a genuine
bug in the *validation methodology itself* --- not in the scheduler code
--- and fixed it before drawing further conclusions.

## The problem this file solves

`validate_plateau_fix.py` used the project's established seeding
convention: one `random.seed(seed)` call, then every scheduler in the
comparison runs sequentially off that same continuously-advancing random
stream. That convention is fine for **aggregate** statistics across many
seeds (any positional bias should average out over 30 independent
trials). But it breaks down the moment you try to do a **single-seed
deep dive** into "why did scheduler X do worse than scheduler Y on this
specific seed" --- because `run_episode()` builds a **fresh environment
every call**, and the emitters (`MarkovEmitter`, `AgileEmitter`) draw
from the global `random` stream on every single simulated step. That
means the 4th scheduler run in a sequence (say, `PlateauOnly`) and the
5th (`Current`) are drawing from *different* points in the random stream
--- so they're facing genuinely different ground-truth comm/agile
activity that step, not the same world. A single-seed comparison under
this convention conflates "the algorithms decided differently" with
"they were reacting to different things," which makes root-cause tracing
unreliable.

## The fix: reset the seed before *every individual scheduler's run*, not once per whole comparison block

## Line-by-line walkthrough

**Lines 1--31 --- docstring.** States the confound precisely (4--16) and
the fix (18--27): with `warmup_steps=0` (the beacon suite's actual
setting), none of the four schedulers under test consume any of their
*own* randomness --- the `random.shuffle` call used during warmup never
fires, since warmup is disabled. That means the *only* thing drawing
from the global random stream during a run is the environment/emitters.
So if you reset `random.seed(seed)` immediately before *each*
scheduler's own `run_episode()` call, every scheduler sees the
byte-identical ground-truth environment trajectory for that seed --- a
much stricter, cleaner pairing than the original convention, at the
honest cost of no longer numerically matching the original suite's
headline numbers (since it's a genuinely different, more controlled
experimental design, not a reproduction).

**Lines 33--40 --- imports.** Notably imports `OriginalPRIAware` and
`PlateauOnlyPRIAware` directly from `validate_plateau_fix` (line 40) ---
reusing the reconstructed intermediate classes from the previous file
rather than redefining them, which is good practice (single source of
truth for those reconstructions).

**Lines 43--52 --- `run_identical_env`, the corrected pairing
primitive.** This is the entire fix, in one small function: line 49,
`random.seed(seed)` is called **immediately before** constructing and
running this *one* scheduler --- not once per whole comparison block.
This is what guarantees every scheduler, no matter its position in the
loop, sees the exact same environment realization for a given seed
value.

**Lines 55--68 --- `main`, setup.** Standard CLI args (seeds,
seed-start, k), and prints an explicit claim about the guarantee being
provided --- "verified: none of these schedulers consume their own
randomness with `warmup_steps=0`" --- a claim the docstring already
justified logically, restated here for anyone reading just the output.

**Lines 70--89 --- the main comparison loop.** For every seed, runs all
four schedulers (`BeliefUCB`, `Original`, `PlateauOnly`, `Current`) each
via `run_identical_env`, collecting both the interception ratio (87) and
the scheduler *object itself* (88, stashed in `schedulers_by_seed`) ---
the latter is what enables the detailed per-band inspection later in the
file.

**Lines 91--100 --- summary table and `delta` helper.** Same statistical
shape as the earlier files: mean/stdev/min/max per scheduler, then a
`delta` closure (97--100) computing paired differences, win counts, and
stdev between any two named schedulers.

**Lines 102--110 --- the four key deltas, now under identical
environments.** This is the payoff of the fix: with the confound
removed, four comparisons become sharp and interpretable rather than
noisy: - `PlateauOnly vs Original`: fix 1's isolated contribution, now
clean - `Current vs PlateauOnly`: **fix 2's added effect on top of fix
1** --- this is the number the whole file exists to nail down
precisely - `Current vs Original`: both fixes combined -
`Current vs BeliefUCB`: the shipped state's net comparison to plain
belief

The result from running this was
decisive: under the confounded sequential-seeding methodology,
`Current vs PlateauOnly` looked like noise (2/30 vs 1/30 wins,
statistically uninterpretable). Under the *corrected*,
identical-environment methodology, the same comparison sharpened into a
clear, consistent signal: **−0.3pp, but `PlateauOnly` wins 28/30 seeds**
--- a real, small, but highly consistent cost from fix 2, not noise at
all. This is a striking demonstration of why the confound mattered:
removing shared-environment noise turned an ambiguous 2-vs-1 split into
a decisive 28-vs-2 one, using the exact same underlying scheduler code,
just a cleaner experimental pairing.

**Lines 112--127 --- worst-case single-seed inspection, now
trustworthy.** Because environments are now genuinely identical between
schedulers, a single-seed deep dive is finally *valid* to draw
conclusions from --- unlike the earlier attempt in
`diagnose_beacon_regression.py`'s aftermath, which had been unknowingly
confounded. Lines 115--118 find the seed where `Current` underperforms
`PlateauOnly` by the largest margin, then lines 121--127 print each
scheduler's final per-band PRI estimate, confidence, and jitter for the
three beacon bands --- directly comparable now, since both schedulers
processed the exact same sequence of comm/beacon/agile events. This is
what revealed the mechanistic story documented in the class docstring
covered earlier in v3: on the worst seed, `PlateauOnly` correctly stays
unlocked (confidence 0) on a band where there wasn't really enough
evidence yet, while `Current` --- because its harmonic-selection fix
makes it more willing to trust a good-looking fit with less rigorous
screening --- confidently locks on (confidence 0.75) to a *slightly
wrong* estimate, and that overconfidence costs real capture. The exact
trade-off: fix 2's added eagerness is precisely the right property for
the PDW dataset's fractional-PRI-vs-harmonic problem (where you
genuinely want to trust a well-fitting candidate with less rigid
screening), but it's the wrong property on a multi-step burst scenario
where the extra confidence just means leaning harder on an imperfect
Gaussian bump instead of well-calibrated Markov belief.

------------------------------------------------------------------------

## File 13 of 18: `tune_confidence_threshold.py` --- proving a trade-off is a genuine Pareto frontier, not a bug

`settle_fix_interaction.py` found a real, mechanistically-understood
cost from the harmonic-selection fix on the beacon scenario. The natural
next question: can that cost be tuned away without losing the benefit
the fix exists for? This file answers that question rigorously --- by
sweeping the relevant parameter and checking *both* sides of the
trade-off simultaneously, not just the side that looks good.

## The problem this file solves

`confidence_scale` (the parameter we already saw in v3's `__init__`)
directly controls how "eager" the harmonic-fix's confidence formula is:
`confidence = 1 − rmse/(confidence_scale × refined_pri)`. A larger scale
is more forgiving (reaches high confidence with a looser fit); a smaller
scale is more conservative. The obvious hypothesis: shrink
`confidence_scale` a bit, and maybe you recover the beacon-scenario cost
without losing anything --- since a more conservative estimator would be
less prone to the "overconfident lock-on that costs a multi-step burst"
failure mode found in `settle_fix_interaction.py`. But the fix's *entire
reason for existing* was to be more eager --- trusting a well-fitting
candidate on real fractional-PRI PDW data. So there's a real risk that
fixing the beacon cost this way just undoes the PDW benefit through a
different mechanism. This file tests that directly instead of assuming
either outcome.

## Line-by-line walkthrough

**Lines 1--39 --- docstring.** States the hypothesis to test cleanly
(13--35): sweep `confidence_scale`, and for each candidate value, check
**two things simultaneously** --- (1) does it move the beacon k=2 cost
toward zero without hurting k=1, using the exact identical-environment
methodology from `settle_fix_interaction.py`; and (2) does it *preserve*
the harmonic fix's whole point on the real PDW fractional-PRI case (band
4's true 32.505-step period), rather than regressing toward the old,
more conservative selection's failures? Line 32--35 states the actual
decision rule plainly: a value that helps (1) but breaks (2) isn't a
fix, it's just re-introducing the old problem through a different door.

**Lines 41--53 --- imports and the candidate grid.** Notably imports
`TRUE_PERIODIC_BANDS` and `classify` from `validate_pdw_multiseed` (line
49) --- a forward dependency on a file we haven't covered yet (coming up
next in this walkthrough), which defines exactly what counts as a
"correct" versus "harmonic" versus "no lock" outcome on real PDW data.
`CANDIDATE_SCALES = [0.25, 0.20, 0.17, 0.15, 0.12, 0.10]` (53) --- six
values to test, with 0.25 explicitly marked as the current/original
baseline for comparison.

**Lines 56--87 --- Check 1: `beacon_check`.** Reuses `run_identical_env`
(61--66, structurally identical to `settle_fix_interaction.py`'s version
--- reset seed immediately before each scheduler's run, guaranteeing
identical ground truth across the compared schedulers). `beacon_check`
(69--87) runs `BeliefUCB`, `PlateauOnly`, and `Current` (with the
*candidate* `confidence_scale` value passed explicitly, line 75) across
a set of seeds, then computes paired deltas of the candidate-scale
`Current` against both `PlateauOnly` and `BeliefUCB` --- mirroring
exactly the comparison structure that revealed the original −0.3pp cost.

**Lines 90--112 --- Check 2: `pdw_check`.** For each seed, generates a
fresh synthetic PDW stream (98), runs a `PRIAwareScheduler` with the
candidate scale on it (104), and then classifies band 4's final result
--- `pri_estimate`, `confidence` --- against the known true period using
the `classify` function imported from `validate_pdw_multiseed`
(106--107). Tallies how many seeds landed in each of four outcome
categories: `correct` (locked onto the true fundamental), `harmonic`
(locked onto a multiple of it --- the exact failure the
harmonic-selection fix was built to prevent), `no_lock` (never confident
enough), `wrong` (locked onto something else entirely).

**Lines 115--174 --- `main`, the sweep and decision logic.** Runs
`beacon_check` at both k=1 and k=2, and `pdw_check`, for every candidate
scale in the grid (133--141), printing a wide comparison table. Lines
143--148 state explicitly what a "good" result would look like
(k=2-vs-Plateau moving toward zero or positive, k=1-vs-Plateau not
getting meaningfully worse, PDW correct-lock count staying at or above
the baseline). Lines 150--154 print the actual baseline numbers for
reference. Lines 156--166 implement the decision rule programmatically:
for each smaller candidate scale, check all three conditions
(`improves_k2`, `no_worse_k1`, `preserves_pdw`) and only accept the
*first* scale (in descending order --- closest to the original) that
satisfies all three simultaneously.

## What this sweep actually found

The result was decisive and somewhat surprising in its cleanliness:
**every value that helped the beacon scenario cost real PDW lock-on
reliability, monotonically** --- there was no candidate that improved
one side without costing the other. At `scale=0.15`, the beacon k=2
delta *did* turn positive, but PDW band-4 correct-lock dropped from
18/20 to 16/20; by `scale=0.10`, PDW lock-on had collapsed to 4/8. This
is a genuine **Pareto frontier**, not a fixable inefficiency --- the
harmonic fix's eagerness *is* what makes it work on real
fractional-period data, so making it more conservative necessarily costs
exactly that. Lines 167--172 encode the honest conclusion: since no
candidate strictly improved on all three fronts, the script's own logic
falls through to keeping `confidence_scale=0.25` --- prioritizing the
real-dataset benefit over the synthetic-scenario cost, a deliberate
choice rather than an oversight, and exactly the value we saw hardcoded
as the default back in `run_on_turing_dataset.py`'s CLI.

------------------------------------------------------------------------

## File 14 of 18: `validate_pdw_multiseed.py` --- the multi-seed check on the real dataset the harmonic fix was built for

This file supplies the `classify`/`TRUE_PERIODIC_BANDS` machinery that
`tune_confidence_threshold.py` imported in the last file, and it's the
first script to properly, statistically validate the harmonic-lock-on
fix specifically on the PDW-shaped data it was diagnosed on --- closing
a gap explicitly flagged earlier: the fix had only ever been
*spot-checked* on a handful of individual seeds, never run through a
proper multi-seed harness on this dataset.

## The problem this file solves

The harmonic-lock-on fix (candidate selection by best refined-fit
quality, rather than the coarse tolerance test) was found and motivated
on the Turing PDW-stand-in data specifically --- a single seed where the
old selection method locked onto \~65 instead of the true \~32.5. But
`multi_seed_robustness.py`'s Suite E predates that fix entirely, and the
30-seed validations in
`validate_plateau_fix.py`/`settle_fix_interaction.py` only cover the
beacon scenario, not PDW data. This file closes that exact gap.

## Line-by-line walkthrough

**Lines 1--60 --- docstring.** Explains the gap being closed (1--14),
then lays out the ground truth of the synthetic dataset precisely
(16--31): three fixed-frequency emitters land in known bands at
`n_bands=8` --- band 1 (1000µs PRI), band 4 (**650µs, the fractional
case** --- at a 20µs dwell this is exactly 32.505 steps, non-integer,
which is precisely what let a harmonic outscore the true fundamental
under the old selection method), band 6 (1500µs). Two frequency-agile
hoppers serve as negative controls --- they should never confidently
lock onto periodicity, the same role the comm/agile bands played in the
beacon-scenario validation.

Lines 33--41 name the four scheduler variants under comparison ---
notably including `PersistentPRIAwareScheduler` (v4) alongside
`PlateauOnly` and current `PRIAware`, letting this file also re-check
the earlier "does v4 help on real PDW data" question from a fresh,
statistically rigorous angle.

Lines 50--56 make an important, reassuring methodological note: unlike
the beacon scenario, **there's no seeding confound here to guard
against**. `generate_synthetic_pdw_stream`'s data is generated by
NumPy's own independent random generator (seeded separately, per-call),
not Python's global `random` module --- and since every scheduler here
runs with `warmup_steps=0` (so none of them consume `random` either),
every scheduler automatically sees a byte-identical PDW stream for a
given seed regardless of run order, with no need for the
`settle_fix_interaction.py`-style seed-reset trick.

**Line 77 ---
`TRUE_PERIODIC_BANDS = {1: 1000.0, 4: 650.0, 6: 1500.0}`.** The
ground-truth lookup table used throughout the file --- maps band index
to true PRI in microseconds.

**Lines 80--90 --- `classify`, the verdict function.** Given an
estimated period (in scan-steps), the dwell length, the true period (in
µs), and confidence values, this returns one of four verdicts. Line 81:
if confidence never cleared the threshold, or there's no estimate at
all, it's `NO LOCK`. Line 83: convert the true period into scan-steps
for direct comparison (`true_pri_us / dwell_us`). Line 84: compute the
ratio of estimated to true. Line 85: within 5% of exactly 1.0 →
`CORRECT`. Lines 87--89: check against a set of common harmonic ratios
--- half, double, triple, or one-third --- if the estimate is close to
any of those, it's `HARMONIC` (locked onto a real periodic structure,
just the wrong multiple of it). Anything else confidently locked-on is
`WRONG` (line 90) --- locked onto something that isn't a harmonic
relationship to the truth at all.

**Lines 93--103 --- `run_one`.** Generates a fresh synthetic PDW stream
for this seed (94), builds the `PDWReplayEnvironment` adapter (96--97),
and runs the given scheduler class through it. Line 100's comment is
worth noting: `random.seed(seed)` is called here even though it's a
genuine no-op for this specific setup (since these schedulers don't
consume `random` with `warmup_steps=0`) --- kept anyway purely for code
clarity/consistency with the rest of the project's conventions, an
honest bit of defensive-but-technically-unnecessary code.

**Lines 106--121 --- `main`, setup.** CLI args including `--dwell-us`
defaulting to 20.0 (explicitly chosen, per the help text, "to match the
fractional-PRI headline test" --- the exact dwell that makes band 4's
period non-integer).

**Lines 127--148 --- the actual multi-seed sweep.** Four scheduler
builders (127--132), then for every seed, every scheduler is run
(140--142) and classified per known-periodic band (144--148) using the
`classify` function.

**Lines 150--181 --- reporting.** Prints overall interception rates
(150--153), then a detailed per-band classification breakdown for every
scheduler that had any PRI capability at all (159--171) --- counting how
many seeds landed in each of the four verdict categories, per band.
Lines 173--181 specifically highlight the fractional-PRI band-4 case ---
the one the whole fix was built for --- directly contrasting
`PlateauOnly` (pre-harmonic-fix) against current `PRIAware`.

The result (at 20 seeds): `PlateauOnly`
locked correctly on band 4 in 14/20 seeds; current `PRIAware` (with the
harmonic fix) reached 18/20 --- a real, substantial improvement, with
two specific seeds (3 and 8) confirmed to flip from `NO LOCK` to
`CORRECT` --- matching the exact mechanism the fix was designed around.
A further finding surfaced by this same file (not fully visible from
the code alone):
`PersistentPRIAwareScheduler`'s persistence bonus turned out to give a
real, substantial edge specifically on the *sparser* band 6 signal (7/20
correct vs. plain `PRIAware`'s 1/20) --- meaning the earlier claim that
"v4 doesn't help on PDW data" (based on checking only band 4) was
incomplete; it simply hadn't been checked against the sparser band where
the sample-starvation mechanism v4 targets actually applies.

**Lines 183--197 --- CSV export.** Writes every scheduler/seed's
interception ratio plus per-band verdict strings to
`pdw_multiseed_results.csv` --- the third and final CSV file present in
the zip.

------------------------------------------------------------------------

## File 15 of 18: `validate_offbyone_fix.py` --- closing the last flagged gap using the now-established rigorous methodology

By this point in the project, a clear validation pattern had been
established: build a reconstructed "before" scheduler with only the fix
under test removed, run it against the "after" version under an
identical-environment methodology, and check the isolated delta. This
file applies that exact pattern to the last remaining unvalidated fix:
the off-by-one neighbor-expansion (testing each candidate's ±1 integer
neighbors, which fixed the seed-5 PDW failure and improved several other
bands as a side effect).

## The problem this file solves

The off-by-one fix had been verified on 20 PDW seeds and spot-checked on
a single beacon-scenario seed --- but unlike the plateau fix and the
harmonic-selection fix, it had never been run through the full
25--30-seed identical-environment beacon harness the rest of the
project's fixes got. This was explicitly flagged as an open gap earlier in the
project, and this file closes it.

## Line-by-line walkthrough

**Lines 1--27 --- docstring.** States the gap precisely (4--10) and the
isolation technique (12--16): `PreOffByOneFixPRIAware` is a
reconstruction of `PRIAwareScheduler` with **only** the
neighbor-expansion block removed --- everything else (plateau fix,
harmonic-selection-by-best-fit, `confidence_scale`) stays exactly as
currently shipped, following the same pattern `PlateauOnlyPRIAware` used
to isolate the earlier fix. Lines 18--23 confirm reuse of the
identical-environment methodology from `settle_fix_interaction.py`.

**Lines 41--108 --- `PreOffByOneFixPRIAware`.** Comparing this
reconstruction line-by-line against the current v3 file we covered
earlier reveals exactly one structural difference: **the entire
candidate-neighbor-expansion block is absent**. Line 79's standalone
comment marks precisely where it would have gone:
`# NOTE: no +-1 neighbor expansion here -- this is the fix being isolated.`
Everything else --- the dense-run guard (54--61), GCD/mode/divisor
candidate generation (69--78), refinement-based candidate selection
(81--94), and the plateau-aware jitter floor (104) --- is copied
verbatim from the current shipped version, confirming this
reconstruction really does isolate just the one change under test.

**Lines 111--116 --- `run_identical_env`.** Byte-identical in structure
to the version in `settle_fix_interaction.py` and
`tune_confidence_threshold.py` --- reset the seed immediately before
each scheduler's run, guaranteeing every compared scheduler faces the
same ground-truth environment.

**Lines 119--162 --- `main`.** For both `k=1` and `k=2`, runs three
schedulers --- `BeliefUCB`, `PreOffByOneFix`, and `Current` (with the
fix) --- across all seeds under the identical-environment methodology,
then computes two deltas: the fix's isolated effect
(`Current vs PreOffByOneFix`), and the net effect versus baseline belief
(`Current vs BeliefUCB`).

## What this file found

The result, running this at 30 seeds, was genuinely
good news, and --- notably --- different in character from every other
fix examined so far: this one showed **essentially zero effect on the
beacon scenario, in either direction** (`+0.1pp ± 0.6pp, won 1/30` at
k=1; `+0.0pp ± 0.1pp, won 1/30` at k=2). Unlike the plateau fix and the
harmonic-selection fix, both of which showed real, measurable trade-offs
on the beacon scenario, this one is functionally a no-op there. The
mechanistic explanation is clean: the beacon's true period is an exact
integer (12), which the existing GCD/mode/divisor candidate-generation
methods were already reliably producing directly --- so the ±1 neighbor
expansion rarely has anything new to contribute. The specific failure
mode this fix targets --- a rounding collision from an off-by-one *seed*
candidate on a genuinely *fractional* period --- only shows up on
non-integer periods, exactly the PDW fractional-PRI case it was built
for. This makes it, per the project's own characterization, "a clean win
with no counterpart cost to weigh" --- a rare thing in this project's
history, where nearly every other fix came with some honest trade-off
attached.

------------------------------------------------------------------------

## File 16 of 18: `switch_cost_comparison.py` --- introducing real-world receiver constraints, and discovering the model's biggest own vulnerability

Every result across the entire project up to this file assumed
band-hopping was instantaneous and free. This file is where that
assumption gets challenged directly --- and in doing so, it surfaced two
of the most consequential findings in the project: RoundRobin's total
collapse under any real switch cost, and a serious weakness in the
project's own headline result.

## The problem this file solves

Real ESM receiver hardware needs actual settling time when re-tuning to
a new band --- the local oscillator and filters need to physically
stabilize, typically low-to-tens of microseconds for a fast synthesizer.
At the fine 20µs dwell used for the fractional-PRI PDW work, this
settling delay isn't negligible relative to a single dwell step at all.
Ignoring it made every prior comparison in the project unrealistically
favorable to whichever scheduler switches bands most often --- which,
unhelpfully, is exactly `RoundRobin`, by construction.

## Line-by-line walkthrough

**Lines 1--29 --- docstring.** States the physical motivation (4--10),
confirms the mechanism was added to `run_episode()` as a fully
backward-compatible, opt-in parameter (12--17, verified byte-for-byte
identical to every existing result at the default of 0 --- a claim we
already saw substantiated when we walked through
`scan_scheduler_v2.py`'s `run_episode`), and states the core hypothesis
to be tested (19--26): `RoundRobin` switches on literally every step by
construction, so it should be hurt by a switch cost far more than a
learned scheduler that tends to camp on a productive band once found.
The rest of the file checks whether that intuition holds, and by how
much.

**Lines 31--41 --- imports and constants.**
`SWITCH_COSTS = [0, 1, 2, 4]` --- the specific range of settling delays
tested, in scan-steps.

**Lines 44--66 --- `beacon_sweep`.** For each `k ∈ {1,2,3}` and each
switch cost, runs `RoundRobin`, `Random`, and `BeliefUCB` on the
standard beacon scenario, printing a table of interception rates. Line
60's conditional construction
(`cls(n_bands) if cls is not BeliefUCBScheduler else cls(n_bands, ucb_c=0.5)`)
is a minor bit of awkward-but-functional Python needed because
`RoundRobinScheduler`/`RandomScheduler` don't accept a `ucb_c` keyword
argument, so the constructor call has to branch.

**Lines 69--83 --- `beacon_switches_breakdown`, the diagnostic that
explains *why* the sweep numbers come out the way they do.** Before even
looking at interception rates, this measures directly how often each
scheduler actually changes bands --- reading `stats.switches` (populated
by `run_episode`'s switch-tracking logic we covered earlier) as a
fraction of total steps. This is the mechanistic explanation, measured
rather than just assumed, behind everything else in the file: RoundRobin
switches on literally 100% of steps by construction, versus BeliefUCB's
much lower \~37%
--- since BeliefUCB tends to camp on a currently-productive band rather
than sweeping continuously.

**Lines 86--152 --- `sparse_radar_sweep`, the file's most important
finding.** This tests per-emitter capture (radar and comm-1) on the
sparse-radar scenario under varying switch cost, and --- notably ---
also tests a *fourth* variant on the fly: `PRIAware` augmented with the
not-yet-covered `warmup_dwell_steps`/`switch_lead_steps` parameters
(lines 92--95's comment previews this: plain `PRIAware`'s warmup
switches every step, so it's devastated by switch cost the same way
RoundRobin is; the "+dwell" variant is a fix for that, validated more
thoroughly in a later file). The `capture` helper (101--135) is another
manually-unrolled simulation loop (matching the pattern seen in earlier
diagnostic files), implementing switch-cost blocking logic inline rather
than relying on `run_episode`, so this file can freely experiment with
the `recommended_warmup_dwell` helper (line 141) for the augmented
variant without needing to thread every parameter through
`run_episode`'s signature.

Lines 137--149: for each switch cost, runs plain `BeliefUCB`, plain
`PRIAware`, and (for `cost > 0`) the dwell-augmented `PRIAware` variant,
using `recommended_warmup_dwell` to auto-derive its dwell/warmup
parameters. Line 150--152's closing note is characteristic of this
project's honest self-scrutiny: explicitly labels these "+dwell" numbers
as single-seed spot checks, and points to the dedicated multi-seed
validation file for the real picture --- "this project has repeatedly
found single-seed reads misleading" is a direct, earned lesson from
everything we've walked through so far.

## What this file actually found

Two major, distinct findings:

**Finding 1: RoundRobin is not just suboptimal under switch cost ---
it's non-functional.** At `switch_cost=1`, RoundRobin's interception
rate collapsed to a flat **0.0%** --- every single band-visit is a fresh
switch, so it's always mid-settle, never actually observing anything.
This is a genuinely strong argument for the whole project's premise: a
learned, camping scheduler isn't just *better* than open-loop sweeping
once retuning has a real cost, it's the *only* viable approach at all.

**Finding 2: the sparse-radar headline result --- the single most-cited
number in the entire project --- also collapses, from 100% to 1.5%, at
`switch_cost=1`.** The mechanism, confirmed directly by tracing scan
behavior: the phase-locked PRI scheduler predicts the pulse's *exact*
arrival instant and switches in exactly then --- meaning it's *always* a
cold, fresh switch (measured: 267 of 285 band-5 visits were fresh
switches). So under any real settling delay, the receiver is still
settling *precisely* when the pulse arrives --- it misses by design, not
by chance. This finding directly motivated the `switch_lead_steps`
mechanism we already saw built into `scan_scheduler_v3_pri.py`'s
`_periodicity_score`.

------------------------------------------------------------------------

## File 17 of 18: `validate_warmup_dwell_fix.py` --- the definitive 5-way ablation that proved jitter is load-bearing, not optional

This is the file that finally properly validated the
warmup-dwell-plus-jitter fix --- the mechanism first sketched, and left
untested, earlier in the project, and then reconstructed and actually
tested here.
It's a genuine ablation study: five variants tested side by side to
isolate exactly which ingredient of the fix does the real work.

## The problem this file solves

`switch_cost_comparison.py` found that under a real switch cost, the
warmup sweep itself is "devastated" the same way `RoundRobin` is --- it
switches bands every single step, so it can never survive settling long
enough to accumulate a valid observation, meaning lock-on may never even
begin. The obvious fix --- make warmup "dwell" longer on each band ---
was tried earlier but never actually validated
multi-seed before this file. And, crucially, the project's own history
(the aliasing bugs found repeatedly in earlier files) warns that a naive
dwell fix could easily introduce a *new*, more subtle bug rather than
solving the old one.

## Line-by-line walkthrough

**Lines 1--28 --- docstring.** States the bug (4--9) and, importantly,
defines a precise five-way ablation to disentangle which specific
ingredient matters (11--21): - **A**: original broken behavior
(`dwell=1`) - **B**: dwell increased, but **no jitter**, and warmup
budget **not** rescaled - **C**: dwell increased, no jitter, but warmup
budget **is** rescaled - **D**: dwell increased, **with** jitter, budget
rescaled --- this is what `PRIAwareScheduler` actually ships with -
**E**: same as D, but on `PersistentPRIAwareScheduler` (v4) --- testing
whether v4's characterization bonus closes whatever residual gap D still
has

Lines 23--25 note that `switch_lead_steps` is held fixed at the
already-validated value (matching the switch cost) throughout, so this
test isolates the **lock-on** question specifically, separate from the
re-acquisition question that fix already addressed.

**Lines 30--42 --- imports and constants.** `SEEDS = list(range(1, 31))`
--- 30 seeds, with an explicit comment: "this project has repeatedly
found single-seed and even 10-seed reads misleading." By this point in
the project's history, that's a hard-earned, explicitly-stated
methodological principle, not just a default choice.

**Lines 45--84 --- `capture`.** Structurally very similar to
`switch_cost_comparison.py`'s inline capture function, but with one
deliberate, explicitly-flagged methodological choice (46--49): switch
cost is applied **from t=0**, contaminating the warmup phase too ---
because a real receiver's hardware doesn't know it's "supposed" to be in
a warmup phase; the settling delay is physical and applies regardless.
This is the realistic case, as opposed to the isolated re-acquisition
test used elsewhere in the project (which deliberately excluded warmup
from switch-cost effects, to test a different, narrower question).

**Lines 87--93 --- `summarize`.** Prints mean, population stdev, min,
max, and --- critically --- a "locked-on \>50%" count, the same style of
binary-outcome tally used throughout the v4 investigation, since this
bug's signature is bimodal (locks fully or barely at all), not a smooth
spread.

**Lines 96--128 --- `main`, the ablation setup.** For each of two switch
costs (`1` and `2`), computes the actual dwell and scaled-warmup values
(107--108) --- and line 109's `assert` is a nice piece of
self-verification: it independently re-derives the same numbers by hand
and checks they match what `recommended_warmup_dwell()` (the helper
function from v2 we covered much earlier) produces, catching any drift
between the helper's logic and this script's own documented derivation.
Lines 116--128 define the five variant configurations precisely,
matching the docstring's A--E list.

**Lines 130--152 --- running the ablation.** For every seed and every
variant, calls `capture` and records radar capture, comm-1 capture, and
final periodicity confidence on band 5. Prints three separate summary
tables: radar capture, comm-1 capture (the honest cost), and final
confidence with a lock-on tally.

**Lines 154--162 --- the critical backward-compatibility sanity check.**
At `switch_cost=0` (no switching penalty at all), *every* dwell/jitter
variant should collapse to producing the exact same result --- since
dwell and jitter only matter when there's actually something to settle
from. This directly re-verifies the project's most important fixed
reference point: the sparse-radar headline invariant, **100.0% radar /
79.0% comm-1**, must reproduce exactly regardless of which dwell/jitter
configuration is nominally active.

## What the ablation actually found (the headline result of the whole file)

The documented 30-seed table, at `switch_cost=1`, told a genuinely
decisive story:

  -----------------------------------------------------------------------
  Variant                             Radar lock-on
  ----------------------------------- -----------------------------------
  A: dwell=1 (original, broken)       3.8% ± 11.7% (1/30 locked)

  B: dwell only, no jitter, unscaled  **0.0% ± 0.0%** (0/30 --- every
  warmup                              single seed)

  C: dwell + jitter=0 + scaled warmup **0.0% ± 0.0%** (0/30 --- every
                                      single seed)

  D: dwell + jitter=1 + scaled warmup 76.7% ± 42.3% (23/30 locked)
  (PRIAware)                          

  E: D + v4's persistent bonus (full  **93.2% ± 0.4% (30/30 locked)**
  fix)                                
  -----------------------------------------------------------------------

Two things this table settles decisively, that a single-seed spot check
never could have: **jitter isn't optional polish, it's load-bearing**
--- variants B and C, which add dwell but withhold jitter, fail
*deterministically* (exactly 0% across every one of 30 seeds, zero
variance at all) --- this is the fixed-parity aliasing bug (explained
back in `scan_scheduler_v2.py`) manifesting as a hard, structural
failure, not noise. And **dwell+jitter alone (D) isn't fully sufficient
either** --- it recovers a real majority (23/30) but not all seeds, the
same residual sample-starvation coin-flip v4 was built to fix in the
first place; combining both fixes (E) closes the gap completely, with
variance collapsing from ±42pp down to ±0.4pp.

------------------------------------------------------------------------

## File 18 of 18: `validate_beacon_switchcost_dwell.py` --- the negative result that scopes the fix

This closes the loop on `validate_warmup_dwell_fix.py`. That file proved
the dwell+jitter+`switch_lead_steps` combo (variant E) fixes
sparse-radar lock-on under switch cost, 30/30 seeds, near-zero variance.
This file asks the obvious next question: does that fix generalize to
the beacon scenario? I ran it rather than just reading it, and the
answer confirmed in the docstring holds up exactly.

## The problem this file solves

Before even testing the fix, the file has to establish a fact worth
stating up front: **the beacon scenario has never used the
sparse-radar's `warmup_steps=800` convention at all** --- it's always
run with `warmup_steps=0`. That's not an oversight; it's because the
beacon (`PeriodicEmitter` on bands 2/5/6, period 12, ON for 4 of every
12 steps) has a duty cycle around 33%, versus the sparse radar's roughly
1-in-many-hundred pulse rate. The beacon is *not* a sample-starved
signal --- plain online belief+UCB learning bumps into it constantly
during normal operation, so there was never an actual justification for
grafting on an artificial warmup phase for this scenario.

So the file checks two separate things, not one: 1. Does switch cost
degrade beacon interception at all (extending the RoundRobin/BeliefUCB
findings from `switch_cost_comparison.py` to
PRIAware/PersistentPRIAware)? 2. Does the sparse-radar dwell+jitter+lead
fix actually help here, or does it cost something?

## Line-by-line walkthrough

**Lines 1--49 --- docstring.** States both questions and, unusually for
this project's docstring style, states the answer to question 2 up
front: **NO**, the fix doesn't generalize, and is actively
counterproductive --- plain `PRIAware` at `warmup=0` beats every "+fix"
variant on both interception and lock-on, at every (k, cost) pair
tested. It also names the mechanism ahead of time: the artificial
warmup-dwell phase itself is the cost, not `switch_lead_steps`
(near-neutral here, consistent with earlier findings).

**Lines 51--65 --- imports and constants.** Pulls in all four schedulers
plus `make_scenario` and `recommended_warmup_dwell`. `N_STEPS = 4000`
(shorter than the radar's runs, since the beacon's fast duty cycle
doesn't need a long horizon to converge), `SEEDS = 1..30`, and
`BASE_WARMUP = 800` kept only for the "+fix" variants so the dwell math
matches the radar validation exactly --- an important control, since if
the fix's parameters were re-tuned for the beacon it would muddy whether
the fix itself transfers.

**Lines 68--80 --- `run_one`.** Seeds RNG, builds the scenario,
constructs whichever scheduler class with `ucb_c=0.5`, runs the episode
with the given `k_channels` and `switch_cost_steps`, and returns two
numbers: the interception percentage, and `beacon_conf` --- the max
periodicity confidence across bands 2, 5, 6 (guarded by
`hasattr(sched, "confidence")` since
`RoundRobinScheduler`/`BeliefUCBScheduler` don't track that at all).

**Lines 83--86 --- `summarize`.** Mean, population stdev, min/max ---
same style as every other validation file in the project.

**Lines 89--125 --- `main`.** For each `k_channels` in `(1, 2)` and each
`switch_cost_steps` in `(0, 1, 2)`: computes the dwell/warmup numbers
via `recommended_warmup_dwell` (only meaningful when `cost > 0`), then
builds a variants dict. At `cost=0` there are three variants
(RoundRobin, BeliefUCB, plain PRIAware) since the fix has nothing to
fix. At `cost > 0`, two more variants are added --- PRIAware and
PersistentPRIAware, both with the dwell/jitter/lead fix applied. Runs
every variant across all 30 seeds, then prints both the interception
table and the lock-on tally.

**Lines 128--154 --- `isolate_mechanism`.** A four-way decomposition,
run only at `cost=1, k=1` across a shorter 10-seed sweep (this is a
diagnostic pass, not the headline validation, hence fewer seeds):
baseline (no fix), dwell-fix only, lead-only, and both together. This
isolates which half of the combined fix is actually responsible for
whatever regression shows up.

**Lines 157--163 --- entrypoint.** Runs `main()` for both k values, then
runs `isolate_mechanism` at cost=1 if that combination was included.

## What I confirmed by actually running it

**k=1 interception table, cost=1:**

  Variant                                    Interception
  ------------------------------------------ ------------------
  RoundRobin                                 0.0%
  BeliefUCB                                  18.2% ± 1.6%
  PRIAware, warmup=0 (existing convention)   **17.3% ± 2.3%**
  PRIAware + dwell/jitter/lead fix           13.6% ± 2.3%
  PersistentPRIAware(v4) + fix               13.8% ± 2.6%

Lock-on tells an even sharper story: plain PRIAware locks on in
**23/30** seeds (mean confidence 0.72) --- the fix variants collapse to
**1/30** and **2/30**. The artificial warmup phase isn't neutral here,
it's actively destructive to the exact thing it was meant to help.

**Mechanism isolation (cost=1, k=1, 10 seeds)** confirmed the
docstring's claim precisely: - Baseline (warmup=0, lead=0): 17.9% -
Dwell-fix only: 14.9% ± 2.6% --- the drop - Lead only: 17.4% ± 2.3% ---
essentially unchanged - Both: 14.1% ± 2.3%

So the regression traces cleanly to the dwell phase itself, not
`switch_lead_steps`. The explanation is straightforward once you have
it: the beacon's \~33% duty cycle across 3 bands means ordinary online
belief+UCB scanning already samples it plenty even under switch cost ---
there's no sample-starvation problem for the fix to solve. A forced,
blind, uniform warmup sweep just burns budget the adaptive policy would
otherwise spend catching the beacon during normal operation.

## The honest bottom line for the whole project

The sparse-radar dwell+jitter+lead fix is a fix for **genuinely rare,
sample-starved periodic signals** specifically --- not a universal
switch-cost patch. Applying it to a signal that was never starved in the
first place is a net loss, confirmed at every (k, cost) combination
tested, not just k=1/cost=1. This is consistent with the project's
running theme: almost every fix so far has carried a cost somewhere, and
this file is the clean demonstration that a fix's scope of validity has
to be checked explicitly rather than assumed.

This covers all 18 source files: the four scheduler generations, the PDW
replay pipeline, and the diagnostic and validation scripts that trace
each fix from hypothesis through multi-seed confirmation.
