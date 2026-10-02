
Completed the first file: `scan_scheduler_prototype.py`. I also marked it complete in the checklist.

# `scan_scheduler_prototype.py` — line-by-line explanation

Blank lines only separate logical sections and have no runtime effect. I identify those ranges explicitly.

## Module documentation: lines 1–27

### Lines 1–3

**Line 1**

```python
"""
```

Starts a module-level triple-quoted documentation string.

**Line 2**

```
Smart Scan Strategy for Electronic Warfare — Working Prototype
```

Gives the file's title and identifies it as the initial working prototype.

**Line 3**

```
================================================================
```

Visual separator used only for documentation.

### Lines 4–7

**Line 4**

```
Simulates a spectrum-scanning receiver deciding, at each time step,
```

Explains that the program models a receiver making repeated scanning decisions.

**Line 5**

```
which single frequency band to listen to, against a mixed population
```

States that only one frequency band is selected at each time step.

**Line 6**

```
of emitters (bursty comms, a periodic beacon, and a frequency-agile
```

Lists the modeled emitter types.

**Line 7**

```
threat) sharing the same band pool.
```

Completes the description: all emitters compete within the same collection of bands.

### Lines 8–14

**Line 8**

Blank line inside the documentation string.

**Line 9**

```
Pipeline (the "workflow"):
```

Introduces the four-stage simulation workflow.

**Line 10**

```
    1. Environment  -> ground-truth emitter ON/OFF state per band per step
```

Explains that the environment produces the actual transmission state of every band.

**Line 11**

```
    2. Scheduler    -> picks ONE band to scan this step (this is the part
```

States that the scheduler chooses the receiver's next band.

**Line 12**

```
                        SIH wants "smart"/ML-driven instead of open-loop)
```

Clarifies that the scheduler is the intelligent part of the system.

**Line 13**

```
    3. Update       -> scheduler learns from the hit/miss it just observed
```

Explains that the scheduler receives feedback after scanning.

**Line 14**

```
    4. Metrics      -> interception ratio, avg reward/step, avg intercept delay
```

Lists the main metrics calculated after or during a run.

### Lines 15–24

**Line 15**

Blank documentation line.

**Line 16**

```
Three schedulers are compared head-to-head on the identical scenario:
```

Introduces the three scheduler implementations used by the script.

**Line 17**

```
    - RoundRobinScheduler   : open-loop baseline (sweeps bands in order)
```

Documents the deterministic sequential baseline.

**Line 18**

```
    - RandomScheduler       : naive baseline
```

Documents the random-selection baseline.

**Line 19**

```
    - BeliefScheduler       : closed-loop, learns a 2-state Markov model
```

Describes the learning scheduler.

**Line 20**

```
                              per band online and scans whichever band it
```

Explains that the Markov model is learned separately for each band.

**Line 21**

```
                              currently believes is most likely ON
```

States the exploitation strategy: scan the band with the greatest estimated activity probability.

**Line 22**

```
                              (a practical/myopic approximation of the
```

Connects this strategy to restless-bandit scheduling.

**Line 23**

```
                              Whittle index used for restless-bandit
```

Mentions the theoretical Whittle-index framework.

**Line 24**

```
                              scheduling problems)
```

Closes that explanatory parenthesis.

### Lines 25–27

**Line 25**

Blank documentation line.

**Line 26**

```
Run:  python3 scan_scheduler_prototype.py
```

Documents the command used to execute the file.

**Line 27**

```python
"""
```

Ends the module-level documentation string.

### Lines 28–34

**Line 28**

Blank line separating documentation from imports.

**Line 29**

```python
import random
```

Imports Python's standard random-number module.

It is used for:

- Random emitter behavior
- Random scheduler choices
- Epsilon exploration
- Reproducible experiments through `random.seed()`

**Line 30**

```python
import statistics
```

Imports standard statistical functions, especially `statistics.mean()`.

**Line 31**

```python
from dataclasses import dataclass, field
```

Imports:

- `dataclass`, which automatically generates boilerplate methods for data containers
- `field`, used to define mutable list fields safely

**Line 32**

```python
from typing import List, Dict, Optional
```

Imports type annotation helpers:

- `List`
- `Dict`
- `Optional`

**Lines 33–34**

Blank lines separating imports from the first section.

---

# 1. RF environment and emitters

## Lines 35–37

**Line 35**

```python
# ----------------------------------------------------------------------
```

A visual comment separator. It has no runtime effect.

**Line 36**

```python
# 1. RF Environment: Emitters
```

Labels the first logical section.

**Line 37**

```python
# ----------------------------------------------------------------------
```

Closes the visual section header.

---

## `Emitter`: lines 39–48

**Line 39**

```python
class Emitter:
```

Defines the base class for all emitter types.

Other emitter classes inherit from this class.

**Line 40**

```python
    """Base class. Occupies one band at a time (band may change for
```

Starts the class documentation string.

**Line 41**

```python
    hoppers) and is either transmitting or silent at that band."""
```

Completes the documentation. An emitter has:

- A current band
- An ON/OFF state

**Line 42**

```python
    def __init__(self, name: str):
```

Defines the constructor.

It accepts a string `name`.

**Line 43**

```python
        self.name = name
```

Stores the emitter's name.

**Line 44**

```python
        self.band: int = -1
```

Initializes the current band to `-1`.

This means “not assigned yet” or “invalid/uninitialized band.”

**Line 45**

```python
        self.on: bool = False
```

Initializes the emitter as silent.

**Line 46**

Blank line inside the class.

**Line 47**

```python
    def step(self, t: int):
```

Declares the interface that all subclasses must implement.

The method receives the current time step `t`.

**Line 48**

```python
        raise NotImplementedError
```

Raises an exception if the base implementation is called directly.

This forces subclasses to provide their own behavior.

**Lines 49–50**

Blank lines separating classes.

---

## `MarkovEmitter`: lines 51–64

**Line 51**

```python
class MarkovEmitter(Emitter):
```

Defines an emitter whose behavior follows a two-state Markov model.

It inherits from `Emitter`.

**Line 52**

```python
    """Fixed-band emitter. ON/OFF governed by a 2-state Markov chain —
```

Starts the class documentation.

**Line 53**

```python
    models bursty comms traffic in a known channel."""
```

Explains that this represents bursty communications on a fixed frequency.

**Line 54**

```python
    def __init__(self, name, band, p_on_given_off=0.15, p_on_given_on=0.85):
```

Defines the constructor.

Arguments:

- `name`: emitter identifier
- `band`: fixed frequency band
- `p_on_given_off`: probability of turning ON after being OFF
- `p_on_given_on`: probability of staying ON after being ON

**Line 55**

```python
        super().__init__(name)
```

Calls the parent `Emitter` constructor.

This initializes `self.name`, `self.band`, and `self.on`.

**Line 56**

```python
        self.band = band
```

Assigns the fixed operating band.

**Line 57**

```python
        self.p_on_given_off = p_on_given_off
```

Stores the transition probability:

```
P(ON at next step | OFF at current step)
```

**Line 58**

```python
        self.p_on_given_on = p_on_given_on
```

Stores the transition probability:

```
P(ON at next step | ON at current step)
```

**Line 59**

```python
        self.on = random.random() < 0.3
```

Randomly initializes the emitter's state.

`random.random()` returns a value in `[0, 1)`. Therefore, the emitter starts ON with probability `0.3`.

**Line 60**

Blank line separating constructor and behavior method.

**Line 61**

```python
    def step(self, t):
```

Defines one simulation step.

The `t` argument is accepted for consistency with other emitters, although it is not used here.

**Line 62**

```python
        p = self.p_on_given_on if self.on else self.p_on_given_off
```

Selects the appropriate transition probability based on the current state.

- If currently ON, use `p_on_given_on`
- If currently OFF, use `p_on_given_off`

**Line 63**

```python
        self.on = random.random() < p
```

Samples the next state.

The emitter becomes ON with probability `p`; otherwise it becomes OFF.

**Line 64**

```python
        return self.band, self.on
```

Returns the emitter's current band and current ON/OFF state.

---

## `PeriodicEmitter`: lines 67–80

**Line 67**

```python
class PeriodicEmitter(Emitter):
```

Defines an emitter that follows a deterministic repeating band sequence.

**Line 68**

```python
    """Hops through a fixed cyclic sequence of bands, `dwell` steps per
```

Starts the class documentation.

**Line 69**

```python
    band (e.g. a periodic scanning radar / cyclic beacon)."""
```

Explains that the emitter stays on each band for a fixed number of steps before moving to the next.

**Line 70**

```python
    def __init__(self, name, band_sequence: List[int], dwell=3):
```

Defines the constructor.

Arguments:

- `name`: emitter name
- `band_sequence`: ordered list of bands
- `dwell`: number of steps spent on each band

**Line 71**

```python
        super().__init__(name)
```

Initializes the base `Emitter` fields.

**Line 72**

```python
        self.band_sequence = band_sequence
```

Stores the cyclic band sequence.

**Line 73**

```python
        self.dwell = dwell
```

Stores how long the emitter remains on each band.

**Line 74**

```python
        self.on = True
```

Makes the periodic emitter always transmit.

Unlike `MarkovEmitter`, it does not randomly turn off.

**Line 75**

Blank line separating constructor and `step()`.

**Line 76**

```python
    def step(self, t):
```

Defines the state update for one time step.

**Line 77**

```python
        idx = (t // self.dwell) % len(self.band_sequence)
```

Calculates which position in the band sequence should be active.

- `t // self.dwell` converts time into a dwell interval
- `% len(self.band_sequence)` wraps around cyclically

For example, with `dwell=4` and three bands:

```
t = 0–3   -> sequence index 0
t = 4–7   -> sequence index 1
t = 8–11  -> sequence index 2
t = 12–15 -> sequence index 0
```

**Line 78**

```python
        self.band = self.band_sequence[idx]
```

Selects the current band from the sequence.

**Line 79**

```python
        self.on = True
```

Ensures the emitter remains active.

**Line 80**

```python
        return self.band, self.on
```

Returns the current band and active state.

---

## `AgileEmitter`: lines 83–98

**Line 83**

```python
class AgileEmitter(Emitter):
```

Defines a frequency-agile emitter.

**Line 84**

```python
    """Frequency-agile emitter: hops to a random band from its pool every
```

Starts the documentation.

**Line 85**

```python
    `dwell` steps, with a duty cycle. No exploitable periodicity —
```

Explains that the band changes periodically, but the actual selected band is random.

**Line 86**

```python
    represents an LPI/LPD-style threat."""
```

Connects the model to low-probability-of-intercept/detection threats.

**Line 87**

```python
    def __init__(self, name, bands: List[int], dwell=2, duty=0.6):
```

Defines the constructor.

Arguments:

- `name`: emitter name
- `bands`: allowed band pool
- `dwell`: how long the current band is retained
- `duty`: probability of transmitting on each step

**Line 88**

```python
        super().__init__(name)
```

Initializes the inherited fields.

**Line 89**

```python
        self.bands = bands
```

Stores the pool of possible bands.

**Line 90**

```python
        self.dwell = dwell
```

Stores the band dwell duration.

**Line 91**

```python
        self.duty = duty
```

Stores the probability that the emitter is ON at each step.

**Line 92**

```python
        self.band = random.choice(bands)
```

Randomly selects the initial band.

**Line 93**

Blank line separating initialization from behavior.

**Line 94**

```python
    def step(self, t):
```

Defines one simulation step.

**Line 95**

```python
        if t % self.dwell == 0:
```

Checks whether the emitter has reached the beginning of a new dwell interval.

**Line 96**

```python
            self.band = random.choice(self.bands)
```

If a new dwell starts, selects a new random band.

**Line 97**

```python
        self.on = random.random() < self.duty
```

Randomly determines whether the emitter transmits during this step.

**Line 98**

```python
        return self.band, self.on
```

Returns the current band and ON/OFF state.

**Lines 99–100**

Blank lines separating the emitter classes from the environment class.

---

# `Environment`: lines 101–116

**Line 101**

```python
@dataclass
```

Instructs Python to generate common data-container methods automatically, including an initializer.

**Line 102**

```python
class Environment:
```

Defines the simulation environment.

**Line 103**

```python
    n_bands: int
```

Declares the number of available frequency bands.

**Line 104**

```python
    emitters: List[Emitter]
```

Declares the list of emitter objects placed in the environment.

**Line 105**

```python
    t: int = 0
```

Declares the simulation clock and initializes it to zero.

**Line 106**

Blank line separating fields from methods.

**Line 107**

```python
    def step(self) -> Dict[int, bool]:
```

Defines one environment update.

It returns a dictionary mapping each band number to a Boolean ON/OFF value.

**Line 108**

```python
        """Advance all emitters one step. Returns ground-truth ON/OFF
```

Starts the method documentation.

**Line 109**

```python
        status for every band this step (OR-combined if bands collide)."""
```

Explains that if multiple emitters use the same band, the result is ON if any of them is ON.

**Line 110**

```python
        status = {b: False for b in range(self.n_bands)}
```

Creates a dictionary containing every band, initially marked OFF.

For `n_bands=4`, this produces:

```python
{0: False, 1: False, 2: False, 3: False}
```

**Line 111**

```python
        for e in self.emitters:
```

Iterates over all emitters.

**Line 112**

```python
            band, on = e.step(self.t)
```

Advances the emitter by one step and receives:

- Its current band
- Its current ON/OFF state

**Line 113**

```python
            if on:
```

Checks whether that emitter is transmitting.

**Line 114**

```python
                status[band] = True
```

Marks the emitter's band as active.

If another emitter already marked that band active, it remains active. This implements logical OR behavior.

**Line 115**

```python
        self.t += 1
```

Advances the environment's simulation clock.

**Line 116**

```python
        return status
```

Returns the complete ground-truth band state for the current step.

**Lines 117–118**

Blank lines separating the environment from the scheduler section.

---

# 2. Scheduler classes

## Lines 119–121

**Line 119**

```python
# ----------------------------------------------------------------------
```

Visual section separator.

**Line 120**

```python
# 2. Schedulers
```

Labels the scheduler section.

**Line 121**

```python
# ----------------------------------------------------------------------
```

Closes the section header.

---

## Base `Scheduler`: lines 123–132

**Line 123**

```python
class Scheduler:
```

Defines the common scheduler interface.

**Line 124**

```python
    def __init__(self, n_bands: int):
```

Defines the base constructor.

**Line 125**

```python
        self.n_bands = n_bands
```

Stores the number of bands available to the scheduler.

**Line 126**

Blank line separating methods.

**Line 127**

```python
    def choose_band(self) -> int:
```

Declares the method that selects the next band.

**Line 128**

```python
        raise NotImplementedError
```

Requires subclasses to implement their own selection policy.

**Line 129**

Blank line.

**Line 130**

```python
    def update(self, band: int, observed_on: bool):
```

Declares the feedback method.

It receives:

- The scanned band
- Whether that band was observed to be ON

**Line 131**

```python
        """Called with the ground-truth result after scanning `band`."""
```

Documents the update method.

In this prototype, the scheduler receives the true state directly without detection noise.

**Line 132**

```python
        pass
```

Provides an empty default implementation.

A subclass may override it if it learns from observations.

**Lines 133–134**

Blank lines between the base class and the first concrete scheduler.

---

## `RoundRobinScheduler`: lines 135–144

**Line 135**

```python
class RoundRobinScheduler(Scheduler):
```

Defines a scheduler that scans bands in fixed order.

**Line 136**

```python
    """Open-loop baseline: sweeps every band in fixed order."""
```

Documents the policy.

It does not use feedback.

**Line 137**

```python
    def __init__(self, n_bands):
```

Defines the constructor.

**Line 138**

```python
        super().__init__(n_bands)
```

Initializes the base scheduler.

**Line 139**

```python
        self.ptr = 0
```

Initializes a pointer to the first band.

**Line 140**

Blank line.

**Line 141**

```python
    def choose_band(self):
```

Defines the selection method.

**Line 142**

```python
        b = self.ptr
```

Stores the current pointer value as the band to return.

**Line 143**

```python
        self.ptr = (self.ptr + 1) % self.n_bands
```

Advances the pointer and wraps it back to zero after the final band.

**Line 144**

```python
        return b
```

Returns the selected band.

**Lines 145–146**

Blank lines.

---

## `RandomScheduler`: lines 147–150

**Line 147**

```python
class RandomScheduler(Scheduler):
```

Defines a scheduler that chooses randomly.

**Line 148**

```python
    """Naive baseline: uniformly random band each step."""
```

Documents that every band has equal selection probability.

**Line 149**

```python
    def choose_band(self):
```

Defines the selection method.

**Line 150**

```python
        return random.randrange(self.n_bands)
```

Returns a random integer from `0` through `self.n_bands - 1`.

**Lines 151–152**

Blank lines.

---

# `BeliefScheduler`: lines 153–210

## Class documentation: lines 153–168

**Line 153**

```python
class BeliefScheduler(Scheduler):
```

Defines the learning-based scheduler.

**Line 154**

```python
    """
```

Starts the class documentation string.

**Line 155**

```
    Closed-loop learned scheduler.
```

Identifies the scheduler as feedback-driven.

**Line 156**

Blank documentation line.

**Line 157**

```
    For each band it online-learns a 2-state Markov model
```

Explains that every band gets its own Markov model.

**Line 158**

```
    (P(on | off), P(on | on)) via counting, and maintains a belief
```

The model learns two transition probabilities:

- Probability of becoming ON after OFF
- Probability of staying ON after ON

It also maintains a current activity belief.

**Line 159**

```
    P(band currently ON):
```

Introduces the meaning of the belief value.

**Line 160**

```
      - set to 0/1 exactly when the band is scanned (fully observed)
```

When the scheduler scans a band, it knows its current state and sets the belief to either 0 or 1.

**Line 161**

```
      - propagated forward via the learned transition model when NOT
```

When the scheduler does not scan a band, it predicts its future state.

**Line 162**

```
        scanned (standard HMM forward step under partial observability)
```

Compares that prediction to a hidden-Markov-model belief update.

**Line 163**

Blank documentation line.

**Line 164**

```
    Each step it scans argmax(belief), with epsilon exploration so it
```

Explains that the scheduler normally chooses the band with maximum belief but occasionally explores randomly.

**Line 165**

```
    keeps learning about rarely-scanned bands. This is a practical
```

Explains why exploration is needed: otherwise ignored bands would never be learned.

**Line 166**

```
    myopic approximation of the Whittle index used for restless
```

Describes the approach as a simple one-step approximation to a more advanced bandit policy.

**Line 167**

```
    multi-armed bandit scheduling.
```

Completes the description.

**Line 168**

```python
    """
```

Ends the class documentation.

## Constructor: lines 169–178

**Line 169**

```python
    def __init__(self, n_bands, epsilon=0.08):
```

Defines the constructor.

Arguments:

- `n_bands`: number of available bands
- `epsilon`: probability of random exploration

The default exploration probability is 8%.

**Line 170**

```python
        super().__init__(n_bands)
```

Initializes the base scheduler.

**Line 171**

```python
        self.epsilon = epsilon
```

Stores the exploration probability.

**Line 172**

```python
        # Laplace-smoothed transition counts
```

Documents the following initialized counters.

Laplace smoothing prevents probabilities from becoming undefined or overconfident at startup.

**Line 173**

```python
        self.off_on = [1.0] * n_bands
```

For every band, initializes the count of observed OFF-to-ON transitions to 1.

**Line 174**

```python
        self.off_tot = [2.0] * n_bands
```

For every band, initializes the total number of transitions from an OFF state to 2.

Therefore the initial estimate is:

```
P(ON | OFF) = 1 / 2 = 0.5
```

**Line 175**

```python
        self.on_on = [1.0] * n_bands
```

Initializes the count of ON-to-ON transitions to 1 for each band.

**Line 176**

```python
        self.on_tot = [2.0] * n_bands
```

Initializes the total ON-originating transition count to 2.

Thus the initial estimate is also:

```
P(ON | ON) = 1 / 2 = 0.5
```

**Line 177**

```python
        self.belief = [0.3] * n_bands
```

Initializes every band's estimated probability of currently being ON to 0.3.

**Line 178**

```python
        self.last_scan_result = [None] * n_bands
```

Stores the most recent observed state for every band.

`None` means that the band has not yet been scanned.

**Lines 179–180**

Blank lines between the constructor and helper methods.

## Transition-probability helpers: lines 181–188

**Line 181**

```python
        return self.off_on[b] / self.off_tot[b]
```

Returns the estimated probability that band `b` turns ON after being OFF.

This line belongs to `_p_on_given_off()`, whose function definition is on line 180.

**Line 182**

Blank line separating helper methods.

**Line 183**

```python
    def _p_on_given_on(self, b):
```

Defines a helper for the ON-to-ON transition probability.

**Line 184**

```python
        return self.on_on[b] / self.on_tot[b]
```

Returns the estimated probability that band `b` remains ON after being ON.

**Line 185**

Blank line.

**Line 186**

```python
    def _propagate(self, b):
```

Defines a helper that predicts the next belief for one band without directly observing it.

**Line 187**

```python
        bel = self.belief[b]
```

Copies the current belief for band `b` into a local variable.

**Line 188**

```python
        self.belief[b] = bel * self._p_on_given_on(b) + (1 - bel) * self._p_on_given_off(b)
```

Applies the Markov prediction equation:

```
new belief =
    current probability of ON × P(ON next | ON now)
  + current probability of OFF × P(ON next | OFF now)
```

Since the probability of OFF is `1 - bel`, this produces the predicted probability that the band is ON at the next time step.

## Choosing a band: lines 190–195

**Line 190**

```python
    def choose_band(self):
```

Defines the scheduler's band-selection method.

**Line 191**

```python
        for b in range(self.n_bands):
```

Iterates over every band.

**Line 192**

```python
            self._propagate(b)
```

Advances every band's belief one step using its learned Markov model.

**Line 193**

```python
        if random.random() < self.epsilon:
```

Draws a random number and checks whether to explore.

With the default `epsilon=0.08`, this condition is true about 8% of the time.

**Line 194**

```python
            return random.randrange(self.n_bands)
```

If exploring, selects a completely random band.

**Line 195**

```python
        return max(range(self.n_bands), key=lambda b: self.belief[b])
```

If not exploring, returns the band with the greatest predicted ON probability.

The `lambda` function tells `max()` to compare bands using their belief values.

## Learning from an observation: lines 197–210

**Line 197**

```python
    def update(self, band, observed_on):
```

Defines the feedback method called after a scan.

**Line 198**

```python
        prev = self.last_scan_result[band]
```

Retrieves the previous observed state for this band.

This is needed to estimate a transition from the previous observation to the current observation.

**Line 199**

```python
        if prev is not None:
```

Only updates transition statistics if the band has been observed before.

The first observation has no previous state to compare against.

**Line 200**

```python
            if prev:
```

Checks whether the previous observation was ON.

**Line 201**

```python
                self.on_tot[band] += 1
```

Increments the total number of transitions whose previous state was ON.

**Line 202**

```python
                if observed_on:
```

Checks whether the current observation is also ON.

**Line 203**

```python
                    self.on_on[band] += 1
```

If the band stayed ON, increments the ON-to-ON transition count.

**Line 204**

```python
            else:
```

Handles the case where the previous observation was OFF.

**Line 205**

```python
                self.off_tot[band] += 1
```

Increments the total number of transitions whose previous state was OFF.

**Line 206**

```python
                if observed_on:
```

Checks whether the band transitioned from OFF to ON.

**Line 207**

```python
                    self.off_on[band] += 1
```

If it did, increments the OFF-to-ON transition count.

**Line 208**

```python
        self.last_scan_result[band] = observed_on
```

Stores the current observation as the band's most recent state.

**Line 209**

```python
        self.belief[band] = 1.0 if observed_on else 0.0
```

Resets the belief to certainty because the band was directly observed.

- Observed ON → belief `1.0`
- Observed OFF → belief `0.0`

**Line 210**

Blank line separating schedulers from metrics.

---

# 3. Simulation statistics

## Lines 212–214

**Line 212**

```python
# ----------------------------------------------------------------------
```

Visual separator.

**Line 213**

```python
# 3. Simulation loop + metrics
```

Labels the metrics and simulation section.

**Line 214**

```python
# ----------------------------------------------------------------------
```

Closes the section header.

---

# `RunStats`: lines 216–233

**Line 216**

```python
@dataclass
```

Automatically generates a constructor and other data-container methods.

**Line 217**

```python
class RunStats:
```

Defines a container for one episode's statistics.

**Line 218**

```python
    total_steps: int = 0
```

Stores how many simulation steps have been completed.

**Line 219**

```python
    total_transmissions: int = 0     # steps where >=1 band was ON somewhere
```

Counts time steps during which at least one band was active anywhere in the environment.

This is not the total number of active band-time pairs; it is the number of active time steps.

**Line 220**

```python
    hits: int = 0                    # scanned band happened to be ON
```

Counts how many times the scheduler selected a band that was ON.

**Line 221**

```python
    intercept_delays: List[int] = field(default_factory=list)
```

Stores detection delays for transmission intervals.

`default_factory=list` ensures every `RunStats` instance gets its own list.

**Line 222**

```python
    rewards: List[int] = field(default_factory=list)
```

Stores one reward value per simulation step.

Each reward is:

- `1` if the selected band was ON
- `0` otherwise

**Line 223**

Blank line.

## `report()`: lines 224–233

**Line 224**

```python
    def report(self):
```

Defines a method that converts raw counters into summary metrics.

**Line 225**

```python
        interception_ratio = self.hits / max(1, self.total_transmissions)
```

Calculates the interception ratio.

The denominator is protected with `max(1, ...)` to avoid division by zero.

Note that `total_transmissions` counts active time steps, not total active bands.

**Line 226**

```python
        avg_reward = statistics.mean(self.rewards) if self.rewards else 0.0
```

Calculates the average reward per simulation step.

If no rewards exist, returns `0.0`.

**Line 227**

```python
        avg_delay = statistics.mean(self.intercept_delays) if self.intercept_delays else None
```

Calculates the average interception delay.

If no delays were recorded, uses `None`.

**Line 228**

```python
        return {
```

Starts a dictionary containing the report.

**Line 229**

```python
            "interception_ratio": round(interception_ratio, 3),
```

Stores the interception ratio rounded to three decimal places.

**Line 230**

```python
            "avg_reward_per_step": round(avg_reward, 3),
```

Stores the average reward rounded to three decimal places.

**Line 231**

```python
            "avg_intercept_delay": round(avg_delay, 2) if avg_delay is not None else "n/a",
```

Stores the average delay rounded to two decimals.

If no delay exists, stores the string `"n/a"`.

**Line 232**

```python
            "hits": self.hits,
```

Includes the raw hit count.

**Line 233**

```python
        }
```

Closes and returns the dictionary.

**Lines 234–235**

Blank lines before the episode runner.

---

# `run_episode()`: lines 236–269

**Line 236**

```python
def run_episode(env_factory, scheduler: Scheduler, n_steps: int, n_bands: int) -> RunStats:
```

Defines the main simulation function.

Arguments:

- `env_factory`: callable that creates a fresh environment
- `scheduler`: scheduler instance
- `n_steps`: number of time steps
- `n_bands`: number of bands

The function returns a `RunStats` object.

**Line 237**

```python
    env = env_factory()
```

Creates a new environment.

Using a factory ensures each run begins with a fresh emitter population.

**Line 238**

```python
    stats = RunStats()
```

Creates an empty statistics object.

**Line 239**

```python
    on_since: List[Optional[int]] = [None] * n_bands
```

Creates one entry per band to track when its current ON interval began.

`None` means the band is not currently known to be in an ON interval.

**Line 240**

```python
    credited = [False] * n_bands
```

Tracks whether the current ON interval for each band has already received interception-delay credit.

This prevents repeatedly crediting the same continuous transmission.

**Line 241**

Blank line.

**Line 242**

```python
    for t in range(n_steps):
```

Starts the main simulation loop.

`t` ranges from `0` through `n_steps - 1`.

**Line 243**

```python
        status = env.step()
```

Advances the environment and obtains the true ON/OFF state of every band.

**Line 244**

Blank line.

**Line 245**

```python
        for b in range(n_bands):
```

Iterates over all bands to maintain transmission interval tracking.

**Line 246**

```python
            if status[b]:
```

Checks whether band `b` is ON at the current time step.

**Line 247**

```python
                if on_since[b] is None:
```

Checks whether this is the beginning of a new ON interval.

**Line 248**

```python
                    on_since[b] = t
```

Records the current time as the start of the ON interval.

**Line 249**

```python
                    credited[b] = False
```

Allows the next successful observation of this interval to receive delay credit.

**Line 250**

```python
            else:
```

Handles the case where band `b` is OFF.

**Line 251**

```python
                on_since[b] = None
```

Clears the start time because the transmission interval has ended.

**Line 252**

```python
                credited[b] = False
```

Resets the credit flag for the next ON interval.

**Line 253**

Blank line.

**Line 254**

```python
        if any(status.values()):
```

Checks whether at least one band is active at this time step.

**Line 255**

```python
            stats.total_transmissions += 1
```

Counts this time step as a transmission-containing step.

**Line 256**

Blank line.

**Line 257**

```python
        band = scheduler.choose_band()
```

Asks the scheduler which band to scan.

**Line 258**

```python
        observed_on = status[band]
```

Looks up the true state of the selected band.

Because this prototype assumes perfect detection, this is the scheduler's observation.

**Line 259**

```python
        scheduler.update(band, observed_on)
```

Feeds the observation back to the scheduler so it can update its model.

**Line 260**

Blank line.

**Line 261**

```python
        stats.rewards.append(1 if observed_on else 0)
```

Adds a reward for this step:

- `1` when the scan found activity
- `0` when it did not

**Line 262**

```python
        if observed_on:
```

Checks whether the scheduler successfully observed an active band.

**Line 263**

```python
            stats.hits += 1
```

Increments the hit counter.

**Line 264**

```python
            if on_since[band] is not None and not credited[band]:
```

Checks whether:

- The selected band belongs to an active interval
- That interval has not already been credited

**Line 265**

```python
                stats.intercept_delays.append(t - on_since[band])
```

Calculates and records the delay between the beginning of the ON interval and the first successful scan.

**Line 266**

```python
                credited[band] = True
```

Marks this interval as credited so later hits during the same continuous interval do not add more delay entries.

**Line 267**

```python
        stats.total_steps += 1
```

Increments the completed-step counter.

**Line 268**

Blank line inside the function.

**Line 269**

```python
    return stats
```

Returns the completed statistics object.

**Lines 270–271**

Blank lines before the scenario builder.

---

# `make_scenario()`: lines 272–283

**Line 272**

```python
def make_scenario(n_bands=8):
```

Defines a function that constructs the standard mixed-emitter scenario.

**Line 273**

```python
    """Mixed scene: two Markov comms channels, one periodic beacon, one
```

Starts the function documentation.

**Line 274**

```python
    frequency-agile threat, all sharing the same band pool."""
```

Describes the four emitters used in the scenario.

**Line 275**

```python
    def factory():
```

Defines an inner factory function.

A factory is used so every experiment can create a fresh environment.

**Line 276**

```python
        emitters = [
```

Starts a list of emitter objects.

**Line 277**

```python
            MarkovEmitter("comm-1", band=1, p_on_given_off=0.05, p_on_given_on=0.9),
```

Creates a bursty communications emitter on band 1.

Its behavior is highly persistent:

- It rarely turns ON from OFF: `0.05`
- It usually stays ON once active: `0.9`

**Line 278**

```python
            MarkovEmitter("comm-2", band=4, p_on_given_off=0.10, p_on_given_on=0.7),
```

Creates another Markov communications emitter on band 4.

It is less persistent than `comm-1`.

**Line 279**

```python
            PeriodicEmitter("beacon", band_sequence=[2, 5, 6], dwell=4),
```

Creates an always-ON periodic beacon.

It cycles through bands 2, 5, and 6, staying four steps on each band.

**Line 280**

```python
            AgileEmitter("agile-threat", bands=[0, 3, 6, 7], dwell=2, duty=0.5),
```

Creates a frequency-agile emitter.

It:

- Randomly selects among bands 0, 3, 6, and 7
- Keeps each selected band for two steps
- Is active with probability 0.5 at each step

**Line 281**

```python
        ]
```

Closes the emitter list.

**Line 282**

```python
        return Environment(n_bands=n_bands, emitters=emitters)
```

Creates and returns an environment containing the configured emitters.

**Line 283**

```python
    return factory
```

Returns the factory function rather than an environment instance.

The caller can invoke it later to get a fresh environment.

**Lines 284–285**

Blank lines before the executable entry point.

---

# `main()`: lines 286–308

**Line 286**

```python
def main():
```

Defines the command-line entry-point function.

**Line 287**

```python
    random.seed(7)
```

Seeds Python's random number generator.

This makes the run reproducible, assuming the same code and Python behavior.

**Line 288**

```python
    N_BANDS = 36
```

Sets the experiment to use 36 frequency bands.

**Line 289**

```python
    n_steps = 4000
```

Sets the simulation length to 4,000 time steps.

**Line 290**

```python
    scenario = make_scenario(N_BANDS)
```

Creates a factory for the four-emitter scenario using 36 bands.

**Line 291**

Blank line.

**Line 292**

```python
    schedulers = {
```

Starts a dictionary mapping display names to scheduler objects.

**Line 293**

```python
        "RoundRobin (open-loop baseline)": RoundRobinScheduler(N_BANDS),
```

Creates the round-robin baseline.

**Line 294**

```python
        "Random (naive baseline)": RandomScheduler(N_BANDS),
```

Creates the random baseline.

**Line 295**

```python
        "BeliefScheduler (learned, closed-loop)": BeliefScheduler(N_BANDS, epsilon=0.08),
```

Creates the learning-based scheduler with 8% random exploration.

**Line 296**

```python
    }
```

Closes the scheduler dictionary.

**Line 297**

Blank line.

**Line 298**

```python
    print(f"Scenario: {N_BANDS} bands, {n_steps} steps, 4 concurrent emitters "
```

Begins printing a human-readable description of the experiment.

The `f` prefix allows insertion of variable values.

**Line 299**

```python
          f"(2 Markov comms, 1 periodic beacon, 1 frequency-agile threat)\n")
```

Continues the formatted string and adds a newline at the end.

The two adjacent f-strings are automatically concatenated by Python.

**Line 300**

```python
    header = f"{'Scheduler':40s} | {'Interception %':>15s} | {'Avg Reward/step':>16s} | {'Avg Intercept Delay':>20s}"
```

Builds a formatted table header.

Formatting instructions:

- `:40s`: left-align text in a 40-character field
- `:>15s`: right-align text in a 15-character field
- Similar formatting is used for the other columns

**Line 301**

```python
    print(header)
```

Prints the table header.

**Line 302**

```python
    print("-" * len(header))
```

Prints a separator line whose length matches the header.

**Line 303**

Blank line.

**Line 304**

```python
    for name, sched in schedulers.items():
```

Iterates over each scheduler name and object.

**Line 305**

```python
        stats = run_episode(scenario, sched, n_steps, N_BANDS)
```

Runs one complete simulation for the current scheduler.

The scenario factory creates a fresh environment.

**Line 306**

```python
        r = stats.report()
```

Converts the raw statistics into a summary dictionary.

**Line 307**

```python
        print(f"{name:40s} | {r['interception_ratio']*100:14.1f}% | "
```

Prints the scheduler name and interception percentage.

The ratio is multiplied by 100 and displayed with one decimal place.

**Line 308**

```python
              f"{r['avg_reward_per_step']:16.3f} | {str(r['avg_intercept_delay']):>20s}")
```

Prints:

- Average reward per step
- Average interception delay

The delay is converted to a string so that both numeric values and `"n/a"` can be displayed.

**Lines 309–310**

Blank lines before the module guard.

---

# Script entry point: lines 311–312

**Line 311**

```python
if __name__ == "__main__":
```

Checks whether this file is being run directly rather than imported as a module.

**Line 312**

```python
    main()
```

Runs the experiment when the file is executed directly.

If another file imports this module, `main()` does not run automatically.

---

## What this first file establishes

This file provides the foundation for the entire codebase:

- A common emitter interface
- Synthetic Markov, periodic, and agile emitters
- A band-status environment
- Baseline schedulers
- A learned belief scheduler
- The episode execution loop
- Initial interception metrics

The later files mainly extend one of these parts:

- `scan_scheduler_v2.py` extends the scheduler interface
- `scan_scheduler_v3_pri.py` adds PRI prediction
- `pdw_environment.py` replaces the synthetic environment with PDW data
- `noise_model.py` replaces perfect observations with noisy detections




Completed and checked off `scan_scheduler_v2.py` in the Notion checklist.

# `scan_scheduler_v2.py` — line-by-line explanation

Blank lines are formatting-only and do not execute. I identify them by range rather than repeating “no runtime effect” for every blank line.

---

## Module documentation and imports

### Lines 1–18

**Line 1**

```python
"""
```

Starts the module-level documentation string.

**Line 2**

```
scan_scheduler_v2.py
```

Names the module.

**Line 3**

```
======================
```

Visual documentation separator.

**Line 4**

```
Two concrete upgrades over BeliefScheduler in scan_scheduler_prototype.py:
```

Explains that this file builds on the original `BeliefScheduler`.

**Line 5**

Blank documentation line.

**Line 6**

```
  1. UCB-style exploration bonus instead of fixed epsilon-greedy.
```

Introduces the first upgrade: UCB-based exploration.

**Line 7**

```
     Each band gets a bonus that shrinks as it's scanned more, so the
```

Explains that underexplored bands receive a larger bonus.

**Line 8**

```
     scheduler explores hard early and locks onto productive bands
```

Describes the intended behavior: explore initially, exploit later.

**Line 9**

```
     later -- no epsilon to hand-tune, and no exploration budget wasted
```

Contrasts UCB with fixed epsilon exploration.

**Line 10**

```
     once a band's behaviour is well understood.
```

Explains that UCB naturally reduces exploration as scan counts increase.

**Line 11**

Blank documentation line.

**Line 12**

```
  2. Multi-channel scanning: the receiver can dwell on k bands per step
```

Introduces the second upgrade: scanning multiple bands at each time step.

**Line 13**

```
     (a digital channelizer / multi-channel ESM receiver), not just one.
```

Relates the feature to a receiver with multiple simultaneous channels.

**Line 14**

```
     All three schedulers (RoundRobin, Random, BeliefUCB) now expose
```

States that all scheduler types use the same multi-channel interface.

**Line 15**

```
     choose_bands(k) and scan k bands per step.
```

Specifies that the new method is `choose_bands(k)`.

**Line 16**

Blank documentation line.

**Line 17**

```
Run:  python3 scan_scheduler_v2.py
```

Documents how to run the module directly.

**Line 18**

```python
"""
```

Ends the module-level documentation string.

---

### Lines 19–29

**Line 19**

Blank line after the module documentation.

**Line 20**

```python
import math
```

Imports mathematical functions such as:

- `sqrt`
- `log`

These are used in the UCB exploration formula.

**Line 21**

```python
import random
```

Imports random-number functionality for:

- Random scheduler choices
- Warm-up shuffling
- Warm-up jitter

**Line 22**

```python
import statistics
```

Imports statistical functions such as `statistics.mean()`.

**Line 23**

```python
from dataclasses import dataclass, field
```

Imports:

- `dataclass` for defining data containers
- `field` for safely creating mutable list fields

**Line 24**

```python
from typing import List, Dict, Optional  # Dict already used by run_episode below
```

Imports type annotations.

The comment explains that `Dict` is used later in `run_episode()`.

**Line 25**

Blank line separating standard-library imports from local imports.

**Line 26**

```python
from scan_scheduler_prototype import (
```

Starts a multi-line import from the previous module.

**Line 27**

```python
    MarkovEmitter, PeriodicEmitter, AgileEmitter, Environment, make_scenario
```

Imports the emitter classes, environment, and scenario builder from `scan_scheduler_prototype.py`.

**Line 28**

```python
)
```

Closes the multi-line import.

**Lines 29–30**

Blank lines before the scheduler section.

---

# Scheduler infrastructure

## Lines 31–33

**Line 31**

```python
# ----------------------------------------------------------------------
```

Visual comment separator.

**Line 32**

```python
# Schedulers (multi-channel interface)
```

Labels the scheduler section.

**Line 33**

```python
# ----------------------------------------------------------------------
```

Closes the section header.

---

# `recommended_warmup_dwell()`

## Lines 35–65

**Line 35**

```python
def recommended_warmup_dwell(switch_cost_steps: int, warmup_steps: int, margin: int = 2):
```

Defines a helper that recommends warm-up settings when receiver switching has a cost.

Arguments:

- `switch_cost_steps`: how many steps are lost while retuning
- `warmup_steps`: baseline warm-up length
- `margin`: additional dwell margin, defaulting to 2

The function returns:

```
(warmup_dwell_steps, scaled_warmup_steps)
```

**Line 36**

```
    """Given a real switch_cost_steps and the warmup_steps you'd use if
```

Starts the function documentation.

**Line 37**

```
    switching were free, returns (warmup_dwell_steps, scaled_warmup_steps)
```

Documents the return values.

**Line 38**

```
    that keep the warmup sweep's per-band expected-hit count comparable to
```

Explains the goal: preserve roughly the same number of useful observations.

**Line 39**

```
    the switch_cost_steps=0 case.
```

Compares the recommendation against the no-switch-cost baseline.

**Line 40**

Blank documentation line.

**Line 41**

```
    Validated (validate_warmup_dwell_fix.py, 30 seeds) that dwell =
```

Records an empirical result from the validation script.

**Line 42**

```
    switch_cost_steps + 1 (bare minimum: settle, then one valid look) is
```

Explains that merely allocating one step for settling plus one observation is insufficient.

**Line 43**

```
    NOT enough margin -- the per-visit valid-observation rate is still too
```

States that this configuration produces too few useful observations.

**Line 44**

```
    thin relative to jitter overhead, and lock-on stays poor even with
```

Explains that jitter and limited valid samples still hurt PRI lock-on.

**Line 45**

```
    jitter enabled. dwell = switch_cost_steps + margin (margin=2 by
```

Recommends a larger dwell.

**Line 46**

```
    default) gives real, majority-seed lock-on (23-25/30 seeds locking on
```

Documents the observed improvement.

**Line 47**

```
    across cost=1 and cost=2 in that validation).
```

Completes the validation result.

**Line 48**

Blank documentation line.

**Line 49**

```
    Because each dwell visit "wastes" switch_cost_steps of its length just
```

Explains why longer dwell visits reduce useful observation density.

**Line 50**

```
    settling, a fixed warmup_steps budget fits proportionally fewer full
```

A fixed total budget covers fewer complete band sweeps.

**Line 51**

```
    sweeps once dwell>1 -- so warmup_steps must scale up by roughly
```

Therefore the overall warm-up duration needs to increase.

**Line 52**

```
    dwell/(dwell - switch_cost_steps) to keep the same expected number of
```

Provides the approximate scaling factor.

**Line 53**

```
    valid per-band observations as the switch_cost_steps=0 case.
```

Explains what the scaling preserves.

**Line 54**

Blank documentation line.

**Line 55**

```
    warmup_dwell_jitter should stay ON (its default, 1) whenever dwell>1:
```

Recommends randomizing dwell lengths whenever the receiver dwells for multiple steps.

**Line 56**

```
    validated that dwell alone, with NO jitter, fails deterministically
```

States that fixed dwell can fail systematically.

**Line 57**

```
    (0% lock-on across every single one of 30 seeds, not just on average)
```

Documents the observed failure rate.

**Line 58**

```
    due to a fixed-parity aliasing between "settling" and "valid" steps --
```

Explains that the periodic emitter can repeatedly fall only on settling steps.

**Line 59**

```
    see the class docstring on _warmup_bands.
```

Points to the more detailed explanation in `_warmup_bands()`.

**Line 60**

```python
    """
```

Ends the function documentation.

**Line 61**

```python
    if switch_cost_steps <= 0:
```

Checks whether switching is free or nonpositive.

**Line 62**

```python
        return 1, warmup_steps
```

For zero switch cost, returns:

- One-step dwell
- The original warm-up duration

This preserves the previous behavior.

**Line 63**

```python
    dwell = switch_cost_steps + margin
```

For a positive switch cost, sets dwell length to the switch cost plus the chosen margin.

**Line 64**

```python
    scaled_warmup = int(round(warmup_steps * dwell / (dwell - switch_cost_steps)))
```

Scales the warm-up duration to compensate for settling time.

The expression estimates how many total steps are needed to obtain approximately the same number of useful samples as the no-cost case.

**Line 65**

```python
    return dwell, scaled_warmup
```

Returns the recommended dwell length and adjusted warm-up length.

**Lines 66–67**

Blank lines before the base scheduler.

---

# Base `Scheduler`

## Lines 68–76

**Line 68**

```python
class Scheduler:
```

Defines the common interface for all v2 schedulers.

**Line 69**

```python
    def __init__(self, n_bands: int):
```

Defines the base constructor.

**Line 70**

```python
        self.n_bands = n_bands
```

Stores the number of available bands.

**Line 71**

Blank line.

**Line 72**

```python
    def choose_bands(self, k: int) -> List[int]:
```

Declares the method used to select up to `k` bands.

It promises to return a list of integers.

**Line 73**

```python
        raise NotImplementedError
```

Forces concrete subclasses to implement the method.

**Line 74**

Blank line.

**Line 75**

```python
    def update(self, band: int, observed_on: bool):
```

Declares the feedback method.

**Line 76**

```python
        pass
```

Provides an empty default implementation.

Schedulers that learn from observations override it.

**Lines 77–78**

Blank lines before `RoundRobinScheduler`.

---

# `RoundRobinScheduler`

## Lines 79–87

**Line 79**

```python
class RoundRobinScheduler(Scheduler):
```

Defines the multi-channel round-robin scheduler.

**Line 80**

```python
    def __init__(self, n_bands):
```

Defines its constructor.

**Line 81**

```python
        super().__init__(n_bands)
```

Initializes the base scheduler.

**Line 82**

```python
        self.ptr = 0
```

Initializes the next starting position.

**Line 83**

Blank line.

**Line 84**

```python
    def choose_bands(self, k):
```

Defines the multi-band selection method.

**Line 85**

```python
        bands = [(self.ptr + i) % self.n_bands for i in range(k)]
```

Builds `k` consecutive band indices, wrapping around at the end.

For example, with 8 bands, `ptr=6`, and `k=3`, the result is:

```python
[6, 7, 0]
```

**Line 86**

```python
        self.ptr = (self.ptr + k) % self.n_bands
```

Advances the pointer by the number of selected bands.

**Line 87**

```python
        return bands
```

Returns the selected list.

**Lines 88–89**

Blank lines.

---

# `RandomScheduler`

## Lines 90–92

**Line 90**

```python
class RandomScheduler(Scheduler):
```

Defines the random multi-channel baseline.

**Line 91**

```python
    def choose_bands(self, k):
```

Defines its selection method.

**Line 92**

```python
        return random.sample(range(self.n_bands), min(k, self.n_bands))
```

Selects distinct random bands.

`min(k, self.n_bands)` prevents requesting more unique bands than exist.

Unlike `random.choices()`, `random.sample()` does not select the same band twice in one step.

**Lines 93–94**

Blank lines.

---

# `BeliefUCBScheduler`

## Class documentation: lines 95–112

**Line 95**

```python
class BeliefUCBScheduler(Scheduler):
```

Defines the main learned scheduler in this file.

**Line 96**

```python
    """
```

Starts the class documentation.

**Line 97**

```
    Learns a per-band 2-state Markov model online (same as BeliefScheduler),
```

Explains that it keeps the Markov learning approach from the prototype.

**Line 98**

```
    but replaces fixed-epsilon exploration with a UCB1-style optimism
```

States that exploration is now based on UCB instead of a fixed random probability.

**Line 99**

```
    bonus: score(b) = priority(b) * belief(b) + c * sqrt(log(t+1) / (scans(b)+1)).
```

Defines the score formula.

Components:

- `priority[b] * belief[b]`: exploitation value
- `ucb_c * sqrt(log(t+1)/(scan_count[b]+1))`: exploration bonus

**Line 100**

```
    Scans the top-k bands by score each step.
```

Explains that the scheduler ranks all bands and selects the best `k`.

**Line 101**

Blank documentation line.

**Line 102**

```
    `priority` lets you tell the scheduler some bands matter more than
```

Introduces configurable band priorities.

**Line 103**

```
    others regardless of how often they transmit -- e.g. a rare,
```

Explains that a rare band can be prioritized over a frequently active band.

**Line 104**

```
    disciplined fixed-PRI radar should outrank a loud, harmless comms
```

Gives the motivating example.

**Line 105**

```
    channel even though the comms channel is easier to rack up
```

Explains the problem with optimizing only raw hit counts.

**Line 106**

```
    interception "credit" against. Without this, a scheduler that only
```

States that an unweighted scheduler may favor easy targets.

**Line 107**

```
    maximizes raw interception count will always favor loud, easy
```

Explains the resulting bias.

**Line 108**

```
    sources over rare, important ones (see the fixed-PRI-radar-vs-comm-1
```

Points to the motivating trade-off.

**Line 109**

```
    trade-off this was built to address). The exploration bonus is left
```

Clarifies how priority is applied.

**Line 110**

```
    unweighted so priority shapes exploitation, not how eagerly a band's
```

The priority affects exploitation only.

**Line 111**

```
    true behaviour gets learned in the first place.
```

Explains that exploration remains comparable across bands.

**Line 112**

```python
    """
```

Ends the class documentation.

---

## Constructor: lines 113–156

**Line 113**

```python
    def __init__(self, n_bands, ucb_c: float = 0.5, warmup_steps: int = 0,
```

Defines the constructor.

Arguments:

- `n_bands`
- `ucb_c`: exploration strength
- `warmup_steps`: number of initial exploratory steps

**Line 114**

```python
                 priority: Optional[List[float]] = None,
```

Adds an optional list of band priority weights.

**Line 115**

```python
                 warmup_dwell_steps: int = 1, warmup_dwell_jitter: int = 1):
```

Adds warm-up dwell and jitter parameters.

**Line 116**

```python
        super().__init__(n_bands)
```

Initializes the base `Scheduler`.

**Line 117**

```python
        self.ucb_c = ucb_c
```

Stores the UCB exploration coefficient.

Larger values encourage more exploration.

**Line 118**

```python
        self.warmup_steps = warmup_steps
```

Stores the number of initial warm-up steps.

**Line 119**

```python
        self.priority = list(priority) if priority is not None else [1.0] * n_bands
```

Creates the priority list.

- If a list was supplied, copies it.
- Otherwise, assigns priority `1.0` to every band.

**Line 120**

```python
        self.off_on = [1.0] * n_bands
```

Initializes OFF-to-ON transition counts with Laplace smoothing.

**Line 121**

```python
        self.off_tot = [2.0] * n_bands
```

Initializes total OFF-originating transition counts.

Initial estimate:

```
P(ON | OFF) = 1 / 2 = 0.5
```

**Line 122**

```python
        self.on_on = [1.0] * n_bands
```

Initializes ON-to-ON transition counts.

**Line 123**

```python
        self.on_tot = [2.0] * n_bands
```

Initializes total ON-originating transition counts.

Initial estimate:

```
P(ON | ON) = 1 / 2 = 0.5
```

**Line 124**

```python
        self.belief = [0.3] * n_bands
```

Initializes every band's current activity belief to 0.3.

**Line 125**

```python
        self.last_scan_result = [None] * n_bands
```

Stores the most recent direct observation for each band.

**Line 126**

```python
        self.scan_count = [0] * n_bands
```

Tracks how many times each band has been validly scanned.

This is used in the UCB formula.

**Line 127**

```python
        self.t = 0
```

Initializes the scheduler's internal clock.

**Line 128**

```python
        self._warmup_order: List[int] = []
```

Creates an empty list that will hold the current shuffled warm-up order.

**Line 129**

```python
        self._warmup_idx = 0
```

Initializes the index into `_warmup_order`.

**Line 130**

```python
        # --- warm-up dwell (for use with switch_cost_steps>0) ---
```

Begins comments explaining warm-up dwell behavior.

**Line 131**

```python
        # Default 1 reproduces the ORIGINAL behaviour exactly: a fresh
```

Documents that the default dwell value preserves the previous implementation.

**Line 132**

```python
        # band every single warmup call, no repeats. That's fine when
```

With dwell equal to one, every warm-up call advances to a new band.

**Line 133**

```python
        # switching is free, but under a real switch_cost_steps>0 the
```

Explains why this becomes a problem when switching is costly.

**Line 134**

```python
        # warmup sweep itself switches on every step -- exactly the
```

The warm-up scan would retune the receiver every step.

**Line 135**

```python
        # RoundRobin failure mode -- so it can NEVER accumulate a valid
```

The receiver may never finish settling.

**Line 136**

```python
        # (post-settling) observation and lock-on never happens at all.
```

Therefore the scheduler cannot learn enough to lock onto a periodic signal.

**Line 137**

Blank comment line.

**Line 138**

```python
        # Setting warmup_dwell_steps > 1 makes the warmup sweep camp on
```

Explains that longer dwell keeps the receiver on each band.

**Line 139**

```python
        # each band for multiple consecutive steps (enough for the
```

This creates time for settling and observation.

**Line 140**

```python
        # switch to settle and still get >=1 valid look), instead of
```

The goal is at least one post-settling observation.

**Line 141**

```python
        # hopping every step. Found the hard way that dwell alone isn't
```

Warns that dwell alone is not enough.

**Line 142**

```python
        # enough and can even make things WORSE: a *fixed* dwell width
```

A fixed dwell can create systematic timing patterns.

**Line 143**

```python
        # creates a *fixed* parity between "settling" and "valid" steps
```

The same relative positions may repeatedly be settling or observable.

**Line 144**

```python
        # relative to the sweep's lap length, and a periodic emitter
```

This matters when the emitter's period aligns with the warm-up cycle.

**Line 145**

```python
        # whose true phase happens to fall on the settling parity is
```

A signal could repeatedly appear during invalid settling steps.

**Line 146**

```python
        # then structurally unreachable forever, no matter how long you
```

The problem would persist indefinitely.

**Line 147**

```python
        # run it -- a new instance of the exact scan/emitter-period
```

This is a form of aliasing between the scan schedule and emitter schedule.

**Line 148**

```python
        # aliasing problem the original warmup *shuffle* was built to
```

The original random shuffling was meant to break this alignment.

**Line 149**

```python
        # avoid. warmup_dwell_jitter randomizes each dwell's length by
```

Introduces random dwell variation.

**Line 150**

```python
        # 0..warmup_dwell_jitter extra steps, which breaks that fixed
```

The dwell receives a random extra length between zero and the configured maximum.

**Line 151**

```python
        # parity the same way shuffling broke the fixed-rotation
```

Randomness prevents permanent alignment.

**Line 152**

```python
        # aliasing. Set to 0 to disable jitter (not recommended once
```

Jitter can be disabled, but this is discouraged for multi-step dwell.

**Line 153**

```python
        # dwell > 1).
```

Completes the comment.

**Line 154**

```python
        self.warmup_dwell_steps = warmup_dwell_steps
```

Stores the base dwell length.

**Line 155**

```python
        self.warmup_dwell_jitter = warmup_dwell_jitter
```

Stores the maximum random extra dwell length.

**Line 156**

```python
        self._warmup_slots: List[Dict[str, int]] = []
```

Creates an empty list of per-channel warm-up state dictionaries.

Each slot will later contain:

```python
{"band": ..., "remaining": ...}
```

**Line 157**

Blank line before helper methods.

---

## Markov helpers: lines 158–166

**Line 158**

```python
    def _p_on_given_off(self, b):
```

Defines a helper to estimate `P(ON next | OFF now)` for band `b`.

**Line 159**

```python
        return self.off_on[b] / self.off_tot[b]
```

Calculates the OFF-to-ON probability.

**Line 160**

Blank line.

**Line 161**

```python
    def _p_on_given_on(self, b):
```

Defines a helper for `P(ON next | ON now)`.

**Line 162**

```python
        return self.on_on[b] / self.on_tot[b]
```

Calculates the ON-to-ON probability.

**Line 163**

Blank line.

**Line 164**

```python
    def _propagate(self, b):
```

Defines a method that predicts the next belief for one band.

**Line 165**

```python
        bel = self.belief[b]
```

Reads the current belief.

**Line 166**

```python
        self.belief[b] = bel * self._p_on_given_on(b) + (1 - bel) * self._p_on_given_off(b)
```

Applies the Markov prediction equation:

```
new belief =
    P(current ON) × P(next ON | current ON)
  + P(current OFF) × P(next ON | current OFF)
```

---

# Warm-up scheduling

## `_next_warmup_band()`: lines 168–179

**Line 168**

```python
    def _next_warmup_band(self):
```

Defines a helper that returns the next band in the shuffled warm-up sequence.

**Line 169**

```python
        """Pull the next band from a freshly-shuffled-per-lap sweep order
```

Starts the method documentation.

**Line 170**

```
        (shuffling, not a fixed rotation, is what avoids a permanent
```

Explains why the order is randomized.

**Line 171**

```
        scan/emitter-period aliasing blind spot -- see class docstring
```

Connects the behavior to the previously described aliasing issue.

**Line 172**

```
        on _warmup_bands' original purpose)."""
```

Ends the documentation.

**Line 173**

```python
        if self._warmup_idx >= len(self._warmup_order):
```

Checks whether the current shuffled order has been exhausted.

**Line 174**

```python
            self._warmup_order = list(range(self.n_bands))
```

Creates a list containing every band index.

**Line 175**

```python
            random.shuffle(self._warmup_order)
```

Randomly shuffles the list in place.

**Line 176**

```python
            self._warmup_idx = 0
```

Resets the position to the beginning of the new shuffled order.

**Line 177**

```python
        band = self._warmup_order[self._warmup_idx]
```

Reads the next band from the order.

**Line 178**

```python
        self._warmup_idx += 1
```

Advances the order index.

**Line 179**

```python
        return band
```

Returns the selected warm-up band.

---

## `_warmup_bands()`: lines 181–217

**Line 181**

```python
    def _warmup_bands(self, k):
```

Defines the method that selects `k` bands during warm-up.

**Line 182**

```python
        """Choose k warmup bands, one per receiver channel/slot. Each
```

Starts the method documentation.

**Line 183**

```
        slot independently sweeps the shuffled band order, but DWELLS on
```

Explains that each receiver channel has its own warm-up slot.

**Line 184**

```
        its current band for warmup_dwell_steps (+jitter) calls before
```

Each slot remains on a band for several calls.

**Line 185**

```
        advancing, instead of moving to a new band every single call.
```

This prevents constant switching.

**Line 186**

Blank documentation line.

**Line 187**

```
        With warmup_dwell_steps=1 (the default) each slot advances every
```

Documents the compatibility behavior.

**Line 188**

```
        call -- identical to the original behaviour, byte-for-byte.
```

With dwell one, the method acts like the original one-band-per-step warm-up.

**Line 189**

```
        Dwelling matters once switch_cost_steps>0 is used together with
```

Explains when longer dwell is needed.

**Line 190**

```
        warmup: without it, the warmup sweep switches bands on literally
```

Without dwell, every warm-up step causes a switch.

**Line 191**

```
        every step (same failure mode as RoundRobin), so under any real
```

The receiver spends its time settling.

**Line 192**

```
        switch cost it never survives settling long enough to get a
```

No useful observation is obtained.

**Line 193**

```
        single valid look -- lock-on can never even begin. Dwelling
```

PRI learning cannot start without valid observations.

**Line 194**

```
        gives each visit enough consecutive steps for a switch to settle
```

Longer dwell allows the receiver to become usable.

**Line 195**

```
        and still leave >=1 valid observation.
```

At least one step remains for actual scanning.

**Line 196**

Blank documentation line.

**Line 197**

```
        The jitter matters because a *fixed* dwell width creates a
```

Begins the explanation of random dwell jitter.

**Line 198**

```
        *fixed* parity between "settling" and "valid" steps relative to
```

Fixed dwell can preserve the same settling/observation alignment.

**Line 199**

```
        the sweep's lap length -- and an emitter whose true phase lands
```

If the emitter's phase aligns badly with that cycle, it may never be observed.

**Line 200**

```
        on that settling parity would otherwise be permanently
```

The signal would consistently occur during invalid scans.

**Line 201**

```
        unreachable, no matter how long the run. Randomizing each dwell's
```

Random dwell changes eventually break the alignment.

**Line 202**

```
        length by a small amount breaks that fixed parity."""
```

Ends the method documentation.

**Line 203**

```python
        if len(self._warmup_slots) < k:
```

Checks whether there are enough state slots for all requested receiver channels.

**Line 204**

```python
            self._warmup_slots.extend(
```

Begins adding missing slot dictionaries.

**Line 205**

```python
                {"band": -1, "remaining": 0} for _ in range(k - len(self._warmup_slots))
```

Creates one uninitialized slot for each missing channel.

Each slot starts with:

- Band `-1`
- Zero remaining dwell steps

**Line 206**

```python
            )
```

Closes the generator expression and the `extend()` call.

**Line 207**

```python
        bands = []
```

Creates the output list of selected bands.

**Line 208**

```python
        for slot in self._warmup_slots[:k]:
```

Processes the first `k` channel slots.

**Line 209**

```python
            if slot["remaining"] <= 0:
```

Checks whether the current slot needs a new band.

**Line 210**

```python
                slot["band"] = self._next_warmup_band()
```

Assigns the next shuffled band to the slot.

**Line 211**

```python
                jitter = (random.randint(0, self.warmup_dwell_jitter)
```

Starts calculating a random dwell extension.

**Line 212**

```python
                          if self.warmup_dwell_steps > 1 and self.warmup_dwell_jitter > 0
```

Only generates jitter when:

- Base dwell is greater than one
- Jitter has been enabled

**Line 213**

```python
                          else 0)
```

Uses zero jitter otherwise.

**Line 214**

```python
                slot["remaining"] = self.warmup_dwell_steps + jitter
```

Sets the number of calls for which this slot will remain on the selected band.

**Line 215**

```python
            bands.append(slot["band"])
```

Adds the slot's current band to the output list.

**Line 216**

```python
            slot["remaining"] -= 1
```

Consumes one dwell call.

**Line 217**

```python
        return bands
```

Returns the `k` warm-up bands.

**Line 218**

Blank line.

---

# Band selection: `choose_bands()`

## Lines 219–233

**Line 219**

```python
    def choose_bands(self, k):
```

Defines the main band-selection method.

**Line 220**

```python
        self.t += 1
```

Advances the scheduler's internal time counter.

**Line 221**

```python
        if self.t <= self.warmup_steps:
```

Checks whether the scheduler is still in its warm-up phase.

**Line 222**

```python
            for b in range(self.n_bands):
```

Iterates over all bands during warm-up.

**Line 223**

```python
                self._propagate(b)
```

Advances each band's Markov belief even though the scheduler is using a predetermined warm-up order.

**Line 224**

```python
            return self._warmup_bands(k)
```

Returns the next warm-up bands instead of using learned scores.

**Line 225**

```python
        for b in range(self.n_bands):
```

After warm-up, iterates over every band again.

**Line 226**

```python
            self._propagate(b)
```

Predicts the next belief for every band.

**Line 227**

```python
        scores = [
```

Starts a list comprehension that calculates one score per band.

**Line 228**

```python
            self.priority[b] * self.belief[b]
```

Computes the exploitation component.

A band's estimated activity is multiplied by its priority.

**Line 229**

```python
            + self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
```

Adds the UCB exploration bonus.

The bonus:

- Increases slowly with overall time through `log(t+1)`
- Decreases as `scan_count[b]` increases
- Is scaled by `ucb_c`

**Line 230**

```python
            for b in range(self.n_bands)
```

Completes the list comprehension by calculating a score for every band.

**Line 231**

```python
        ]
```

Closes the score list.

**Line 232**

```python
        order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
```

Sorts band indices by descending score.

The highest-scoring band appears first.

**Line 233**

```python
        return order[:k]
```

Returns the top `k` bands.

If `k` exceeds the number of bands, slicing simply returns all available bands.

---

# Learning from observations: `update()`

## Lines 235–248

**Line 235**

```python
    def update(self, band, observed_on):
```

Defines the feedback method.

It is called once for every validly observed band.

**Line 236**

```python
        prev = self.last_scan_result[band]
```

Retrieves the previous direct observation for the selected band.

**Line 237**

```python
        if prev is not None:
```

Only updates transition statistics when a previous observation exists.

**Line 238**

```python
            if prev:
```

Checks whether that previous observation was ON.

**Line 239**

```python
                self.on_tot[band] += 1
```

Increments the total number of transitions that started from ON.

**Line 240**

```python
                if observed_on:
```

Checks whether the band is ON again now.

**Line 241**

```python
                    self.on_on[band] += 1
```

Records an ON-to-ON transition.

**Line 242**

```python
            else:
```

Handles the case where the previous observation was OFF.

**Line 243**

```python
                self.off_tot[band] += 1
```

Increments the total number of transitions that started from OFF.

**Line 244**

```python
                if observed_on:
```

Checks whether the band turned ON.

**Line 245**

```python
                    self.off_on[band] += 1
```

Records an OFF-to-ON transition.

**Line 246**

```python
        self.last_scan_result[band] = observed_on
```

Stores the latest observation.

**Line 247**

```python
        self.belief[band] = 1.0 if observed_on else 0.0
```

Resets the belief to certainty because the band was directly observed.

**Line 248**

```python
        self.scan_count[band] += 1
```

Increments the valid scan count for this band.

This reduces its future UCB exploration bonus.

**Lines 249–250**

Blank lines before the metrics section.

---

# Simulation and metrics

## Lines 251–253

**Line 251**

```python
# ----------------------------------------------------------------------
```

Visual separator.

**Line 252**

```python
# Simulation loop (multi-channel) + metrics
```

Labels the multi-channel execution section.

**Line 253**

```python
# ----------------------------------------------------------------------
```

Closes the section header.

---

# `RunStats`

## Lines 255–275

**Line 255**

```python
@dataclass
```

Automatically generates the statistics object's constructor.

**Line 256**

```python
class RunStats:
```

Defines the statistics container.

**Line 257**

```python
    total_steps: int = 0
```

Counts completed simulation steps.

**Line 258**

```python
    total_band_transmissions: int = 0   # sum over steps of #bands ON
```

Counts active band-time pairs.

For example, if three bands are ON during one step, this counter increases by three.

**Line 259**

```python
    hits: int = 0                        # #(band,step) pairs scanned AND on
```

Counts selected band-time pairs where the band was ON.

**Line 260**

```python
    intercept_delays: List[int] = field(default_factory=list)
```

Stores delays from the beginning of an ON interval to its first successful scan.

**Line 261**

```python
    step_hit_rewards: List[int] = field(default_factory=list)  # 1 if >=1 hit this step
```

Stores one reward per time step.

The value is `1` if at least one selected band was active.

**Line 262**

```python
    switches: int = 0                    # #times a chosen band differed from last step
```

Counts receiver band switches when switch-cost modeling is enabled.

**Line 263**

```python
    wasted_scans: int = 0                # #scan-steps spent settling after a switch, unable to observe
```

Counts scans that occurred while the receiver was still settling.

**Line 264**

Blank line.

**Line 265**

```python
    def report(self):
```

Defines the summary-report method.

**Line 266**

```python
        interception_ratio = self.hits / max(1, self.total_band_transmissions)
```

Calculates the fraction of active band-time pairs that were intercepted.

The denominator is protected from zero.

**Line 267**

```python
        avg_reward = statistics.mean(self.step_hit_rewards) if self.step_hit_rewards else 0.0
```

Calculates the mean per-step reward.

**Line 268**

```python
        avg_delay = statistics.mean(self.intercept_delays) if self.intercept_delays else None
```

Calculates the mean interception delay, or `None` if no delays exist.

**Line 269**

```python
        return {
```

Starts the report dictionary.

**Line 270**

```python
            "interception_ratio": round(interception_ratio, 3),
```

Stores the interception ratio rounded to three decimals.

**Line 271**

```python
            "avg_reward_per_step": round(avg_reward, 3),
```

Stores the average reward rounded to three decimals.

**Line 272**

```python
            "avg_intercept_delay": round(avg_delay, 2) if avg_delay is not None else "n/a",
```

Stores the average delay rounded to two decimals, or `"n/a"` if unavailable.

**Line 273**

```python
            "switches": self.switches,
```

Adds the number of receiver switches.

**Line 274**

```python
            "wasted_scans": self.wasted_scans,
```

Adds the count of settling-period scans.

**Line 275**

```python
        }
```

Closes the report dictionary.

**Lines 276–277**

Blank lines before `run_episode()`.

---

# `run_episode()`

## Function signature and documentation: lines 278–299

**Line 278**

```python
def run_episode(env_factory, scheduler: Scheduler, n_steps: int, n_bands: int, k_channels: int = 1,
```

Defines the episode runner.

Arguments:

- `env_factory`
- `scheduler`
- `n_steps`
- `n_bands`
- `k_channels`

**Line 279**

```python
                 switch_cost_steps: int = 0) -> RunStats:
```

Adds the optional receiver switching cost and declares that the function returns `RunStats`.

**Line 280**

```
    """switch_cost_steps models real receiver hardware needing time to
```

Starts the function documentation.

**Line 281**

```
    re-tune (LO/filter settling) when the scheduler moves a channel to a
```

Explains the physical meaning of switch cost.

`LO` means local oscillator.

**Line 282**

```
    band it wasn't already parked on. Default 0 preserves every existing
```

A zero switch cost preserves previous behavior.

**Line 283**

```
    result exactly (this is purely opt-in) -- set > 0 to see how the
```

Switch-cost modeling is optional.

**Line 284**

```
    comparisons change once switching isn't free.
```

Explains why the parameter is useful.

**Line 285**

Blank documentation line.

**Line 286**

```
    When a channel switches to a band it wasn't scanning last step, that
```

Defines when settling begins.

**Line 287**

```
    band is unobservable for the next `switch_cost_steps` steps: no
```

The receiver cannot produce a valid observation during settling.

**Line 288**

```
    scheduler.update() call happens (its belief model isn't corrupted
```

The scheduler is not given fake OFF/ON data.

**Line 289**

```
    with a fabricated observation -- it just gets no information, same
```

The scheduler simply receives no update during settling.

**Line 290**

```
    as a real receiver that isn't listening yet), and no hit/interception
```

No successful intercept is credited during those steps.

**Line 291**

```
    credit is given even if the band was genuinely transmitting during
```

A transmission during settling remains undetected by design.

**Line 292**

```
    that window. Time still advances and the channel is still tied up on
```

The simulation clock continues, and the receiver remains committed to that band.

**Line 293**

```
    that band (it can't scan elsewhere while settling), so this is a
```

The settling period cannot be used to scan another band.

**Line 294**

```
    real, direct cost -- not merely a delayed observation.
```

Clarifies that settling consumes actual receiver capacity.

**Line 295**

Blank documentation line.

**Line 296**

```
    A revisited band (scanned before, then left, then scanned again)
```

Explains the behavior when returning to a previously visited band.

**Line 297**

```
    pays the full switch cost again, matching real hardware: the LO was
```

The receiver must retune again.

**Line 298**

```
    retuned elsewhere in between, so there's nothing to still be "warm."
```

A previously scanned band does not remain settled after leaving it.

**Line 299**

```python
    """
```

Ends the function documentation.

---

## Episode initialization: lines 300–305

**Line 300**

```python
    env = env_factory()
```

Creates a fresh environment.

**Line 301**

```python
    stats = RunStats()
```

Creates an empty statistics object.

**Line 302**

```python
    on_since = [None] * n_bands
```

Tracks the start time of the current ON interval for every band.

**Line 303**

```python
    credited = [False] * n_bands
```

Tracks whether the current interval has already been credited with an interception delay.

**Line 304**

```python
    prev_bands = set()
```

Stores the set of bands selected during the previous simulation step.

It is used to detect band switches.

**Line 305**

```python
    settling_remaining: Dict[int, int] = {}
```

Creates a dictionary mapping bands to remaining settling steps.

---

## Main loop: lines 307–319

**Line 307**

```python
    for t in range(n_steps):
```

Begins the time-step loop.

**Line 308**

```python
        status: Dict[int, bool] = env.step()
```

Advances the environment and obtains the ON/OFF state of every band.

**Line 309**

Blank line.

**Line 310**

```python
        for b in range(n_bands):
```

Iterates over all bands to update transmission-interval state.

**Line 311**

```python
            if status[b]:
```

Checks whether band `b` is active.

**Line 312**

```python
                stats.total_band_transmissions += 1
```

Counts this active band-time pair.

**Line 313**

```python
                if on_since[b] is None:
```

Checks whether this is the beginning of a new ON interval.

**Line 314**

```python
                    on_since[b] = t
```

Records the current time as the interval's start.

**Line 315**

```python
                    credited[b] = False
```

Allows the first successful scan of the interval to receive credit.

**Line 316**

```python
            else:
```

Handles an inactive band.

**Line 317**

```python
                on_since[b] = None
```

Clears the interval start.

**Line 318**

```python
                credited[b] = False
```

Resets the credit marker for the next interval.

**Line 319**

Blank line.

---

## Selecting and scanning bands: lines 320–340

**Line 320**

```python
        bands = scheduler.choose_bands(k_channels)
```

Asks the scheduler to select up to `k_channels` bands.

**Line 321**

```python
        step_hit = False
```

Initializes a flag indicating whether any selected band is active during this step.

**Line 322**

```python
        for band in bands:
```

Processes each selected band independently.

**Line 323**

```python
            if switch_cost_steps > 0:
```

Enables switch-cost handling only when the configured cost is positive.

**Line 324**

```python
                if band not in prev_bands:
```

Checks whether this band was not selected during the previous step.

That means the receiver has switched to it.

**Line 325**

```python
                    settling_remaining[band] = switch_cost_steps
```

Starts a new settling period for this band.

**Line 326**

```python
                    stats.switches += 1
```

Counts the switch.

**Line 327**

```python
                if settling_remaining.get(band, 0) > 0:
```

Checks whether the band still has settling time remaining.

If the band is not in the dictionary, `.get()` returns zero.

**Line 328**

```python
                    settling_remaining[band] -= 1
```

Consumes one settling step.

**Line 329**

```python
                    stats.wasted_scans += 1
```

Counts this scan as wasted because it cannot produce a valid observation.

**Line 330**

```python
                    continue  # tied up settling -- no valid observation this step
```

Skips the rest of the loop for this band.

Consequently:

- No scheduler update occurs
- No hit is counted
- No delay is recorded

**Line 331**

Blank line after the settling branch.

**Line 332**

```python
            observed_on = status[band]
```

Reads the current true state of the selected band.

If settling was active, execution would have continued earlier and never reached this line.

**Line 333**

```python
            scheduler.update(band, observed_on)
```

Feeds the observation into the scheduler.

**Line 334**

```python
            if observed_on:
```

Checks whether this selected band is active.

**Line 335**

```python
                step_hit = True
```

Marks the current time step as successful.

**Line 336**

```python
                stats.hits += 1
```

Counts the successful band-time interception.

**Line 337**

```python
                if on_since[band] is not None and not credited[band]:
```

Checks whether this is the first successful scan during the current ON interval.

**Line 338**

```python
                    stats.intercept_delays.append(t - on_since[band])
```

Records how long the scheduler waited after the interval began before detecting it.

**Line 339**

```python
                    credited[band] = True
```

Prevents additional detections during the same interval from creating duplicate delay values.

**Line 340**

Blank line.

---

## Completing each step: lines 341–345

**Line 341**

```python
        stats.step_hit_rewards.append(1 if step_hit else 0)
```

Records one reward for the whole simulation step.

The reward is `1` if any selected channel had a hit.

**Line 342**

```python
        stats.total_steps += 1
```

Counts the completed time step.

**Line 343**

```python
        prev_bands = set(bands)
```

Stores the currently selected bands for switch detection during the next iteration.

**Line 344**

Blank line.

**Line 345**

```python
    return stats
```

Returns the completed episode statistics.

**Lines 346–347**

Blank lines before `main()`.

---

# `main()`

## Lines 348–377

**Line 348**

```python
def main():
```

Defines the script's executable entry point.

**Line 349**

```python
    N_BANDS = 36
```

Sets the experiment to use 36 frequency bands.

**Line 350**

```python
    n_steps = 4000
```

Sets each episode length to 4,000 steps.

**Line 351**

```python
    scenario = make_scenario(N_BANDS)
```

Creates the standard mixed-emitter environment factory.

**Line 352**

Blank line.

**Line 353**

```python
    print(f"Scenario: {N_BANDS} bands, {n_steps} steps, 4 concurrent emitters "
```

Begins printing the experiment description.

**Line 354**

```python
          f"(2 Markov comms, 1 periodic beacon, 1 frequency-agile threat)\n")
```

Completes the formatted description and prints a newline.

**Line 355**

Blank line.

**Line 356**

```python
    for k in (1, 2, 3):
```

Runs comparisons for three receiver configurations:

- One scanned band per step
- Two scanned bands per step
- Three scanned bands per step

**Line 357**

```python
        random.seed(7)
```

Resets the random-number generator for each `k` value.

This makes each comparison reproducible.

**Line 358**

```python
        print(f"--- k_channels = {k} (receiver scans {k} band(s) per step) ---")
```

Prints a heading for the current channel count.

**Line 359**

```python
        schedulers = {
```

Begins constructing the scheduler dictionary.

**Line 360**

```python
            "RoundRobin (open-loop baseline)": RoundRobinScheduler(N_BANDS),
```

Creates the multi-channel round-robin scheduler.

**Line 361**

```python
            "Random (naive baseline)": RandomScheduler(N_BANDS),
```

Creates the random scheduler.

**Line 362**

```python
            "BeliefUCB (learned, closed-loop)": BeliefUCBScheduler(N_BANDS, ucb_c=0.5),
```

Creates the UCB-based learned scheduler with exploration coefficient `0.5`.

**Line 363**

```python
        }
```

Closes the scheduler dictionary.

**Line 364**

```python
        header = (f"{'Scheduler':40s} | {'Interception %':>15s} | "
```

Begins constructing the output table header.

**Line 365**

```python
                  f"{'Avg Reward/step':>16s} | {'Avg Intercept Delay':>20s}")
```

Completes the header string.

**Line 366**

```python
        print(header)
```

Prints the table header.

**Line 367**

```python
        print("-" * len(header))
```

Prints a matching separator line.

**Line 368**

```python
        for name, sched in schedulers.items():
```

Iterates over each scheduler.

**Line 369**

```python
            stats = run_episode(scenario, sched, n_steps, N_BANDS, k_channels=k)
```

Runs one episode with the current scheduler and channel count.

The default switch cost remains zero.

**Line 370**

```python
            r = stats.report()
```

Converts raw statistics into a report dictionary.

**Line 371**

```python
            print(f"{name:40s} | {r['interception_ratio']*100:14.1f}% | "
```

Prints the scheduler name and interception percentage.

**Line 372**

```python
                  f"{r['avg_reward_per_step']:16.3f} | {str(r['avg_intercept_delay']):>20s}")
```

Prints average reward and average interception delay.

**Line 373**

```python
        print()
```

Adds a blank line between channel-count sections.

**Lines 374–375**

Blank lines before the module guard.

**Line 376**

```python
if __name__ == "__main__":
```

Checks whether the file is being executed directly.

**Line 377**

```python
    main()
```

Runs the comparison experiment when executed directly.

---

# What changed from `scan_scheduler_prototype.py`

This file introduces three major changes:

1. **Multiple bands per step**

   The old interface was:

   ```python
   choose_band()
   ```

   The new interface is:

   ```python
   choose_bands(k)
   ```
2. **UCB exploration**

   Instead of exploring randomly with a fixed epsilon, the scheduler scores each band using:

   ```
   priority × belief + exploration bonus
   ```
3. **Switch-cost-aware warm-up**

   The scheduler can dwell on a band long enough for receiver settling, and jitter can be added to avoid periodic aliasing.




The next file is much larger—`scan_scheduler_v3_pri.py` has 919 lines—so I’ll explain it in three parts to keep it readable.

This is **Part 1 of 3: lines 1–320**. I will leave its checklist box unchecked until all three parts are complete.

# `scan_scheduler_v3_pri.py` — Part 1

## Module documentation and imports

### Lines 1–22

**Line 1**

```python
"""
```

Starts the module-level documentation string.

**Line 2**

```
scan_scheduler_v3_pri.py
```

Names the module.

**Line 3**

```
==========================
```

Visual separator for the documentation.

**Line 4**

```
Adds an explicit Pulse Repetition Interval (PRI) predictor on top of the
```

Explains the main purpose: add PRI prediction to the previous scheduler.

**Line 5**

```
BeliefUCBScheduler from scan_scheduler_v2.py.
```

States that `PRIAwareScheduler` inherits from `BeliefUCBScheduler`.

**Line 6**

Blank documentation line.

**Line 7**

```
Why: a first-order Markov model only knows "this band was recently
```

Explains the limitation of the Markov-only model.

**Line 8**

```
active, so it's probably still active" -- it has no notion of a
```

A Markov model tracks persistence but not a repeating schedule.

**Line 9**

```
repeating cycle, so it's a poor fit for fixed-PRI radars and periodic
```

Explains why Markov behavior is insufficient for periodic emitters.

**Line 10**

```
beacons (exactly the emitter types the real Turing Synthetic Radar
```

Connects the motivation to the target dataset.

**Line 11**

```
Dataset's fixed-frequency emitters are: near-constant-PRI). This
```

Notes that many fixed-frequency emitters have nearly constant PRI.

**Line 12**

```
scheduler tracks the actual gaps between confirmed hits on a band,
```

Describes the data used for PRI estimation.

**Line 13**

```
estimates the period and its jitter, and predicts the PHASE of the next
```

The scheduler estimates both timing regularity and the next expected phase.

**Line 14**

```
expected occurrence -- catching periodic emitters right when they're
```

Explains the intended operational benefit.

**Line 15**

```
due, not just "recently seen so probably still there."
```

Contrasts prediction with simple recency-based exploitation.

**Line 16**

Blank documentation line.

**Line 17**

```
For bursty/agile bands (no stable period), the gap variance stays high,
```

Explains how the scheduler behaves for non-periodic signals.

**Line 18**

```
confidence drops to ~0, and the scheduler falls back to the plain
```

Unreliable periodicity receives little or no influence.

**Line 19**

```
belief+UCB score -- so this is a strict upgrade, not a trade-off.
```

The scheduler should behave like the v2 scheduler when periodicity is not useful.

**Line 20**

Blank documentation line.

**Line 21**

```
Run:  python3 scan_scheduler_v3_pri.py
```

Documents the direct execution command.

**Line 22**

```python
"""
```

Ends the module documentation string.

### Lines 23–38

**Line 23**

Blank line separating documentation from imports.

**Line 24**

```python
import math
```

Imports mathematical functions such as `sqrt`, `log`, `gcd`, and `exp`.

**Line 25**

```python
import random
```

Provides random-number generation for experiment seeding and scenario behavior.

**Line 26**

```python
import statistics
```

Provides statistical functions, including median calculations.

**Line 27**

```python
from collections import Counter
```

Imports `Counter`, used to find the most common pairwise time difference.

**Line 28**

```python
from functools import reduce
```

Imports `reduce`, used to compute the GCD across many time differences.

**Line 29**

```python
from typing import List, Optional
```

Imports type annotation helpers.

**Line 30**

Blank line.

**Line 31**

```python
from scan_scheduler_v2 import (
```

Starts a multi-line import from the v2 scheduler module.

**Line 32**

```python
    Scheduler, RunStats, run_episode, RoundRobinScheduler, RandomScheduler,
```

Imports:

- Base scheduler interface
- Statistics container
- Episode runner
- Round-robin scheduler
- Random scheduler

**Line 33**

```python
    BeliefUCBScheduler,
```

Imports the v2 learning scheduler that this file extends.

**Line 34**

```python
)
```

Closes the import list.

**Line 35**

```python
from scan_scheduler_prototype import (
```

Starts another multi-line import.

**Line 36**

```python
    Emitter, MarkovEmitter, AgileEmitter, Environment, make_scenario
```

Imports the base emitter, synthetic emitter types, environment, and standard scenario.

**Line 37**

```python
)
```

Closes the import list.

**Lines 38–39**

Blank lines before the sparse-emitter definition.

---

# `SparsePeriodicEmitter`

## Lines 40–58

**Line 40**

```python
class SparsePeriodicEmitter(Emitter):
```

Defines a new emitter type that produces one brief pulse every PRI interval.

**Line 41**

```python
    """
```

Starts the class documentation.

**Line 42**

```
    A single, brief pulse every `pri` steps on a fixed band -- much closer
```

Explains that the emitter transmits only at periodic instants.

**Line 43**

```
    to a real fixed-PRI radar (short pulse width, long dead time between
```

Relates the model to a radar with a short pulse and long silence.

**Line 44**

```
    pulses) than the multi-step "beacon" in the base scenario. This is
```

Contrasts this emitter with the always-ON multi-step beacon.

**Line 45**

```
    exactly the case a first-order Markov model struggles with: the band
```

Explains why the v2 Markov model performs poorly here.

**Line 46**

```
    is OFF almost all the time, so "recently on -> probably still on"
```

A sparse radar is mostly silent, so recency is not useful.

**Line 47**

```
    gives almost no signal between pulses, whereas a PRI estimate tells
```

The periodic model can identify when the next pulse is due.

**Line 48**

```
    you precisely when the next one is due.
```

Completes the motivation.

**Line 49**

```python
    """
```

Ends the class documentation.

**Line 50**

```python
    def __init__(self, name, band, pri):
```

Defines the constructor.

Arguments:

- `name`: emitter name
- `band`: fixed band
- `pri`: pulse repetition interval in simulation steps

**Line 51**

```python
        super().__init__(name)
```

Initializes the inherited emitter fields.

**Line 52**

```python
        self.band = band
```

Stores the fixed operating band.

**Line 53**

```python
        self.pri = pri
```

Stores the pulse repetition interval.

**Line 54**

Blank line.

**Line 55**

```python
    def step(self, t):
```

Defines the emitter's behavior for one time step.

**Line 56**

```python
        self.on = (t % self.pri == 0)
```

Turns the emitter ON exactly when the time is divisible by the PRI.

For `pri=12`, pulses occur at:

```
t = 0, 12, 24, 36, ...
```

**Line 57**

```python
        return self.band, self.on
```

Returns the fixed band and current ON/OFF state.

**Line 58**

Blank line.

---

# `make_sparse_scenario()`

## Lines 60–71

**Line 60**

```python
def make_sparse_scenario(n_bands=36):
```

Defines a scenario factory for testing sparse fixed-PRI radar behavior.

**Line 61**

```python
    """Same comm + agile mix as make_scenario, but the periodic source is
```

Explains that the scenario retains the communications and agile emitters.

**Line 62**

```python
    a sparse single-pulse-per-cycle radar (period 12) on one fixed band."""
```

States that the periodic emitter is now a single pulse every 12 steps.

**Line 63**

```python
    def factory():
```

Defines an inner function that creates a fresh environment.

**Line 64**

```python
        emitters = [
```

Starts the emitter list.

**Line 65**

```python
            MarkovEmitter("comm-1", band=1, p_on_given_off=0.05, p_on_given_on=0.9),
```

Creates a persistent bursty communications emitter on band 1.

**Line 66**

```python
            MarkovEmitter("comm-2", band=4, p_on_given_off=0.10, p_on_given_on=0.7),
```

Creates a second Markov communications emitter on band 4.

**Line 67**

```python
            SparsePeriodicEmitter("fixed-pri-radar", band=5, pri=12),
```

Creates the sparse radar on band 5 with a 12-step period.

**Line 68**

```python
            AgileEmitter("agile-threat", bands=[0, 3, 6, 7], dwell=2, duty=0.5),
```

Creates a randomly hopping threat on four possible bands.

**Line 69**

```python
        ]
```

Closes the emitter list.

**Line 70**

```python
        return Environment(n_bands=n_bands, emitters=emitters)
```

Creates and returns the environment.

**Line 71**

```python
    return factory
```

Returns the environment factory.

**Lines 72–73**

Blank lines before the PRI-aware scheduler.

---

# `PRIAwareScheduler`

## Class documentation: lines 74–99

**Line 74**

```python
class PRIAwareScheduler(BeliefUCBScheduler):
```

Defines the PRI-aware scheduler as a subclass of `BeliefUCBScheduler`.

It inherits:

- Markov belief tracking
- UCB exploration
- Priorities
- Warm-up logic
- Multi-channel selection structure

**Line 75**

```python
    """
```

Starts the class documentation.

**Line 76**

```
    Per band, keeps the last `history_len` confirmed-hit step indices,
```

Explains that each band has a bounded history of hit times.

**Line 77**

```
    estimates PRI = median(gaps) and jitter = stdev(gaps), and derives a
```

Describes the original conceptual model: estimate period from hit gaps and timing variation from their spread.

The implementation later became more sophisticated than a simple median/stdev calculation.

**Line 78**

```
    periodicity confidence (1 - coefficient_of_variation, clipped to
```

Explains the general confidence idea: lower relative error means higher confidence.

**Line 79**

```
    [0,1], zeroed below a CoV cutoff so bursty/agile bands never earn
```

Confidence is bounded and should fall for irregular signals.

**Line 80**

```
    confidence). The scan score blends the Markov belief with a Gaussian
```

The scheduler combines Markov belief with a probability-shaped periodicity score.

**Line 81**

```
    "phase bump" centred on the nearest predicted occurrence
```

The periodicity score is highest near the predicted next pulse.

**Line 82**

```
    ((t - last_hit) mod PRI), weighted by that confidence, plus the same
```

The phase is computed relative to the most recent hit and the estimated PRI.

**Line 83**

```
    UCB exploration bonus as the parent class.
```

UCB exploration remains part of the final score.

**Line 84**

Blank documentation line.

**Line 85**

```
    IMPORTANT caveat this class had to learn the hard way (found via
```

Introduces a discovered failure mode.

**Line 86**

```
    diagnose_beacon_regression.py): the phase bump's width (jitter) is
```

The issue was investigated in the beacon regression diagnostic.

**Line 87**

```
    fit from residual timing error, which is near-zero for a truly
```

A highly regular emitter produces very small timing residuals.

**Line 88**

```
    periodic emitter -- but that only means the ONSET time is precise,
```

Low onset timing error does not mean the signal lasts only one step.

**Line 89**

```
    not that the emitter is a single-instant event. A multi-step burst
```

A multi-step burst may have precise starts but extended duration.

**Line 90**

```
    (e.g. a beacon that stays ON for 4 consecutive steps every cycle)
```

Provides an example of a four-step burst.

**Line 91**

```
    still has a near-zero *onset* jitter, which used to collapse the
```

The old implementation made the periodicity score too narrow.

**Line 92**

```
    bump to a single-point spike and made the scheduler abandon the
```

The scheduler would leave the band immediately after the first observed step.

**Line 93**

```
    burst after its first step -- actively WORSE than plain Markov
```

This could perform worse than the simpler Markov model.

**Line 94**

```
    belief, which stays elevated for the whole burst via learned
```

The Markov model naturally maintains high probability during a persistent ON run.

**Line 95**

```
    P(on|on). `max_run_ever` (persistent burst-width estimate) widens
```

The fix stores the longest observed consecutive hit run.

**Line 96**

```
    the jitter floor so the bump plateaus across the observed burst
```

The periodicity score is widened to cover the full burst.

**Line 97**

```
    length instead of collapsing to a point, without affecting emitters
```

Single-pulse emitters are intended to remain unaffected.

**Line 98**

```
    that really are single-instant (max_run_ever stays 1 for those).
```

For single-step pulses, the stored run length remains one.

**Line 99**

```python
    """
```

Ends the class documentation.

---

## Constructor signature: lines 100–108

**Line 100**

```python
    def __init__(self, n_bands, ucb_c: float = 0.5, history_len: int = 30,
```

Defines the constructor.

Arguments:

- `n_bands`: number of frequency bands
- `ucb_c`: exploration strength
- `history_len`: maximum hit history retained per band

**Line 101**

```python
                 min_confidence: float = 0.75, periodicity_weight: float = 1.5,
```

Adds:

- Minimum confidence required for a PRI lock
- Weight applied to the periodicity score

**Line 102**

```python
                 warmup_steps: int = 0, priority: Optional[List[float]] = None,
```

Adds inherited warm-up and band-priority controls.

**Line 103**

```python
                 confidence_scale: float = 0.25, switch_lead_steps: int = 0,
```

Adds:

- `confidence_scale`: controls how much fitting error is tolerated
- `switch_lead_steps`: starts favoring a periodic band before the predicted pulse

**Line 104**

```python
                 min_cycles: int = 4, max_blend_confidence: float = 1.0,
```

Adds:

- `min_cycles`: minimum number of distinct cycles needed for a lock
- `max_blend_confidence`: maximum confidence used in score blending

**Line 105**

```python
                 warmup_dwell_steps: int = 1, warmup_dwell_jitter: int = 1):
```

Passes through the v2 warm-up dwell parameters.

---

## Constructor initialization: lines 106–111

**Line 106**

```python
        super().__init__(n_bands, ucb_c=ucb_c, warmup_steps=warmup_steps, priority=priority,
```

Initializes the parent `BeliefUCBScheduler` with the main inherited parameters.

**Line 107**

```python
                          warmup_dwell_steps=warmup_dwell_steps,
```

Passes the warm-up dwell duration to the parent.

**Line 108**

```python
                          warmup_dwell_jitter=warmup_dwell_jitter)
```

Passes the warm-up jitter setting and closes the parent constructor call.

**Line 109**

```python
        self.history_len = history_len
```

Stores the maximum number of recent hits retained for ordinary PRI fitting.

**Line 110**

```python
        self.min_confidence = min_confidence
```

Stores the minimum confidence needed to accept a PRI estimate.

**Line 111**

```python
        self.periodicity_weight = periodicity_weight
```

Stores the multiplier applied to the periodicity score.

---

## Confidence configuration: lines 112–122

**Line 112**

```python
        # Denominator scale in the confidence formula
```

Introduces comments describing confidence calculation.

**Line 113**

```python
        # (confidence = 1 - rmse / (confidence_scale * refined_pri)). Larger
```

Defines the confidence formula:

```
confidence = 1 - RMSE / (confidence_scale × estimated PRI)
```

**Line 114**

```python
        # = more forgiving (reaches high confidence with a looser relative
```

A larger scale tolerates more error.

**Line 115**

```python
        # fit); smaller = requires a tighter fit before trusting a
```

A smaller scale makes the lock stricter.

**Line 116**

```python
        # candidate. Tunable because a fixed 0.25 turned out to be eager
```

Explains why the parameter is configurable.

**Line 117**

```python
        # enough to occasionally lock onto a spurious candidate on a
```

The default can sometimes accept false periodicity.

**Line 118**

```python
        # non-periodic band (found via settle_fix_interaction.py: a -0.3pp
```

References a measured performance cost.

**Line 119**

```python
        # beacon-scenario cost from the harmonic-selection fix's added
```

The improved candidate search made locking more eager.

**Line 120**

```python
        # eagerness) -- see tune_confidence_threshold.py for the sweep
```

Points to the script that tests different confidence scales.

**Line 121**

```python
        # that selected this value.
```

Completes the explanation.

**Line 122**

```python
        self.confidence_scale = confidence_scale
```

Stores the confidence scaling factor.

---

## Minimum cycle requirement: lines 123–147

**Line 123**

```python
        # Minimum number of DISTINCT observed cycles of the candidate
```

Introduces a guard against fitting too few cycles.

**Line 124**

```python
        # period before a lock is allowed.
```

A low-error fit is not trusted unless it covers enough independent cycles.

**Line 125**

Blank comment line.

**Line 126**

```python
        # Found on real TSRD data (Validation/config_169.h5, band 1),
```

Documents the origin of this guard.

**Line 127**

```python
        # never on the synthetic stand-in. The stand-in's emitters pulse
```

The issue primarily appears in real recordings.

**Line 128**

```python
        # uniformly, so `history_len` (30) hits = ~30 observed cycles.
```

In the synthetic case, each hit is roughly a separate cycle.

**Line 129**

```python
        # A real emitter's pulses arrive in dense BURSTS -- both the
```

Real data can contain clusters of pulses.

**Line 130**

```python
        # transmitter and the recording receiver are scanning, so the
```

The transmitter and receiver scanning patterns affect observations.

**Line 131**

```python
        # band is only live during their beam overlap. There, 30 hits =
```

Thirty hits may not represent thirty independent cycles.

**Line 132**

```python
        # two tight clusters of 15, i.e. only TWO independent looks at
```

Two dense clusters could contain only two actual periods.

**Line 133**

```python
        # the period. _refine_pri then fits a straight line through what
```

The least-squares fit could treat those clusters as a clean progression.

**Line 134**

```python
        # are effectively two points, which any period equal to the
```

Many incorrect periods could fit two points perfectly.

**Line 135**

```python
        # cluster separation fits perfectly.
```

Completes the false-lock explanation.

**Line 136**

Blank comment line.

**Line 137**

```python
        # The confidence formula cannot catch this on its own because it
```

Explains why RMSE-based confidence is insufficient.

**Line 138**

```python
        # is scale-RELATIVE: confidence = 1 - rmse / (confidence_scale *
```

The error is normalized relative to the estimated period.

**Line 139**

```python
        # period), so a larger period makes the same absolute residual
```

A large incorrect period can make the same absolute error appear small.

**Line 140**

```python
        # look better. The observed failure was a reported period of
```

Introduces an example of a false lock.

**Line 141**

```python
        # 6354 scan-steps (6.35 s) at confidence 0.98 on a band whose
```

The system reported an extremely long period with very high confidence.

**Line 142**

```python
        # true period is 700 us -- a period longer than most of the
```

The estimate was inconsistent with the true signal period.

**Line 143**

```python
        # recording, asserted with near-maximum confidence.
```

This shows why an independent cycle-count guard is necessary.

**Line 144**

Blank comment line.

**Line 145**

```python
        # The existing 8-hit threshold does not help: it counts hits,
```

The existing minimum hit count is insufficient.

**Line 146**

```python
        # not cycles. This counts cycles.
```

`min_cycles` specifically counts distinct estimated cycles.

**Line 147**

```python
        self.min_cycles = min_cycles
```

Stores the minimum required cycle count.

---

## Blend-confidence cap: lines 148–187

**Line 148**

```python
        # Cap on the CONFIDENCE VALUE USED FOR BLENDING (never on the
```

Introduces the distinction between lock confidence and blend confidence.

**Line 149**

```python
        # lock decision itself -- confidence still needs to clear
```

A cap does not make an invalid lock acceptable.

**Line 150**

```python
        # min_confidence to lock at all; this only limits how much
```

The cap only reduces the weight given to periodicity in the final score.

**Line 151**

```python
        # weight a locked band's belief term loses). At confidence=1.0
```

At full confidence, the original blend gives no weight to Markov belief.

**Line 152**

```python
        # the blend formula below gives belief ZERO weight, so the
```

The periodicity model fully controls exploitation when confidence equals one.

**Line 153**

```python
        # scheduler trusts the periodicity model completely.
```

Completes the explanation.

**Line 154**

Blank comment line.

**Line 155**

```python
        # Found necessary on real TSRD data (config_169.h5, band 1,
```

Documents the real-data motivation for this parameter.

**Line 156**

```python
        # the AEGIS staggered emitter isolated to a window where it is
```

Describes the specific emitter and evaluation window.

**Line 157**

```python
        # the ONLY live band): the periodicity model is exactly right
```

The period estimate itself was correct.

**Line 158**

```python
        # (confidence 1.00, period matches the file's declared PRIs to
```

The model matched the declared PRI very closely.

**Line 159**

```python
        # the microsecond) but its Gaussian bumps are NARROW --
```

The problem was the shape of the score, not the period estimate.

**Line 160**

```python
        # jitter_estimate floors at 0.5 steps for a genuinely single-
```

The score's minimum width was only half a step.

**Line 161**

```python
        # instant occurrence -- so between the 5 predicted spikes each
```

A staggered pattern created several narrow predicted spikes per cycle.

**Line 162**

```python
        # cycle, periodicity_score is near zero, and with belief's
```

Between spikes, the periodicity score became almost zero.

**Line 163**

```python
        # weight zeroed out by full confidence, nothing tells the
```

The Markov fallback was unavailable because it had no blend weight.

**Line 164**

```python
        # scheduler it's fine to just KEEP dwelling on this band during
```

The scheduler abandoned the band during expected silent intervals.

**Line 165**

```python
        # its own silence, since every alternative band is equally or
```

This was harmful when there were no better alternatives.

**Line 166**

```python
        # more silent (dead). Interception collapsed to 44.3% against
```

Documents the measured performance degradation.

**Line 167**

```python
        # BeliefUCB's simpler "recently on -> still on" momentum
```

The Markov scheduler performed better in that case.

**Line 168**

```python
        # hitting 93.7% on the identical window -- not a detection
```

The difference was not due to detection quality.

**Line 169**

```python
        # failure (confirmed: the PRI itself is exactly right), a
```

The PRI predictor was correct.

**Line 170**

```python
        # scoring-policy one: a perfectly-predictable-but-narrow signal
```

The problem was how predicted activity was scored.

**Line 171**

```python
        # can score WORSE than a sloppier always-camp heuristic when
```

A less precise model can be better if it keeps the receiver on the band.

**Line 172**

```python
        # there is nothing better to switch to. (This is precisely the
```

Explains when the issue is most severe.

**Line 173**

```python
        # gap a proper Whittle-index policy -- still on this project's
```

Points toward the theoretical scheduler.

**Line 174**

```python
        # open list -- would close correctly; capping blend confidence
```

The cap is only a partial heuristic.

**Line 175**

```python
        # is a cheap partial mitigation, not that.)
```

Clarifies that the cap is not a full solution.

**Line 176**

Blank comment line.

**Line 177**

```python
        # This is a real Pareto trade-off, not a free fix, so the
```

Explains that improving one scenario may harm another.

**Line 178**

```python
        # default (1.0) changes NOTHING and every existing result stays
```

The default preserves existing behavior.

**Line 179**

```python
        # exact: measured directly, a cap tight enough to meaningfully
```

A useful cap has measurable side effects.

**Line 180**

```python
        # help the above case (<=0.8) already costs the sparse-radar
```

Lower caps reduce sparse-radar performance.

**Line 181**

```python
        # headline (100.0%/79.4% -> 96.6%/64.3% at 0.8), and even 0.9 --
```

Provides measured example values.

**Line 182**

```python
        # which preserves that headline exactly -- gives zero
```

A cap of 0.9 did not improve the problematic real-data case.

**Line 183**

```python
        # improvement on the band-1 case (still 44.3%). There is no
```

No single cap solved both use cases.

**Line 184**

```python
        # value that helps one without costing the other; pick this per
```

The appropriate value depends on deployment priorities.

**Line 185**

```python
        # deployment based on whether isolated, low-duty periodic
```

One possible priority is isolated low-duty signals.

**Line 186**

```python
        # emitters or busy multi-emitter environments matter more.
```

The alternative is favoring crowded multi-emitter environments.

**Line 187**

```python
        self.max_blend_confidence = max_blend_confidence
```

Stores the cap used later in `choose_bands()`.

---

## Switch lead and per-band state: lines 188–247

**Line 188**

```python
        # How many steps early to start favoring a periodic band, so that
```

Introduces the switch-lead parameter.

**Line 189**

```python
        # if the receiver needs real settling time after a switch
```

This matters when hardware switching is not instantaneous.

**Line 190**

```python
        # (switch_cost_steps in run_episode), it finishes settling right
```

The desired behavior is to start moving before the signal arrives.

**Line 191**

```python
        # as the predicted pulse arrives instead of missing it entirely.
```

The receiver should become usable at the predicted pulse time.

**Line 192**

```python
        # Found necessary by switch_cost_comparison.py: with this at 0,
```

Documents the experimental origin of the parameter.

**Line 193**

```python
        # the scheduler predicts the pulse's exact arrival time and jumps
```

With no lead, the scheduler switches exactly at the predicted time.

**Line 194**

```python
        # to the band exactly then -- which means it's ALWAYS a fresh
```

That switch may always be a new retune.

**Line 195**

```python
        # switch (confirmed: 267 of 285 sparse-radar band-5 visits were
```

Provides a measured example.

**Line 196**

```python
        # fresh switches), so it's still settling precisely when the
```

The receiver loses the pulse while settling.

**Line 197**

```python
        # pulse hits. Set this equal to your deployment's actual
```

Recommends configuring the lead equal to hardware switching cost.

**Line 198**

```python
        # switch_cost_steps to fix that. Default 0 preserves every
```

The default remains backward-compatible.

**Line 199**

```python
        # existing result exactly (no lead = arrive exactly on time,
```

Describes the no-lead behavior.

**Line 200**

```python
        # the original -- and for switch_cost_steps=0 in the simulator,
```

It is correct when switching is free.

**Line 201**

```python
        # correct -- behavior).
```

Completes the explanation.

**Line 202**

```python
        self.switch_lead_steps = switch_lead_steps
```

Stores the early-favoring window.

**Line 203**

```python
        self.hit_times: List[List[int]] = [[] for _ in range(n_bands)]
```

Creates a separate hit-time list for each band.

**Line 204**

```python
        self.pri_estimate: List[Optional[float]] = [None] * n_bands
```

Stores the estimated PRI for each band.

`None` means no valid estimate exists.

**Line 205**

```python
        self.jitter_estimate: List[float] = [1.0] * n_bands
```

Stores the timing-width parameter used by the Gaussian periodicity score.

It starts at `1.0`.

**Line 206**

```python
        self.confidence: List[float] = [0.0] * n_bands
```

Stores periodicity confidence per band.

Every band initially has zero confidence.

**Line 207**

```python
        # Persistent (never-shrinking) estimate of how many consecutive
```

Introduces burst-width tracking.

**Line 208**

```python
        # scan-steps this band's occurrences tend to stay ON for -- e.g.
```

The scheduler estimates how long a transmission remains active.

**Line 209**

```python
        # 1 for a single-pulse radar, ~4 for a multi-step periodic burst.
```

Examples of expected values.

**Line 210**

```python
        # This must be tracked separately from the transient hit_times
```

The burst width is not derived only from the sliding hit-history window.

**Line 211**

```python
        # window: once periodicity locks on with a too-narrow jitter, the
```

A narrow score can cause the scheduler to stop scanning a burst too early.

**Line 212**

```python
        # scheduler starts abandoning bursts early (see class docstring
```

Explains the feedback problem.

**Line 213**

```python
        # addendum below), which shortens newly-observed runs and can
```

Abandoning bursts can corrupt future measurements.

**Line 214**

```python
        # erase the evidence of the true burst width from the sliding
```

The sliding window may no longer contain the original evidence.

**Line 215**

```python
        # window before the plateau fix below ever gets to use it.
```

Therefore the maximum is retained permanently.

**Line 216**

```python
        self.max_run_ever: List[int] = [1] * n_bands
```

Initializes every band's longest observed consecutive ON run to one.

**Line 217**

```python
        # Staggered-PRI fallback state (see _try_stagger_model /
```

Introduces support for staggered PRI patterns.

**Line 218**

```python
        # _update_pri_model). Only populated for a band when the
```

This state is used only when the uniform model fails.

**Line 219**

```python
        # single-period (uniform) model above has failed to lock AND a
```

Both conditions must be true before staggered fitting is used.

**Line 220**

```python
        # repeating multi-value gap pattern was found instead -- e.g. a
```

A staggered emitter has a repeating sequence of different gaps.

**Line 221**

```python
        # radar cycling PRI1, PRI2, ..., PRIL, PRI1, ... (TSRD's own
```

Provides a typical pattern.

**Line 222**

```python
        # PRIConfig pri_mode='Staggered', a standard ECCM technique).
```

Connects it to radar electronic counter-countermeasures.

**Line 223**

```python
        # `pri_estimate`/`confidence`/`jitter_estimate` are still the
```

The general scheduler interface still uses the same main fields.

**Line 224**

```python
        # fields everything else in this class (and every diagnostic
```

Diagnostics do not need a separate output format.

**Line 225**

```python
        # script) reads -- is_staggered just tells _periodicity_score
```

The Boolean flag controls how the score interprets the estimate.

**Line 226**

```python
        # HOW to interpret them (many unevenly-spaced predicted points
```

A staggered period contains multiple predicted pulse positions.

**Line 227**

```python
        # per period, not one).
```

Contrasts it with a uniform PRI.

**Line 228**

```python
        self.is_staggered: List[bool] = [False] * n_bands
```

Tracks whether each band currently has a staggered model.

**Line 229**

```python
        self.stagger_pattern: List[Optional[List[float]]] = [None] * n_bands
```

Stores the repeating list of staggered gap values.

**Line 230**

```python
        self.stagger_phase: List[Optional[int]] = [None] * n_bands
```

Stores which position in the stagger pattern predicts the next gap.

**Line 231**

```python
        # A SEPARATE, longer-retention hit history used only by the
```

Introduces a longer history specifically for staggered fitting.

**Line 232**

```python
        # stagger fallback -- history_len (30) is plenty for the
```

The ordinary uniform model needs less history.

**Line 233**

```python
        # uniform model (one global least-squares fit over the whole
```

Uniform fitting uses one global arithmetic progression.

**Line 234**

```python
        # window, immune to needing an unbroken run), but a stagger fit
```

Stagger fitting needs more repeated pattern evidence.

**Line 235**

```python
        # needs to separately discriminate L position-buckets, which
```

Each possible position in the pattern needs enough samples.

**Line 236**

```python
        # needs strictly more repeats. Measured directly on real data
```

Documents that this requirement came from real data testing.

**Line 237**

```python
        # (config_169.h5 band 1, true L=5): at 30 hits the position-
```

Thirty hits were insufficient for a five-value stagger pattern.

**Line 238**

```python
        # bucketed search picks the WRONG L (4, on a spuriously
```

A shorter incorrect pattern could look plausible with too little data.

**Line 239**

```python
        # near-constant small sample) with plausible-looking low
```

The false model still produced a low residual.

**Line 240**

```python
        # residual; L=5 (the correct answer, rmse=0.0 once given
```

With enough data, the correct pattern fitted exactly.

**Line 241**

```python
        # enough data) only becomes reliably available/competitive from
```

The correct pattern becomes identifiable at a larger sample size.

**Line 242**

```python
        # ~50 hits onward, consistently correct from there through the
```

Approximately 50 hits were needed.

**Line 243**

```python
        # full window (1594 hits) tested. 300 gives comfortable margin
```

The implementation retains up to 300 hits for safety.

**Line 244**

```python
        # above that empirical floor without keeping unbounded history.
```

This balances robustness and memory usage.

**Line 245**

```python
        self.stagger_history_len = 300
```

Sets the staggered hit-history limit.

**Line 246**

```python
        self.stagger_min_hits = 50
```

Requires at least 50 hits before trying staggered fitting.

**Line 247**

```python
        self.stagger_hit_times: List[List[int]] = [[] for _ in range(n_bands)]
```

Creates a separate long-term hit-time history for each band.

**Line 248**

Blank line.

---

# Candidate scoring and PRI refinement

## `_score_candidate()`: lines 249–252

**Line 249**

```python
    @staticmethod
```

Declares that the following method does not need access to `self`.

**Line 250**

```python
    def _score_candidate(diffs, candidate, tol):
```

Defines a helper that measures how well a candidate period explains observed differences.

**Line 251**

```python
        close = sum(1 for d in diffs if abs(d - max(1, round(d / candidate)) * candidate) <= tol)
```

For each observed difference:

1. Divides it by the candidate period.
2. Rounds to the nearest integer multiple.
3. Reconstructs that multiple.
4. Checks whether the error is within `tol`.
5. Counts how many differences pass.

**Line 252**

```python
        return close / len(diffs)
```

Returns the fraction of differences explained by the candidate.

This helper is retained as a coarse scoring utility, although later logic relies heavily on refined least-squares fitting.

**Lines 253–254**

Blank lines.

---

## `_refine_pri()`: lines 254–294

**Line 254**

```python
    @staticmethod
```

Declares the method independent of instance state.

**Line 255**

```python
    def _refine_pri(times, seed_candidate):
```

Defines the least-squares PRI refinement method.

Arguments:

- `times`: observed hit times
- `seed_candidate`: initial approximate period

**Line 256**

```python
        """
```

Starts the method documentation.

**Line 257**

```
        Fit an arithmetic progression t_i = a + b*n_i by least squares,
```

Describes the mathematical model:

```
observed time = starting offset + period × cycle index
```

**Line 258**

```
        where n_i = round((t_i - t_0) / seed_candidate) is each hit's
```

Explains how each hit is assigned an estimated cycle number.

**Line 259**

```
        inferred cycle index. Returns (refined_pri, rmse).
```

Documents the return values.

**Line 260**

Blank documentation line.

**Line 261**

```
        This matters whenever the true period isn't an exact integer
```

Explains why refinement is needed.

**Line 262**

```
        number of scan steps (e.g. a 650us PRI sampled at a 20us dwell
```

A physical PRI may map to a fractional number of scan steps.

**Line 263**

```
        is 32.5 steps) -- consecutive gaps then alternate between
```

The discretized gaps may alternate between integer values.

**Line 264**

```
        adjacent integers (32, 33, 32, 34, ...) and that rounding error
```

Fixed integer estimates accumulate timing error.

**Line 265**

```
        compounds over many cycles, so a single fixed-integer-with-fixed-
```

The error becomes worse over a long observation history.

**Line 266**

```
        tolerance model degrades badly over a long history even though
```

A simple tolerance test can reject a genuinely periodic signal.

**Line 267**

```
        the emitter is perfectly periodic. Fitting the whole history at
```

Least-squares fitting uses all observations together.

**Line 268**

```
        once recovers the fractional period precisely.
```

The fitted slope can be fractional.

**Line 269**

```python
        """
```

Ends the documentation.

**Line 270**

```python
        if len(times) < 4:
```

Requires at least four hit times for a meaningful fit.

**Line 271**

```python
            return None, None
```

Returns no estimate and no error when insufficient data exists.

**Line 272**

```python
        t0 = times[0]
```

Uses the first hit as the time origin.

**Line 273**

```python
        ns = [round((t - t0) / seed_candidate) for t in times]
```

Assigns each hit an integer cycle index based on the initial candidate period.

**Line 274**

```python
        if len(set(ns)) < 2:
```

Checks whether at least two distinct cycle indices were assigned.

**Line 275**

```python
            return None, None
```

Rejects the fit if all hits were mapped to the same cycle.

**Line 276**

```python
        # Plain float division, not statistics.mean(): confirmed by
```

Begins a performance-related comment.

**Line 277**

```python
        # profiling ScanAwarePRIScheduler's multi-candidate sweep (which
```

The later scan-aware scheduler calls this method many times.

**Line 278**

```python
        # calls this 33,836 times over just 2000 steps) that
```

Documents the measured call volume.

**Line 279**

```python
        # statistics.mean()'s internal exact-Fraction arithmetic alone
```

Explains that `statistics.mean()` can use exact rational arithmetic internally.

**Line 280**

```python
        # accounted for 60% of total scheduler runtime here -- needless
```

That precision was too expensive for this numerical use case.

**Line 281**

```python
        # precision for a least-squares score where every other term
```

The rest of the computation already uses floating-point arithmetic.

**Line 282**

```python
        # (b, a, rmse) is already plain-float. Semantically identical
```

Plain floating-point averages produce equivalent results here.

**Line 283**

```python
        # result for these inputs (list of ints/floats), just without
```

The optimization removes unnecessary overhead.

**Line 284**

```python
        # the Fraction overhead.
```

Completes the performance comment.

**Line 285**

```python
        n_mean = sum(ns) / len(ns)
```

Computes the average cycle index.

**Line 286**

```python
        t_mean = sum(times) / len(times)
```

Computes the average observed time.

**Line 287**

```python
        den = sum((n - n_mean) ** 2 for n in ns)
```

Computes the denominator of the least-squares slope formula.

**Line 288**

```python
        if den == 0:
```

Checks whether all cycle indices are identical.

**Line 289**

```python
            return None, None
```

Rejects the fit if the slope cannot be calculated.

**Line 290**

```python
        b = sum((n - n_mean) * (t - t_mean) for n, t in zip(ns, times)) / den
```

Calculates the least-squares slope.

Here, `b` is the refined PRI estimate.

**Line 291**

```python
        a = t_mean - b * n_mean
```

Calculates the least-squares intercept.

**Line 292**

```python
        residuals = [t - (a + b * n) for n, t in zip(ns, times)]
```

Computes the error between each observed time and its fitted time.

**Line 293**

```python
        rmse = (sum(r * r for r in residuals) / len(residuals)) ** 0.5
```

Calculates root mean squared error.

**Line 294**

```python
        return b, rmse
```

Returns:

- Refined PRI estimate
- Fit RMSE

**Lines 295**

Blank line.

---

# PRI model update

## `_update_pri_model()`: lines 296–320

**Line 296**

```python
    def _update_pri_model(self, band):
```

Defines the top-level PRI-model update method for one band.

**Line 297**

```python
        """Try the single-period (uniform) model first; if it doesn't
```

Documents the model-selection strategy.

**Line 298**

```
        lock, fall back to a staggered-PRI model. See
```

Uniform PRI is always attempted first.

**Line 299**

```
        _try_stagger_model's docstring for why these need to be two
```

Points to the staggered fitting explanation.

**Line 300**

```
        separate models rather than one generalized fit: the uniform
```

Explains why separate algorithms are used.

**Line 301**

```
        model's t_i = a + b*n_i has exactly one free "gap" parameter
```

A uniform model assumes one constant gap.

**Line 302**

```
        (b), which cannot represent an emitter whose consecutive gaps
```

It cannot represent genuinely different pulse intervals.

**Line 303**

```
        genuinely differ pulse to pulse by construction.
```

Completes the limitation.

**Line 304**

Blank documentation line.

**Line 305**

```
        Found necessary on real TSRD data (config_169.h5's band 1, an
```

Documents the real-data motivation.

**Line 306**

```
        AEGIS SPY-1D with pri_mode='Staggered', 5 PRIs of 100-180us):
```

Describes the staggered emitter configuration.

**Line 307**

```
        the uniform model never locked at any min_cycles setting --
```

The fixed-period model could not fit the staggered signal.

**Line 308**

```
        against any single candidate period, dense clusters of 5
```

The five different intervals create a complicated gap structure.

**Line 309**

```
        different pulse-to-pulse gaps either collapse onto one cycle
```

Some observations may be incorrectly assigned to one cycle.

**Line 310**

```
        index (destroying the fit) or scatter across many, both giving
```

Other observations may be assigned to many cycle indices.

**Line 311**

```
        huge residuals. This was never exercised by the synthetic
```

The synthetic data did not originally contain staggered PRI.

**Line 312**

```
        stand-in, where every periodic emitter has one fixed PRI.
```

Completes the comparison.

**Line 313**

Blank documentation line.

**Line 314**

```
        is_staggered is reset to False on every call so a band that
```

Explains why stale staggered state must be cleared.

**Line 315**

```
        WAS staggered but has since re-locked onto a genuine single
```

A band may change from staggered to uniform behavior.

**Line 316**

```
        period (or lost lock entirely) doesn't keep stale stagger state
```

Old state could otherwise corrupt future scoring.

**Line 317**

```
        that _periodicity_score would otherwise still read.
```

The scoring method reads this flag.

**Line 318**

```python
        """
```

Ends the method documentation.

**Line 319**

```python
        self.is_staggered[band] = False
```

Clears the staggered flag before recalculating the model.

**Line 320**

```python
        self._update_pri_model_uniform(band)
```

Attempts to fit a normal uniform PRI model first.

At this point, the file continues with the uniform-lock decision and the staggered fallback.


# `scan_scheduler_v3_pri.py` — Part 2 of 3

This part covers **lines 321–650**, including:

- Uniform versus staggered PRI selection
- Staggered-pattern discovery
- Phase recovery
- Beginning of uniform PRI fitting

The checklist remains unchecked until Part 3 is complete.

---

## Completing `_update_pri_model()`

### Lines 321–355

**Line 321**

```python
        if self.confidence[band] >= self.min_confidence:
```

Checks whether the uniform PRI model achieved sufficient confidence.

**Line 322**

```python
            return  # uniform model locked -- done, no need to try stagger
```

If the uniform model is reliable, stops immediately.

The staggered fallback is only attempted when uniform fitting fails.

**Line 323**

Blank line.

**Line 324**

```python
        result = self._try_stagger_model(self.stagger_hit_times[band])
```

Attempts to fit a staggered PRI model using the longer hit history.

**Line 325**

```python
        if result is None or result["phase"] is None:
```

Rejects the result if:

- No staggered pattern was found
- The next-gap phase could not be determined

**Line 326**

```python
            # result["phase"] is None means the clean repeating run we
```

Begins explaining why phase may be unavailable.

**Line 327**

```python
            # found doesn't reach the end of the hit history -- i.e.
```

The clean pattern may occur only in an older portion of the history.

**Line 328**

```python
            # something (a missed scan, a burst boundary) happened
```

A missed pulse or burst boundary may interrupt the pattern.

**Line 329**

```python
            # between it and the most recent hit, so we can't say which
```

The scheduler cannot safely identify the current position in the pattern.

**Line 330**

```python
            # position in the pattern predicts the NEXT gap. Detecting
```

Recognizing a pattern is not enough; the scheduler must know its phase.

**Line 331**

```python
            # "this band has staggered structure" without being able to
```

A pattern with unknown current position cannot generate a useful prediction.

**Line 332**

```python
            # predict its next occurrence isn't useful to the
```

Therefore it cannot help the band-selection policy.

**Line 333**

```python
            # scheduler, so this is treated the same as no lock rather
```

The code treats it as if no valid model exists.

**Line 334**

```python
            # than reported with a guessed phase.
```

It deliberately avoids making an unreliable phase guess.

**Line 335**

```python
            return
```

Stops without installing a staggered model.

**Line 336**

```python
        pattern, period = result["pattern"], result["period"]
```

Extracts:

- The repeating gap pattern
- The total period of one full pattern cycle

**Line 337**

```python
        L = len(pattern)
```

Stores the number of gap positions in the staggered pattern.

**Line 338**

```python
        # Scale-relative confidence, same form as the uniform model's,
```

Begins explaining staggered confidence.

**Line 339**

```python
        # but against the average INDIVIDUAL gap (period / L) rather
```

Uses the average individual gap as the scale.

**Line 340**

```python
        # than the full period -- rmse here is a residual on individual
```

The RMSE measures individual-gap errors, not full-cycle errors.

**Line 341**

```python
        # gap values, not on a full-cycle position, so comparing it
```

Therefore the denominator must represent the same type of quantity.

**Line 342**

```python
        # against the full period would make confidence trivially high
```

Using the larger full period would make any error appear small.

**Line 343**

```python
        # regardless of fit quality (period is L times larger than the
```

The full period is approximately `L` times the average individual gap.

**Line 344**

```python
        # scale rmse is actually measured on).
```

Completes the reasoning.

**Line 345**

```python
        confidence = min(1.0, max(0.0, 1.0 - result["rmse"] /
```

Begins computing staggered confidence and clamps it to `[0, 1]`.

**Line 346**

```python
                                  (self.confidence_scale * (period / L))))
```

Finishes the confidence formula:

```
1 - RMSE / (confidence_scale × average gap)
```

**Line 347**

```python
        if confidence < self.min_confidence:
```

Checks whether the staggered fit is reliable enough.

**Line 348**

```python
            return
```

Rejects the model if confidence is too low.

**Line 349**

```python
        self.is_staggered[band] = True
```

Marks the band as using a staggered model.

**Line 350**

```python
        self.stagger_pattern[band] = pattern
```

Stores the repeating list of individual gaps.

**Line 351**

```python
        self.stagger_phase[band] = result["phase"]
```

Stores the pattern position that predicts the next gap.

**Line 352**

```python
        self.pri_estimate[band] = period
```

Stores the complete staggered cycle period.

**Line 353**

```python
        self.jitter_estimate[band] = max(0.5, result["rmse"], self.max_run_ever[band] / 2.0)
```

Sets the timing-width parameter used by scoring.

The jitter floor is the largest of:

- `0.5`
- Staggered fit RMSE
- Half the longest observed ON run

**Line 354**

```python
        self.confidence[band] = confidence
```

Stores the accepted confidence value.

**Line 355**

Blank line.

---

# `_try_stagger_model()`

## Method documentation: lines 356–402

**Line 356**

```python
    def _try_stagger_model(self, times):
```

Defines the staggered PRI fitting method.

**Line 357**

```python
        """
```

Starts the method documentation.

**Line 358**

```
        Attempt to explain `times` as a STAGGERED-PRI emitter: a small,
```

Describes the expected structure.

**Line 359**

```
        fixed-length sequence of L distinct pulse-to-pulse gaps that
```

The emitter should repeat a finite list of gaps.

**Line 360**

```
        repeats (gap[i] depends on i mod L, not on one fixed period) --
```

The gap depends on its position within the repeating pattern.

**Line 361**

```
        as opposed to the uniform model's single fixed gap. This is a
```

Contrasts staggered behavior with constant PRI.

**Line 362**

```
        standard radar ECCM technique (varying PRI defeats a receiver
```

Explains why radars use staggered PRI.

**Line 363**

```
        that's only looking for one fixed period) and is exactly what
```

A fixed-period detector can be defeated by varying intervals.

**Line 364**

```
        TSRD's own PRIConfig(pri_mode='Staggered') generates.
```

Connects the model to the dataset's configuration.

**Line 365**

Blank documentation line.

**Line 366**

```
        Only called from _update_pri_model AFTER the uniform model has
```

Documents that this is a fallback.

**Line 367**

```
        already failed to lock -- a strict fallback, so it cannot cost
```

Normal uniform signals do not pay for staggered analysis.

**Line 368**

```
        anything on emitters the uniform model already handles (a
```

This keeps ordinary cases efficient.

**Line 369**

```
        single-PRI emitter's gaps are constant, i.e. a degenerate L=1
```

A constant PRI could technically be viewed as a one-value pattern.

**Line 370**

```
        "pattern" the uniform model already fits better and more
```

But the uniform model is the appropriate implementation.

**Line 371**

```
        cheaply).
```

Completes the fallback explanation.

**Line 372**

Blank documentation line.

**Line 373**

```
        Method (SDIF-family: cluster consecutive gaps by position in a
```

Introduces the general method.

**Line 374**

```
        candidate cycle length, not by absolute value):
```

Gaps are grouped according to pattern position, not just numerical size.

**Line 375**

```
          1. Take RAW CONSECUTIVE gaps (not all pairwise diffs, unlike
```

Step one uses adjacent pulse gaps only.

**Line 376**

```
             the uniform model -- a stagger pattern is only visible in
```

Staggered structure appears in the actual sequence of neighboring gaps.

**Line 377**

```
             the actual pulse-to-pulse sequence; pairwise diffs between
```

Non-adjacent differences combine multiple individual gaps.

**Line 378**

```
             non-adjacent hits are sums of several different individual
```

Those sums obscure the underlying repeating pattern.

**Line 379**

```
             gaps and don't share a common structure to cluster on).
```

Therefore, pairwise differences are inappropriate here.

**Line 380**

```
          2. Find the longest contiguous run of "plausible intra-
```

Step two identifies a clean run of likely within-pattern gaps.

**Line 381**

```
             pattern" gaps (below 4x the smaller half's median) --
```

The initial conceptual threshold uses a multiple of the smaller gap scale.

**Line 382**

```
             excludes cross-burst silences and missed-scan artifacts,
```

Large gaps are treated as possible interruptions.

**Line 383**

```
             which are typically much larger than any individual
```

Normal stagger gaps should be relatively small.

**Line 384**

```
             stagger step.
```

Completes the gap-filtering description.

**Line 385**

```
          3. For each candidate cycle length L = 2..9: split that run
```

Step three tests pattern lengths from 2 through 9.

**Line 386**

```
             into L position-buckets (gap[p], gap[p+L], gap[p+2L], ...)
```

Gaps at the same repeating position are grouped together.

**Line 387**

```
             and require at least `min_cycles` full repeats in every
```

Every pattern position needs enough repeated observations.

**Line 388**

```
             bucket. The canonical value at position p is that
```

Each position's representative value is the mean of its bucket.

**Line 389**

```
             bucket's mean; the candidate period is their sum. Residual
```

The complete period is the sum of pattern values.

**Line 390**

```
             = each observed gap vs. its bucket's canonical value.
```

Residuals measure how far each gap is from its position's average.

**Line 391**

```
          4. Pick the L with the lowest RELATIVE residual (rmse /
```

Step four chooses the pattern length with the smallest normalized error.

**Line 392**

```
             period) among candidates with enough support.
```

The candidate must also contain sufficient data.

**Line 393**

```
          5. Determine phase: which pattern position predicts the very
```

Step five determines the current position in the pattern.

**Line 394**

```
             NEXT gap after times[-1]. Only defined if the winning
```

The model must be able to predict the next interval.

**Line 395**

```
             clean run reaches all the way to the end of the observed
```

The clean pattern must connect to the most recent hit.

**Line 396**

```
             gaps -- otherwise there's an unaccounted-for gap (a missed
```

An interruption makes phase ambiguous.

**Line 397**

```
             pulse, a burst boundary) between the verified pattern and
```

Possible causes include missed pulses or separate bursts.

**Line 398**

```
             "now", and the phase would be a guess, not a fit.
```

The scheduler avoids guessing.

**Line 399**

Blank documentation line.

**Line 400**

```
        Returns None, or a dict with keys pattern (list[float], length
```

Documents the return format.

**Line 401**

```
        L), period (float), rmse (float), phase (int or None).
```

Lists the dictionary fields.

**Line 402**

```python
        """
```

Ends the documentation.

---

## Input validation and gap extraction: lines 403–413

**Line 403**

```python
        if len(times) < max(4 * self.min_cycles, self.stagger_min_hits):
```

Requires enough hit times for staggered fitting.

The requirement is the larger of:

- Four times the minimum cycle count
- The configured minimum stagger hit count

**Line 404**

```python
            return None
```

Rejects insufficient data.

**Line 405**

```python
        sorted_times = sorted(times)
```

Sorts the observed hit times.

**Line 406**

```python
        gaps = [sorted_times[i + 1] - sorted_times[i] for i in range(len(sorted_times) - 1)]
```

Calculates consecutive time differences.

**Line 407**

```python
        if len(gaps) < 2 * self.min_cycles:
```

Requires at least two gaps per expected pattern cycle.

**Line 408**

```python
            return None
```

Rejects a history that is too short.

**Line 409**

Blank line.

**Line 410**

```python
        small_half = sorted(gaps)[: max(1, len(gaps) // 2)]
```

Takes the smaller half of the sorted gaps.

This estimates the typical within-burst gap scale while excluding large silences.

**Line 411**

```python
        scale = statistics.median(small_half)
```

Computes the median of that smaller half.

**Line 412**

```python
        if scale <= 0:
```

Checks for an invalid zero or negative gap scale.

**Line 413**

```python
            return None
```

Rejects invalid data.

---

## Avoiding false staggered locks: lines 415–450

**Line 415**

```python
        # Floor on the SMALLEST canonical pattern value, derived from
```

Begins the explanation of a minimum pattern-gap safeguard.

**Line 416**

```python
        # the longest run of literally-adjacent (gap==1) hits in this
```

The safeguard depends on consecutive one-step hits.

**Line 417**

```python
        # window -- the SAME degenerate-fit guard the uniform model
```

The uniform model has a similar protection.

**Line 418**

```python
        # already has (its min_candidate = max(8, 2*max_run)), which I
```

The uniform model avoids fitting extremely small periods caused by dense scans.

**Line 419**

```python
        # initially failed to carry over here.
```

Documents a previous omission.

**Line 420**

Blank comment line.

**Line 421**

```python
        # Found the hard way, on the SYNTHETIC beacon scenario (not
```

Introduces an observed false-positive case.

**Line 422**

```python
        # real data): a densely-scanned Markov band (comm-1,
```

A highly persistent communications band can produce dense hits.

**Line 423**

```python
        # p_on_given_on=0.9) that the scheduler dwells on for many
```

The scheduler may repeatedly scan this sticky band.

**Line 424**

```python
        # consecutive steps produces a long run of gap==1 values, which
```

The hit gaps become all or mostly one.

**Line 425**

```python
        # trivially "fits" pattern=[1,1] (period=2) with rmse=0.0,
```

This can create a perfect but meaningless two-value stagger model.

**Line 426**

```python
        # confidence=1.000 -- a textbook false positive, not detecting
```

The false model would appear maximally confident.

**Line 427**

```python
        # real 2-value stagger structure, just describing "this band
```

It is actually describing persistent activity, not periodicity.

**Line 428**

```python
        # tends to stay on." Confirmed directly: this cost -6.6pp to
```

Documents the measured impact.

**Line 429**

```python
        # -19.5pp on the beacon scenario across every min_cycles value
```

Increasing the minimum number of cycles did not solve this.

**Line 430**

```python
        # tried, and was NOT fixed by min_cycles (which counts cycles,
```

The issue is gap magnitude, not merely sample count.

**Line 431**

```python
        # not gap magnitude -- a dense sticky band has plenty of
```

A sticky band can contain many fake short cycles.

**Line 432**

```python
        # "cycles" of a fake period=2).
```

Completes the explanation.

**Line 433**

Blank comment line.

**Line 434**

```python
        # A blind reuse of the uniform model's exact min_candidate
```

Explains why the uniform threshold cannot simply be copied.

**Line 435**

```python
        # formula (hardcoded floor of 8) is WRONG here: it would also
```

A fixed minimum of eight would be too restrictive.

**Line 436**

```python
        # reject config_169.h5's real stagger pattern (individual PRIs
```

Real staggered intervals can be shorter than eight scan steps.

**Line 437**

```python
        # of 5-9 scan-steps, legitimately below 8). The right floor is
```

The threshold must adapt to the signal's observed density.

**Line 438**

```python
        # relative to how DENSE this specific band's scanning has been,
```

Dense one-step runs should produce a larger rejection threshold.

**Line 439**

```python
        # same principle as the uniform model, different scale: real
```

The purpose is the same, but the implementation is adapted.

**Line 440**

```python
        # stagger positions are never adjacent scan-steps (min PRI on
```

The real stagger pattern has gaps larger than one.

**Line 441**

```python
        # config_169's band 1 is 5 steps > 1, so its own max_run stays
```

The real stagger signal does not create long adjacent runs.

**Line 442**

```python
        # at 1, giving a floor of only 2) while a sticky Markov band's
```

The minimum canonical gap becomes 2 for the real stagger case.

**Line 443**

```python
        # max_run climbs into the tens, correctly excluding it.
```

Sticky bands get a larger threshold and are rejected as false stagger signals.

**Line 444**

```python
        stagger_max_run, run_len = 1, 1
```

Initializes counters for the longest consecutive one-step hit run.

**Line 445**

```python
        sorted_times = sorted(times)
```

Sorts the hit times again for the adjacency analysis.

**Line 446**

```python
        for a, b in zip(sorted_times[:-1], sorted_times[1:]):
```

Iterates over adjacent pairs of hit times.

**Line 447**

```python
            run_len = run_len + 1 if b - a == 1 else 1
```

Extends the current run if the gap equals one; otherwise resets the run length to one.

**Line 448**

```python
            stagger_max_run = max(stagger_max_run, run_len)
```

Retains the longest adjacent-hit run observed.

**Line 449**

```python
        min_pattern_value = max(2, 2 * stagger_max_run)
```

Requires every stagger-pattern value to be at least twice the longest adjacent run, with an absolute minimum of two.

**Line 450**

Blank line.

---

## Finding a clean gap run: lines 451–479

**Line 451**

```python
        # Longest contiguous run of gaps <= scale * stagger_gap_ceiling,
```

Introduces the clean-run search.

**Line 452**

```python
        # tracked by [start, end) INDEX into `gaps` so we can tell
```

The code tracks indices, not just values.

**Line 453**

```python
        # afterwards whether it reaches the very end (needed for phase,
```

The endpoint matters for phase determination.

**Line 454**

```python
        # see docstring).
```

Completes the explanation.

**Line 455**

Blank comment line.

**Line 456**

```python
        # stagger_gap_ceiling=2.0 (not the much looser 4x used
```

Documents the chosen gap threshold multiplier.

**Line 457**

```python
        # elsewhere in this file for excluding cross-burst gaps) was
```

This threshold is stricter than another conceptual threshold mentioned earlier.

**Line 458**

```python
        # chosen from real data: on config_169.h5's band 1 (AEGIS
```

Explains the real-data basis.

**Line 459**

```python
        # SPY-1D, 5-value stagger, PRIs 100-180us = 5-9 scan-steps at
```

Describes the real stagger pattern's scale.

**Line 460**

```python
        # dwell=20us), the true per-position gaps and the genuine
```

Explains the time discretization.

**Line 461**

```
        # missed-pulse gaps are NOT well separated at 4x scale (~28
```

A four-times threshold would include many missed-pulse gaps.

**Line 462**

```
        # steps) -- real missed-pulse gaps start around 11 steps, only
```

Some missed-pulse gaps are not extremely large.

**Line 463**

```
        # ~1.5x the largest canonical value (9), so a 4x ceiling lets
```

A loose threshold would misclassify interruptions as clean gaps.

**Line 464**

```
        # ~15% of gaps through as spurious "clean" data, which corrupts
```

Those false inclusions distort the pattern buckets.

**Line 465**

```
        # the position-bucket means enough that L detection picks the
```

The inferred pattern length can become wrong.

**Line 466**

```
        # wrong cycle length. At 2x scale (~14 steps here), measured
```

A tighter two-times threshold works better.

**Line 467**

```
        # directly on this file: 92.5% of gaps are genuine single-
```

Most true individual stagger gaps fall below this threshold.

**Line 468**

```
        # position values and the ceiling correctly excludes nearly all
```

The tighter threshold removes most interruption gaps.

**Line 469**

```
        # of the rest.
```

Completes the empirical justification.

**Line 470**

```python
        stagger_gap_ceiling = 2.0
```

Sets the actual threshold multiplier.

**Line 471**

```python
        best_start, best_end, cur_start = 0, 0, 0
```

Initializes indices for the longest-clean-run search.

**Line 472**

```python
        for i, g in enumerate(gaps):
```

Iterates over all consecutive gaps with their indices.

**Line 473**

```python
            if g > scale * stagger_gap_ceiling:
```

Checks whether the gap is too large to be considered part of a clean stagger sequence.

**Line 474**

```python
                cur_start = i + 1
```

Starts a new candidate clean run after a large gap.

**Line 475**

```python
            if i - cur_start + 1 > best_end - best_start:
```

Checks whether the current clean run is longer than the best recorded run.

**Line 476**

```python
                best_start, best_end = cur_start, i + 1
```

Stores the current run as the best run.

**Line 477**

```python
        run = gaps[best_start:best_end]
```

Extracts the longest clean gap run.

**Line 478**

```python
        if len(run) < 2 * self.min_cycles:
```

Checks whether the clean run has enough gaps for at least two observations per cycle.

**Line 479**

```python
            return None
```

Rejects the staggered model if the clean run is too short.

---

## Testing candidate stagger lengths: lines 481–506

**Line 481**

```python
        best = None  # (L, pattern, rmse, rel)
```

Initializes the best candidate result.

The expected tuple is:

```
(pattern length, pattern values, RMSE, relative error)
```

**Line 482**

```python
        for L in range(2, 10):
```

Tests pattern lengths from 2 through 9.

**Line 483**

```python
            if len(run) < L * self.min_cycles:
```

Checks whether there are enough gaps for `min_cycles` complete repetitions of a pattern of length `L`.

**Line 484**

```python
                continue
```

Skips unsupported pattern lengths.

**Line 485**

```python
            positions = [run[p::L] for p in range(L)]
```

Splits the gap sequence into `L` position buckets.

For `L=3`, the buckets contain:

```
position 0: run[0], run[3], run[6], ...
position 1: run[1], run[4], run[7], ...
position 2: run[2], run[5], run[8], ...
```

**Line 486**

```python
            if any(len(p) < self.min_cycles for p in positions):
```

Checks whether every position bucket has enough observations.

**Line 487**

```python
                continue
```

Skips the candidate if any bucket is undersampled.

**Line 488**

```python
            # Plain float division here too -- see _refine_pri's comment;
```

Begins another performance comment.

**Line 489**

```python
            # same needless statistics.mean() Fraction overhead, lower
```

Explains that ordinary float arithmetic is faster here.

**Line 490**

```python
            # call volume in this path but the same fix.
```

The same optimization is applied even though this path is called less frequently.

**Line 491**

```python
            pattern = [sum(p) / len(p) for p in positions]
```

Calculates the mean gap for each pattern position.

**Line 492**

```python
            if min(pattern) < min_pattern_value:
```

Rejects the candidate if any canonical gap is too small.

This prevents dense persistent activity from being interpreted as staggered periodicity.

**Line 493**

```python
                continue
```

Skips invalid candidates.

**Line 494**

```python
            period = sum(pattern)
```

Calculates the full staggered cycle period.

**Line 495**

```python
            if period <= 0:
```

Checks for an invalid nonpositive period.

**Line 496**

```python
                continue
```

Skips invalid candidates.

**Line 497**

```python
            residuals = [v - pattern[i % L] for i, v in enumerate(run)]
```

Calculates the difference between each observed gap and the expected value for its repeating position.

**Line 498**

```python
            rmse = (sum(r * r for r in residuals) / len(residuals)) ** 0.5
```

Calculates the root mean squared fitting error.

**Line 499**

```python
            rel = rmse / period
```

Normalizes the error by the full period.

**Line 500**

```python
            if best is None or rel < best[3]:
```

Checks whether this is the first valid candidate or better than the current best.

**Line 501**

```python
                best = (L, pattern, rmse, rel)
```

Stores the current candidate as the best result.

**Line 502**

Blank line.

**Line 503**

```python
        if best is None:
```

Checks whether no candidate pattern was valid.

**Line 504**

```python
            return None
```

Rejects the staggered model.

**Line 505**

```python
        L, pattern, rmse, _rel = best
```

Unpacks the winning candidate.

The relative error is stored in `_rel` because it is no longer needed.

**Line 506**

```python
        period = sum(pattern)
```

Recomputes the full period from the selected pattern.

---

## Resolving staggered phase: lines 508–535

**Line 508**

```python
        # Phase resolution is deliberately a SEPARATE step from pattern
```

Explains that detecting a pattern and determining the current phase are different tasks.

**Line 509**

```python
        # discovery above, against ALL of `times` rather than just the
```

Phase is estimated using the complete hit history.

**Line 510**

```python
        # clean run.
```

The clean run is used to learn the pattern, not exclusively to determine phase.

**Line 511**

Blank comment line.

**Line 512**

```python
        # First version of this tied phase directly to whether the
```

Describes an earlier implementation.

**Line 513**

```python
        # clean run reached the end of `gaps` -- correct when it did,
```

That approach worked only when the clean sequence ended at the newest observation.

**Line 514**

```python
        # but on real data (config_169.h5 band 1) it essentially never
```

Real data frequently contains interruptions.

**Line 515**

```python
        # did: with min_cycles=4 requiring long runs, the LONGEST clean
```

The longest clean run often ended before the current time.

**Line 516**

```python
        # run in a window is frequently an INTERIOR segment (there's
```

The clean sequence was often inside the history.

**Line 517**

```
        # almost always a slightly-larger real gap -- a genuine
```

A somewhat larger but valid gap could interrupt the clean run.

**Line 518**

```
        # occasional missed pulse, confirmed directly: ~7.5% of this
```

Documents the observed missed-pulse rate.

**Line 519**

```
        # emitter's true consecutive gaps are irregular -- somewhere
```

The pattern is mostly regular but not perfectly contiguous.

**Line 520**

```
        # after the best segment but before times[-1]), so phase came
```

This made the old phase method return no result.

**Line 521**

```
        # back None on every window size tried (30 up to 500 hits)
```

The failure occurred across several history sizes.

**Line 522**

```
        # even though the pattern itself was found exactly right
```

Pattern identification still worked.

**Line 523**

```
        # (rmse=0.0, matching the file's declared PRIs precisely).
```

The issue was phase continuity, not pattern accuracy.

**Line 524**

Blank comment line.

**Line 525**

```python
        # _resolve_stagger_phase instead fits a REPEATING NON-UNIFORM
```

Introduces the replacement phase method.

**Line 526**

```python
        # GRID (built from the now-known pattern) against every
```

It constructs a theoretical repeating timeline.

**Line 527**

```python
        # observed time via nearest-grid-point residual, not requiring
```

Each hit is matched to its nearest expected grid point.

**Line 528**

```python
        # unbroken contiguity -- a handful of missed pulses just cost
```

Missed pulses increase error but do not completely invalidate phase tracking.

**Line 529**

```python
        # a few grid points' worth of residual, they don't break
```

The model remains usable despite small gaps in observations.

**Line 530**

```python
        # phase tracking for everything downstream the way an index-based
```

This is more robust than requiring uninterrupted sequence indices.

**Line 531**

```python
        # walk would.
```

Completes the comparison.

**Line 532**

```python
        phase, phase_rmse = self._resolve_stagger_phase(sorted_times, pattern)
```

Calls the phase-recovery method and receives:

- Predicted next-gap position
- Phase-fitting RMSE

**Line 533**

Blank line.

**Line 534**

```python
        return {"pattern": pattern, "period": period, "rmse": max(rmse, phase_rmse),
```

Returns a result dictionary.

The final RMSE is the worse of:

- Pattern-fit RMSE
- Phase-fit RMSE

**Line 535**

```python
                "phase": phase}
```

Adds the predicted phase and closes the dictionary.

**Lines 536–537**

Blank lines before the phase helper.

---

# `_resolve_stagger_phase()`

## Lines 537–580

**Line 537**

```python
    @staticmethod
```

Declares that the method does not need instance state.

**Line 538**

```python
    def _resolve_stagger_phase(times, pattern):
```

Defines the phase-fitting method.

**Line 539**

```python
        """Given an already-validated stagger `pattern`, find which
```

Starts the method documentation.

**Line 540**

```
        pattern position predicts the gap from times[-1] to the NEXT
```

The target is the next expected gap after the latest hit.

**Line 541**

```
        hit, by fitting a repeating non-uniform grid (the pattern's
```

The method builds a timeline from the nonuniform pattern.

**Line 542**

```
        cumulative offsets, tiled) against every observed time and
```

The pattern is repeated enough times to cover the history.

**Line 543**

```
        picking whichever of the L possible starting phases gives the
```

Each possible starting position is tested.

**Line 544**

```
        lowest nearest-grid-point residual. See _try_stagger_model's
```

The best phase minimizes matching error.

**Line 545**

```
        docstring for why this needs to be separate from pattern
```

References the earlier design explanation.

**Line 546**

```
        discovery. Returns (phase, rmse).
```

Documents the return values.

**Line 547**

```python
        """
```

Ends the documentation.

**Line 548**

```python
        L = len(pattern)
```

Stores the pattern length.

**Line 549**

```python
        period = sum(pattern)
```

Calculates the complete pattern period.

**Line 550**

```python
        t0 = times[0]
```

Uses the first observed hit as the grid origin.

**Line 551**

```python
        span = max(1.0, times[-1] - t0)
```

Calculates the observed time span, with a minimum of `1.0` to avoid degenerate division.

**Line 552**

```python
        n_cycles = int(span / period) + 2
```

Calculates how many pattern cycles are needed to cover the observation window, adding two extra cycles for safety.

**Line 553**

Blank line.

**Line 554**

```python
        best_phase, best_err = 0, None
```

Initializes the best phase and its error.

**Line 555**

```python
        for p0 in range(L):
```

Tests every possible starting position in the staggered pattern.

**Line 556**

```python
            grid = []
```

Creates an empty expected-time grid.

**Line 557**

```python
            acc = 0.0
```

Initializes the cumulative time offset.

**Line 558**

```python
            idx = p0
```

Starts at the candidate phase position.

**Line 559**

```python
            for _ in range(n_cycles * L):
```

Generates enough grid points to cover the observed data.

**Line 560**

```python
                grid.append(t0 + acc)
```

Adds the current expected pulse time to the grid.

**Line 561**

```python
                acc += pattern[idx % L]
```

Advances by the next pattern gap, wrapping around the pattern.

**Line 562**

```python
                idx += 1
```

Moves to the next pattern position.

**Line 563**

```python
            sq_err, gi = 0.0, 0
```

Initializes:

- Total squared matching error
- Current grid-index pointer

**Line 564**

```python
            for t in times:
```

Processes each observed hit time.

**Line 565**

```python
                while gi + 1 < len(grid) and abs(grid[gi + 1] - t) <= abs(grid[gi] - t):
```

Moves forward through the grid while the next expected point is closer to the observation.

**Line 566**

```python
                    gi += 1
```

Advances the nearest-grid pointer.

**Line 567**

```python
                sq_err += (grid[gi] - t) ** 2
```

Adds the squared difference between the observed hit and its closest grid point.

**Line 568**

```python
            err = (sq_err / len(times)) ** 0.5
```

Converts total squared error into RMSE.

**Line 569**

```python
            if best_err is None or err < best_err:
```

Checks whether this phase has the lowest error so far.

**Line 570**

```python
                best_phase, best_err = p0, err
```

Stores the best phase and error.

**Line 571**

Blank line.

**Line 572**

```python
        # Walk the winning grid forward from t0 to find which cycle
```

Begins the second phase of the algorithm.

**Line 573**

```python
        # position times[-1] itself landed nearest to, then the pattern
```

The method now determines where the latest observed hit lies in the winning grid.

**Line 574**

```python
        # index one further is what predicts the NEXT gap.
```

The following pattern position predicts the next interval.

**Line 575**

```python
        acc, idx, last_idx = 0.0, best_phase, best_phase
```

Initializes cumulative time and pattern indices.

**Line 576**

```python
        while t0 + acc <= times[-1] + pattern[idx % L] / 2.0:
```

Walks through the pattern until reaching the latest observed time, allowing half-gap tolerance.

**Line 577**

```python
            last_idx = idx
```

Stores the current pattern position.

**Line 578**

```python
            acc += pattern[idx % L]
```

Advances by the current pattern gap.

**Line 579**

```python
            idx += 1
```

Moves to the next pattern position.

**Line 580**

```python
        return (last_idx + 1) % L, best_err
```

Returns:

- The next pattern position
- The best phase-fitting RMSE

**Line 581**

Blank line.

---

# Uniform PRI fitting

## Initial checks: lines 582–587

**Line 582**

```python
    def _update_pri_model_uniform(self, band):
```

Defines the method for fitting a single fixed PRI.

**Line 583**

```python
        times = self.hit_times[band]
```

Retrieves the recent hit times for the selected band.

**Line 584**

```python
        if len(times) < 8:
```

Requires at least eight hits before attempting a uniform PRI fit.

**Line 585**

```python
            self.pri_estimate[band] = None
```

Clears any PRI estimate when there is insufficient data.

**Line 586**

```python
            self.confidence[band] = 0.0
```

Clears the confidence.

**Line 587**

```python
            return
```

Stops the update.

---

## Pairwise differences: lines 588–620

**Line 588**

```python
        # PRI histogramming (a standard ESM technique): take ALL pairwise
```

Introduces the pairwise-difference approach.

**Line 589**

```python
        # time differences between recent hits (using raw hits, not just
```

Uses every hit, not only burst onsets.

**Line 590**

```python
        # burst onsets, gives more data points and avoids misclassifying
```

This increases sample count and avoids treating mid-burst hits as new bursts.

**Line 591**

```python
        # a mid-burst re-scan as a "new" onset). A fixed absolute
```

Explains why raw hits are retained.

**Line 592**

```python
        # tolerance (not one that scales with the candidate) is used when
```

The coarse candidate test uses an absolute tolerance.

**Line 593**

```python
        # checking whether a diff is an integer multiple of a candidate
```

A difference is compared against a rounded candidate multiple.

**Line 594**

```python
        # period -- a tolerance that scales with the candidate lets tiny
```

Candidate-scaled tolerances could make small periods too flexible.

**Line 595**

```python
        # candidates trivially "explain" almost anything by chance.
```

This would cause false periodicity detections.

**Line 596**

```python
        diffs = [times[j] - times[i] for i in range(len(times)) for j in range(i + 1, len(times))]
```

Builds all pairwise positive time differences between hits.

**Line 597**

Blank line.

**Line 598**

```python
        # Guard against a subtle false positive: once the scheduler locks
```

Introduces a dense-hit false-positive safeguard.

**Line 599**

```python
        # onto a band it likes, it may scan several consecutive steps in a
```

The scheduler's own behavior can create dense observations.

**Line 600**

```python
        # row. A dense run of consecutive integers trivially contains
```

Consecutive times create many apparent small periods.

**Line 601**

```python
        # "multiples" of almost any small candidate just by combinatorics
```

Many small candidates can explain dense runs accidentally.

**Line 602**

```python
        # (e.g. the run 100..110 contains diffs of 2, 3, 4... up to 10),
```

Provides an example.

**Line 603**

```python
        # which can look like false periodicity for an emitter that's
```

The apparent periodicity may be an artifact.

**Line 604**

```python
        # just persistently on, not actually cyclic. Ignore any candidate
```

The model should reject periods explained only by persistence.

**Line 605**

```python
        # period small enough to be explained by the densest run of
```

The minimum candidate depends on the longest consecutive run.

**Line 606**

```python
        # back-to-back hits observed.
```

Completes the safeguard explanation.

**Line 607**

```python
        max_run = 1
```

Initializes the longest consecutive-hit run.

**Line 608**

```python
        run = 1
```

Initializes the current consecutive-hit run.

**Line 609**

```python
        sorted_times = sorted(times)
```

Sorts the hit times.

**Line 610**

```python
        for a, b in zip(sorted_times[:-1], sorted_times[1:]):
```

Iterates through adjacent hit pairs.

**Line 611**

```python
            run = run + 1 if b - a == 1 else 1
```

Extends the current run when hits are exactly one step apart; otherwise resets it.

**Line 612**

```python
            max_run = max(max_run, run)
```

Records the largest consecutive-hit run.

**Line 613**

```python
        self.max_run_ever[band] = max(self.max_run_ever[band], max_run)
```

Stores the largest run permanently.

This value is used both for false-lock prevention and periodicity-score widening.

**Line 614**

```python
        min_candidate = max(8, 2 * max_run)
```

Sets the minimum candidate period.

It must be at least:

- Eight steps
- Twice the current longest consecutive-hit run

**Line 615**

Blank line.

**Line 616**

```python
        candidate_pool = [d for d in diffs if d >= min_candidate]
```

Filters pairwise differences to those large enough to be plausible candidate periods.

**Line 617**

```python
        if not candidate_pool:
```

Checks whether any usable difference remains.

**Line 618**

```python
            self.pri_estimate[band] = None
```

Clears the PRI estimate if there are no candidates.

**Line 619**

```python
            self.confidence[band] = 0.0
```

Clears confidence.

**Line 620**

```python
            return
```

Stops the update.

---

## Generating candidate periods: lines 622–640

**Line 622**

```python
        # Candidate periods to test, from two complementary methods:
```

Introduces the candidate-generation process.

**Line 623**

```python
        #  1) GCD of all diffs -- exact and immediate when diffs are
```

The first method is the GCD of all pairwise differences.

**Line 624**

```python
        #     (near) noise-free integer multiples of the true period,
```

GCD works well when observations are clean integer multiples.

**Line 625**

```python
        #     which a pure mode/frequency count can miss badly if the
```

A frequency-based mode may miss the fundamental period.

**Line 626**

```python
        #     most common diff happens to be a large multiple (e.g. 168
```

For example, the most common gap may be a large multiple.

**Line 627**

```python
        #     instead of 12) rather than the period itself.
```

The GCD can recover the smaller fundamental period.

**Line 628**

```python
        #  2) The pairwise mode and its small-integer divisors -- more
```

The second method uses the most common difference.

**Line 629**

```python
        #     robust when there's timing jitter, where an exact GCD
```

The mode is more tolerant of noisy differences.

**Line 630**

```python
        #     would collapse to 1.
```

Small timing variations can make a numeric GCD useless.

**Line 631**

```python
        candidates = set()
```

Creates an empty set of candidate period values.

**Line 632**

```python
        g = reduce(math.gcd, diffs)
```

Computes the GCD across all pairwise differences.

**Line 633**

```python
        if g >= min_candidate:
```

Checks whether the GCD is large enough to be plausible.

**Line 634**

```python
            candidates.add(g)
```

Adds the GCD candidate.

**Line 635**

```python
        mode_candidate, _freq = Counter(candidate_pool).most_common(1)[0]
```

Finds the most frequent usable pairwise difference.

`_freq` receives the occurrence count but is not used later.

**Line 636**

```python
        candidates.add(mode_candidate)
```

Adds the modal difference as a candidate.

**Line 637**

```python
        for k in (2, 3, 4, 5, 6, 7, 8):
```

Tests small integer divisors of the modal difference.

**Line 638**

```python
            sub = round(mode_candidate / k)
```

Calculates a rounded submultiple.

**Line 639**

```python
            if sub >= min_candidate:
```

Checks whether the submultiple passes the minimum-period guard.

**Line 640**

```python
                candidates.add(sub)
```

Adds the valid submultiple to the candidate set.

---

## Neighbor expansion: lines 642–660

**Line 642**

```python
        # Also test each candidate's immediate integer neighbors
```

Introduces an off-by-one safeguard.

**Line 643**

```python
        # (+-1). Found via a real failing case (a PDW seed where the
```

The fix was motivated by a real failed fractional-PRI case.

**Line 644**

```python
        # true period was 32.5 steps, but the pairwise-diff mode came
```

The true period was fractional, while the modal difference rounded to 33.

**Line 645**

```python
        # out as 33): an off-by-one seed candidate isn't just "slightly
```

A one-step candidate error can change cycle-index assignments.

**Line 646**

```python
        # wrong" -- the n_i = round((t-t0)/candidate) index used by
```

The candidate determines the inferred cycle numbers.

**Line 647**

```python
        # _refine_pri can pick up a ROUNDING COLLISION (two genuinely
```

Two different observations can map to the same cycle index.

**Line 648**

```python
        # different hits mapping to the same cycle index) once the
```

This becomes more likely as candidate error accumulates.

**Line 649**

```python
        # seed's error accumulates across enough cycles, which inflates
```

Incorrect index assignments increase RMSE.

**Line 650**

```python
        # that candidate's residual far more than a 1-step error would
```

The fitting penalty can be disproportionately large.

# `scan_scheduler_v3_pri.py` — Part 3 of 3

This final part covers **lines 651–919** and completes the file. The checklist box has now been marked complete.

## Completing uniform candidate generation

### Lines 651–681

**Line 651**

```python
        # suggest (confirmed directly: candidate 33 gave rel error
```

Begins a concrete example of the off-by-one problem.

**Line 652**

```python
        # 0.229, candidate 34 gave 0.255, but the untried candidate 32
```

Candidates 33 and 34 were both much worse than 32.

**Line 653**

```python
        # gave 0.029 -- neither the mode, gcd, nor any submultiple of
```

The best candidate was not produced by the original candidate-generation methods.

**Line 654**

```python
        # the mode ever generated 32 as a candidate at all). Testing
```

Therefore, neighboring candidates are explicitly added.

**Line 655**

```python
        # neighbors costs little (the refine+RMSE step is what actually
```

The extra candidates are inexpensive compared with the fitting operation.

**Line 656**

```python
        # discriminates) and directly covers this failure mode.
```

The least-squares RMSE decides which candidate is genuinely best.

**Line 657**

```python
        for c in list(candidates):
```

Iterates over a snapshot of the candidate set.

Using `list()` is important because the set is modified inside the loop.

**Line 658**

```python
            for neighbor in (c - 1, c + 1):
```

Creates the immediate lower and upper integer neighbors for each candidate.

**Line 659**

```python
                if neighbor >= min_candidate:
```

Rejects neighbors below the minimum allowed period.

**Line 660**

```python
                    candidates.add(neighbor)
```

Adds the valid neighboring candidate.

**Line 661**

Blank line.

**Line 662**

```python
        # Refine EVERY candidate via least-squares and pick whichever
```

Introduces the final candidate-selection method.

**Line 663**

```python
        # yields the best RELATIVE fit (rmse / refined_pri) -- not
```

The selection criterion is normalized RMSE.

**Line 664**

```python
        # whichever scores best on the coarse tol=1 exact-multiple test.
```

The old coarse multiple-count score is not trusted as the final criterion.

**Line 665**

```python
        # That coarse test is only a rough screen: when the true period
```

Explains why the coarse test is insufficient.

**Line 666**

```python
        # isn't an integer (real jitter, or a fractional PRI-vs-dwell
```

Fractional periods create alternating integer gaps.

**Line 667**

```python
        # ratio) and GCD-of-diffs collapses to 1, a harmonic of the true
```

A harmonic candidate may appear more common than the fundamental.

**Line 668**

```python
        # period can score BETTER on the coarse test for a given noise
```

This can cause the coarse test to select the wrong period.

**Line 669**

```python
        # draw than the true fundamental does (found via
```

Documents that this behavior was observed experimentally.

**Line 670**

```python
        # diagnose_beacon_regression-style inspection on a PDW seed that
```

References the diagnostic process.

**Line 671**

```python
        # locked onto ~65 instead of ~32.5 this way). The refined fit's
```

Provides an example of harmonic lock-on.

**Line 672**

```python
        # own residual is a much more sensitive, appropriate discriminator
```

Least-squares residual is more informative.

**Line 673**

```python
        # for a fractional period than a binary in/out-of-tolerance test.
```

Completes the justification.

**Line 674**

```python
        best_base, best_rmse, best_rel = None, None, None
```

Initializes variables for the best candidate.

**Line 675**

```python
        for c in candidates:
```

Evaluates every candidate period.

**Line 676**

```python
            refined, rmse = self._refine_pri(sorted_times, c)
```

Refines the candidate using least squares.

**Line 677**

```python
            if refined is None or rmse is None or refined < min_candidate * 0.5:
```

Rejects invalid or implausibly small refined estimates.

**Line 678**

```python
                continue
```

Skips the invalid candidate.

**Line 679**

```python
            rel = rmse / refined
```

Computes the candidate's relative error.

**Line 680**

```python
            if best_rel is None or rel < best_rel:
```

Checks whether the candidate is better than the current best.

**Line 681**

```python
                best_base, best_rmse, best_rel = refined, rmse, rel
```

Stores the candidate's:

- Refined PRI
- RMSE
- Relative error

---

## Validating the selected uniform model

### Lines 683–716

**Line 683**

```python
        if best_base is None:
```

Checks whether every candidate failed.

**Line 684**

```python
            self.pri_estimate[band] = None
```

Clears the PRI estimate.

**Line 685**

```python
            self.confidence[band] = 0.0
```

Clears confidence.

**Line 686**

```python
            return
```

Stops the update.

**Line 687**

```python
        refined_pri, rmse = best_base, best_rmse
```

Extracts the selected refined period and fitting error.

**Line 688**

Blank line.

**Line 689**

```python
        if refined_pri is None or refined_pri < min_candidate * 0.5 or rmse is None:
```

Performs another defensive validity check.

**Line 690**

```python
            self.pri_estimate[band] = None
```

Clears the estimate if it is invalid.

**Line 691**

```python
            self.confidence[band] = 0.0
```

Clears confidence.

**Line 692**

```python
            return
```

Stops processing.

**Line 693**

Blank line.

**Line 694**

```python
        # Cycle-count guard (see self.min_cycles in __init__): how many
```

Introduces the distinct-cycle safeguard.

**Line 695**

```python
        # DISTINCT cycles of the winning period did we actually observe?
```

The fit must span enough independent cycles.

**Line 696**

```python
        # Dense bursts can supply many hits across very few cycles, and
```

Many hits do not necessarily mean many cycles.

**Line 697**

```python
        # a fit through 2 cycle-clusters is a fit through 2 points.
```

A fit through only two clusters is not trustworthy.

**Line 698**

```python
        n_cycles = len({round((t - sorted_times[0]) / refined_pri) for t in sorted_times})
```

Assigns every hit to an estimated cycle index and counts distinct indices.

**Line 699**

```python
        if n_cycles < self.min_cycles:
```

Checks whether enough cycles were observed.

**Line 700**

```python
            self.pri_estimate[band] = None
```

Clears the estimate when too few cycles exist.

**Line 701**

```python
            self.confidence[band] = 0.0
```

Clears confidence.

**Line 702**

```python
            return
```

Stops the update.

**Line 703**

Blank line.

**Line 704**

```python
        confidence = min(1.0, max(0.0, 1.0 - rmse / (self.confidence_scale * refined_pri)))
```

Calculates confidence from relative fitting error.

The result is clamped to `[0, 1]`.

**Line 705**

```python
        if confidence >= self.min_confidence:
```

Checks whether the candidate is reliable enough to lock.

**Line 706**

```python
            self.pri_estimate[band] = refined_pri
```

Stores the accepted PRI.

**Line 707**

```python
            # Floor jitter at half the largest observed consecutive-hit
```

Explains the burst-width-based jitter floor.

**Line 708**

```python
            # run, not just the fit residual -- a burst that stays ON
```

A multi-step burst needs a wider score than timing residual alone provides.

**Line 709**

```python
            # for `max_run_ever` steps needs the phase bump to plateau
```

The Gaussian phase score should cover the burst duration.

**Line 710**

```python
            # across roughly that width, or the scheduler abandons the
```

Otherwise the scheduler may leave the band prematurely.

**Line 711**

```python
            # burst after its first step (see class docstring).
```

References the original failure explanation.

**Line 712**

```python
            self.jitter_estimate[band] = max(0.5, rmse, self.max_run_ever[band] / 2.0)
```

Sets the jitter estimate to the largest of:

- Minimum width `0.5`
- Fitting RMSE
- Half the longest observed ON run

**Line 713**

```python
            self.confidence[band] = confidence
```

Stores the accepted confidence.

**Line 714**

```python
        else:
```

Handles a candidate whose confidence is below the threshold.

**Line 715**

```python
            self.pri_estimate[band] = None
```

Rejects the candidate.

**Line 716**

```python
            self.confidence[band] = 0.0
```

Sets confidence to zero.

**Line 717**

Blank line.

---

# Staggered periodicity scoring

## `_stagger_distance()`: lines 718–737

**Line 718**

```python
    def _stagger_distance(self, band, t, last):
```

Defines a method that calculates distance from the current time to the nearest predicted staggered pulse.

**Line 719**

```python
        """Circular distance from t to the nearest predicted pulse under
```

Starts the method documentation.

**Line 720**

```
        a staggered-PRI model. Unlike the uniform model -- one predicted
```

Explains that uniform PRI has one predicted pulse location per period.

**Line 721**

```
        point per period, so a plain mod suffices -- a stagger pattern
```

Staggered PRI has multiple predicted points.

**Line 722**

```
        has L unevenly-spaced predicted points per period, so the
```

The method must test all pattern positions.

**Line 723**

```
        nearest one is found by minimum over all L candidates (checked
```

It finds the closest predicted point.

**Line 724**

```
        both within this cycle and one cycle back, to handle wraparound
```

It checks points on both sides of a period boundary.

**Line 725**

```
        correctly for a point near the cycle boundary)."""
```

Ends the documentation.

**Line 726**

```python
        pattern = self.stagger_pattern[band]
```

Retrieves the stagger pattern for the band.

**Line 727**

```python
        L = len(pattern)
```

Stores the number of pattern positions.

**Line 728**

```python
        phase0 = self.stagger_phase[band]
```

Retrieves the current pattern phase.

**Line 729**

```python
        period = sum(pattern)
```

Calculates the full staggered cycle period.

**Line 730**

```python
        offsets = []
```

Creates a list for cumulative offsets within one period.

**Line 731**

```python
        acc = 0.0
```

Initializes the cumulative offset.

**Line 732**

```python
        for i in range(L):
```

Iterates through all pattern positions.

**Line 733**

```python
            acc += pattern[(phase0 + i) % L]
```

Adds the next pattern gap, wrapping around when necessary.

**Line 734**

```python
            offsets.append(acc)  # offsets[-1] == period (one full cycle from `last`)
```

Stores each predicted offset.

The final offset equals one complete period.

**Line 735**

```python
        elapsed = (t - last) % period
```

Calculates the current phase relative to the most recent hit.

**Line 736**

```python
        candidates = offsets + [o - period for o in offsets]
```

Creates predicted offsets from both the current and previous cycle.

**Line 737**

```python
        return min(abs(elapsed - o) for o in candidates)
```

Returns the distance to the closest predicted staggered pulse.

---

# `_periodicity_score()`

## Lines 739–767

**Line 739**

```python
    def _periodicity_score(self, band, t):
```

Defines the method that converts timing proximity into a score between zero and one.

**Line 740**

```python
        pri = self.pri_estimate[band]
```

Retrieves the band's current PRI estimate.

**Line 741**

```python
        if pri is None or self.confidence[band] <= 0 or not self.hit_times[band]:
```

Checks whether a usable periodicity model exists.

It requires:

- A PRI estimate
- Positive confidence
- At least one hit

**Line 742**

```python
            return 0.0
```

Returns no periodicity score if the model is unavailable.

**Line 743**

```python
        last = self.hit_times[band][-1]
```

Retrieves the most recent hit time.

**Line 744**

```python
        if self.is_staggered[band] and self.stagger_pattern[band] and self.stagger_phase[band] is not None:
```

Checks whether the band has a complete staggered model.

**Line 745**

```python
            dist = self._stagger_distance(band, t, last)
```

Uses the staggered distance calculation.

**Line 746**

```python
        else:
```

Handles a uniform PRI model.

**Line 747**

```python
            phase = (t - last) % pri
```

Computes the current phase within the uniform period.

**Line 748**

```python
            dist = min(phase, pri - phase)
```

Calculates circular distance to the nearest expected pulse.

For example, a point near either end of the period is considered close to the predicted pulse.

**Line 749**

```python
        # Plateau the score across a window of width switch_lead_steps on
```

Introduces the switch-lead adjustment.

**Line 750**

```python
        # EITHER side of the predicted instant, rather than the original
```

The score is widened rather than simply shifted.

**Line 751**

```python
        # single-point peak. A first attempt just shifted the whole score
```

Documents an earlier implementation.

**Line 752**

```python
        # curve forward by switch_lead_steps (checking phase against
```

The old version moved the score peak earlier.

**Line 753**

```python
        # t+lead) -- that only moves WHERE the peak sits, it doesn't
```

Moving the peak alone does not keep the score high at arrival.

**Line 754**

```python
        # widen it, so by the time t reaches the real arrival the score
```

The score would already have started declining.

**Line 755**

```python
        # is already past its (now-early) peak and declining, and gets
```

A competing band could then win at the important time.

**Line 756**

```python
        # outscored by a loud always-on band exactly when it matters
```

This caused missed pulses.

**Line 757**

```python
        # (confirmed directly: with lead=1, the scheduler switched to
```

Provides an observed example.

**Line 758**

```python
        # band 5 one step early as intended, got blocked settling, then
```

The early switch began settling at the wrong time.

**Line 759**

```python
        # abandoned band 5 for band 1 on the very next step -- the real
```

The scheduler left before the pulse arrived.

**Line 760**

```python
        # arrival instant -- losing the pulse anyway). Flooring the
```

The old adjustment did not solve the hardware timing problem.

**Line 761**

```python
        # distance at (dist - switch_lead_steps) instead makes the score
```

The new approach subtracts the lead from the distance.

**Line 762**

```python
        # sit at its maximum for the whole [predicted-lead, predicted]
```

This creates a plateau before the predicted arrival.

**Line 763**

```python
        # window, so switching in early and then STAYING through the
```

The scheduler is rewarded for remaining on the band.

**Line 764**

```python
        # real arrival is what actually gets rewarded.
```

Completes the rationale.

**Line 765**

```python
        dist = max(0.0, dist - self.switch_lead_steps)
```

Reduces the effective distance by the configured lead, never allowing it below zero.

**Line 766**

```python
        sigma = self.jitter_estimate[band]
```

Uses the band-specific timing width as the Gaussian standard deviation.

**Line 767**

```python
        return math.exp(-(dist ** 2) / (2 * sigma ** 2))
```

Calculates the Gaussian score:

```
exp(-distance² / (2 × sigma²))
```

The score is:

- Near `1` at predicted times
- Lower farther away from the prediction

---

# PRI-aware band selection

## Lines 769–785

**Line 769**

```python
    def choose_bands(self, k):
```

Defines the PRI-aware multi-band selection method.

**Line 770**

```python
        self.t += 1
```

Advances the scheduler clock.

**Line 771**

```python
        if self.t <= self.warmup_steps:
```

Checks whether the scheduler remains in warm-up.

**Line 772**

```python
            for b in range(self.n_bands):
```

Iterates over all bands.

**Line 773**

```python
                self._propagate(b)
```

Advances Markov beliefs during warm-up.

**Line 774**

```python
            return self._warmup_bands(k)
```

Uses the shuffled warm-up policy instead of learned scoring.

**Line 775**

```python
        for b in range(self.n_bands):
```

After warm-up, iterates over all bands again.

**Line 776**

```python
            self._propagate(b)
```

Updates each band's Markov belief.

**Line 777**

```python
        scores = []
```

Creates an empty list for final band scores.

**Line 778**

```python
        for b in range(self.n_bands):
```

Calculates a score for each band.

**Line 779**

```python
            ucb_bonus = self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
```

Calculates the UCB exploration bonus.

**Line 780**

```python
            conf = min(self.confidence[b], self.max_blend_confidence)
```

Caps the confidence used for blending.

The underlying confidence remains unchanged; only the score blend is capped.

**Line 781**

```python
            periodic = self._periodicity_score(b, self.t)
```

Calculates the predicted periodicity score.

**Line 782**

```python
            blended = (1 - conf) * self.belief[b] + conf * self.periodicity_weight * periodic
```

Combines Markov belief and periodic prediction.

When confidence is:

- `0`: use only Markov belief
- Between `0` and `1`: blend both
- `1`: use periodicity exclusively, apart from weighting and exploration

**Line 783**

```python
            scores.append(self.priority[b] * blended + ucb_bonus)
```

Adds the final score.

Priority scales exploitation, while UCB remains unweighted.

**Line 784**

```python
        order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
```

Sorts all band indices by descending score.

**Line 785**

```python
        return order[:k]
```

Returns the highest-scoring `k` bands.

**Line 786**

Blank line.

---

# Learning from hits

## Lines 787–798

**Line 787**

```python
    def update(self, band, observed_on):
```

Defines the feedback method.

**Line 788**

```python
        super().update(band, observed_on)
```

Calls the parent implementation.

This updates:

- Markov transition counts
- Direct belief
- Scan count

**Line 789**

```python
        if observed_on:
```

Only records timing information for positive observations.

Misses do not provide confirmed pulse times.

**Line 790**

```python
            times = self.hit_times[band]
```

Retrieves the ordinary sliding hit-time history.

**Line 791**

```python
            times.append(self.t)
```

Records the current scheduler time as a confirmed hit.

**Line 792**

```python
            if len(times) > self.history_len:
```

Checks whether the ordinary history is too long.

**Line 793**

```python
                del times[0]
```

Removes the oldest hit time to maintain a sliding window.

**Line 794**

```python
            stagger_times = self.stagger_hit_times[band]
```

Retrieves the longer staggered-model history.

**Line 795**

```python
            stagger_times.append(self.t)
```

Adds the current hit to the stagger history.

**Line 796**

```python
            if len(stagger_times) > self.stagger_history_len:
```

Checks whether the staggered history exceeds its limit.

**Line 797**

```python
                del stagger_times[0]
```

Removes the oldest staggered hit.

**Line 798**

```python
            self._update_pri_model(band)
```

Recalculates the band's periodicity model after every confirmed hit.

This may:

- Update a uniform PRI estimate
- Install a staggered model
- Clear an invalid model
- Update confidence and jitter

**Lines 799–800**

Blank lines before comparison functions.

---

# `run_comparison()`

## Lines 801–827

**Line 801**

```python
def run_comparison():
```

Defines a standard beacon-scenario comparison.

**Line 802**

```python
    n_bands = 36
```

Uses 36 bands.

**Line 803**

```python
    n_steps = 4000
```

Runs for 4,000 steps.

**Line 804**

```python
    scenario = make_scenario(n_bands)
```

Creates the standard mixed-emitter scenario.

**Line 805**

Blank line.

**Line 806**

```python
    print(f"Scenario: {n_bands} bands, {n_steps} steps, 4 concurrent emitters "
```

Begins printing the scenario description.

**Line 807**

```python
          f"(2 Markov comms, 1 periodic beacon [bands 2,5,6 -- true period 12 steps], "
```

Documents the beacon's bands and 12-step period.

**Line 808**

```python
          f"1 frequency-agile threat)\n")
```

Completes the description.

**Line 809**

Blank line.

**Line 810**

```python
    for k in (1, 2):
```

Runs comparisons with one and two scanned channels.

**Line 811**

```python
        random.seed(7)
```

Resets the random seed for reproducibility.

**Line 812**

```python
        print(f"--- k_channels = {k} ---")
```

Prints the current channel count.

**Line 813**

```python
        schedulers = {
```

Starts the scheduler dictionary.

**Line 814**

```python
            "RoundRobin (open-loop baseline)": RoundRobinScheduler(n_bands),
```

Creates the round-robin scheduler.

**Line 815**

```python
            "BeliefUCB (Markov-only, learned)": BeliefUCBScheduler(n_bands, ucb_c=0.5),
```

Creates the Markov/UCB scheduler.

**Line 816**

```python
            "PRIAware (Markov + periodicity, learned)": PRIAwareScheduler(n_bands, ucb_c=0.5),
```

Creates the new PRI-aware scheduler.

**Line 817**

```python
        }
```

Closes the scheduler dictionary.

**Line 818**

```python
        header = (f"{'Scheduler':42s} | {'Interception %':>15s} | "
```

Begins the comparison table header.

**Line 819**

```python
                  f"{'Avg Reward/step':>16s} | {'Avg Intercept Delay':>20s}")
```

Completes the header.

**Line 820**

```python
        print(header)
```

Prints the header.

**Line 821**

```python
        print("-" * len(header))
```

Prints the separator.

**Line 822**

```python
        for name, sched in schedulers.items():
```

Iterates over each scheduler.

**Line 823**

```python
            stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
```

Runs one episode with the current channel count.

**Line 824**

```python
            r = stats.report()
```

Builds the summary report.

**Line 825**

```python
            print(f"{name:42s} | {r['interception_ratio']*100:14.1f}% | "
```

Prints the scheduler name and interception percentage.

**Line 826**

```python
                  f"{r['avg_reward_per_step']:16.3f} | {str(r['avg_intercept_delay']):>20s}")
```

Prints average reward and average interception delay.

**Line 827**

```python
        print()
```

Separates the one-channel and two-channel output sections.

---

## PRI diagnostic output: lines 829–845

**Line 829**

```python
    # Diagnostic: did it actually learn the true beacon period?
```

Introduces a diagnostic run focused on period estimation.

**Line 830**

```python
    random.seed(7)
```

Resets the random generator.

**Line 831**

```python
    pri_sched = PRIAwareScheduler(n_bands, ucb_c=0.5)
```

Creates a fresh PRI-aware scheduler.

**Line 832**

```python
    run_episode(scenario, pri_sched, n_steps, n_bands, k_channels=1)
```

Runs the scheduler on the beacon scenario with one channel.

**Line 833**

```python
    print("PRI diagnostic (true beacon period = 12 steps, on bands 2/5/6):")
```

Prints the known ground truth for the beacon.

**Line 834**

```python
    for b in (2, 5, 6):
```

Examines the three beacon bands.

**Line 835**

```python
        pri, conf = pri_sched.pri_estimate[b], pri_sched.confidence[b]
```

Reads each band's estimated PRI and confidence.

**Line 836**

```python
        if pri is not None:
```

Checks whether a PRI estimate exists.

**Line 837**

```python
            print(f"  band {b} (beacon):        estimated PRI = {pri:5.1f}  confidence = {conf:.2f}")
```

Prints the estimated period and confidence.

**Line 838**

```python
        else:
```

Handles bands with no estimate.

**Line 839**

```python
            print(f"  band {b} (beacon):        not enough hits observed yet")
```

Reports insufficient evidence.

**Line 840**

```python
    for b in (1, 4, 0, 3, 7):
```

Examines non-beacon bands:

- Communications bands 1 and 4
- Agile-threat bands 0, 3, and 7

**Line 841**

```python
        pri, conf = pri_sched.pri_estimate[b], pri_sched.confidence[b]
```

Reads the estimate and confidence.

**Line 842**

```python
        if pri is not None:
```

Checks whether the scheduler found a period.

**Line 843**

```python
            print(f"  band {b} (comm/agile):    estimated PRI = {pri:5.1f}  confidence = {conf:.2f}  (should stay low)")
```

Prints the estimate while warning that non-periodic bands should not achieve high confidence.

**Line 844**

```python
        else:
```

Handles the no-estimate case.

**Line 845**

```python
            print(f"  band {b} (comm/agile):    not enough hits observed yet")
```

Reports that the scheduler did not have enough observations.

**Lines 846–847**

Blank lines before the sparse comparison.

---

# `run_sparse_comparison()`

## Lines 848–859

**Line 848**

```python
def run_sparse_comparison():
```

Defines a comparison designed specifically for the sparse radar.

**Line 849**

```python
    n_bands = 36
```

Uses 36 bands.

**Line 850**

```python
    n_steps = 4000
```

Runs for 4,000 steps.

**Line 851**

```python
    warmup = 800   # brief open-loop sweep so the sparse radar gets enough
```

Sets an 800-step warm-up.

**Line 852**

```python
                   # early samples for the PRI estimator to lock on (see
```

Explains why warm-up is needed.

**Line 853**

```python
                   # module docstring / write-up: this is a real
```

Points to the broader exploration/exploitation discussion.

**Line 854**

```python
                   # exploration/exploitation trade-off, not free)
```

Warm-up consumes time that could otherwise be used for exploitation.

**Line 855**

```python
    scenario = make_sparse_scenario(n_bands)
```

Creates the sparse fixed-PRI radar environment.

**Line 856**

Blank line.

**Line 857**

```python
    print(f"Sparse scenario: {n_bands} bands, {n_steps} steps ({warmup}-step warmup) -- a "
```

Begins printing the sparse scenario description.

**Line 858**

```python
          f"single-pulse-per-cycle fixed-PRI radar (band 5, true period 12 steps, ON for "
```

Documents the radar's band, period, and one-step pulse duration.

**Line 859**

```python
          f"just 1 step per cycle) alongside 2 Markov comms + 1 agile threat\n")
```

Completes the description.

---

## Sparse comparison loop: lines 861–878

**Line 861**

```python
    for k in (1, 2):
```

Runs one-channel and two-channel comparisons.

**Line 862**

```python
        random.seed(11)
```

Uses a fixed seed for reproducibility.

**Line 863**

```python
        print(f"--- k_channels = {k} ---")
```

Prints the current channel count.

**Line 864**

```python
        schedulers = {
```

Starts the scheduler dictionary.

**Line 865**

```python
            "RoundRobin (open-loop baseline)": RoundRobinScheduler(n_bands),
```

Creates the round-robin baseline.

**Line 866**

```python
            "BeliefUCB (Markov-only, learned)": BeliefUCBScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
```

Creates the Markov/UCB scheduler with the 800-step warm-up.

**Line 867**

```python
            "PRIAware (Markov + periodicity, learned)": PRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
```

Creates the PRI-aware scheduler with the same warm-up.

**Line 868**

```python
        }
```

Closes the dictionary.

**Line 869**

```python
        header = (f"{'Scheduler':42s} | {'Interception %':>15s} | "
```

Begins the output table header.

**Line 870**

```python
                  f"{'Avg Reward/step':>16s} | {'Avg Intercept Delay':>20s}")
```

Completes the header.

**Line 871**

```python
        print(header)
```

Prints the header.

**Line 872**

```python
        print("-" * len(header))
```

Prints the separator line.

**Line 873**

```python
        for name, sched in schedulers.items():
```

Iterates over the schedulers.

**Line 874**

```python
            stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
```

Runs an episode for the current scheduler.

**Line 875**

```python
            r = stats.report()
```

Builds the summary dictionary.

**Line 876**

```python
            print(f"{name:42s} | {r['interception_ratio']*100:14.1f}% | "
```

Prints interception percentage.

**Line 877**

```python
                  f"{r['avg_reward_per_step']:16.3f} | {str(r['avg_intercept_delay']):>20s}")
```

Prints average reward and interception delay.

**Line 878**

```python
        print()
```

Adds spacing between channel-count sections.

---

## Explaining why aggregate interception can mislead: lines 880–883

**Line 880**

```python
    print("The blended interception % above can be misleading here -- it's dominated by\n"
```

Warns that the aggregate interception percentage may not reflect the hard target's performance.

**Line 881**

```python
          "the loud, near-always-on comm-1 channel. What actually matters for an EW system\n"
```

Explains that the communications emitter produces many easy hits.

**Line 882**

```python
          "is PER-EMITTER capture, especially of the one threat that's genuinely hard to\n"
```

States that per-emitter capture is more useful.

**Line 883**

```python
          "predict without a periodicity model:\n")
```

Identifies the sparse radar as the difficult target.

---

# Per-emitter capture function

## Lines 885–905

**Line 885**

```python
    def per_emitter_capture(sched_cls, warmup):
```

Defines an inner helper that measures capture separately for the radar and `comm-1`.

**Line 886**

```python
        random.seed(11)
```

Resets randomness for the individual scheduler run.

**Line 887**

```python
        sched = sched_cls(n_bands, ucb_c=0.5, warmup_steps=warmup)
```

Creates the requested scheduler class with UCB and warm-up settings.

**Line 888**

```python
        env = scenario()
```

Creates a fresh sparse environment.

**Line 889**

```python
        radar_pulses = radar_caught = 0
```

Initializes:

- Total radar pulses
- Radar pulses caught by the scheduler

**Line 890**

```python
        comm1_on = comm1_caught = 0
```

Initializes:

- Total active occurrences of `comm-1`
- `comm-1` occurrences caught

**Line 891**

```python
        for t in range(n_steps):
```

Begins the manual episode loop.

**Line 892**

```python
            status = env.step()
```

Advances the environment.

**Line 893**

```python
            bands = sched.choose_bands(1)
```

Asks the scheduler to select one band.

The result is still a list because v2 uses the multi-channel interface.

**Line 894**

```python
            for b in bands:
```

Iterates over the selected band list.

**Line 895**

```python
                sched.update(b, status[b])
```

Feeds the observation back into the scheduler.

**Line 896**

```python
            if t > warmup:
```

Only evaluates post-warm-up performance.

**Line 897**

```python
                if status[5]:
```

Checks whether the sparse radar is transmitting on band 5.

**Line 898**

```python
                    radar_pulses += 1
```

Counts the radar pulse.

**Line 899**

```python
                    if 5 in bands:
```

Checks whether the scheduler selected the radar band.

**Line 900**

```python
                        radar_caught += 1
```

Counts a successful radar interception.

**Line 901**

```python
                if status[1]:
```

Checks whether `comm-1` is ON.

**Line 902**

```python
                    comm1_on += 1
```

Counts an active `comm-1` step.

**Line 903**

```python
                    if 1 in bands:
```

Checks whether band 1 was selected.

**Line 904**

```python
                        comm1_caught += 1
```

Counts a successful `comm-1` capture.

**Line 905**

```python
        return radar_pulses, radar_caught, comm1_on, comm1_caught, sched
```

Returns:

- Total radar pulses
- Caught radar pulses
- Total `comm-1` active steps
- Caught `comm-1` steps
- The scheduler itself, so its final PRI estimate can be inspected

---

## Printing per-emitter results: lines 907–913

**Line 907**

```python
    for name, cls in [("BeliefUCB", BeliefUCBScheduler), ("PRIAware", PRIAwareScheduler)]:
```

Runs the per-emitter measurement for both scheduler types.

**Line 908**

```python
        rp, rc, cp, cc, sched = per_emitter_capture(cls, warmup)
```

Executes the helper and unpacks its results.

**Line 909**

```python
        pri = getattr(sched, "pri_estimate", [None] * n_bands)[5]
```

Reads band 5's PRI estimate.

`getattr()` provides a fallback list in case the scheduler has no `pri_estimate` attribute.

**Line 910**

```python
        conf = getattr(sched, "confidence", [0.0] * n_bands)[5]
```

Reads band 5's confidence, again with a fallback.

**Line 911**

```python
        print(f"  {name:10s}: fixed-PRI radar caught {rc:4d}/{rp} ({100*rc/rp:5.1f}%)   "
```

Prints the radar capture count and percentage.

**Line 912**

```python
              f"comm-1 caught {cc:4d}/{cp} ({100*cc/cp:5.1f}%)   "
```

Prints the `comm-1` capture count and percentage.

**Line 913**

```python
              f"[band5 estimated PRI={pri}, confidence={conf:.2f]")
```

Prints the final radar PRI estimate and confidence.

**Lines 914–915**

Blank lines before the module guard.

---

# Direct execution

## Lines 916–919

**Line 916**

```python
if __name__ == "__main__":
```

Checks whether the file is being run directly.

**Line 917**

```python
    run_comparison()
```

Runs the ordinary beacon comparison first.

**Line 918**

```python
    print("=" * 100)
```

Prints a long separator between the two experiments.

**Line 919**

```python
    run_sparse_comparison()
```

Runs the sparse fixed-PRI radar comparison.

---

# What this file adds to the project

`scan_scheduler_v3_pri.py` adds the first real predictive model.

Its main flow is:

```
Observed hit
   ↓
Store hit time
   ↓
Generate candidate periods
   ↓
Refine candidates with least squares
   ↓
Require enough distinct cycles
   ↓
Calculate confidence
   ↓
Predict next pulse phase
   ↓
Blend periodic score with Markov belief
   ↓
Select the best bands
```

It supports two kinds of periodic behavior:

1. **Uniform PRI**

   One consistent interval between pulses.
2. **Staggered PRI**

   A repeating sequence of different intervals.

It also includes safeguards against:

- Harmonic lock-on
- Off-by-one candidate errors
- Dense persistent bands being mistaken for periodic signals
- False locks based on too few cycles
- Multi-step bursts receiving an excessively narrow score
- Receiver switching costs causing the scheduler to arrive too late



Completed and checked off `scan_scheduler_v4_persistent.py`.

# `scan_scheduler_v4_persistent.py` — line-by-line explanation

## Module documentation

### Lines 1–61

**Line 1**

```python
"""
```

Starts the module documentation string.

**Line 2**

```
scan_scheduler_v4_persistent.py
```

Names the module.

**Line 3**

```
=================================
```

Documentation separator.

**Line 4**

```
Fixes the seed-sensitive lock-on bug diagnosed in diagnose_pri_lockon.py:
```

States the purpose of this version: fix inconsistent PRI lock-on across random seeds.

**Line 5**

Blank documentation line.

**Line 6**

```
  PRIAwareScheduler requires >= 8 confirmed hits on a band before it will
```

Explains that v3 needs at least eight confirmed hits before attempting PRI estimation.

**Line 7**

```
  even attempt a PRI estimate. The fixed 800-step warmup sweep gives the
```

Describes the warm-up process used in the sparse-radar experiment.

**Line 8**

```
  sparse fixed-PRI radar band an EXPECTED ~8.3 confirmed hits (100 warmup
```

A band scanned approximately 100 times should theoretically produce about 8.3 hits.

**Line 9**

```
  scans / 12-step period) -- right on top of that threshold, so whether a
```

Because the expected count is close to the threshold, random variation matters greatly.

**Line 10**

```
  given seed crosses it is close to a coin flip (Binomial noise on ~100
```

Some seeds produce enough hits; others do not.

**Line 11**

```
  trials at p=1/12). Worse: once warmup ends, a band that came up short
```

The probability of hitting the sparse radar on any given scan is approximately `1/12`.

**Line 12**

```
  gets almost no further scans (its UCB exploration credit is already
```

After warm-up, UCB may no longer explore the band much.

**Line 13**

```
  spent from the 100 warmup visits, and its Markov belief is near-zero
```

The band looks both well-explored and mostly inactive.

**Line 14**

```
  since it's off ~92% of the time) -- so a seed that didn't cross the
```

The Markov estimate also discourages future scans.

**Line 15**

```
  threshold during warmup is locked out FOREVER. That combination turns
```

A missed threshold during warm-up becomes a permanent failure.

**Line 16**

```
  ordinary sampling noise into a permanent, binary 0%-or-100% outcome
```

Small random differences produce extreme final outcomes.

**Line 17**

```
  (measured: 30.0% +/- 48.3% capture across 10 seeds).
```

Documents the observed instability.

**Line 18**

Blank documentation line.

**Line 19**

```
The fix: track TOTAL confirmed hits per band (total_hits, never
```

Introduces the v4 solution: keep a lifetime hit count.

**Line 20**

```
truncated -- separate from the sliding hit_times window used for PRI
```

The lifetime count is separate from the sliding history used for fitting.

**Line 21**

```
estimation itself), and give a band that HASN'T YET ACCUMULATED ENOUGH
```

Bands below the required hit count receive additional attention.

**Line 22**

```
HITS TO EVEN ATTEMPT A PRI ESTIMATE (total_hits < required_hits, the
```

The condition is based on total confirmed hits.

**Line 23**

```
same threshold _update_pri_model itself uses) a PERSISTENT
```

The threshold is aligned with the v3 estimator's minimum-hit requirement.

**Line 24**

```
characterization bonus that decays with its OWN HIT COUNT rather than
```

The bonus decreases as positive evidence accumulates.

**Line 25**

```
with total scan count:
```

This is the important distinction from ordinary UCB exploration.

**Line 26**

Blank documentation line.

**Line 27**

```
    char_bonus(b) = char_bonus_c * sqrt(log(t+2) / (total_hits[b] + 1))
```

Defines the characterization bonus formula.

The bonus is larger when:

- Time increases
- The band has few confirmed hits

**Line 28**

Blank documentation line.

**Line 29**

```
This targets the actual scarce resource -- confirmed ON samples, not
```

Explains that the scheduler needs positive observations, not merely scans.

**Line 30**

```
scans in general -- so a band that was scanned 100 times during warmup
```

A band may have many scans but few hits.

**Line 31**

```
but only produced 6 hits still looks "worth probing" after warmup,
```

The characterization bonus keeps such a band eligible.

**Line 32**

```
unlike the existing UCB term (which sees scan_count=100 and treats the
```

Ordinary UCB considers the band sufficiently explored.

**Line 33**

```
band as thoroughly explored).
```

Completes the contrast.

**Line 34**

Blank documentation line.

**Line 35**

```
TWO bounds were needed, found by testing each in turn -- a single
```

Introduces two safeguards needed to make the bonus safe.

**Line 36**

```
gate wasn't enough:
```

A single condition caused other failure modes.

**Line 37**

Blank documentation line.

**Line 38**

```
  1. Gate on total_hits < required_hits, NOT on "confidence still
```

The first safeguard uses total hits rather than confidence.

**Line 39**

```
     below threshold." Gating on confidence alone means a genuinely
```

Confidence is not the right condition for deciding whether a band deserves exploration.

**Line 40**

```
     aperiodic band (e.g. the frequency-agile threat, split across 4
```

An agile emitter can remain low-confidence forever.

**Line 41**

```
     bands so none of them individually rack up many hits) NEVER
```

Its individual bands may never accumulate enough regular evidence.

**Line 42**

```
     earns periodicity confidence, so it gets chased forever,
```

A confidence-only bonus would keep rewarding it indefinitely.

**Line 43**

```
     permanently stealing scan budget from everything else --
```

This harms other targets.

**Line 44**

```
     confirmed by a first test tanking comm-1 capture from ~85% to
```

Documents the measured degradation.

**Line 45**

```
     ~21%.
```

Completes the result.

**Line 46**

Blank documentation line.

**Line 47**

```
  2. ALSO cap total scan attempts per band (give_up_after_scans),
```

The second safeguard caps how many times an underperforming band may be scanned.

**Line 48**

```
     independent of hit count. A band with a total_hits gate alone
```

A hit-only condition is insufficient.

**Line 49**

```
     still fails catastrophically for a band that is simply NEVER on
```

Always-silent bands would never gain hits.

**Line 50**

```
     (e.g. an unassigned band with no emitter at all): total_hits
```

Provides an example.

**Line 51**

```
     stays 0 forever, so 1/(total_hits+1) never decays, and that one
```

The bonus would remain high forever.

**Line 52**

```
     band absorbed ~85% of the ENTIRE post-warmup budget in testing
```

Documents the resulting scan starvation.

**Line 53**

```
     (3300 of 4000 total scans went to a single always-silent band).
```

Provides the measured count.

**Line 54**

```
     Capping scan attempts means the scheduler gives up on a band
```

The scan cap causes eventual abandonment.

**Line 55**

```
     that isn't paying off within a bounded number of tries, exactly
```

This is a controlled exploration policy.

**Line 56**

```
     like the original UCB term already does for confidence in
```

The cap preserves the general spirit of UCB exploration.

**Line 57**

```
     general -- this bonus just gets its own, hit-count-aware version
```

The new bonus is specialized for positive evidence.

**Line 58**

```
     of that same discipline.
```

Completes the explanation.

**Line 59**

Blank documentation line.

**Line 60**

```
Run:  python3 scan_scheduler_v4_persistent.py
```

Documents the direct execution command.

**Line 61**

```python
"""
```

Ends the module documentation.

---

## Imports

### Lines 62–67

**Line 62**

Blank line separating documentation from imports.

**Line 63**

```python
import math
```

Imports mathematical functions used by the exploration and characterization formulas.

**Line 64**

```python
from typing import List
```

Imports the `List` type annotation.

**Line 65**

Blank line.

**Line 66**

```python
from scan_scheduler_v3_pri import PRIAwareScheduler
```

Imports the v3 PRI-aware scheduler.

The v4 scheduler inherits nearly all PRI-estimation behavior from it.

**Line 67**

Blank line.

---

# `PersistentPRIAwareScheduler`

## Constructor: lines 69–93

**Line 69**

```python
class PersistentPRIAwareScheduler(PRIAwareScheduler):
```

Defines the v4 scheduler as a subclass of `PRIAwareScheduler`.

It inherits:

- Markov belief tracking
- UCB exploration
- PRI fitting
- Staggered PRI support
- Periodicity scoring
- Warm-up handling

**Line 70**

```python
    def __init__(self, n_bands, char_bonus_c: float = 1.5,
```

Defines the constructor.

`char_bonus_c` controls the strength of the new characterization bonus.

**Line 71**

```python
                 required_hits: int = 8, give_up_after_scans: int = 300,
```

Adds two new controls:

- `required_hits`: number of positive observations needed before characterization is complete
- `give_up_after_scans`: scan limit for bands that remain under-characterized

**Line 72**

```python
                 **kwargs):
```

Accepts all other constructor arguments and forwards them to the parent class.

**Line 73**

```python
        super().__init__(n_bands, **kwargs)
```

Initializes `PRIAwareScheduler`.

**Line 74**

```python
        self.char_bonus_c = char_bonus_c
```

Stores the characterization bonus coefficient.

**Line 75**

```python
        # Must match the >= 8 threshold _update_pri_model uses internally
```

Documents that the required-hit threshold should match v3's internal minimum.

**Line 76**

```python
        # -- the bonus exists purely to help bands REACH that sample
```

Explains that the bonus is intended only to gather enough samples.

**Line 77**

```python
        # size, not to chase periodicity confidence indefinitely.
```

It should not cause endless pursuit of bands that never produce evidence.

**Line 78**

```python
        self.required_hits = required_hits
```

Stores the required positive-hit count.

**Line 79**

```python
        # Bound on total scans (warmup + post-warmup) a band gets while
```

Introduces the scan-attempt cap.

**Line 80**

```python
        # still under required_hits, before the scheduler gives up on
```

A band can eventually lose its characterization bonus.

**Line 81**

```python
        # ever characterizing it. Needed for bands with duty cycle ~0
```

This is important for nearly silent bands.

**Line 82**

```python
        # (or literally no emitter) where total_hits never climbs no
```

Such bands may never reach the required hit count.

**Line 83**

```python
        # matter how many times it's scanned -- without this, such a
```

Without a cap, they would remain attractive forever.

**Line 84**

```python
        # band's bonus never decays and it can consume most of the
```

The scheduler could waste most of its scan budget.

**Line 85**

```python
        # remaining run (observed: one always-silent band absorbed 3300
```

Documents the observed failure.

**Line 86**

```python
        # of 4000 total scans without this cap).
```

Completes the example.

**Line 87**

```python
        self.give_up_after_scans = give_up_after_scans
```

Stores the scan-attempt limit.

**Line 88**

```python
        # Total confirmed hits ever seen on this band -- unlike
```

Introduces the lifetime hit counter.

**Line 89**

```python
        # hit_times (capped at history_len for the PRI estimator itself),
```

Contrasts it with the sliding PRI history.

**Line 90**

```python
        # this never shrinks, so it's a clean signal of "how much ON
```

The counter retains all confirmed positive observations.

**Line 91**

```python
        # evidence have we actually accumulated," independent of how
```

It measures accumulated evidence, not recent activity alone.

**Line 92**

```python
        # long ago the sliding window discarded it.
```

Old evidence remains represented.

**Line 93**

```python
        self.total_hits: List[int] = [0] * n_bands
```

Creates a lifetime confirmed-hit counter for every band.

---

## Updating hit counts: lines 95–98

**Line 95**

```python
    def update(self, band, observed_on):
```

Overrides the parent update method.

**Line 96**

```python
        super().update(band, observed_on)
```

Runs all inherited update logic first.

This updates the Markov model and PRI history.

**Line 97**

```python
        if observed_on:
```

Checks whether the latest observation was a confirmed hit.

**Line 98**

```python
            self.total_hits[band] += 1
```

Increments the lifetime hit count for the band.

---

# Persistent scoring

## `choose_bands()`: lines 100–123

**Line 100**

```python
    def choose_bands(self, k):
```

Defines the v4 band-selection method.

**Line 101**

```python
        self.t += 1
```

Advances the scheduler clock.

**Line 102**

```python
        if self.t <= self.warmup_steps:
```

Checks whether the scheduler is still warming up.

**Line 103**

```python
            for b in range(self.n_bands):
```

Iterates over all bands.

**Line 104**

```python
                self._propagate(b)
```

Advances each band's Markov belief.

**Line 105**

```python
            return self._warmup_bands(k)
```

Uses the inherited shuffled warm-up policy.

**Line 106**

```python
        for b in range(self.n_bands):
```

After warm-up, iterates over every band again.

**Line 107**

```python
            self._propagate(b)
```

Predicts each band's next activity probability.

**Line 108**

```python
        scores = []
```

Creates an empty list for final band scores.

**Line 109**

```python
        for b in range(self.n_bands):
```

Begins scoring each band.

**Line 110**

```python
            ucb_bonus = self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
```

Calculates the inherited UCB exploration bonus.

It decreases as the band's scan count increases.

**Line 111**

```python
            conf = min(self.confidence[b], self.max_blend_confidence)
```

Caps the periodicity confidence used for blending.

**Line 112**

```python
            periodic = self._periodicity_score(b, self.t)
```

Calculates how close the current time is to the predicted periodic event.

**Line 113**

```python
            blended = (1 - conf) * self.belief[b] + conf * self.periodicity_weight * periodic
```

Combines:

- Markov belief
- Periodic prediction
- Periodicity weight

This is the same basic blend used by v3.

**Line 114**

Blank line separating ordinary scoring from the new characterization bonus.

**Line 115**

```python
            char_bonus = 0.0
```

Initializes the new bonus to zero.

**Line 116**

```python
            if (self.total_hits[b] < self.required_hits
```

Checks whether the band has fewer confirmed hits than required.

**Line 117**

```python
                    and self.scan_count[b] < self.give_up_after_scans):
```

Also checks whether the band has not exceeded its total scan limit.

The bonus is active only when both conditions are true.

**Line 118**

```python
                char_bonus = self.char_bonus_c * math.sqrt(
```

Begins calculating the characterization bonus.

**Line 119**

```python
                    math.log(self.t + 2) / (self.total_hits[b] + 1))
```

Completes the formula:

```
char_bonus =
    char_bonus_c × sqrt(log(t + 2) / (total_hits[b] + 1))
```

The bonus decreases as the lifetime hit count rises.

**Line 120**

Blank line.

**Line 121**

```python
            scores.append(self.priority[b] * blended + ucb_bonus + char_bonus)
```

Builds the final score.

Unlike the exploitation score, the characterization bonus is added directly and is not multiplied by priority.

The final score is:

```
priority × blended periodic/belief score
+ UCB exploration
+ characterization bonus
```

**Line 122**

```python
        order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
```

Sorts band indices from highest score to lowest.

**Line 123**

```python
        return order[:k]
```

Returns the top `k` bands.

**Lines 124–125**

Blank lines before the executable test section.

---

# Direct execution and sanity check

## Lines 126–149

**Line 126**

```python
if __name__ == "__main__":
```

Checks whether the file is being executed directly.

**Line 127**

```python
    import random
```

Imports `random` locally because it is only needed for the standalone test.

**Line 128**

```python
    from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
```

Imports the Markov-only baseline and episode runner.

**Line 129**

```python
    from scan_scheduler_v3_pri import make_sparse_scenario
```

Imports the sparse fixed-PRI scenario builder.

**Line 130**

Blank line.

**Line 131**

```python
    n_bands = 36
```

Sets the test to use 36 frequency bands.

**Line 132**

```python
    n_steps = 4000
```

Sets each test episode to 4,000 steps.

**Line 133**

```python
    warmup = 800
```

Sets the warm-up period to 800 steps.

**Line 134**

```python
    scenario = make_sparse_scenario(n_bands)
```

Creates the sparse-radar scenario factory.

**Line 135**

```python
    random.seed(11)
```

Sets a reproducible random seed.

**Line 136**

```python
    print("Quick single-seed sanity check (seed=11, matches earlier reports):\n")
```

Prints a heading describing the test.

**Line 137**

```python
    schedulers = {
```

Starts a dictionary of scheduler instances.

**Line 138**

```python
        "BeliefUCB (Markov-only)": BeliefUCBScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
```

Creates the v2 Markov/UCB baseline.

**Line 139**

```python
        "PRIAware (original)": PRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
```

Creates the original v3 PRI-aware scheduler.

**Line 140**

```python
        "PRIAware (persistent, fixed)": PersistentPRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
```

Creates the v4 scheduler with persistent characterization.

**Line 141**

```python
    }
```

Closes the scheduler dictionary.

**Line 142**

```python
    header = (f"{'Scheduler':32s} | {'Interception %':>15s} | {'Avg Reward/step':>16s}")
```

Builds the output table header.

**Line 143**

```python
    print(header)
```

Prints the header.

**Line 144**

```python
    print("-" * len(header))
```

Prints a separator line matching the header width.

**Line 145**

```python
    for name, sched in schedulers.items():
```

Iterates over the three scheduler instances.

**Line 146**

```python
        random.seed(11)
```

Resets the seed before each scheduler run.

This attempts to make each comparison use the same random sequence.

**Line 147**

```python
        stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=1)
```

Runs one 4,000-step, single-channel episode.

**Line 148**

```python
        r = stats.report()
```

Converts the raw statistics into a summary dictionary.

**Line 149**

```python
        print(f"{name:32s} | {r['interception_ratio']*100:14.1f}% | {r['avg_reward_per_step']:16.3f}")
```

Prints:

- Scheduler name
- Interception percentage
- Average reward per step

---

# What this file changes

`scan_scheduler_v4_persistent.py` does not replace the PRI estimator. Instead, it changes **how the scheduler allocates exploration before PRI estimation succeeds**.

The key problem is:

```
A sparse radar may be scanned many times but produce too few hits.
```

The v3 scheduler then incorrectly treats it as fully explored.

The v4 solution adds:

```
Lifetime hit count
+ hit-aware characterization bonus
+ maximum scan-attempt cap
```

This prevents both failure modes:

1. Sparse periodic emitters being permanently abandoned.
2. Silent or aperiodic bands being explored forever.



Completed and checked off `scan_scheduler_v5_hedge.py`.

# `scan_scheduler_v5_hedge.py` — line-by-line explanation

## Module documentation

### Lines 1–73

**Line 1**

```python
"""
```

Starts the module documentation string.

**Line 2**

```
scan_scheduler_v5_hedge.py
```

Names the module.

**Line 3**

```
==========================
```

Documentation separator.

**Line 4**

```
HedgeBlendedPRIAwareScheduler: replaces PRIAwareScheduler's hand-tuned
```

Introduces the scheduler and explains that it replaces v3's manually controlled blend.

**Line 5**

```
confidence-based blend (`blended = (1-conf)*belief + conf*periodicity`,
```

Shows the original formula used to mix Markov belief and periodicity.

**Line 6**

```
conf capped by max_blend_confidence) with a per-band online-learned
```

Explains that v5 replaces the fixed confidence cap with learned weights.

**Line 7**

```
trust weight between two "experts" -- the Markov belief score and the
```

The two experts are:

- Markov belief
- Periodicity prediction

**Line 8**

```
periodicity score -- updated via multiplicative-weights (Hedge) from
```

The trust weights are updated using the Hedge algorithm.

**Line 9**

```
each expert's realized prediction error.
```

Each expert's performance is evaluated against the observed result.

**Line 10**

Blank documentation line.

**Line 11**

```
WHY: confidence_scale (scan_scheduler_v3_pri.py), max_blend_confidence
```

Lists earlier manually tuned parameters.

**Line 12**

```
(added for the real-data stagger case), and char_bonus_c
```

Adds the v4 characterization parameter to the list.

**Line 13**

```
(scan_scheduler_v4_persistent.py) have each independently shown the
```

Explains that each parameter had similar limitations.

**Line 14**

```
same pattern under sweep (tune_confidence_threshold.py; the
```

Parameter sweeps exposed the problem.

**Line 15**

```
max_blend_confidence sweep in diagnose_fullfile_regression.py): no
```

No single fixed parameter value worked everywhere.

**Line 16**

```
single fixed value serves both the synthetic sparse-radar/beacon
```

Synthetic scenarios preferred different settings.

**Line 17**

```
scenarios and real TSRD data well. Most strikingly,
```

Real data had different needs.

**Line 18**

```
diagnose_fullfile_regression.py found max_blend_confidence wants to be
```

Documents the most significant example.

**Line 19**

```
near 1.0 for the sparse-radar headline but near 0.1 for config_169.h5's
```

The ideal confidence cap varied dramatically between datasets.

**Line 20**

```
band 1 (a correctly-locked staggered PRI, confidence 1.0, whose narrow
```

The real band had a correct staggered PRI lock but narrow prediction spikes.

**Line 21**

```
spikes still crowd out belief on an already-near-saturated band) --
```

The periodic score caused the scheduler to abandon a frequently active band.

**Line 22**

```
and separately found that locked confidence isn't even stable within a
```

Confidence itself can change over time.

**Line 23**

```
single real run (drifts 1.0 -> 0.791 late in the 815,948-step replay).
```

Provides an example of confidence drift.

**Line 24**

```
A static cap can't respond to that drift; a per-band LEARNED weight
```

A fixed cap cannot adapt during a run.

**Line 25**

```
can, in principle -- that's the bet this class makes.
```

The v5 hypothesis is that learned trust weights can adapt.

**Line 26**

Blank documentation line.

**Line 27**

```
MECHANISM: per band, w_belief[b] + w_pri[b] = 1.0, initialized
```

Defines the core weight invariant.

**Line 28**

```
BELIEF-BIASED (0.8 / 0.2) rather than 50/50. This is a deliberate
```

The initial weights favor Markov belief.

**Line 29**

```
cold-start guard: the periodicity expert only ever produces a nonzero
```

Explains why belief receives the larger initial weight.

**Line 30**

```
prediction once PRIAwareScheduler's own lock gating (8-hit threshold,
```

The periodic expert is inactive until v3's safeguards accept a PRI.

**Line 31**

```
min_cycles) has already accepted a period, so the raw sample-starvation
```

The upstream PRI estimator already requires enough evidence.

**Line 32**

```
risk is already handled upstream -- but a *freshly locked*, still
```

A newly accepted period may still be uncertain.

**Line 33**

```
low-evidence periodicity estimate could still be wrong, and a belief-
```

The belief-biased starting point makes the periodic model prove itself.

**Line 34**

```
biased prior means it has to prove itself correct over several
```

The periodic expert gains trust only after successful predictions.

**Line 35**

```
observations before it's trusted as much as belief, rather than
```

This avoids immediate domination by a new model.

**Line 36**

```
instantly overriding it the way a fixed high confidence_scale can.
```

Contrasts learned trust with a fixed high-confidence blend.

**Line 37**

Blank documentation line.

**Line 38**

```
score(b) = priority[b] * (w_belief[b]*belief[b]
```

Begins the v5 score formula.

**Line 39**

```
                           + w_pri[b]*periodicity_weight*periodic(b))
```

Completes the weighted expert mixture.

**Line 40**

```
           + ucb_bonus(b)
```

Adds the ordinary UCB exploration bonus.

**Line 41**

Blank documentation line.

**Line 42**

```
After every observation on a scanned band, both experts' RAW
```

Both experts are evaluated after each valid observation.

**Line 43**

```
[0,1] predictions (belief[b], and periodic(b) WITHOUT the
```

The predictions are normalized raw values.

**Line 44**

```
periodicity_weight scale-up -- that scale-up is a score boost, not a
```

The periodicity weight is excluded from the loss calculation.

**Line 45**

```
probability estimate, and mixing it into the loss would unfairly
```

Including it would penalize the periodic expert for a deliberate score multiplier.

**Line 46**

```
penalize the periodicity expert for periodicity_weight > 1) are scored
```

The raw predictions are compared to reality.

**Line 47**

```
against the realized outcome with squared error, and weights are
```

Squared error is used as the loss function.

**Line 48**

```
updated multiplicatively:
```

Introduces the Hedge update equations.

**Line 49**

```
    loss_X = (pred_X - outcome) ** 2
```

Defines the squared prediction error.

**Line 50**

```
    w_X[b] *= exp(-eta * loss_X)
```

Reduces an expert's weight exponentially according to its loss.

**Line 51**

```
then renormalized to sum to 1, with a floor (default 0.05) on each so
```

Weights are normalized and prevented from reaching zero.

**Line 52**

```
an expert that goes cold for a while (e.g. after the confidence-drift
```

A temporarily poor expert can recover later.

**Line 53**

```
event found on real data) can still recover instead of being
```

The floor prevents permanent exclusion.

**Line 54**

```
permanently zeroed out.
```

Completes the explanation.

**Line 55**

Blank documentation line.

**Line 56**

```
SCOPE, STATED HONESTLY: this is a first-pass build. Squared-error loss
```

States that v5 is experimental.

**Line 57**

```
against a binary outcome turned out NOT to be safe as-is -- it has two
```

Raw squared error causes class-imbalance problems.

**Line 58**

```
confirmed class-imbalance failure modes (pre-lock: an unlocked expert's
```

Introduces the first failure mode.

**Line 59**

```
placeholder-0 prediction wins by never being scanned during an on-step;
```

An unlocked periodic expert predicts zero and can appear accurate on OFF observations.

**Line 60**

```
post-lock: a genuinely-locked but low-duty periodic signal's frequent,
```

Introduces the second failure mode.

**Line 61**

```
marginally-correct off-peak predictions still outweigh its rarer,
```

Frequent OFF predictions can dominate the loss.

**Line 62**

```
much-more-valuable on-peak wins). Both are fixed here: the pre-lock
```

The implementation addresses both issues.

**Line 63**

```
case via the `locked` gate (choose_bands/`_hedge_update`), the post-lock
```

The pre-lock issue is solved by not scoring an inactive periodic expert.

**Line 64**

```
case via inverse-class-frequency loss reweighting (`_hedge_update`). This is
```

The post-lock issue is solved by class-balanced loss.

**Line 65**

```
NOT the same thing as the full bandit-style/decision-relevant loss still
```

Clarifies that this is not a complete bandit loss.

**Line 66**

```
flagged below as deferred -- that would weight a LOSS by whether the two
```

A more advanced loss would consider whether the disagreement changed the selected band.

**Line 67**

```
experts' disagreement actually changed which band got scanned, a finer
```

That would measure decision impact rather than prediction error alone.

**Line 68**

```
distinction than class balance alone captures. `eta` has not been swept
```

The learning rate still needs broader validation.

**Line 69**

```
against the four reference points (sparse-radar headline, beacon k=1/k=2,
```

Lists the intended validation scenarios.

**Line 70**

```
PDW band-4 fractional-PRI, config_169.h5 band 1) the way confidence_scale
```

Adds the remaining data references.

**Line 71**

```
was swept against two -- this file ships a plausible default and an
```

The default is provisional.

**Line 72**

```
explicit script to do that sweep, not a validated one.
```

The parameter sweep is delegated to another script.

**Line 73**

```python
"""
```

Ends the module documentation.

---

## Imports

### Lines 74–79

**Line 74**

```python
import math
```

Imports `sqrt`, `log`, and `exp`, used in scoring and weight updates.

**Line 75**

```python
from typing import List, Optional
```

Imports type annotation helpers.

These are not heavily used in this file but are available for annotations.

**Line 76**

Blank line.

**Line 77**

```python
from scan_scheduler_v3_pri import PRIAwareScheduler
```

Imports the v3 PRI-aware scheduler.

**Line 78**

```python
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
```

Imports the v4 persistent-characterization scheduler.

**Line 79**

Blank line.

---

# `HedgeBlendedPRIAwareScheduler`

## Class documentation: lines 81–117

**Line 81**

```python
class HedgeBlendedPRIAwareScheduler(PersistentPRIAwareScheduler):
```

Defines the v5 scheduler.

It inherits from v4 so it can reuse:

- PRI fitting
- Staggered PRI handling
- Persistent characterization state
- Markov belief tracking
- UCB exploration

**Line 82**

```python
    """
```

Starts the class documentation.

**Line 83**

```
    Blend, choose_bands, and _hedge_update all gate on confidence[b] > 0
```

Explains that the periodicity expert is only active when a valid lock exists.

**Line 84**

```
    -- i.e. the learned weight only competes belief against periodicity
```

Hedge weighting begins only after periodicity becomes meaningful.

**Line 85**

```
    once periodicity has an ACTUAL lock to offer, falling back to plain
```

Before that, the scheduler uses belief alone.

**Line 86**

```
    belief_pred (mirroring PRIAwareScheduler's own conf=0 behavior)
```

This matches the v3 behavior when confidence is zero.

**Line 87**

```
    otherwise. That gate is load-bearing, not cosmetic -- found via
```

The gate is essential for correctness.

**Line 88**

```
    this class's own first validation pass (validate_hedge_blend.py), not
```

Its necessity was discovered experimentally.

**Line 89**

```
    guessed upfront: an unlocked periodicity expert always predicts
```

Before locking, the periodic prediction is always zero.

**Line 90**

```
    exactly 0 (a structural placeholder, not a real prediction), and
```

That zero is not meaningful evidence.

**Line 91**

```
    squared-error loss against a binary outcome rewards that "predict 0"
```

Zero prediction gets low loss on OFF observations.

**Line 92**

```
    placeholder perfectly on every OFF-step -- which for any low-duty
```

This is especially harmful for mostly OFF signals.

**Line 93**

```
    band (most comms, most of the time) means the uninformative
```

The placeholder may beat a useful nonzero predictor.

**Line 94**

```
    placeholder accumulates LOWER total loss than a genuinely calibrated
```

This creates incorrect weight updates.

**Line 95**

```
    but nonzero belief score, purely from class imbalance. Confirmed
```

The cause is the imbalance between OFF and ON observations.

**Line 96**

```
    directly: without this gate, comm-1's capture crashed from
```

Documents the measured impact.

**Line 97**

```
    PRIAware's 79.4% to 3.3% on the sparse-radar reference scenario,
```

The failure was severe.

**Line 98**

```
    because the degenerate zero-predictor won the weight competition on
```

The meaningless periodic expert gained too much weight.

**Line 99**

```
    a band it had nothing useful to say about.
```

Completes the explanation.

**Line 100**

Blank documentation line.

**Line 101**

```
    Rebased onto PersistentPRIAwareScheduler (v4), not PRIAwareScheduler
```

Explains why the class inherits from v4.

**Line 102**

```
    (v3), for a reason found by multi-seeding this class's own default
```

The reason was discovered through multi-seed testing.

**Line 103**

```
    (multiseed_alpha_default.py), not designed in upfront: subclassing
```

This was not part of the original design.

**Line 104**

```
    v3 directly meant inheriting v3's own known sample-starvation
```

Direct v3 inheritance would retain the sparse-radar lock-on problem.

**Line 105**

```
    coin-flip on the sparse-radar scenario (30 seeds: PRIAware 50.0% +/-
```

Documents the measured bimodal result.

**Line 106**

```
    50.9% radar capture, bimodal -- locks fully or never, exactly the
```

The scheduler either locked successfully or failed completely.

**Line 107**

```
    8-hit-threshold cliff v4 was built to fix). The single seed used
```

This is the same v3 threshold problem addressed by v4.

**Line 108**

```
    throughout this class's earlier single-seed validation (seed=11)
```

Earlier tests used only one seed.

**Line 109**

```
    happened to be a "locks" seed, masking this entirely. Because this
```

That seed hid the inherited failure.

**Line 110**

```
    class's own choose_bands() fully replaces the parent's (needed for
```

v5 must override `choose_bands()` to use Hedge blending.

**Line 111**

```
    the Hedge blend), inheriting from v4 does NOT automatically pull in
```

Normal inheritance does not automatically preserve v4 scoring.

**Line 112**

```
    v4's characterization bonus the way normal method inheritance would
```

The v4 `choose_bands()` method is bypassed.

**Line 113**

```
    -- v4's own choose_bands() is never called. The bonus term is
```

Therefore, the v4 bonus must be explicitly recreated.

**Line 114**

```
    re-added explicitly below, reusing the state v4's __init__/update()
```

The v4 state variables are still available.

**Line 115**

```
    already provide (total_hits, required_hits, give_up_after_scans,
```

These fields are reused.

**Line 116**

```
    char_bonus_c) via the now-corrected base class.
```

Completes the inheritance explanation.

**Line 117**

```python
    """
```

Ends the class documentation.

---

## Constructor: lines 118–152

**Line 118**

```python
    def __init__(self, n_bands, eta: float = 4.0,
```

Defines the constructor.

`eta` controls the speed of Hedge weight updates.

**Line 119**

```python
                 initial_weight_belief: float = 0.8,
```

Sets the initial Markov-expert weight.

**Line 120**

```python
                 weight_floor: float = 0.05,
```

Sets the minimum allowed weight for either expert.

**Line 121**

```python
                 class_balance_alpha: float = 0.1,
```

Controls how strongly class balancing affects the loss.

**Line 122**

```python
                 **kwargs):
```

Accepts all inherited scheduler parameters.

**Line 123**

```python
        # confidence_scale/max_blend_confidence are still accepted (via
```

Explains compatibility with v3 parameters.

**Line 124**

```python
        # **kwargs -> PRIAwareScheduler.__init__) because the underlying
```

Those parameters continue to configure PRI lock behavior.

**Line 125**

```python
        # PRI lock/confidence machinery (_update_pri_model etc.) is
```

The PRI estimation code is unchanged.

**Line 126**

```python
        # untouched -- only the SCORE BLEND is replaced. Passing a
```

Only the final score combination changes.

**Line 127**

```python
        # non-default max_blend_confidence here has no effect, since
```

The old confidence cap no longer controls v5 blending.

**Line 128**

```python
        # choose_bands (overridden below) never reads self.confidence
```

The v5 method uses Hedge weights instead.

**Line 129**

```python
        # for blending; it's harmless but pointless, not silently wrong.
```

Passing the parameter is accepted but has no practical effect on the v5 blend.

**Line 130**

```python
        super().__init__(n_bands, **kwargs)
```

Initializes the v4 parent scheduler.

**Line 131**

```python
        self.eta = eta
```

Stores the Hedge learning rate.

**Line 132**

```python
        self.weight_floor = weight_floor
```

Stores the minimum expert weight.

**Line 133**

```python
        assert 0.0 <= class_balance_alpha <= 1.0
```

Validates that the class-balance interpolation parameter is between zero and one.

**Line 134**

```python
        self.class_balance_alpha = class_balance_alpha
```

Stores the class-balance strength.

**Line 135**

```python
        assert 0.0 <= initial_weight_belief <= 1.0
```

Validates the initial belief weight.

**Line 136**

```python
        self.w_belief = [initial_weight_belief] * n_bands
```

Initializes the Markov expert's weight for every band.

**Line 137**

```python
        self.w_pri = [1.0 - initial_weight_belief] * n_bands
```

Initializes the periodic expert's complementary weight.

The two weights sum to one for every band.

**Line 138**

```python
        # Raw [0,1] expert predictions made for each SCANNED band this
```

Introduces prediction caching.

**Line 139**

```python
        # step, cached in choose_bands so update() can score them
```

Predictions are saved during decision time.

**Line 140**

```python
        # against the realized outcome without recomputing (propagate()
```

They must not be recomputed later.

**Line 141**

```python
        # has already advanced belief[b] by the time update() runs for
```

The belief may change between choosing and updating another band.

**Line 142**

```python
        # a DIFFERENT band in the same multi-channel step, so the
```

This matters when multiple bands are selected.

**Line 143**

```python
        # prediction must be captured at decision time, not looked up
```

The cached value is the prediction actually used for selection.

**Line 144**

```python
        # after the fact).
```

Completes the explanation.

**Line 145**

```python
        self._pending_pred: dict = {}
```

Creates a dictionary mapping selected bands to their cached predictions.

**Line 146**

```python
        # Per-band, per-class (on/off) observation counts, used only to
```

Introduces class-frequency tracking.

**Line 147**

```python
        # class-balance the Hedge loss (see _hedge_update) -- tracked
```

These counts affect only loss weighting.

**Line 148**

```python
        # separately from scan_count/hit_times because those exist for
```

They are deliberately independent from other scheduler statistics.

**Line 149**

```python
        # other purposes and mixing in this bookkeeping there would be
```

Avoids coupling unrelated concepts.

**Line 150**

```python
        # a needless coupling.
```

Completes the comment.

**Line 151**

```python
        self._class_on = [0] * n_bands
```

Initializes the count of observed ON outcomes per band.

**Line 152**

```python
        self._class_off = [0] * n_bands
```

Initializes the count of observed OFF outcomes per band.

**Line 153**

Blank line.

---

# Raw predictions

## Lines 154–157

**Line 154**

```python
    def _raw_predictions(self, b, t):
```

Defines a helper that returns both experts' raw predictions for a band.

**Line 155**

```python
        belief_pred = self.belief[b]
```

Uses the current Markov belief as the belief expert's prediction.

**Line 156**

```python
        periodic_raw = self._periodicity_score(b, t)  # already in [0,1], no periodicity_weight applied
```

Calculates the raw periodicity prediction.

The periodicity weight is intentionally excluded here because it is a scoring multiplier, not a probability estimate.

**Line 157**

```python
        return belief_pred, periodic_raw
```

Returns both predictions.

**Line 158**

Blank line.

---

# Selecting bands with Hedge

## Lines 159–213

**Line 159**

```python
    def choose_bands(self, k):
```

Defines the v5 multi-band selection method.

**Line 160**

```python
        self.t += 1
```

Advances the scheduler's internal clock.

**Line 161**

```python
        if self.t <= self.warmup_steps:
```

Checks whether the scheduler is still warming up.

**Line 162**

```python
            for b in range(self.n_bands):
```

Iterates over all bands.

**Line 163**

```python
                self._propagate(b)
```

Advances Markov beliefs.

**Line 164**

```python
            return self._warmup_bands(k)
```

Uses the inherited warm-up selection strategy.

No Hedge prediction is used during warm-up.

**Line 165**

```python
        for b in range(self.n_bands):
```

After warm-up, iterates over every band.

**Line 166**

```python
            self._propagate(b)
```

Propagates Markov beliefs before scoring.

**Line 167**

```python
        scores = []
```

Creates an empty list for final band scores.

**Line 168**

```python
        preds = {}
```

Creates a dictionary for caching predictions.

**Line 169**

```python
        for b in range(self.n_bands):
```

Begins scoring every band.

**Line 170**

```python
            ucb_bonus = self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
```

Calculates the ordinary UCB exploration bonus.

**Line 171**

```python
            belief_pred, periodic_raw = self._raw_predictions(b, self.t)
```

Calculates the current raw expert predictions.

**Line 172**

```python
            locked = self.confidence[b] > 0
```

Checks whether a usable PRI model exists.

Positive confidence means the periodicity model is locked.

**Line 173**

```python
            preds[b] = (belief_pred, periodic_raw, locked)
```

Caches both predictions and the lock status for this band.

**Line 174**

```python
            if locked:
```

Branches depending on whether periodicity is available.

**Line 175**

```python
                blended = (self.w_belief[b] * belief_pred
```

Starts the Hedge-weighted mixture.

**Line 176**

```python
                           + self.w_pri[b] * self.periodicity_weight * periodic_raw)
```

Adds the weighted periodicity prediction.

The periodicity score is multiplied by its configured score weight.

**Line 177**

```python
            else:
```

Handles bands without a valid periodicity lock.

**Line 178**

```python
                # Periodicity is a structural placeholder here (always 0,
```

Explains why the unlocked periodicity prediction must not participate.

**Line 179**

```python
                # not a real prediction) -- squared-error loss rewards
```

A zero prediction would otherwise be rewarded on OFF observations.

**Line 180**

```python
                # that "predict 0" placeholder on every off-step purely
```

This is the class-imbalance problem.

**Line 181**

```python
                # by class imbalance, which would otherwise win the
```

The inactive expert could incorrectly gain weight.

**Line 182**

```python
                # weight competition against a genuinely calibrated but
```

This could overpower the meaningful belief prediction.

**Line 183**

```python
                # nonzero belief score on any low-duty band (confirmed:
```

The failure was observed on low-duty bands.

**Line 184**

```python
                # this crashed comm-1 from 79.4% to 3.3% on the
```

Documents the severe measured degradation.

**Line 185**

```python
                # sparse-radar reference before this guard). Mirror
```

Motivates matching v3 behavior before lock.

**Line 186**

```python
                # PRIAware's own conf=0 behavior exactly instead: full,
```

Uses full belief trust when periodicity is unavailable.

**Line 187**

```python
                # unweighted belief trust, no expert competition until
```

Hedge weights are not used before lock.

**Line 188**

```python
                # periodicity has an actual lock to compete with.
```

Completes the gating rule.

**Line 189**

```python
                blended = belief_pred
```

Uses only the Markov prediction for an unlocked band.

**Line 190**

```python
            # v4's characterization bonus, re-added explicitly since this
```

Explains why the v4 exploration bonus is copied here.

**Line 191**

```python
            # class's own choose_bands() fully replaces
```

The v5 method replaces the parent method.

**Line 192**

```python
            # PersistentPRIAwareScheduler's (v4's version is never
```

The parent v4 `choose_bands()` is not invoked.

**Line 193**

```python
            # called) -- see class docstring for why this is here at
```

The bonus must therefore be restored manually.

**Line 194**

```python
            # all. Formula and gating unchanged from v4: give a band
```

The copied formula retains v4's semantics.

**Line 195**

```python
            # that hasn't yet accumulated required_hits confirmed ON
```

The bonus targets under-characterized bands.

**Line 196**

```python
            # samples a persistent bonus that decays with ITS OWN hit
```

The bonus decreases based on confirmed hits.

**Line 197**

```python
            # count (not total scan count, which the ordinary ucb_bonus
```

This differs from UCB's scan-count dependence.

**Line 198**

```python
            # above already uses), bounded by give_up_after_scans so a
```

The scan cap prevents endless exploration.

**Line 199**

```python
            # band with no real signal at all doesn't absorb the budget
```

Silent bands eventually lose the bonus.

**Line 200**

```python
            # forever.
```

Completes the comment.

**Line 201**

```python
            char_bonus = 0.0
```

Initializes the characterization bonus.

**Line 202**

```python
            if (self.total_hits[b] < self.required_hits
```

Checks whether the band lacks enough confirmed hits.

**Line 203**

```python
                    and self.scan_count[b] < self.give_up_after_scans):
```

Checks whether the band is still below its scan-attempt cap.

**Line 204**

```python
                char_bonus = self.char_bonus_c * math.sqrt(
```

Begins calculating the v4 characterization bonus.

**Line 205**

```python
                    math.log(self.t + 2) / (self.total_hits[b] + 1))
```

Completes the bonus formula.

**Line 206**

```python
            scores.append(self.priority[b] * blended + ucb_bonus + char_bonus)
```

Adds the final band score.

**Line 207**

```python
        order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
```

Sorts all bands by descending score.

**Line 208**

```python
        chosen = order[:k]
```

Selects the best `k` bands.

**Line 209**

```python
        # Only cache predictions for bands actually scanned -- update()
```

Explains why only selected bands are cached.

**Line 210**

```python
        # is only called for those, and dict stays small.
```

This keeps the pending-prediction dictionary compact.

**Line 211**

```python
        for b in chosen:
```

Iterates over selected bands.

**Line 212**

```python
            self._pending_pred[b] = preds[b]
```

Stores each selected band's predictions and lock state.

**Line 213**

```python
        return chosen
```

Returns the selected bands.

**Line 214**

Blank line.

---

# Hedge weight update

## Lines 215–294

**Line 215**

```python
    def _hedge_update(self, band, observed_on):
```

Defines the method that updates expert weights after an observation.

**Line 216**

```python
        if band not in self._pending_pred:
```

Checks whether a prediction was cached for this band.

**Line 217**

```python
            return  # shouldn't happen outside warmup, but never crash on it
```

Safely ignores missing predictions.

This prevents unexpected calls from crashing the scheduler.

**Line 218**

```python
        belief_pred, periodic_pred, locked = self._pending_pred.pop(band)
```

Retrieves and removes the cached prediction.

Removing it prevents stale reuse.

**Line 219**

```python
        if not locked:
```

Checks whether the periodicity expert was unlocked when the decision was made.

**Line 220**

```python
            # No real periodicity prediction was made at decision time --
```

Explains why the update is skipped.

**Line 221**

```python
            # nothing to score it against, and updating weights from a
```

The placeholder prediction should not affect the weights.

**Line 222**

```python
            # placeholder 0 is exactly the class-imbalance trap this
```

Otherwise the zero predictor could win unfairly.

**Line 223**

```python
            # guard exists to avoid. Leave weights untouched.
```

The weights remain unchanged.

**Line 224**

```python
            return
```

Stops the update for an unlocked band.

**Line 225**

```python
        outcome = 1.0 if observed_on else 0.0
```

Converts the Boolean observation to a numeric outcome.

**Line 226**

```python
        # Class-balance the loss: an unlocked-then-locked LOW-DUTY
```

Introduces the class-balanced loss adjustment.

**Line 227**

```python
        # periodic signal's off-peak observations vastly outnumber its
```

Low-duty signals produce many more OFF observations than ON observations.

**Line 228**

```python
        # on-peak ones, so raw per-observation squared-error lets the
```

Raw loss would be dominated by OFF observations.

**Line 229**

```python
        # far more frequent off-step class dominate total accumulated
```

This can drown out important ON predictions.

**Line 230**

```python
        # loss even when periodicity's rare on-peak wins are individually
```

A periodic expert may correctly predict rare pulses.

**Line 231**

```python
        # large and more valuable -- the same class-imbalance mechanism
```

Those rare correct predictions may be operationally more important.

**Line 232**

```python
        # the pre-lock `locked` gate fixed, recurring in a milder POST-
```

The same basic imbalance reappears after a lock, in a less extreme form.

**Line 233**

```python
        # lock form. Confirmed directly: band 6 in the synthetic PDW
```

Documents an observed synthetic-data case.

**Line 234**

```python
        # scenario is a genuinely, correctly-locked low-duty periodic
```

Band 6 had a valid periodic model.

**Line 235**

```python
        # emitter (confidence 0.88, true PRI), yet w_pri[6] still
```

Even a correct periodic expert lost weight.

**Line 236**

```python
        # collapsed to the floor under the unweighted loss -- belief's
```

The periodic weight fell to its minimum.

**Line 237**

```python
        # marginally-smaller off-peak error, repeated over far more
```

Belief gained from frequent small OFF errors.

**Line 238**

```python
        # off-peak than on-peak observations, slowly outweighed
```

The class imbalance accumulated over time.

**Line 239**

```python
        # periodicity's much rarer but individually-correct on-peak
```

Correct rare pulse predictions were underweighted.

**Line 240**

```python
        # wins. That misallocation was traced (not just theorized) to
```

Documents the downstream impact.

**Line 241**

```python
        # starving a DIFFERENT band (band 4) of the scan timing it
```

One band's incorrect weight updates affected another band's opportunity to be scanned.

**Line 242**

```python
        # needed to clear its own min_cycles guard, even though
```

Band 4's raw scan count did not obviously change.

**Line 243**

```python
        # 4's raw scan COUNT was nearly unchanged -- an emergent,
```

The problem was timing and distribution, not just total count.

**Line 244**

```python
        # project-wide consequence of one band's weights converging
```

The scheduler's bands compete for the same scanning budget.

**Line 245**

```python
        # wrong. Reweighting each observation's loss by the inverse of
```

Introduces the correction.

**Line 246**

```python
        # its own class's running frequency makes on-steps and off-steps
```

Each class receives an inverse-frequency weight.

**Line 247**

```python
        # contribute EQUAL total loss mass regardless of its duty
```

This makes ON and OFF classes contribute more evenly.

**Line 248**

```python
        # cycle -- removing the volume imbalance itself, not papering
```

The fix addresses the underlying statistical imbalance.

**Line 249**

```python
        # over its symptom. Laplace-smoothed (+1/+2) so early counts
```

The frequency estimate is smoothed to prevent unstable early weights.

**Line 250**

```python
        # don't produce an extreme class weight before either class has
```

Early observations should not cause drastic updates.

**Line 251**

```python
        # enough samples to estimate its true frequency.
```

Completes the explanation.

**Line 252**

Blank comment line.

**Line 253**

```python
        # FULL balancing (class_balance_alpha=1) recovered band 4 but
```

Documents the result of fully balancing the loss.

**Line 254**

```python
        # cost real band-1 (99.6% -> 94.7%) -- opposite duty profiles
```

Full balancing helped one case but harmed another.

**Line 255**

```python
        # want opposite amounts of correction. class_balance_alpha
```

Different bands require different balancing strengths.

**Line 256**

```python
        # linearly interpolates between UNWEIGHTED loss (alpha=0,
```

Defines the lower endpoint.

**Line 257**

```python
        # class_w == 1.0 always) and FULLY class-balanced loss (alpha=1,
```

Defines the upper endpoint.

**Line 258**

```python
        # class_w == the raw inverse-frequency weight), swept in
```

The parameter interpolates between those behaviors.

**Line 259**

```python
        # sweep_class_balance_alpha.py against all four references. The
```

References the dedicated sweep script.

**Line 260**

```python
        # relationship is sharply nonlinear, not a smooth trade-off:
```

The effect of alpha is not gradual in all scenarios.

**Line 261**

```python
        # band 4's lock is a THRESHOLD effect (alpha=0.02: never locks;
```

A small change can determine whether band 4 locks at all.

**Line 262**

```python
        # alpha=0.05: locks at the SAME confidence as full balancing,
```

Once a threshold is crossed, the result can change abruptly.

**Line 263**

```python
        # 0.89) while real band-1's cost scales roughly continuously
```

Other bands show a smoother response.

**Line 264**

```python
        # with alpha (99.6% at 0.0 -> 98.5% at 0.05 -> 94.7% at 1.0).
```

Provides measured performance values.

**Line 265**

```python
        # Because a small alpha already buys the full band-4 fix, the
```

This motivates using a small nonzero alpha.

**Line 266**

```python
        # shipped default (0.1) sits just above that threshold with a
```

The default is set to 0.1.

**Line 267**

```python
        # safety margin (0.05, measured on one seed, is too close to the
```

Alpha 0.05 was considered too fragile.

**Line 268**

```python
        # 0.02 failure point to trust as a default) -- band 4 fully
```

The default provides additional margin.

**Line 269**

```python
        # fixed, real band-1 at 98.0% rather than 94.7%.
```

Summarizes the chosen trade-off.

**Line 270**

```python
        on_c, off_c = self._class_on[band], self._class_off[band]
```

Reads the current ON and OFF counts for the band.

**Line 271**

```python
        p_on = (on_c + 1) / (on_c + off_c + 2)
```

Computes a Laplace-smoothed estimate of the ON frequency.

**Line 272**

```python
        p_off = 1.0 - p_on
```

Computes the smoothed OFF probability.

**Line 273**

```python
        raw_class_w = 0.5 / p_on if observed_on else 0.5 / p_off
```

Assigns an inverse-frequency weight to the class that just occurred.

The rarer class receives a larger weight.

**Line 274**

```python
        class_w = 1.0 + self.class_balance_alpha * (raw_class_w - 1.0)
```

Interpolates between:

- No class balancing: `class_w = 1`
- Full inverse-frequency balancing: `class_w = raw_class_w`

**Line 275**

```python
        if observed_on:
```

Checks which class was observed.

**Line 276**

```python
            self._class_on[band] += 1
```

Increments the ON count.

**Line 277**

```python
        else:
```

Handles an OFF observation.

**Line 278**

```python
            self._class_off[band] += 1
```

Increments the OFF count.

**Line 279**

```python
        loss_belief = class_w * (belief_pred - outcome) ** 2
```

Calculates the class-weighted squared error of the belief expert.

**Line 280**

```python
        loss_pri = class_w * (periodic_pred - outcome) ** 2
```

Calculates the class-weighted squared error of the periodic expert.

**Line 281**

```python
        wb = self.w_belief[band] * math.exp(-self.eta * loss_belief)
```

Applies the Hedge multiplicative update to the belief weight.

A larger loss produces a smaller new weight.

**Line 282**

```python
        wp = self.w_pri[band] * math.exp(-self.eta * loss_pri)
```

Applies the same update to the periodicity weight.

**Line 283**

```python
        total = wb + wp
```

Calculates the unnormalized combined weight.

**Line 284**

```python
        if total <= 0:
```

Checks for numerical underflow or another invalid result.

**Line 285**

```python
            wb, wp = 0.5, 0.5
```

Falls back to equal weights if both updated values are unusable.

**Line 286**

```python
        else:
```

Handles the normal case.

**Line 287**

```python
            wb, wp = wb / total, wp / total
```

Renormalizes the two weights so that they sum to one.

**Line 288**

```python
        # Floor + renormalize so neither expert is ever permanently
```

Introduces the weight-floor safeguard.

**Line 289**

```python
        # zeroed out (lets a cold expert recover, e.g. after the
```

A temporarily poor expert can regain trust later.

**Line 290**

```python
        # confidence-drift event found on real config_169.h5 data).
```

Connects the safeguard to the real-data motivation.

**Line 291**

```python
        wb = min(max(wb, self.weight_floor), 1.0 - self.weight_floor)
```

Clamps the belief weight between the configured floor and its complementary maximum.

**Line 292**

```python
        wp = 1.0 - wb
```

Sets the periodicity weight to the complementary value.

**Line 293**

```python
        self.w_belief[band] = wb
```

Stores the updated belief-expert weight.

**Line 294**

```python
        self.w_pri[band] = wp
```

Stores the updated periodic-expert weight.

**Line 295**

Blank line.

---

# Final update method

## Lines 296–303

**Line 296**

```python
    def update(self, band, observed_on):
```

Overrides the public update method.

**Line 297**

```python
        # super().update() now chains PersistentPRIAwareScheduler.update()
```

Explains the inheritance chain.

**Line 298**

```python
        # (increments total_hits) -> PRIAwareScheduler.update() (belief +
```

The parent update increments lifetime hits and updates Markov belief.

**Line 299**

```python
        # PRI/stagger model, hit_times, _update_pri_model) -- all of that
```

It also updates PRI and staggered-model state.

**Line 300**

```python
        # machinery is reused as-is; only the SCORE BLEND differs here.
```

The v5 change is primarily in band scoring and expert weighting.

**Line 301**

```python
        super().update(band, observed_on)
```

Runs the complete inherited update chain.

**Line 302**

```python
        if self.t > self.warmup_steps:
```

Only performs Hedge updates after warm-up.

**Line 303**

```python
            self._hedge_update(band, observed_on)
```

Updates the expert weights using the cached predictions and actual outcome.

---

# Overall purpose of v5

This file changes the v4 scheduler from a fixed blend:

```
belief versus periodicity based on confidence
```

to an adaptive per-band competition:

```
belief expert versus periodicity expert
```

The learned weights adapt according to prediction performance while preserving:

- UCB exploration
- PRI fitting
- Staggered PRI support
- Persistent characterization
- Warm-up behavior

It also adds two important protections:

1. Do not score the periodicity expert before it has a real lock.
2. Correct for the imbalance between frequent OFF observations and rare ON observations.



Completed and checked off `spatial_scan_emitter.py`.

# `spatial_scan_emitter.py` — line-by-line explanation

## Module documentation

### Lines 1–36

**Line 1**

```python
"""
```

Starts the module documentation string.

**Line 2**

```
spatial_scan_emitter.py
```

Names the module.

**Line 3**

```
=========================
```

Documentation separator.

**Line 4**

```
Models the gap the codebase had zero coverage for: an emitter whose
```

Explains that this file adds a previously missing emitter behavior.

**Line 5**

```
antenna itself mechanically or electronically scans/rotates, so it is
```

The emitter's antenna direction changes over time.

**Line 6**

```
only detectable during the brief window each rotation that its beam
```

The receiver can only observe the emitter during a beam-illumination window.

**Line 7**

```
points at the receiver -- a periodicity completely independent of, and
```

The antenna scan period is separate from the emitter's own pulse timing.

**Line 8**

```
layered on top of, its own PRI or frequency-hopping pattern. This is
```

The spatial scan is an additional periodic layer.

**Line 9**

```
what the PS names twice: "spatially scanning ... emitters" and
```

Connects the model to the requirements or problem statement.

**Line 10**

```
"a periodic scan receiver."
```

Completes that connection.

**Line 11**

Blank documentation line.

**Line 12**

```
Why a decorator, not a new Emitter subclass duplicating PRI logic:
```

Explains the design choice.

**Line 13**

```
every existing Emitter (MarkovEmitter, PeriodicEmitter,
```

Lists emitter classes that already exist.

**Line 14**

```
SparsePeriodicEmitter, AgileEmitter) already answers "is this emitter
```

Those emitters already determine their own transmission behavior.

**Line 15**

```
transmitting right now" -- that's orthogonal to "is its beam pointed at
```

Transmission state and antenna orientation are separate concepts.

**Line 16**

```
us right now." SpatiallyScanningEmitter wraps any of them and ANDs a
```

The new class wraps an existing emitter and adds a beam gate.

**Line 17**

```
beam-illumination gate on top, so it composes with the existing
```

This permits reuse of all existing emitter types.

**Line 18**

```
population instead of re-implementing it.
```

Completes the composition explanation.

**Line 19**

Blank documentation line.

**Line 20**

```
Physical picture (mapped to real EW terms):
```

Introduces the physical interpretation of the parameters.

**Line 21**

```
    scan_period_steps  -- steps per full antenna rotation/scan cycle
```

Defines the number of simulation steps in one complete antenna scan.

**Line 22**

```
    beam_dwell_steps   -- of those, how many steps the mainbeam is
```

Defines the duration of the main-beam illumination window.

**Line 23**

```
                          actually pointed at the receiver (the
```

Clarifies that this is the portion of the scan directed toward the receiver.

**Line 24**

```
                          "main-beam illumination time", MBIT)
```

Provides the real-world terminology.

**Line 25**

```
    phase_offset       -- where in the rotation cycle we start (models
```

Defines the initial position within the antenna rotation.

**Line 26**

```
                          "we don't know where the radar's dish
```

Explains that the initial antenna orientation may be unknown.

**Line 27**

```
                          happened to be pointed when we arrived")
```

Completes the phase-offset interpretation.

**Line 28**

Blank documentation line.

**Line 29**

```
A receiver only ever sees on = (inner emitter transmitting) AND
```

Defines the visibility rule.

**Line 30**

```
(beam pointed at receiver). AoA is untouched by this: the emitter's
```

The model gates whether the signal arrives but does not modify its direction.

**Line 31**

```
true bearing from the receiver doesn't change as its beam sweeps --
```

Antenna scanning does not change the emitter's physical bearing.

**Line 32**

```
only whether we're currently inside that beam does. (pdw_loader's AoA
```

Only signal visibility changes.

**Line 33**

```
field is the receiver's bearing measurement and stays exactly as
```

The PDW angle-of-arrival field remains unchanged.

**Line 34**

```
meaningful/noisy as before; this model only gates *whether* a pulse
```

The model does not add or remove angle noise.

**Line 35**

```
reaches the receiver at all, not what AoA gets reported for it.)
```

Completes the physical-model explanation.

**Line 36**

```python
"""
```

Ends the module documentation.

---

## Imports

### Lines 37–42

**Line 37**

Blank line.

**Line 38**

```python
import random
```

Imports random-number generation.

It is used for optional sidelobe leakage.

**Line 39**

```python
from typing import Tuple
```

Imports the `Tuple` type annotation.

**Line 40**

Blank line.

**Line 41**

```python
from scan_scheduler_prototype import Emitter
```

Imports the base emitter class.

The spatial scanner uses inheritance to behave like any other emitter.

**Line 42**

Blank line.

---

# `SpatiallyScanningEmitter`

## Constructor

### Lines 44–67

**Line 44**

```python
class SpatiallyScanningEmitter(Emitter):
```

Defines the spatially scanning emitter wrapper.

**Line 45**

```python
    def __init__(self, inner: Emitter, scan_period_steps: int,
```

Defines the constructor.

`inner` is the underlying emitter being wrapped.

**Line 46**

```python
                 beam_dwell_steps: int, phase_offset: int = 0,
```

Adds:

- Beam illumination duration
- Optional starting phase

**Line 47**

```python
                 sidelobe_leak_prob: float = 0.0):
```

Adds an optional probability that a pulse leaks through a sidelobe while out of beam.

**Line 48**

```python
        """sidelobe_leak_prob: chance, on any OUT-of-beam step where the
```

Starts the constructor documentation.

**Line 49**

```
        inner emitter is transmitting, that a sidelobe pulse still gets
```

Sidelobe leakage is possible only when the inner emitter is actually transmitting.

**Line 50**

```
        through. Models real antenna sidelobes rather than a perfect
```

Explains the physical motivation.

**Line 51**

```
        mainbeam-only gate. 0.0 (default) keeps the original hard gate.
```

A probability of zero creates a strict beam/no-beam boundary.

**Line 52**

```
        Low values (real sidelobes are typically 20-40dB down, i.e. a
```

Explains why the default leakage probabilities should be small.

**Line 53**

```
        small fraction of mainbeam gain) should still read as
```

Sidelobe detections should be rare.

**Line 54**

```
        "occasional, unreliable" to a scheduler -- not a second regular
```

They should not form a clean alternative periodic signal.

**Line 55**

```
        periodicity worth locking onto."""
```

Ends the constructor documentation.

**Line 56**

```python
        super().__init__(inner.name + "-scanning")
```

Initializes the parent emitter using a derived name.

For example, an inner emitter named `"radar"` becomes `"radar-scanning"`.

**Line 57**

```python
        if beam_dwell_steps > scan_period_steps:
```

Checks that the beam cannot remain pointed at the receiver longer than the entire scan cycle.

**Line 58**

```python
            raise ValueError("beam_dwell_steps can't exceed scan_period_steps")
```

Raises an error for an impossible beam configuration.

**Line 59**

```python
        if not 0.0 <= sidelobe_leak_prob <= 1.0:
```

Validates that the sidelobe probability is a valid probability.

**Line 60**

```python
            raise ValueError("sidelobe_leak_prob must be in [0, 1]")
```

Raises an error for an invalid probability.

**Line 61**

```python
        self.inner = inner
```

Stores the wrapped emitter.

**Line 62**

```python
        self.scan_period_steps = scan_period_steps
```

Stores the full antenna scan period.

**Line 63**

```python
        self.beam_dwell_steps = beam_dwell_steps
```

Stores the number of steps during which the main beam points at the receiver.

**Line 64**

```python
        self.phase_offset = phase_offset % scan_period_steps
```

Normalizes the phase offset into the range:

```
0 <= phase_offset < scan_period_steps
```

**Line 65**

```python
        self.sidelobe_leak_prob = sidelobe_leak_prob
```

Stores the sidelobe leakage probability.

**Line 66**

```python
        self.in_beam = False  # last step's gate value, exposed for diagnostics/tests
```

Initializes the beam-status diagnostic flag.

It records whether the previous/current gate calculation placed the receiver inside the main beam.

**Line 67**

Blank line.

---

## `_in_beam()`

### Lines 68–70

**Line 68**

```python
    def _in_beam(self, t: int) -> bool:
```

Defines a helper that determines whether the antenna beam points at the receiver at time `t`.

**Line 69**

```python
        phase = (t + self.phase_offset) % self.scan_period_steps
```

Calculates the current position within the antenna's scan cycle.

The phase offset shifts the starting point.

**Line 70**

```python
        return phase < self.beam_dwell_steps
```

Returns `True` while the phase is within the beam dwell window.

For example, with:

```
scan_period_steps = 40
beam_dwell_steps = 6
```

the beam is active for phases `0` through `5`.

**Line 71**

Blank line.

---

## `step()`

### Lines 72–81

**Line 72**

```python
    def step(self, t: int) -> Tuple[int, bool]:
```

Defines the emitter's simulation-step method.

It returns:

```
(current band, visible ON/OFF state)
```

**Line 73**

```python
        band, transmitting = self.inner.step(t)
```

Advances the wrapped emitter.

This determines:

- Which band the inner emitter uses
- Whether the inner emitter is transmitting

**Line 74**

```python
        self.in_beam = self._in_beam(t)
```

Calculates and stores whether the receiver is inside the main beam.

**Line 75**

```python
        visible = self.in_beam or (
```

Begins calculating whether the signal is visible.

The signal is visible either through the main beam or through a sidelobe.

**Line 76**

```python
            transmitting and self.sidelobe_leak_prob > 0.0
```

Sidelobe leakage is possible only if:

- The inner emitter is transmitting
- Sidelobe leakage is enabled

**Line 77**

```python
            and random.random() < self.sidelobe_leak_prob
```

Performs the random sidelobe detection trial.

**Line 78**

```python
        )
```

Closes the visibility expression.

**Line 79**

```python
        self.band = band
```

Copies the inner emitter's current band onto the wrapper.

**Line 80**

```python
        self.on = transmitting and visible
```

The wrapped emitter is considered ON to the outside world only if:

- The inner emitter is transmitting
- The signal is visible through the main beam or a sidelobe

**Line 81**

```python
        return self.band, self.on
```

Returns the externally visible band and ON/OFF state.



The next file is `scan_aware_scheduler.py`, which has 609 lines. I’ll explain it in three parts.

This is **Part 1 of 3: lines 1–240**. Its checklist box will remain unchecked until all three parts are complete.

# `scan_aware_scheduler.py` — Part 1

## Module documentation

### Lines 1–68

**Line 1**

```python
"""
```

Starts the module documentation.

**Line 2**

```
scan_aware_scheduler.py
```

Names the module.

**Line 3**

```
=========================
```

Documentation separator.

**Line 4**

```
Extends PRIAwareScheduler to handle SpatiallyScanningEmitter targets,
```

Explains that this scheduler builds on the PRI-aware scheduler.

**Line 5**

```
where a single band shows TWO independent periodicities nested inside
```

A single band can exhibit two separate repeating patterns.

**Line 6**

```
each other: a fast intra-burst PRI (pulses while the beam is on us) and
```

The first pattern is the fast pulse repetition interval while the beam is visible.

**Line 7**

```
a slow inter-burst scan_period (when the beam comes back around). The
```

The second pattern is the slower antenna revisit period.

**Line 8**

```
base PRIAwareScheduler models one periodicity per band; feeding it a
```

The normal PRI-aware scheduler only models one period.

**Line 9**

```
scanning emitter's hit stream directly would make it try to fit a
```

Giving it nested scan data directly would confuse the period estimator.

**Line 10**

```
single period to a bimodal gap distribution, and -- since it selects
```

The hit gaps contain both short intra-burst gaps and long inter-burst gaps.

**Line 11**

```
whichever candidate gets the tightest least-squares fit -- it would
```

The candidate-selection algorithm might favor the tightest-fitting short gaps.

**Line 12**

```
most likely lock onto the tight, well-fit intra-burst PRI and stay
```

The scheduler could lock onto only the fast PRI.

**Line 13**

```
structurally blind to the much larger scan_period, meaning it could
```

It would fail to predict when the beam returns.

**Line 14**

```
only ever "stumble into" a beam pass, never predict one.
```

It would detect bursts only by chance.

**Line 15**

Blank documentation line.

**Line 16**

```
This scheduler tracks the two periodicities as separate estimates with
```

Introduces the solution.

**Line 17**

```
separate confidences:
```

Each periodicity gets its own confidence measure.

**Line 18**

```
  - scan_confidence / scan_period_estimate  -- when does the NEXT BURST
```

The outer model predicts the next beam burst.

**Line 19**

```
    start (from burst-onset times)
```

It is fitted using the times at which bursts begin.

**Line 20**

```
  - pri_confidence / pri_estimate           -- once inside a predicted
```

The inner model predicts pulse timing within a burst.

**Line 21**

```
    burst window, when's the next PULSE within it (from gaps between
```

It uses gaps between hits in the same burst.

**Line 22**

```
    hits inside the same burst)
```

Completes the inner-period explanation.

**Line 23**

Blank documentation line.

**Line 24**

```
Both burst segmentation AND scan_period fitting went through real,
```

States that both parts experienced practical failure modes.

**Line 25**

```
found-not-assumed failure modes worth stating plainly:
```

The safeguards were added because of observed failures.

**Line 26**

Blank documentation line.

**Line 27**

```
  1. Burst segmentation originally split on the largest ratio jump
```

Introduces the first failure: detecting bursts by gap-ratio jumps.

**Line 28**

```
     between sorted consecutive-hit gaps ("gap in the gaps"), which
```

The old approach examined sorted adjacent hit gaps.

**Line 29**

```
     looked scale-agnostic but broke down under sparse, self-selected
```

The method appeared general but failed with sparse observations.

**Line 30**

```
     scanning (the receiver doesn't catch every pulse of every beam
```

The receiver may miss pulses during each beam pass.

**Line 31**

```
     pass): consecutive detected onsets jitter enough that the ratio
```

Missed detections make burst onset gaps irregular.

**Line 32**

```
     heuristic sometimes merged two real bursts into one. Fixed by
```

The old method could merge separate bursts.

**Line 33**

```
     seeding a robust intra-burst PRI estimate FIRST
```

The fix first estimates the short pulse interval.

**Line 34**

```
     (_robust_intra_burst_pri_seed), then splitting on a FIXED multiple
```

It uses that estimate to define a burst boundary threshold.

**Line 35**

```
     of that seed instead of guessing the split point from noisy local
```

This is more stable than using a local gap-ratio guess.

**Line 36**

```
     gap statistics. The old ratio-jump method is kept only as a
```

The old method remains available as a fallback.

**Line 37**

```
     cold-start fallback for when there isn't yet enough data to seed
```

It is used only before enough hits exist to estimate the inner PRI.

**Line 38**

```
     a PRI at all.
```

Completes the first failure explanation.

**Line 39**

Blank documentation line.

**Line 40**

```
  2. scan_period fitting originally used naive adjacent-onset-gap
```

Introduces the second failure: naive outer-period estimation.

**Line 41**

```
     median/stdev, gated by a raw coefficient-of-variation threshold.
```

The original method used basic statistics on burst onset gaps.

**Line 42**

```
     That fails for exactly the reason the base class's PRI model
```

Missed cycles create misleading large gaps.

**Line 43**

```
     already had to solve: whenever the scheduler misses an ENTIRE
```

The receiver may miss a whole beam rotation.

**Line 44**

```
     rotation (never scans the band during that beam pass), the
```

No burst onset is observed during that rotation.

**Line 45**

```
     resulting onset-to-onset gap is a MULTIPLE of the true
```

The next observed gap may represent two or more true scan periods.

**Line 46**

```
     scan_period, not the period itself -- inflating apparent variance
```

This makes a perfectly periodic emitter look irregular.

**Line 47**

```
     even though the underlying signal is perfectly periodic. Fixed by
```

The fix reuses the robust candidate search.

**Line 48**

```
     reusing the exact same GCD/mode/submultiple candidate search +
```

Candidate periods are generated from GCDs, modes, and submultiples.

**Line 49**

```
     least-squares refinement the base class uses for PRI
```

Candidates are refined with the existing least-squares routine.

**Line 50**

```
     (_search_best_period, shared by both tiers), which is precisely
```

The same helper is used for inner and outer periodicity.

**Line 51**

```
     the technique built to handle missed-cycle multiples.
```

Completes the second failure explanation.

**Line 52**

Blank documentation line.

**Line 53**

```
Downstream gating (min_bursts, burst-size consistency, and the
```

Introduces safeguards against false outer-period locks.

**Line 54**

```
refined-fit confidence threshold) is the actual safety net against
```

Several conditions must pass before accepting a scan period.

**Line 55**

```
false periodicity locks on genuinely non-periodic bands -- found
```

These gates prevent agile or random signals from appearing periodic.

**Line 56**

```
directly during testing: with looser gates, an AgileEmitter band (no
```

Documents an observed false-positive case.

**Line 57**

```
real periodicity at all) reached scan_confidence=0.93 from spurious
```

A non-periodic band achieved very high confidence under weak safeguards.

**Line 58**

```
least-squares overfitting on too few burst onsets.
```

The cause was overfitting a small number of detected bursts.

**Line 59**

Blank documentation line.

**Line 60**

```
The combined periodicity score is burst_score * pri_score: burst_score
```

Defines the final periodicity score as the product of two components.

**Line 61**

```
alone gates broad interest in a band (no point favoring it at all
```

The outer burst score determines whether the band is near a beam return.

**Line 62**

```
outside a predicted burst window), and pri_score sharpens WITHIN that
```

The inner score is used within the predicted burst window.

**Line 63**

```
window once enough intra-burst pulses have been seen to fit a PRI --
```

The inner score becomes useful only after enough pulse evidence exists.

**Line 64**

```
before that, pri_score defaults to 1.0 so early bursts aren't
```

Before inner lock, the inner model does not penalize the band.

**Line 65**

```
suppressed just because fine-grained PRI hasn't locked yet.
```

This prevents premature suppression of newly discovered bursts.

**Line 66**

Blank documentation line.

**Line 67**

```
Run:  python3 scan_aware_scheduler.py
```

Documents how to run the module.

**Line 68**

```python
"""
```

Ends the module documentation.

---

## Imports

### Lines 69–77

**Line 69**

Blank line after the module documentation.

**Line 70**

```python
import math
```

Imports mathematical functions such as `sqrt`, `log`, and `exp`.

**Line 71**

```python
import statistics
```

Imports statistical helpers such as `median` and `pstdev`.

**Line 72**

```python
from collections import Counter
```

Imports `Counter` for finding common gap values.

**Line 73**

```python
from functools import reduce
```

Imports `reduce` for calculating GCDs across collections.

**Line 74**

```python
from typing import List, Optional
```

Imports type annotation helpers.

**Line 75**

Blank line.

**Line 76**

```python
from scan_scheduler_v3_pri import PRIAwareScheduler
```

Imports the v3 scheduler that this class extends.

**Line 77**

Blank line.

---

# `ScanAwarePRIScheduler`

## Constructor signature

### Lines 79–94

**Line 79**

```python
class ScanAwarePRIScheduler(PRIAwareScheduler):
```

Defines the scan-aware scheduler as a subclass of `PRIAwareScheduler`.

**Line 80**

```python
    def __init__(self, n_bands, ucb_c: float = 0.5, history_len: int = 60,
```

Defines the constructor.

The history is longer than v3's default because nested periodicity needs more evidence.

**Line 81**

```python
                 min_confidence: float = 0.75, periodicity_weight: float = 1.0,
```

Adds the standard confidence and periodicity-weight parameters.

**Line 82**

```python
                 warmup_steps: int = 0, priority: Optional[List[float]] = None,
```

Adds warm-up and band priorities.

**Line 83**

```python
                 confidence_scale: float = 0.25, switch_lead_steps: int = 0,
```

Adds confidence scaling and switch-lead behavior.

**Line 84**

```python
                 warmup_dwell_steps: int = 1, warmup_dwell_jitter: int = 1,
```

Adds inherited warm-up dwell controls.

**Line 85**

```python
                 min_gap_ratio: float = 3.0, min_burst_hits: int = 2,
```

Adds:

- Ratio threshold for cold-start segmentation
- Minimum hits needed in a burst for PRI estimation

**Line 86**

```python
                 min_bursts: int = 5, min_burst_size_consistency: float = 0.5,
```

Adds:

- Minimum number of bursts
- Fraction of similarly sized bursts required

**Line 87**

```python
                 min_scan_to_pri_ratio: float = 3.0, period_agreement_tol: float = 0.05,
```

Adds:

- Minimum ratio between outer scan period and inner PRI
- Tolerance for requiring two period estimates to agree

**Line 88**

```python
                 beam_dwell_sigma_divisor: float = 3.0):
```

Adds the divisor used to turn estimated beam width into a Gaussian score width.

---

## Parent initialization and configuration

### Lines 89–129

**Line 89**

```python
        super().__init__(n_bands, ucb_c=ucb_c, history_len=history_len,
```

Initializes the v3 parent scheduler.

**Line 90**

```python
                          min_confidence=min_confidence, periodicity_weight=periodicity_weight,
```

Passes confidence and periodicity settings.

**Line 91**

```python
                          warmup_steps=warmup_steps, priority=priority,
```

Passes warm-up and priority settings.

**Line 92**

```python
                          confidence_scale=confidence_scale, switch_lead_steps=switch_lead_steps,
```

Passes confidence scaling and switch-lead settings.

**Line 93**

```python
                          warmup_dwell_steps=warmup_dwell_steps,
```

Passes warm-up dwell duration.

**Line 94**

```python
                          warmup_dwell_jitter=warmup_dwell_jitter)
```

Passes warm-up jitter and closes the parent constructor call.

**Line 95**

```python
        # Cold-start-only fallback split (see module docstring point 1).
```

Documents the purpose of `min_gap_ratio`.

**Line 96**

```python
        self.min_gap_ratio = min_gap_ratio
```

Stores the fallback gap-ratio threshold.

**Line 97**

```python
        self.min_burst_hits = min_burst_hits
```

Stores the minimum number of hits required in a burst to estimate its internal PRI.

**Line 98**

```python
        # A least-squares fit trivially finds a near-perfect line
```

Begins an explanation of the minimum-burst guard.

**Line 99**

```python
        # through almost any handful of points -- this must be high
```

A small sample can be overfit easily.

**Line 100**

```python
        # enough that a spurious segmentation of non-periodic noise
```

The threshold must prevent random data from being accepted.

**Line 101**

```python
        # doesn't get enough onsets to overfit confidently (found
```

Documents the reason for the parameter.

**Line 102**

```python
        # directly: min_bursts=3 let an AgileEmitter band reach
```

Three bursts were insufficient.

**Line 103**

```python
        # scan_confidence=0.93). Mirrors the base class's len(times)<8
```

The false lock achieved high confidence.

**Line 104**

```python
        # gate before it even attempts a PRI fit.
```

The scheduler requires a larger sample before fitting.

**Line 105**

```python
        self.min_bursts = min_bursts
```

Stores the minimum number of bursts.

**Line 106**

```python
        # A real rotating scanner illuminates for roughly the same
```

Introduces burst-size consistency.

**Line 107**

```python
        # number of pulses each pass; bursty/agile noise split by the
```

Real beam passes should have similar sizes.

**Line 108**

```python
        # segmentation heuristic tends to produce wildly uneven "burst"
```

Random data produces irregular group sizes.

**Line 109**

```python
        # sizes -- reject those before ever attempting a period fit.
```

The scheduler rejects inconsistent segmentation early.

**Line 110**

```python
        # (Fraction of bursts required within +-1 of the median size;
```

Defines how consistency is measured.

**Line 111**

```python
        # see _evaluate_burst_split for why raw CoV is the wrong
```

Points to the implementation details.

**Line 112**

```python
        # statistic here.)
```

Completes the comment.

**Line 113**

```python
        self.min_burst_size_consistency = min_burst_size_consistency
```

Stores the required fraction of near-median bursts.

**Line 114**

```python
        # A genuine OUTER period must be substantially larger than the
```

Introduces the outer/inner period separation guard.

**Line 115**

```python
        # inner PRI seed it was segmented against -- otherwise the
```

The outer period must not collapse to the inner PRI.

**Line 116**

```python
        # "outer" search has just degenerated into rediscovering the
```

Otherwise the scan model merely rediscovers the pulse period.

**Line 117**

```python
        # same small-scale structure twice. Found directly: once the
```

Explains the failure mode.

**Line 118**

```python
        # scheduler over-commits scan time to a band, occasional
```

Continuous scanning can expose sidelobe hits.

**Line 119**

```python
        # sidelobe-leak hits caught DURING the dead window (now that
```

Those hits occur outside the true beam window.

**Line 120**

```python
        # it's scanning continuously, not just during true bursts)
```

They contaminate the hit-time distribution.

**Line 121**

```python
        # pollute the pairwise-diff pool with extra small-scale
```

The extra short gaps resemble the inner PRI.

**Line 122**

```python
        # samples, dragging scan_period_estimate back down to equal
```

The outer estimate can collapse to the inner one.

**Line 123**

```python
        # pri_estimate (confirmed: scan_period locked to 3.0, the same
```

Documents an observed false lock.

**Line 124**

```python
        # as the true inner PRI, with scan_confidence=1.00 and 90% of
```

The false outer lock appeared highly confident.

**Line 125**

```python
        # all scan time then dumped onto that one band). This ratio
```

The incorrect lock caused the scheduler to over-focus on one band.

**Line 126**

```python
        # check is a cheap, principled guard against that self-
```

The ratio threshold prevents this feedback loop.

**Line 127**

```python
        # reinforcing runaway, without needing to filter sidelobe
```

It avoids explicitly modeling every sidelobe event.

**Line 128**

```python
        # leaks explicitly.
```

Completes the explanation.

**Line 129**

```python
        self.min_scan_to_pri_ratio = min_scan_to_pri_ratio
```

Stores the required outer-to-inner period ratio.

---

## Per-band model state

### Lines 131–168

**Line 131**

```python
        self.burst_starts: List[List[int]] = [[] for _ in range(n_bands)]
```

Stores the detected burst-start times for each band.

**Line 132**

```python
        self.scan_period_estimate: List[Optional[float]] = [None] * n_bands
```

Stores the estimated outer scan period for each band.

**Line 133**

```python
        self.scan_jitter_estimate: List[float] = [1.0] * n_bands
```

Stores timing uncertainty for the outer scan period.

**Line 134**

```python
        self.scan_confidence: List[float] = [0.0] * n_bands
```

Stores confidence in the outer-period model.

**Line 135**

```python
        self.pri_confidence: List[float] = [0.0] * n_bands
```

Stores confidence in the inner PRI model.

**Line 136**

```python
        # Persistent (never-shrinking) estimate of burst width in steps,
```

Introduces beam-dwell tracking.

**Line 137**

```python
        # same rationale as PRIAwareScheduler.max_run_ever: widens the
```

Uses the same idea as v3's persistent maximum run.

**Line 138**

```python
        # burst_score plateau so the scheduler doesn't abandon a burst
```

The scheduler should remain interested through the full burst.

**Line 139**

```python
        # partway through once locked on.
```

Completes the rationale.

**Line 140**

```python
        self.beam_dwell_estimate: List[int] = [1] * n_bands
```

Initializes the estimated beam illumination width for every band.

**Line 141**

```python
        # Lock-stability gate for scan_period_estimate (see
```

Introduces the requirement that outer-period estimates agree across calls.

**Line 142**

```python
        # _update_scan_model): a single _evaluate_burst_split fit is
```

One good-looking fit is not enough.

**Line 143**

```python
        # NOT enough to trust, however good its own RMSE looks --
```

The fit may be an overfit.

**Line 144**

```python
        # found directly (seeds 1 and 5 of the mixed scenario): a
```

Documents observed false locks.

**Line 145**

```python
        # corrupted pri_seed at cold start produced a one-off spurious
```

A bad inner PRI seed caused an incorrect outer period.

**Line 146**

```python
        # fit (scan_period=89.7 against a true 40) that got published
```

The incorrect estimate was immediately accepted.

**Line 147**

```python
        # immediately, and then self-reinforced, because the beam_dwell
```

The bad estimate influenced later segmentation.

**Line 148**

```python
        # sane_cap in _update_intra_burst_state is itself scaled off
```

The sanity cap depended on the bad period.

**Line 149**

```python
        # scan_period_estimate -- a bad first lock loosens the cap that
```

This made later bad measurements easier to accept.

**Line 150**

```python
        # was supposed to catch further bad spans. Requiring the NEXT
```

The fix requires a second independent fit.

**Line 151**

```python
        # independent fit (one call later, over the then-larger hit
```

The second fit uses more data.

**Line 152**

```python
        # history) to land within period_agreement_tol of this one
```

The two fits must agree within tolerance.

**Line 153**

```python
        # before publishing either is a cheap, principled way to reject
```

This filters one-off overfits.

**Line 154**

```python
        # one-off overfits without needing a hardcoded "sanity" period
```

It avoids assuming a known period.

**Line 155**

```python
        # the scheduler has no ground truth to derive.
```

Completes the motivation.

**Line 156**

```python
        self.period_agreement_tol = period_agreement_tol
```

Stores the allowed relative disagreement.

**Line 157**

```python
        self._pending_period: List[Optional[float]] = [None] * n_bands
```

Stores the most recent unconfirmed outer-period candidate.

**Line 158**

```python
        self._pending_pri_seed: List[Optional[float]] = [None] * n_bands
```

Stores the previous raw inner-PRI seed.

**Line 159**

```python
        self._trusted_pri_seed: List[Optional[float]] = [None] * n_bands
```

Stores the inner-PRI seed only after it agrees across calls.

**Line 160**

```python
        # beam_dwell_estimate is a never-shrinking MAX over noisy
```

Explains a bias in the beam-width estimate.

**Line 161**

```python
        # per-pass spans, so it systematically drifts toward the upper
```

The maximum tends to increase toward the upper tail.

**Line 162**

```python
        # tail of the true dwell's natural variation, not its center --
```

It estimates an upper bound more than an average.

**Line 163**

```python
        # confirmed directly across seeds (stabilizing at 13, 10, 7
```

Documents observed estimates.

**Line 164**

```python
        # against a true beam_dwell_steps=6). Dividing by more than 2
```

A divisor greater than two compensates for the upward bias.

**Line 165**

```python
        # compensates for that known upward bias when turning it into a
```

The estimate is later converted into a Gaussian width.

**Line 166**

```python
        # gaussian sigma, tightening the high-interest window back
```

The score should focus on the real beam window.

**Line 167**

```python
        # toward the actual illumination time instead of padding it.
```

Completes the explanation.

**Line 168**

```python
        self.beam_dwell_sigma_divisor = beam_dwell_sigma_divisor
```

Stores the divisor used to compute the beam score width.

**Line 169**

Blank line.

---

# Shared period search

## `_search_best_period()`: lines 170–205

**Line 170**

```python
    @staticmethod
```

Declares that the helper does not use instance state.

**Line 171**

```python
    def _search_best_period(times, refine_pri_fn, min_candidate=1):
```

Defines a shared period-search routine.

It can be used for:

- Inner PRI
- Outer scan period

**Line 172**

```python
        """Shared robust period search: GCD + mode + small-integer
```

Starts the method documentation.

**Line 173**

```
        submultiples + immediate neighbors of the pairwise-diff pool,
```

Lists the candidate-generation strategies.

**Line 174**

```
        each refined via least squares, best RELATIVE fit wins. Used
```

Every candidate is refined and compared using normalized RMSE.

**Line 175**

```
        for both the intra-burst PRI seed and the inter-burst
```

The helper is shared by both model layers.

**Line 176**

```
        scan_period, so both get the same protection against "a missed
```

Both models handle missed cycles consistently.

**Line 177**

```
        cycle produces a gap that's a multiple of the true period, not
```

A missed cycle can create a multiple-sized gap.

**Line 178**

```
        the period itself" -- which naive adjacent-gap median/stdev
```

Simple adjacent-gap statistics do not handle this well.

**Line 179**

```
        does not handle."""
```

Ends the documentation.

**Line 180**

```python
        if len(times) < 4:
```

Requires at least four time points.

**Line 181**

```python
            return None, None
```

Rejects insufficient data.

**Line 182**

```python
        diffs = [times[j] - times[i] for i in range(len(times)) for j in range(i + 1, len(times))]
```

Calculates every pairwise positive time difference.

**Line 183**

```python
        diffs = [d for d in diffs if d >= min_candidate]
```

Removes differences below the configured minimum candidate period.

**Line 184**

```python
        if not diffs:
```

Checks whether any differences remain.

**Line 185**

```python
            return None, None
```

Rejects the input if no valid differences exist.

**Line 186**

```python
        g = reduce(math.gcd, diffs)
```

Computes the GCD of all retained differences.

**Line 187**

```python
        mode_candidate, _freq = Counter(diffs).most_common(1)[0]
```

Finds the most common difference.

**Line 188**

```python
        candidates = {c for c in (g, mode_candidate) if c >= min_candidate}
```

Starts the candidate set with valid GCD and mode candidates.

**Line 189**

```python
        for k in (2, 3, 4, 5, 6, 7, 8):
```

Tests small divisors of the modal difference.

**Line 190**

```python
            sub = round(mode_candidate / k)
```

Calculates a rounded submultiple.

**Line 191**

```python
            if sub >= min_candidate:
```

Checks whether the submultiple is large enough.

**Line 192**

```python
                candidates.add(sub)
```

Adds the valid submultiple.

**Line 193**

```python
        for c in list(candidates):
```

Iterates over a snapshot of the candidates.

**Line 194**

```python
            for neighbor in (c - 1, c + 1):
```

Generates immediate integer neighbors.

**Line 195**

```python
                if neighbor >= min_candidate:
```

Rejects neighbors below the minimum period.

**Line 196**

```python
                    candidates.add(neighbor)
```

Adds valid neighbors.

**Line 197**

```python
        best_period, best_rmse, best_rel = None, None, None
```

Initializes the best-fit tracking variables.

**Line 198**

```python
        for c in candidates:
```

Evaluates every candidate period.

**Line 199**

```python
            refined, rmse = refine_pri_fn(times, c)
```

Uses the supplied refinement function to fit the candidate.

**Line 200**

```python
            if refined is None or rmse is None or refined < min_candidate * 0.5:
```

Rejects invalid or implausibly small refined periods.

**Line 201**

```python
                continue
```

Skips invalid candidates.

**Line 202**

```python
            rel = rmse / refined
```

Calculates relative fitting error.

**Line 203**

```python
            if best_rel is None or rel < best_rel:
```

Checks whether this candidate is the best so far.

**Line 204**

```python
                best_period, best_rmse, best_rel = refined, rmse, rel
```

Stores the best period and fitting statistics.

**Line 205**

```python
        return best_period, best_rmse
```

Returns the best refined period and its RMSE.

**Lines 206**

Blank line.

---

# Initial intra-burst PRI seed

## `_robust_intra_burst_pri_seed()`: lines 207–220

**Line 207**

```python
    def _robust_intra_burst_pri_seed(self, times):
```

Defines a method that estimates the rough inner PRI scale.

**Line 208**

```python
        """Rough estimate of the intra-burst spacing scale, used ONLY to
```

Starts the documentation.

**Line 209**

```
        set a burst-segmentation threshold -- not the final per-burst
```

This estimate is only used for separating bursts.

**Line 210**

```
        PRI (that's fit separately, per burst, once segmentation is
```

The final inner PRI is calculated later.

**Line 211**

```
        clean). A cluster of n nearby hits contributes O(n^2) pairwise
```

Dense bursts produce many short pairwise differences.

**Line 212**

```
        diffs at the intra-burst scale, while there are only
```

Inter-burst differences are less numerous near the short scale.

**Line 213**

```
        O(#bursts) diffs anywhere near the inter-burst scale, so the
```

The short-scale structure tends to dominate.

**Line 214**

```
        dominant small-scale structure in _search_best_period's result
```

The shared search can therefore find a useful inner-period seed.

**Line 215**

```
        is overwhelmingly intra-burst even with zero segmentation done
```

This works before the bursts have been explicitly separated.

**Line 216**

```
        yet -- this is what avoids the chicken-and-egg problem of
```

It avoids needing clean bursts before estimating PRI.

**Line 217**

```
        needing clean bursts to find PRI and needing PRI to find clean
```

The method breaks the circular dependency.

**Line 218**

```
        bursts."""
```

Ends the documentation.

**Line 219**

```python
        period, _rmse = self._search_best_period(times, self._refine_pri, min_candidate=1)
```

Runs the shared period search with the inherited least-squares refiner.

**Line 220**

```python
        return period
```

Returns only the rough period seed.

**Line 221**

Blank line.

---

# Cold-start burst segmentation

## `_segment_bursts_ratio()`: lines 222–240

**Line 222**

```python
    @staticmethod
```

Declares that this helper does not use instance state.

**Line 223**

```python
    def _segment_bursts_ratio(times, min_gap_ratio):
```

Defines the fallback segmentation method.

**Line 224**

```python
        """Cold-start fallback: split on the largest ratio jump between
```

Starts the method documentation.

**Line 225**

```
        sorted consecutive-hit gap values. Only used before enough data
```

Explains that gaps are sorted and compared.

**Line 226**

```
        exists to seed a PRI (see _segment_bursts_fixed for the
```

This is only used before a robust PRI seed exists.

**Line 227**

```
        normal path)."""
```

Ends the documentation.

**Line 228**

```python
        if len(times) < 2:
```

Checks whether at least two hit times exist.

**Line 229**

```python
            return [list(times)] if times else []
```

Returns:

- One burst containing the available times
- An empty list if there are no times

**Line 230**

```python
        gaps = sorted(set(b - a for a, b in zip(times[:-1], times[1:]) if b > a))
```

Calculates positive adjacent gaps, removes duplicates, and sorts them.

**Line 231**

```python
        split_value = None
```

Initializes the candidate gap boundary.

**Line 232**

```python
        if len(gaps) >= 2:
```

Only searches for a ratio jump if at least two distinct gap sizes exist.

**Line 233**

```python
            best_ratio = min_gap_ratio
```

Sets the minimum acceptable jump ratio.

**Line 234**

```python
            for g1, g2 in zip(gaps[:-1], gaps[1:]):
```

Examines adjacent values in the sorted gap list.

**Line 235**

```python
                ratio = g2 / g1
```

Calculates the ratio between two neighboring gap sizes.

**Line 236**

```python
                if ratio >= best_ratio:
```

Checks whether this gap jump is large enough.

**Line 237**

```python
                    best_ratio, split_value = ratio, (g1 + g2) / 2.0
```

Stores the strongest ratio and places the split threshold halfway between the two gap values.

**Line 238**

```python
        if split_value is None:
```

Checks whether no meaningful gap separation was found.

**Line 239**

```python
            return [list(times)]
```

Treats all times as one burst.

**Line 240**

```python
        return ScanAwarePRIScheduler._segment_bursts_fixed(times, split_value)
```

Uses the fixed-threshold segmentation helper with the discovered split value.



# `scan_aware_scheduler.py` — Part 2 of 3

This part covers **lines 241–480**, including:

- Fixed-threshold burst segmentation
- Scan-period model updates
- Inner PRI and beam-dwell estimation
- Burst-split validation

The checklist remains unchecked until Part 3 is complete.

---

# Fixed-threshold burst segmentation

## `_segment_bursts_fixed()`: lines 241–250

**Line 241**

Blank line.

**Line 242**

```python
    @staticmethod
```

Declares that the method does not use instance state.

**Line 243**

```python
    def _segment_bursts_fixed(times, split_value):
```

Defines a segmentation method that uses a fixed gap threshold.

**Line 244**

```python
        bursts = [[times[0]]]
```

Starts the first burst with the first observed hit.

This assumes `times` is non-empty.

**Line 245**

```python
        for prev, cur in zip(times[:-1], times[1:]):
```

Iterates through adjacent hit-time pairs.

**Line 246**

```python
            if cur - prev > split_value:
```

Checks whether the gap between adjacent hits is larger than the threshold.

A large gap indicates a new beam pass.

**Line 247**

```python
                bursts.append([cur])
```

Starts a new burst at the current hit.

**Line 248**

```python
            else:
```

Handles a gap that is small enough to belong to the current burst.

**Line 249**

```python
                bursts[-1].append(cur)
```

Adds the current hit to the most recent burst.

**Line 250**

```python
        return bursts
```

Returns the list of segmented bursts.

**Line 251**

Blank line.

---

# Updating the scan-period model

## `_update_scan_model()`: initial setup

### Lines 252–279

**Line 252**

```python
    def _update_scan_model(self, band):
```

Defines the method that updates the outer scan-period model for one band.

**Line 253**

```python
        times = self.hit_times[band]
```

Retrieves the recent hit times for the band.

**Line 254**

Blank line.

**Line 255**

```python
        raw_seed = self._robust_intra_burst_pri_seed(times)
```

Attempts to estimate the inner pulse spacing.

This estimate is used to determine how to segment bursts.

**Line 256**

```python
        # Stability-gate the SEED itself, one level upstream of the
```

Introduces a stability check for the inner PRI seed.

**Line 257**

```python
        # scan_period lock-stability gate below. Found directly (seed 7
```

Documents why this extra gate was needed.

**Line 258**

```python
        # of the mixed scenario): pri_seed can be wrong (39, a harmonic
```

A wrong seed may be a harmonic of the outer period.

**Line 259**

```python
        # of the OUTER period, not the true inner PRI of 3) and stay
```

The wrong value can remain consistently wrong across updates.

**Line 260**

```python
        # *consistently* wrong call after call -- not a one-off outlier
```

This is more dangerous than a single bad estimate.

**Line 261**

```python
        # but a systematic bias. Since it's consistent, it drives the
```

The bad seed can repeatedly influence segmentation.

**Line 262**

```python
        # SAME wrong multiplier sweep on consecutive calls and produces
```

The same incorrect segmentation can recur.

**Line 263**

```python
        # two consecutive outer-period fits (~482) that agree with each
```

The resulting wrong outer estimates may appear stable.

**Line 264**

```python
        # other, which is exactly what the scan_period_estimate
```

The normal stability gate might accept those estimates.

**Line 265**

```python
        # stability gate below was trusting as "real". Requiring the
```

The solution is to validate the seed first.

**Line 266**

```python
        # seed to reproduce itself across two independent calls before
```

The seed must agree across consecutive updates.

**Line 267**

```python
        # it's allowed to drive segmentation at all catches the
```

This catches the problem at its source.

**Line 268**

```python
        # corruption at its origin instead of downstream, where two
```

It prevents downstream gates from agreeing on the same corrupted input.

**Line 269**

```python
        # gates can each individually look satisfied while both
```

A pair of individually valid checks can still share the same bad seed.

**Line 270**

```python
        # being fed the same bad input.
```

Completes the explanation.

**Line 271**

```python
        pending_seed = self._pending_pri_seed[band]
```

Retrieves the previous raw inner-PRI seed.

**Line 272**

```python
        if raw_seed is not None and raw_seed >= 1:
```

Only processes a valid positive seed.

**Line 273**

```python
            if (pending_seed is not None and pending_seed >= 1
```

Checks that a previous valid seed exists.

**Line 274**

```python
                    and abs(raw_seed - pending_seed) <= self.period_agreement_tol * pending_seed):
```

Checks whether the new seed agrees with the old seed within the configured tolerance.

**Line 275**

```python
                self._trusted_pri_seed[band] = raw_seed
```

If the two seeds agree, promotes the new seed to trusted status.

**Line 276**

```python
            # else: leave the existing trusted seed (possibly None)
```

If the seeds disagree, the existing trusted seed is preserved.

**Line 277**

```python
            # alone -- don't jump to a single disagreeing new estimate.
```

The scheduler avoids switching to one unstable estimate.

**Line 278**

```python
            self._pending_pri_seed[band] = raw_seed
```

Stores the current raw seed for comparison during the next update.

**Line 279**

```python
        pri_seed = self._trusted_pri_seed[band]
```

Retrieves the currently trusted inner-PRI seed.

---

## Selecting a segmentation strategy

### Lines 281–320

**Line 281**

```python
        if pri_seed is None or pri_seed < 1:
```

Checks whether no trusted inner seed exists.

**Line 282**

```python
            # Too little data to seed a PRI yet -- cold-start fallback.
```

Documents the cold-start behavior.

**Line 283**

```python
            bursts = self._segment_bursts_ratio(times, self.min_gap_ratio)
```

Uses the ratio-jump fallback segmentation method.

**Line 284**

```python
            best = self._evaluate_burst_split(band, bursts, pri_seed)
```

Evaluates the resulting burst segmentation.

**Line 285**

```python
        else:
```

Handles the normal case with a trusted inner PRI seed.

**Line 286**

```python
            # A single fixed split multiplier is fragile when beam_dwell
```

Explains why several segmentation thresholds are tested.

**Line 287**

```python
            # is only a few multiples of PRI (missing just 1-2 intra-
```

Missing one or two inner pulses can make a true within-burst gap appear large.

**Line 288**

```python
            # burst pulses can push a real gap past a tight threshold,
```

A strict threshold could incorrectly split one burst.

**Line 289**

```python
            # wrongly splitting one true burst into two -- confirmed
```

Documents the observed failure.

**Line 290**

```python
            # directly: 2.5x split pri=3 into bursts whose onset gaps
```

A threshold of 2.5 times the inner PRI caused bad segmentation.

**Line 291**

```python
            # were STILL all clean multiples of 3, degenerating the
```

The resulting burst onsets still appeared to follow the inner PRI.

**Line 292**

```python
            # outer fit right back to 3). Try a spread of multipliers
```

The fix tests multiple thresholds.

**Line 293**

```python
            # and let whichever produces the best-fitting, non-
```

Each segmentation is evaluated by fit quality and degeneracy guards.

**Line 294**

```python
            # degenerate outer period win -- same "search candidates,
```

The method follows the project's general candidate-search pattern.

**Line 295**

```python
            # keep the best fit" approach used everywhere else here.
```

The best valid outer period is selected.

**Line 296**

```python
            best = None
```

Initializes the best segmentation result.

**Line 297**

```python
            # Multipliers capped at 6.0: wider ones (9.0, 13.0, tried in
```

Documents the maximum threshold multiplier.

**Line 298**

```python
            # earlier iterations of this fix) produce split thresholds
```

Larger multipliers were tested previously.

**Line 299**

```python
            # that can approach or exceed the true inter-pass gap for
```

Very wide thresholds can merge separate beam passes.

**Line 300**

```python
            # realistic period/dwell ratios, which merges consecutive
```

This destroys the outer-period structure.

**Line 301**

```python
            # beam passes into one "burst" by construction -- found
```

Documents the observed problem.

**Line 302**

```python
            # directly (seed 16): mult=13.0 against pri_seed=3 gave a
```

Provides a concrete example.

**Line 303**

```python
            # split of 39 against a true period of 40, guaranteeing
```

The threshold was almost equal to the actual scan period.

**Line 304**

```python
            # merges. A period-aware exclusion bound was tried instead
```

Another attempted fix used the estimated period to restrict thresholds.

**Line 305**

```python
            # of trimming the list, but it created a worse failure: once
```

That alternative introduced a new failure mode.

**Line 306**

```python
            # scan_period_estimate freezes on any value (even one
```

A rejected or stale period could remain stored.

**Line 307**

```python
            # already rejected back to scan_confidence=0.0), the bound
```

The stale value still affected threshold selection.

**Line 308**

```python
            # derived from that frozen value can end up excluding every
```

All candidate multipliers could be eliminated.

**Line 309**

```python
            # multiplier including the smallest, permanently starving
```

No new scan-period estimate could then be generated.

**Line 310**

```python
            # the sweep (found directly, seed 0: 90 scans total in an
```

Documents an extreme result.

**Line 311**

```python
            # 8000-step episode, then silence). Missing 1-2 intra-burst
```

The scheduler effectively stopped exploring.

**Line 312**

```python
            # pulses -- the reason a spread of multipliers exists at
```

The threshold spread is still necessary to handle missed inner pulses.

**Line 313**

```python
            # all -- only needs a modest margin above 2x PRI; 6.0x
```

A multiplier of six is considered sufficient.

**Line 314**

```python
            # already covers missing several consecutive pulses without
```

It accommodates several missed inner hits.

**Line 315**

```python
            # ever approaching a realistic period.
```

It remains safely below typical outer scan periods.

**Line 316**

```python
            for mult in (2.0, 2.5, 3.0, 4.0, 6.0):
```

Tests five segmentation multipliers.

**Line 317**

```python
                bursts = self._segment_bursts_fixed(times, pri_seed * mult)
```

Segments the hit times using the current multiplier.

**Line 318**

```python
                result = self._evaluate_burst_split(band, bursts, pri_seed)
```

Evaluates the candidate segmentation.

**Line 319**

```python
                if result is not None and (best is None or result[-1] < best[-1]):
```

Accepts the result if valid and better than the existing best relative error.

**Line 320**

```python
                    best = result
```

Stores the best segmentation result.

---

## Handling failed scan-period fits

### Lines 322–359

**Line 322**

```python
        if best is None:
```

Checks whether no segmentation produced a trustworthy outer-period candidate.

**Line 323**

```python
            self.scan_confidence[band] = 0.0
```

Clears the outer-period confidence.

**Line 324**

```python
            # self.confidence[band] (read by the inherited choose_bands)
```

Introduces an important synchronization requirement.

**Line 325**

```python
            # must be kept in sync with scan_confidence here too, not
```

The inherited scheduler reads `self.confidence`.

**Line 326**

```python
            # just on the success path below -- found directly (seed 11
```

Documents a bug where only the success path updated it.

**Line 327**

```python
            # of the mixed scenario): without this line, a stale
```

A previous confidence could remain in memory.

**Line 328**

```python
            # self.confidence left over from an earlier successful
```

The stale confidence might indicate a lock that no longer exists.

**Line 329**

```python
            # round (e.g. 1.0 from a since-rejected false lock) stays
```

A rejected lock could leave confidence at one.

**Line 330**

```python
            # frozen forever once _update_scan_model starts taking this
```

The stale value would never be corrected.

**Line 331**

```python
            # early-return branch every time. choose_bands' blended
```

This would corrupt the inherited scoring formula.

**Line 332**

```python
            # score is (1-conf)*belief + conf*periodicity_weight*
```

Shows the inherited blend.

**Line 333**

```python
            # periodic; with conf stuck at 1.0 and periodic correctly
```

A stale confidence of one gives full control to periodicity.

**Line 334**

```python
            # at 0.0 (periodicity_score does read the fresh
```

The periodicity score itself correctly sees the new zero confidence.

**Line 335**

```python
            # scan_confidence), BOTH terms of blended collapse to zero
```

Both belief and periodicity contributions become zero.

**Line 336**

```python
            # -- not just underweighted, entirely zeroed -- so the band
```

The band is effectively scored only by exploration.

**Line 337**

```python
            # only ever scores from its raw UCB exploration bonus. That
```

Its normal value is discarded.

**Line 338**

```python
            # silently starves scan_count for the rest of the episode
```

The band receives very few future scans.

**Line 339**

```python
            # (confirmed: 63 scans total across 8000 steps) with no
```

Documents the measured consequence.

**Line 340**

```python
            # visible sign in scan_confidence, which correctly read 0.0
```

The outer confidence appeared correct, hiding the synchronization bug.

**Line 341**

```python
            # the whole time -- the bug was in a value nothing else
```

The incorrect field was `self.confidence`.

**Line 342**

```python
            # was checking.
```

Completes the explanation.

**Line 343**

```python
            self.confidence[band] = 0.0
```

Synchronizes inherited confidence with the failed scan-period confidence.

**Line 344**

```python
            self.burst_starts[band] = []
```

Clears previously stored burst starts.

**Line 345**

```python
            # For intra-burst PRI/beam-dwell tracking while scan_period
```

Introduces fallback tracking even without a valid outer lock.

**Line 346**

```python
            # is still unresolved, use the TIGHTEST seeded split (or
```

If an inner seed exists, use the smallest threshold.

**Line 347**

```python
            # skip entirely if no seed exists yet) -- NOT the raw
```

Do not use the unstable ratio fallback for beam-width tracking.

**Line 348**

```python
            # ratio-jump fallback, which can return one mega-burst
```

The ratio method may merge nearly all hits.

**Line 349**

```python
            # spanning nearly the whole hit history when there's no
```

Such a mega-burst would be unrealistic.

**Line 350**

```python
            # clear separation yet. beam_dwell_estimate is a never-
```

The beam estimate is persistent and cannot shrink.

**Line 351**

```python
            # shrinking max, so a single such mega-burst would corrupt
```

One bad fallback could permanently inflate it.

**Line 352**

```python
            # it permanently (confirmed directly: a degenerate span
```

Documents the observed impact.

**Line 353**

```python
            # inflated it to ~200 against a true beam_dwell of 6,
```

The estimate became far too wide.

**Line 354**

```python
            # which then made every future periodicity score
```

The inflated width affected future scoring.

**Line 355**

```python
            # uselessly wide regardless of whether scan_period ever
```

The score lost useful selectivity.

**Line 356**

```python
            # locked correctly afterward).
```

Completes the warning.

**Line 357**

```python
            if pri_seed is not None and pri_seed >= 1:
```

Checks whether a usable inner seed exists.

**Line 358**

```python
                self._update_intra_burst_state(band, self._segment_bursts_fixed(times, pri_seed * 2.0))
```

Uses the tightest seeded split to update inner PRI and beam-width state.

**Line 359**

```python
            return
```

Stops the scan-model update after the failed outer fit.

---

## Publishing a candidate scan period

### Lines 361–400

**Line 361**

```python
        bursts, onsets, refined, rmse, _rel = best
```

Unpacks the best segmentation result:

- Bursts
- Burst onset times
- Refined outer period
- RMSE
- Relative error

**Line 362**

```python
        # Update intra-burst PRI/beam-dwell BEFORE (possibly) publishing
```

Explains the order of updates.

**Line 363**

```python
        # the new candidate period below: the sane_cap inside this call
```

The inner-state update uses a sanity cap.

**Line 364**

```python
        # must be scaled off the last TRUSTED scan_period_estimate, not
```

It must not use the unconfirmed new candidate.

**Line 365**

```python
        # off a brand-new, not-yet-confirmed candidate.
```

This prevents a bad candidate from loosening its own validation.

**Line 366**

```python
        self._update_intra_burst_state(band, bursts)
```

Updates inner PRI, inner jitter, and beam-width estimates.

**Line 367**

```python
        self.burst_starts[band] = onsets
```

Stores the new burst onset times.

**Line 368**

Blank line.

**Line 369**

```python
        pending = self._pending_period[band]
```

Retrieves the previous unconfirmed outer-period candidate.

**Line 370**

```python
        agrees_with_pending = (pending is not None and pending > 0
```

Begins checking whether the new candidate agrees with the previous candidate.

**Line 371**

```python
                                and abs(refined - pending) <= self.period_agreement_tol * pending)
```

Requires relative agreement within the configured tolerance.

**Line 372**

```python
        if agrees_with_pending:
```

Handles the case where two consecutive independent estimates agree.

**Line 373**

```python
            # Two independent fits (this call and the last one, over a
```

Explains the stability requirement.

**Line 374**

```python
            # hit history that grew in between) landing within
```

The second fit is based on additional observations.

**Line 375**

```python
            # tolerance of each other is real signal that this is a
```

Agreement is treated as evidence of a genuine period.

**Line 376**

```python
            # genuine period, not a one-off overfit -- publish it as
```

The period can now be trusted.

**Line 377**

```python
            # the trusted estimate used both for periodicity scoring
```

The estimate drives future burst scoring.

**Line 378**

```python
            # and for the beam_dwell sane_cap.
```

It also controls beam-width validation.

**Line 379**

```python
            confidence = min(1.0, max(0.0, 1.0 - rmse / (self.confidence_scale * refined)))
```

Calculates and clamps confidence using relative RMSE.

**Line 380**

```python
            self.scan_period_estimate[band] = refined
```

Publishes the newly trusted outer scan period.

**Line 381**

```python
            self.scan_jitter_estimate[band] = max(0.5, rmse)
```

Stores outer-period timing uncertainty.

**Line 382**

```python
            self.scan_confidence[band] = confidence
```

Stores confidence in the scan-period estimate.

**Line 383**

```python
        elif self.scan_period_estimate[band] is None:
```

Handles a disagreeing candidate when no trusted scan period exists yet.

**Line 384**

```python
            # Nothing trusted yet and this candidate doesn't match the
```

Explains why the candidate is not published.

**Line 385**

```python
            # last one either -- hold at zero confidence rather than
```

Confidence remains zero.

**Line 386**

```python
            # publishing an unconfirmed single fit (this is exactly
```

A single fit is not sufficient.

**Line 387**

```python
            # what let a spurious 89.7-step lock through previously).
```

References the earlier false-lock failure.

**Line 388**

```python
            self.scan_confidence[band] = 0.0
```

Keeps the outer confidence at zero.

**Line 389**

```python
        # else: a fit already exists and this new candidate disagrees
```

Handles the case where an existing trusted estimate conflicts with a new candidate.

**Line 390**

```python
        # with the last one -- keep trusting the existing lock rather
```

The existing trusted lock is preserved.

**Line 391**

```python
        # than jumping to a single disagreeing new fit.
```

The scheduler avoids instability.

**Line 392**

```python
        self._pending_period[band] = refined
```

Stores the new candidate for comparison with the next update.

**Line 393**

Blank line.

**Line 394**

```python
        # Overall confidence gates the belief-vs-periodic blend in the
```

Explains how scan confidence affects the inherited scheduler.

**Line 395**

```python
        # inherited choose_bands(): without a scan_period lock there's
```

No usable outer prediction exists without a scan-period lock.

**Line 396**

```python
        # no usable periodic prediction at all, regardless of how good
```

A good inner PRI alone is insufficient.

**Line 397**

```python
        # the intra-burst PRI fit looks in isolation (you'd need to
```

The scheduler must know when to return to the beam.

**Line 398**

```python
        # already be scanning during a burst to have observed it).
```

This explains why outer-period confidence gates the combined score.

**Line 399**

```python
        self.confidence[band] = self.scan_confidence[band]
```

Synchronizes the inherited confidence field with scan-period confidence.

**Line 400**

Blank line.

---

# Inner PRI and beam-dwell state

## `_update_intra_burst_state()`: lines 401–424

**Line 401**

```python
    def _update_intra_burst_state(self, band, bursts):
```

Defines the method that updates the fast PRI and beam-width estimates.

**Line 402**

```python
        """intra-burst PRI + persistent beam-dwell width, factored out
```

Starts the method documentation.

**Line 403**

```
        so both the successful-lock path and the no-lock fallback path
```

This method is used whether or not the outer period has locked.

**Line 404**

```
        can update it consistently.
```

Ensures both paths use identical state updates.

**Line 405**

Blank documentation line.

**Line 406**

```
        Both quantities below are computed only from TYPICAL-sized
```

The method filters out abnormal burst sizes.

**Line 407**

```
        bursts, not the raw split. Found directly: a merged burst
```

Merged bursts can corrupt both estimates.

**Line 408**

```
        (e.g. size 11 against a true ~2-pulse beam pass) doesn't just
```

Provides an example of a merged burst.

**Line 409**

```
        corrupt beam_dwell_estimate via its span -- it also dumps a
```

The merged burst affects more than the beam width.

**Line 410**

```
        pile of its own internal gaps into the intra_gaps pool used to
```

Its internal gaps enter the inner PRI fitting data.

**Line 411**

```
        fit pri_estimate. Those internal gaps sit near the OUTER scan
```

The merged-burst gaps can resemble the outer scan period.

**Line 412**

```
        period (since the "burst" is actually several merged beam
```

The apparent burst contains multiple real passes.

**Line 413**

```
        passes), which drags pri_estimate up from the true ~3 toward
```

The inner PRI estimate becomes too large.

**Line 414**

```
        the scan period itself (confirmed: pri_estimate climbing to
```

Documents the observed corruption.

**Line 415**

```
        36-39 against scan_period~40). Once pri_estimate is corrupted
```

The inner estimate nearly equals the outer period.

**Line 416**

```
        that way, every downstream consumer (min_scan_to_pri_ratio's
```

Other safeguards then use the incorrect number.

**Line 417**

```
        degeneracy guard, the sane_cap below) is now working off a
```

The error propagates through the model.

**Line 418**

```
        wrong number too -- so the typical-size filter has to be
```

Therefore filtering must happen first.

**Line 419**

```
        applied before either estimate is touched, not just tacked
```

The method filters before calculating PRI or beam width.

**Line 420**

```
        onto the beam_dwell computation."""
```

Ends the documentation.

**Line 421**

```python
        sizes = [len(b) for b in bursts if b]
```

Collects the size of every nonempty burst.

**Line 422**

```python
        median_size = statistics.median(sizes) if sizes else 0
```

Calculates the median burst size, or zero if no bursts exist.

**Line 423**

```python
        tolerance = max(1, 0.5 * median_size)
```

Defines how far a burst size may differ from the median while remaining typical.

The tolerance is at least one hit.

**Line 424**

```python
        typical_bursts = [b for b in bursts if b and abs(len(b) - median_size) <= tolerance]
```

Keeps only bursts whose sizes are close to the median.

---

## Estimating the inner PRI

### Lines 426–437

**Line 426**

```python
        intra_gaps = []
```

Creates a list for within-burst pulse gaps.

**Line 427**

```python
        for burst in typical_bursts:
```

Processes each typical burst.

**Line 428**

```python
            if len(burst) >= self.min_burst_hits:
```

Uses only bursts containing enough hits.

**Line 429**

```python
                intra_gaps.extend(b - a for a, b in zip(burst[:-1], burst[1:]))
```

Calculates and collects consecutive gaps within the burst.

**Line 430**

```python
        if len(intra_gaps) >= 3:
```

Requires at least three inner gaps before estimating PRI.

**Line 431**

```python
            self.pri_estimate[band] = statistics.median(intra_gaps)
```

Sets the inner PRI estimate to the median within-burst gap.

**Line 432**

```python
            spread = statistics.pstdev(intra_gaps) if len(intra_gaps) > 1 else 0.5
```

Calculates the population standard deviation of the inner gaps.

**Line 433**

```python
            self.jitter_estimate[band] = max(0.5, spread)
```

Stores the inner timing uncertainty with a minimum of `0.5`.

**Line 434**

```python
            cov = spread / max(1e-6, self.pri_estimate[band])
```

Calculates the coefficient of variation.

The tiny denominator floor prevents division by zero.

**Line 435**

```python
            self.pri_confidence[band] = max(0.0, min(1.0, 1.0 - cov))
```

Converts the coefficient of variation into confidence.

Low variation produces high confidence.

**Line 436**

```python
        else:
```

Handles the case where there are too few inner gaps.

**Line 437**

```python
            self.pri_confidence[band] = 0.0
```

Clears inner PRI confidence.

---

## Estimating beam dwell width

### Lines 439–457

**Line 439**

```python
        if typical_bursts:
```

Checks whether at least one typical burst exists.

**Line 440**

```python
            last_typical = typical_bursts[-1]
```

Selects the most recent typical burst.

**Line 441**

```python
            span = last_typical[-1] - last_typical[0]
```

Calculates the time span from the first to last hit in that burst.

**Line 442**

```python
            # Defensive sanity cap: beam_dwell_estimate is a never-
```

Introduces validation for the persistent beam-width estimate.

**Line 443**

```python
            # shrinking max, so one bad segmentation could otherwise
```

A bad segmentation could permanently inflate it.

**Line 444**

```python
            # corrupt it permanently. A genuine beam dwell can't be
```

The real beam dwell should be relatively short.

**Line 445**

```python
            # anywhere near a full scan_period (SpatiallyScanningEmitter
```

The wrapped emitter itself prevents beam dwell from exceeding the scan period.

**Line 446**

```python
            # itself enforces beam_dwell <= scan_period at construction,
```

References the emitter's constructor validation.

**Line 447**

```python
            # and physically it's the SMALL fraction of a rotation the
```

The main beam normally points at the receiver for only part of a rotation.

**Line 448**

```python
            # beam is on you) -- so bound it relative to whichever
```

The estimate should have a relative sanity bound.

**Line 449**

```python
            # period signal is available, not just a loose PRI multiple.
```

The cap should use both inner and outer periodicity when possible.

**Line 450**

```python
            pri = self.pri_estimate[band]
```

Retrieves the current inner PRI estimate.

**Line 451**

```python
            period = self.scan_period_estimate[band]
```

Retrieves the trusted outer scan period.

**Line 452**

```python
            sane_cap = 30 * pri if pri else float("inf")
```

Starts the sanity cap at thirty times the inner PRI.

If no PRI exists, the initial cap is infinite.

**Line 453**

```python
            if period:
```

Checks whether an outer period is available.

**Line 454**

```python
                sane_cap = min(sane_cap, 0.5 * period)
```

Limits the cap to at most half the outer period.

**Line 455**

```python
            if span + 1 <= sane_cap:
```

Checks whether the observed burst span is plausible.

The `+1` converts a difference between endpoints into an approximate number of occupied steps.

**Line 456**

```python
                self.beam_dwell_estimate[band] = max(self.beam_dwell_estimate[band], span + 1)
```

Updates the persistent beam-width estimate, never decreasing it.

**Line 457**

Blank line.

---

# Evaluating a burst segmentation

## `_evaluate_burst_split()`: lines 458–480

**Line 458**

```python
    def _evaluate_burst_split(self, band, bursts, pri_seed):
```

Defines a method that validates one candidate burst segmentation.

**Line 459**

```python
        """Checks one candidate burst segmentation against the size-
```

Starts the documentation.

**Line 460**

```
        consistency and degeneracy gates, and if it passes, returns
```

The method applies several safety checks.

**Line 461**

```
        (bursts, onsets, refined_period, rmse, relative_fit) -- or None
```

Documents the successful return format.

**Line 462**

```
        if this split doesn't produce a trustworthy outer period."""
```

Ends the documentation.

**Line 463**

```python
        onsets = [b[0] for b in bursts if len(b) >= 1]
```

Extracts the first hit time from every nonempty burst.

**Line 464**

```python
        if len(onsets) < self.min_bursts:
```

Checks whether enough bursts exist.

**Line 465**

```python
            return None
```

Rejects the segmentation if too few bursts were found.

**Line 466**

```python
        sizes = [len(b) for b in bursts if len(b) >= 1]
```

Collects the sizes of all nonempty bursts.

**Line 467**

```python
        # Raw coefficient-of-variation on burst sizes is oversensitive
```

Explains why burst-size consistency is not measured with ordinary CoV.

**Line 468**

```python
        # at small absolute scale: with mean size ~1-2 (this band is
```

When bursts contain only one or two hits, one extra hit changes CoV dramatically.

**Line 469**

```python
        # barely being scanned twice per pass), a single burst of size
```

Sparse observations naturally cause small-size variation.

**Line 470**

```python
        # 3 or 7 swings CoV wildly even though it's still plausibly the
```

Large relative variation may still be reasonable.

**Line 471**

```python
        # same target occasionally catching one extra/fewer pulse.
```

The target may produce slightly different observed burst sizes.

**Line 472**

```python
        # Check instead what fraction of bursts sit within +-1 of the
```

The implementation uses a tolerance around the median.

**Line 473**

```python
        # median size -- tolerant of natural small-N variability, still
```

This is more robust for small samples.

**Line 474**

```python
        # rejects genuinely erratic (non-periodic) segmentations.
```

It still rejects highly inconsistent patterns.

**Line 475**

```python
        median_size = statistics.median(sizes) if sizes else 0
```

Calculates the median burst size.

**Line 476**

```python
        near_median_frac = (sum(1 for s in sizes if abs(s - median_size) <= 1) / len(sizes)
```

Calculates the fraction of burst sizes within one hit of the median.

**Line 477**

```python
                             if sizes else 0.0)
```

Uses zero when there are no sizes.

**Line 478**

```python
        if near_median_frac < self.min_burst_size_consistency:
```

Checks whether the fraction meets the configured requirement.

**Line 479**

```python
            return None
```

Rejects inconsistent burst segmentation.

**Line 480**

```python
        refined, rmse = self._search_best_period(
```

Begins searching for the outer period using the burst onset times.



# `scan_aware_scheduler.py` — Part 3 of 3

This final part covers **lines 481–609** and completes the file. The checklist has now been marked complete.

---

# Completing `_evaluate_burst_split()`

## Lines 481–497

**Line 481**

```python
            onsets, self._refine_pri,
```

Continues the call to `_search_best_period()`.

The burst onset times are passed as the data, and `_refine_pri` is used to refine candidates.

**Line 482**

```python
            # Excluding degenerate candidates from the search itself,
```

Begins an explanation of the minimum outer-period constraint.

**Line 483**

```python
            # not just rejecting them after the fact: since the inner
```

The implementation excludes invalid candidates before fitting rather than afterward.

**Line 484**

```python
            # PRI gates every transmission opportunity (beam-window
```

The inner PRI controls the possible transmission times.

**Line 485**

```python
            # catches AND sidelobe leaks alike), candidate=pri_seed is
```

Even sidelobe observations are still constrained by the inner pulse timing.

**Line 486**

```python
            # an exact algebraic divisor of every onset time and will
```

The inner PRI can explain burst-onset differences mathematically.

**Line 487**

```python
            # ALWAYS win a best-relative-fit contest against the true
```

It may fit better than the actual outer period.

**Line 488**

```python
            # outer period, structurally -- not from noise. Asking
```

This is a structural degeneracy, not a random error.

**Line 489**

```python
            # _search_best_period to only consider candidates already
```

The search is constrained to avoid such candidates.

**Line 490**

```python
            # >= pri_seed * min_scan_to_pri_ratio forces it to report
```

The candidate must be sufficiently larger than the inner PRI.

**Line 491**

```python
            # the best candidate that COULD be the outer period,
```

This makes the search focus on plausible scan periods.

**Line 492**

```python
            # instead of finding pri_seed, discarding it as degenerate,
```

Without the constraint, the search could select the inner PRI.

**Line 493**

```python
            # and giving up with nothing.
```

The constraint avoids ending with no outer-period result.

**Line 494**

```python
            min_candidate=int(pri_seed * self.min_scan_to_pri_ratio) if pri_seed else 1)
```

Sets the minimum candidate period.

If a seed exists, the minimum is:

```
integer PRI seed × minimum outer/inner ratio
```

Otherwise, the minimum defaults to one.

**Line 495**

```python
        if refined is None or rmse is None or refined <= 0:
```

Checks whether the outer-period fit is valid.

**Line 496**

```python
            return None
```

Rejects invalid results.

**Line 497**

```python
        return bursts, onsets, refined, rmse, rmse / refined
```

Returns:

- Burst segmentation
- Burst onset times
- Refined outer period
- RMSE
- Relative fitting error

**Line 498**

Blank line.

---

# Scan-aware periodicity score

## `_periodicity_score()`: lines 499–526

**Line 499**

```python
    def _periodicity_score(self, band, t):
```

Defines the combined periodicity score for one band at time `t`.

**Line 500**

```python
        scan_conf = self.scan_confidence[band]
```

Reads confidence in the outer scan-period model.

**Line 501**

```python
        period = self.scan_period_estimate[band]
```

Reads the estimated outer scan period.

**Line 502**

```python
        if scan_conf <= 0 or period is None or not self.burst_starts[band]:
```

Checks whether a usable outer model exists.

It requires:

- Positive scan confidence
- A scan-period estimate
- At least one known burst start

**Line 503**

```python
            return 0.0
```

Returns no periodicity score if the outer model is unavailable.

**Line 504**

```python
        last_burst = self.burst_starts[band][-1]
```

Retrieves the most recent burst-start time.

**Line 505**

```python
        phase = (t - last_burst) % period
```

Calculates the current position within the outer scan cycle.

**Line 506**

```python
        dist = min(phase, period - phase)
```

Calculates circular distance from the nearest predicted burst onset.

**Line 507**

```python
        dist = max(0.0, dist - self.switch_lead_steps)
```

Subtracts the configured switch lead.

This creates an early plateau so the receiver can retune before the predicted burst.

**Line 508**

```python
        sigma = max(0.5, self.scan_jitter_estimate[band],
```

Begins calculating the Gaussian width for the burst score.

**Line 509**

```python
                    self.beam_dwell_estimate[band] / self.beam_dwell_sigma_divisor)
```

Uses the largest of:

- Minimum width `0.5`
- Estimated scan jitter
- Estimated beam dwell divided by its sigma divisor

**Line 510**

```python
        burst_score = math.exp(-(dist ** 2) / (2 * sigma ** 2))
```

Calculates the Gaussian score for proximity to the expected beam return.

The score is highest near the predicted burst.

**Line 511**

Blank line.

**Line 512**

```python
        pri_conf = self.pri_confidence[band]
```

Reads confidence in the inner PRI model.

**Line 513**

```python
        pri = self.pri_estimate[band]
```

Reads the inner PRI estimate.

**Line 514**

```python
        if pri_conf > 0 and pri and self.hit_times[band]:
```

Checks whether a usable inner PRI model exists.

**Line 515**

```python
            last_hit = self.hit_times[band][-1]
```

Retrieves the latest observed pulse time.

**Line 516**

```python
            phase2 = (t - last_hit) % pri
```

Calculates the current phase within the inner PRI cycle.

**Line 517**

```python
            dist2 = min(phase2, pri - phase2)
```

Calculates the circular distance to the nearest expected pulse.

**Line 518**

```python
            sigma2 = max(0.5, self.jitter_estimate[band])
```

Calculates the inner timing width, with a minimum of `0.5`.

**Line 519**

```python
            pri_score = math.exp(-(dist2 ** 2) / (2 * sigma2 ** 2))
```

Calculates the Gaussian score for the predicted intra-burst pulse.

**Line 520**

```python
        else:
```

Handles the case where the inner PRI is not yet reliable.

**Line 521**

```python
            # No fine-grained intra-burst timing yet -- don't suppress
```

Explains why the inner score should not penalize the band prematurely.

**Line 522**

```python
            # interest across the whole predicted burst window just
```

The scheduler should still favor the band during a predicted burst.

**Line 523**

```python
            # because we haven't resolved PRI within it yet.
```

Lack of inner lock should not prevent early burst discovery.

**Line 524**

```python
            pri_score = 1.0
```

Uses a neutral inner score.

**Line 525**

Blank line.

**Line 526**

```python
        return burst_score * pri_score
```

Combines the outer and inner scores multiplicatively.

This means:

- Outside a predicted burst, the total score is low.
- Inside a predicted burst, inner PRI timing can sharpen the score.

**Line 527**

Blank line.

---

# Scan-aware band selection

## `choose_bands()`: lines 528–567

**Line 528**

```python
    def choose_bands(self, k):
```

Defines the multi-band selection method.

**Line 529**

```python
        self.t += 1
```

Advances the scheduler's internal clock.

**Line 530**

```python
        if self.t <= self.warmup_steps:
```

Checks whether the scheduler is still warming up.

**Line 531**

```python
            for b in range(self.n_bands):
```

Iterates through all bands.

**Line 532**

```python
                self._propagate(b)
```

Advances each band's Markov belief.

**Line 533**

```python
            return self._warmup_bands(k)
```

Uses the inherited warm-up scan order.

**Line 534**

```python
        for b in range(self.n_bands):
```

After warm-up, iterates through every band.

**Line 535**

```python
            self._propagate(b)
```

Predicts each band's Markov activity.

**Line 536**

```python
        scores = []
```

Creates a list for final band scores.

**Line 537**

```python
        for b in range(self.n_bands):
```

Begins scoring each band.

**Line 538**

```python
            ucb_bonus = self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
```

Calculates the normal UCB exploration bonus.

**Line 539**

```python
            conf = self.confidence[b]
```

Reads the outer scan-period confidence.

This inherited field is synchronized by `_update_scan_model()`.

**Line 540**

```python
            periodic = self._periodicity_score(b, self.t)
```

Calculates the combined outer/inner periodicity score.

**Line 541**

```python
            blended = (1 - conf) * self.belief[b] + conf * self.periodicity_weight * periodic
```

Blends Markov belief and scan-aware periodicity.

- Low confidence → mostly Markov belief
- High confidence → mostly nested periodicity

**Line 542**

```python
            # Extra exploration pull for a high-priority band that
```

Introduces a special pre-lock exploration adjustment.

**Line 543**

```python
            # hasn't locked yet. The base class's UCB bonus is NOT
```

The ordinary UCB bonus is not priority-weighted.

**Line 544**

```python
            # weighted by priority -- only the "known value" (blended)
```

Priority normally affects only the exploitation component.

**Line 545**

```python
            # term is -- so a rare, low-occupancy but important target
```

A high-priority sparse band may still receive too little exploration.

**Line 546**

```python
            # competes for scan time on equal exploration footing with
```

Its exploration bonus is otherwise the same as every other band.

**Line 547**

```python
            # every other band, even though bootstrapping a scan_period
```

Outer-period learning requires special observation patterns.

**Line 548**

```python
            # lock specifically needs several CONSECUTIVE close-
```

The scheduler needs repeated nearby hits to identify a burst.

**Line 549**

```python
            # together hits (to see intra-burst gaps at all), not just
```

Occasional isolated hits are not sufficient.

**Line 550**

```python
            # occasional isolated ones. Found directly (seeds 9, 16,
```

Documents observed failures.

**Line 551**

```python
            # 20, 21, 22, 24 of the mixed scenario, uncovered only
```

Several random seeds failed to bootstrap the scan model.

**Line 552**

```python
            # after fixing the confidence-desync bug above -- that bug
```

These failures became visible only after an earlier bug was fixed.

**Line 553**

```python
            # had been masking this separate, broader issue): even with
```

The issue was independent of confidence synchronization.

**Line 554**

```python
            # confidence correctly falling back to pure belief pre-
```

Even correct pre-lock behavior was insufficient.

**Line 555**

```python
            # lock, belief alone for a naturally-sparse band stayed too
```

Sparse bands had low Markov belief.

**Line 556**

```python
            # low against louder comms bands to ever earn enough
```

Louder communications bands dominated the score.

**Line 557**

```python
            # consecutive visits, leaving scan_period_estimate at None
```

The outer model never got enough data.

**Line 558**

```python
            # (never even a first candidate) for the whole episode.
```

The band remained uncharacterized.

**Line 559**

```python
            # Scaling the bonus by priority ONLY pre-lock (conf<=0)
```

The fix increases exploration only before a lock exists.

**Line 560**

```python
            # targets exactly the bootstrap phase; once locked, the
```

After a lock, the normal periodicity score takes over.

**Line 561**

```python
            # periodicity term already takes over and this has no
```

The special pre-lock adjustment is no longer needed.

**Line 562**

```python
            # further effect.
```

Completes the explanation.

**Line 563**

```python
            if conf <= 0:
```

Checks whether the band has not yet acquired scan-period confidence.

**Line 564**

```python
                ucb_bonus *= self.priority[b]
```

Temporarily scales exploration by priority.

This gives important sparse bands more opportunity to bootstrap.

**Line 565**

```python
            scores.append(self.priority[b] * blended + ucb_bonus)
```

Adds the priority-weighted exploitation score and adjusted UCB bonus.

**Line 566**

```python
        order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
```

Sorts all bands by descending score.

**Line 567**

```python
        return order[:k]
```

Returns the highest-scoring `k` bands.

**Line 568**

Blank line.

---

# Updating observations

## `update()`: lines 569–580

**Line 569**

```python
    def update(self, band, observed_on):
```

Defines the observation-update method.

**Line 570**

```python
        # Deliberately skip PRIAwareScheduler.update (it would call the
```

Explains why the normal v3 update method is bypassed.

**Line 571**

```python
        # single-periodicity _update_pri_model this class overrides the
```

The v3 method is designed for a single periodicity.

**Line 572**

```python
        # meaning of); go straight to the belief/UCB update it wraps.
```

The code calls the grandparent update instead.

**Line 573**

```python
        super(PRIAwareScheduler, self).update(band, observed_on)
```

Calls the method after `PRIAwareScheduler` in the method-resolution order.

That reaches the v2 `BeliefUCBScheduler.update()` implementation, updating:

- Markov transitions
- Belief
- Scan count

**Line 574**

```python
        if observed_on:
```

Only confirmed hits provide timing information.

**Line 575**

```python
            times = self.hit_times[band]
```

Retrieves the band's hit-time history.

**Line 576**

```python
            times.append(self.t)
```

Records the current scheduler time.

**Line 577**

```python
            if len(times) > self.history_len:
```

Checks whether the sliding hit history is too long.

**Line 578**

```python
                del times[0]
```

Removes the oldest hit.

**Line 579**

```python
            self._update_scan_model(band)
```

Updates the nested scan-period model.

**Line 580**

Blank line.

---

# Standalone demonstration

## Lines 582–588

**Line 582**

```python
if __name__ == "__main__":
```

Checks whether this module is being run directly.

**Line 583**

```python
    import random as _random
```

Imports the random module under a private alias for the demonstration.

**Line 584**

```python
    from scan_scheduler_v2 import run_episode, RoundRobinScheduler
```

Imports the episode runner and round-robin baseline.

**Line 585**

```python
    from scan_scheduler_prototype import Environment
```

Imports the synthetic environment class.

**Line 586**

```python
    from scan_scheduler_v3_pri import SparsePeriodicEmitter
```

Imports the fixed-PRI pulse emitter.

**Line 587**

```python
    from spatial_scan_emitter import SpatiallyScanningEmitter
```

Imports the spatial scanning wrapper.

**Line 588**

Blank line.

---

## Demonstration scenario

### Lines 589–598

**Line 589**

```python
    n_bands, n_steps = 8, 6000
```

Configures:

- Eight frequency bands
- Six thousand simulation steps

**Line 590**

Blank line.

**Line 591**

```python
    def scenario():
```

Defines a factory for the demonstration environment.

**Line 592**

```python
        inner = SparsePeriodicEmitter("fixed-pri-radar", band=5, pri=3)
```

Creates an inner radar that emits on band 5 every three steps.

**Line 593**

```python
        scanning = SpatiallyScanningEmitter(inner, scan_period_steps=40,
```

Wraps the radar in a spatial scan with a 40-step antenna rotation.

**Line 594**

```python
                                             beam_dwell_steps=6, sidelobe_leak_prob=0.02)
```

Configures:

- Six steps of main-beam illumination
- Two-percent sidelobe leakage probability

**Line 595**

```python
        return Environment(n_bands=n_bands, emitters=[scanning])
```

Creates an environment containing the spatially scanning radar.

**Line 596**

Blank line.

**Line 597**

```python
    print("Isolated scenario: one spatially-scanning fixed-PRI radar (band 5), "
```

Begins printing the scenario description.

**Line 598**

```python
          f"scan_period=40, beam_dwell=6, inner PRI=3, sidelobe_leak=2%, {n_steps} steps\n")
```

Completes the description with the configured timing and length.

**Line 599**

Blank line.

---

## Comparing schedulers

### Lines 600–609

**Line 600**

```python
    for name, sched in [
```

Begins iterating over the scheduler comparison list.

**Line 601**

```python
        ("RoundRobin (open-loop baseline)", RoundRobinScheduler(n_bands)),
```

Adds the round-robin baseline.

**Line 602**

```python
        ("PRIAware (single-periodicity, blind to nesting)", PRIAwareScheduler(n_bands, ucb_c=0.5)),
```

Adds the ordinary PRI-aware scheduler.

The label explicitly notes that it does not model nested periodicity.

**Line 603**

```python
        ("ScanAwarePRIScheduler (this class)", ScanAwarePRIScheduler(n_bands, ucb_c=0.5)),
```

Adds the scan-aware scheduler being tested.

**Line 604**

```python
    ]:
```

Closes the comparison list and begins the loop body.

**Line 605**

```python
        _random.seed(7)
```

Resets the random generator for reproducibility.

**Line 606**

```python
        stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=1)
```

Runs the current scheduler for 6,000 steps using one scanning channel.

**Line 607**

```python
        r = stats.report()
```

Builds the summary metrics.

**Line 608**

```python
        print(f"{name:52s} | interception={r['interception_ratio']*100:5.1f}% | "
```

Prints the scheduler name and interception percentage.

**Line 609**

```python
              f"avg_reward/step={r['avg_reward_per_step']:.3f}")
```

Prints the average reward per simulation step.

---

# Overall purpose of `scan_aware_scheduler.py`

This file handles a target with nested timing:

```
Outer cycle:
    Antenna returns to the receiver every scan_period steps

Inner cycle:
    Pulses repeat every PRI steps while the beam is visible
```

The scheduler separates the two problems:

1. Detect and predict burst starts.
2. Predict pulse timing within each burst.

It includes safeguards for:

- Missed beam passes
- Incorrect inner-PRI seeds
- False outer-period locks
- Merged bursts
- Inconsistent burst sizes
- Sidelobe leakage
- Sparse pre-lock exploration
- Overly wide beam-dwell estimates



Completed and checked off `whittle_index.py`.

# `whittle_index.py` — line-by-line explanation

## Module documentation

### Lines 1–61

**Line 1**

```python
"""
```

Starts the module documentation string.

**Line 2**

```
whittle_index.py
```

Names the module.

**Line 3**

```
==================
```

Documentation separator.

**Line 4**

```
Computes Whittle indices for the 2-state Markov ("Gilbert-Elliott")
```

Explains that the file computes Whittle indices for two-state Markov channels.

**Line 5**

```
restless-bandit channel model this whole project's belief tracking
```

Connects the solver to the Markov belief model used throughout the project.

**Line 6**

```
already uses (BeliefUCBScheduler's belief[b], learned via
```

The scheduler's `belief[b]` is the Whittle model's belief state.

**Line 7**

```
_p_on_given_on/_p_on_given_off, IS exactly the belief state omega in
```

The transition probabilities correspond directly to the model's parameters.

**Line 8**

```
this model; _propagate IS exactly the T(omega) update below). This is
```

The inherited belief propagation matches the mathematical transition function.

**Line 9**

```
the biggest remaining theoretical item from the original gap analysis:
```

Positions this solver as the project's theoretical scheduling extension.

**Line 10**

```
a genuinely optimal (for this restless-bandit relaxation) alternative
```

The Whittle policy is optimal under the corresponding relaxation, not necessarily for the complete finite system.

**Line 11**

```
to the myopic belief+UCB/Hedge heuristic every other scheduler in this
```

Contrasts it with the heuristic schedulers.

**Line 12**

```
project uses.
```

Completes the comparison.

**Line 13**

Blank documentation line.

**Line 14**

```
MODEL (matches Liu & Zhao 2010, "Indexability of Restless Bandit
```

Introduces the mathematical model and reference.

**Line 15**

```
Problems and Optimality of Whittle Index for Dynamic Multichannel
```

Continues the cited paper title.

**Line 16**

```
Access", IEEE Trans. Info. Theory -- confirmed via direct paper search,
```

States the source of the model.

**Line 17**

```
not assumed from memory): a band is a 2-state Markov chain (on/off).
```

Defines each band as ON/OFF with Markov transitions.

**Line 18**

```
Scanning it (ACTIVATE) reveals its true current state (reward = 1 if
```

The active action scans the band and earns a reward if it is ON.

**Line 19**

```
on, 0 if off) and, going forward, the belief resets to p11 = P(on |
```

After observing ON, the next belief resets to the ON-to-ON probability.

**Line 20**

```
just observed on) or p01 = P(on | just observed off). NOT scanning
```

After observing OFF, the next belief resets to `p01`.

**Line 21**

```
(PASSIVE) reveals nothing; belief evolves via T(omega) = omega*p11 +
```

The passive action provides no observation, so belief propagates mathematically.

**Line 22**

```
(1-omega)*p01.
```

Completes the belief-transition equation.

**Line 23**

Blank documentation line.

**Line 24**

```
WHY NUMERICAL, NOT THE PAPER'S CLOSED FORM, STATED HONESTLY: Liu & Zhao
```

Explains why the implementation uses numerical solving.

**Line 25**

```
prove a closed-form Whittle index exists and give it, but the exact
```

A closed-form formula exists theoretically.

**Line 26**

```
expression is piecewise (splits on p11 vs p01, and further by regions
```

The formula has multiple cases.

**Line 27**

```
of the belief space) and is genuinely easy to mistranscribe from a
```

It is easy to implement incorrectly.

**Line 28**

```
paper I can't fully verify character-by-character here. Computing the
```

The author explicitly avoids copying an uncertain formula.

**Line 29**

```
Whittle index NUMERICALLY -- by directly solving the average-reward
```

Instead, the code solves the formal optimization problem directly.

**Line 30**

```
subsidized single-arm MDP that Whittle's index is DEFINED by, via
```

The index is found by adding a subsidy for choosing the passive action.

**Line 31**

```
relative value iteration -- sidesteps that transcription risk entirely
```

Relative value iteration numerically solves the average-reward dynamic program.

**Line 32**

```
by construction: it can't be "the wrong formula" because it isn't a
```

The implementation does not depend on manually reproducing the closed form.

**Line 33**

```
formula, it's the direct definition, solved. This is also a
```

It computes the index from its definition.

**Line 34**

```
standard, legitimate technique in this literature (see e.g. "Efficient
```

States that the numerical approach is standard.

**Line 35**

```
Algorithms for Finite Horizon and Streaming Restless Bandits" and
```

References another supporting work.

**Line 36**

```
"Uncertainty-of-Information Scheduling" -- both compute Whittle indices
```

Adds another reference.

**Line 37**

```
this way rather than via closed form, explicitly for problems where a
```

Explains why numerical solving is useful.

**Line 38**

```
clean closed form is unavailable or error-prone). Validated below
```

Introduces the built-in validation.

**Line 39**

```
against the ONE piece of the closed form confirmed directly from
```

The implementation checks a known analytical property.

**Line 40**

```
multiple independent sources: W(p11) = p11 (the Whittle index of the
```

The index at the post-ON belief should equal `p11`.

**Line 41**

```
belief state immediately after observing the channel ON).
```

Completes the validation rule.

**Line 42**

Blank documentation line.

**Line 43**

```
ALGORITHM: the belief space, restricted to states actually reachable
```

Introduces the discrete belief-chain approach.

**Line 44**

```
from p01/p11 under repeated passive evolution, is a COUNTABLE chain
```

Only a countable subset of belief values is reachable.

**Line 45**

```
(not the full continuum) -- exactly as established in the cited
```

The solver avoids discretizing the entire belief interval.

**Line 46**

```
literature ("the belief state space of a single-bandit is a countably
```

References the theoretical property.

**Line 47**

```
infinite set"). Build this chain by iterating T from p01 and from p11
```

The chain is generated by repeatedly applying the passive transition.

**Line 48**

```
until both converge (geometrically) to the shared fixed point, merge
```

The two branches converge to a common steady-state belief.

**Line 49**

```
into one terminal state there. For a swept grid of candidate subsidies
```

The solver then tests a grid of subsidy values.

**Line 50**

```
m (ascending), solve the average-reward relative-value-iteration
```

For each subsidy, it solves the dynamic program.

**Line 51**

```
Bellman equation for the two-action MDP over this chain, warm-started
```

The solution from the previous subsidy is reused as the next starting point.

**Line 52**

```
from the previous (slightly lower) m's solution -- since V varies
```

This works because the value function changes gradually with the subsidy.

**Line 53**

```
continuously in m, this converges in a handful of iterations per grid
```

Warm starts improve convergence.

**Line 54**

```
point rather than from scratch, making a fine sweep computationally
```

This makes a detailed subsidy sweep practical.

**Line 55**

```
cheap. Indexability (proven in the cited paper, not re-derived here)
```

Indexability guarantees orderly policy changes.

**Line 56**

```
guarantees each state's optimal action flips from ACTIVATE to PASSIVE
```

As the passive subsidy rises, each state eventually prefers passivity.

**Line 57**

```
exactly once as m increases; that crossover m IS the state's Whittle
```

The transition subsidy is the Whittle index.

**Line 58**

```
index.
```

Completes the algorithm description.

**Line 59**

Blank documentation line.

**Line 60**

```
Run:  python3 whittle_index.py   (self-test: anchor + monotonicity)
```

Documents direct execution and the two self-tests.

**Line 61**

```python
"""
```

Ends the documentation string.

---

## Imports

### Lines 62–64

**Line 62**

Blank line.

**Line 63**

```python
import numpy as np
```

Imports NumPy for:

- Numerical arrays
- Vectorized operations
- Boolean masks
- Value iteration
- Grid construction

**Line 64**

Blank line.

---

# `build_belief_chain()`

## Lines 66–104

**Line 66**

```python
def build_belief_chain(p01: float, p11: float, n_truncate: int = 60, tol: float = 1e-7):
```

Defines the function that builds reachable belief states.

Arguments:

- `p01`: probability of ON after observing OFF
- `p11`: probability of ON after observing ON
- `n_truncate`: maximum number of passive transitions per branch
- `tol`: convergence tolerance

**Line 67**

```python
    """Returns (omegas, succ_passive, idx_p01, idx_p11) where omegas is
```

Starts the function documentation.

**Line 68**

```
    a sorted array of distinct reachable belief values, succ_passive[i]
```

Documents the belief-state array and passive-transition mapping.

**Line 69**

```
    is the index (into omegas) of T(omegas[i]), and idx_p01/idx_p11 are
```

Explains the meaning of the mapping and reset indices.

**Line 70**

```
    the indices of p01 and p11 themselves (the two ACTIVATE-branch
```

When a band is activated, its belief resets to one of these values.

**Line 71**

```
    restart points, constant across every state)."""
```

Ends the documentation.

**Line 72**

```python
    def T(w):
```

Defines the passive belief-transition function.

**Line 73**

```python
        return w * p11 + (1 - w) * p01
```

Calculates the next belief when the current band is not scanned.

**Line 74**

Blank line.

**Line 75**

```python
    fixed_point = p01 / (1 - p11 + p01) if abs(1 - p11 + p01) > 1e-12 else 0.5
```

Calculates the stationary belief satisfying:

```
T(w) = w
```

If the denominator is nearly zero, it uses `0.5` as a safe fallback.

**Line 76**

Blank line.

**Line 77**

```python
    def build_branch(start):
```

Defines a helper for building one belief branch.

**Line 78**

```python
        vals = [start]
```

Starts the branch with its initial belief.

**Line 79**

```python
        w = start
```

Stores the current belief value.

**Line 80**

```python
        for _ in range(n_truncate):
```

Limits the branch to a maximum number of iterations.

**Line 81**

```python
            w = T(w)
```

Advances the belief through one passive transition.

**Line 82**

```python
            if abs(w - fixed_point) < tol:
```

Checks whether the new belief is sufficiently close to the stationary point.

**Line 83**

```python
                break
```

Stops the branch when convergence is reached.

**Line 84**

```python
            vals.append(w)
```

Adds the new belief to the branch.

**Line 85**

```python
        return vals
```

Returns the generated branch.

**Line 86**

Blank line.

**Line 87**

```python
    branch_a = build_branch(p01)  # "just observed OFF" branch
```

Builds the branch beginning after an OFF observation.

**Line 88**

```python
    branch_b = build_branch(p11)  # "just observed ON" branch
```

Builds the branch beginning after an ON observation.

**Line 89**

Blank line.

**Line 90**

```python
    raw = branch_a + branch_b + [fixed_point]
```

Combines both branches and explicitly adds the fixed point.

**Line 91**

```python
    # Merge near-duplicates (branches can converge to values that are
```

Begins explaining duplicate handling.

**Line 92**

```python
    # numerically indistinguishable well before hitting the fixed point
```

Floating-point branches may become nearly identical before exact convergence.

**Line 93**

```python
    # exactly), then sort -- np.unique with a rounding key is enough
```

Rounding before uniqueness handles near-duplicates.

**Line 94**

```python
    # here since chain values are well-separated except near the tail.
```

The approximation is considered safe for this chain.

**Line 95**

```python
    rounded = np.round(np.array(raw), 9)
```

Converts the raw values into a NumPy array and rounds to nine decimals.

**Line 96**

```python
    omegas = np.unique(rounded)
```

Removes duplicates and sorts the resulting belief values.

**Line 97**

Blank line.

**Line 98**

```python
    def nearest_idx(w):
```

Defines a helper that finds the nearest belief-state index.

**Line 99**

```python
        return int(np.argmin(np.abs(omegas - w)))
```

Calculates the absolute difference between `w` and every chain value, then returns the index of the closest one.

**Line 100**

Blank line.

**Line 101**

```python
    succ_passive = np.array([nearest_idx(T(w)) for w in omegas], dtype=np.int64)
```

For every belief state, calculates the index of the state reached after taking the passive action.

**Line 102**

```python
    idx_p01 = nearest_idx(p01)
```

Finds the chain index corresponding to `p01`.

**Line 103**

```python
    idx_p11 = nearest_idx(p11)
```

Finds the chain index corresponding to `p11`.

**Line 104**

```python
    return omegas, succ_passive, idx_p01, idx_p11
```

Returns the chain and all required transition indices.

**Lines 105–106**

Blank lines.

---

# Subsidy grid

## Lines 107–109

**Line 107**

```python
def _default_m_grid(m_hi: float, n_grid: int):
```

Defines the default grid of passive-action subsidy values.

**Line 108**

```python
    return np.concatenate([np.geomspace(1e-6, 1e-2, 60),
```

Creates 60 logarithmically spaced values between `1e-6` and `1e-2`.

This gives fine resolution near zero.

**Line 109**

```python
                           np.linspace(1e-2, m_hi, n_grid)[1:]])
```

Appends a linearly spaced upper range, excluding the duplicated `1e-2` endpoint.

**Line 110**

Blank line.

---

# Subsidy sweep and value iteration

## `_sweep()`: lines 112–156

**Line 112**

```python
def _sweep(omegas, succ_passive, idx_p01, idx_p11, m_grid, vi_tol, vi_max_iter,
```

Defines the function that sweeps through subsidy values.

**Line 113**

```python
           early_exit=True, check_first_passive=False, patience=0):
```

Adds optional performance controls:

- Early exit after all states become passive
- Validation that the first subsidy is sufficiently low
- Policy-stability patience shortcut

**Line 114**

```python
    """Warm-started ascending-m sweep. Returns (whittle, ok). ok is False only
```

Starts the documentation.

**Line 115**

```
    when check_first_passive is set and some state was already passive at the
```

Explains the failure condition.

**Line 116**

```
    first grid point (i.e. a flip happened below the trimmed start)."""
```

If a state is already passive at the starting subsidy, the optimized sweep may have started too late.

**Line 117**

```python
    n = len(omegas)
```

Stores the number of reachable belief states.

**Line 118**

```python
    ref = n - 1
```

Uses the final belief state as the reference state for relative value iteration.

**Line 119**

```python
    whittle = np.full(n, np.nan)
```

Creates an array for each state's Whittle index, initially filled with `NaN`.

**Line 120**

```python
    still_active = np.ones(n, dtype=bool)
```

Tracks which belief states still prefer the active action.

**Line 121**

```python
    V = np.zeros(n)
```

Initializes the relative value function to zero.

**Line 122**

```python
    first = True
```

Tracks whether the current subsidy is the first one in the sweep.

**Line 123**

```python
    for m in m_grid:
```

Iterates over subsidy values in ascending order.

**Line 124**

```python
        same = 0
```

Initializes the policy-stability counter.

**Line 125**

```python
        prev = None
```

Stores the previous action vector for the optional patience shortcut.

**Line 126**

```python
        for _ in range(vi_max_iter):
```

Begins relative value iteration for the current subsidy.

**Line 127**

```python
            q_active = omegas + omegas * V[idx_p11] + (1 - omegas) * V[idx_p01]
```

Calculates the value of activating each belief state.

Components:

- Immediate reward: `omegas`
- Future value after observing ON: `V[idx_p11]`
- Future value after observing OFF: `V[idx_p01]`

**Line 128**

```python
            q_passive = m + V[succ_passive]
```

Calculates the value of remaining passive.

Components:

- Passive subsidy: `m`
- Future value after passive belief propagation

**Line 129**

```python
            V_new = np.maximum(q_active, q_passive) - V[ref]
```

Updates the relative value function.

The reference-state value is subtracted to prevent the average-reward value from drifting by a constant.

**Line 130**

```python
            if np.max(np.abs(V_new - V)) < vi_tol:
```

Checks whether the value function has converged.

**Line 131**

```python
                V = V_new
```

Stores the converged value.

**Line 132**

```python
                break
```

Stops iteration for this subsidy.

**Line 133**

```python
            V = V_new
```

If convergence has not occurred, continues with the new value function.

**Line 134**

```python
            if patience:
```

Enables an optional early stop based on policy stability.

**Line 135**

```python
                # Only the ACTION per state matters for the index, and for
```

Explains that the action choice matters more than exact value convergence.

**Line 136**

```python
                # sparse bands (small p01) V converges slowly (often hitting
```

Sparse bands may require many value iterations.

**Line 137**

```python
                # the iteration cap) while the policy settles within a few
```

The active/passive decisions can stabilize earlier than the values.

**Line 138**

```python
                # iterations. Stop once it has been unchanged `patience` times.
```

The optional shortcut stops after repeated policy stability.

**Line 139**

```python
                act = q_active >= q_passive
```

Creates a Boolean vector indicating which action is currently preferred.

**Line 140**

```python
                if prev is not None and np.array_equal(act, prev):
```

Checks whether the action vector matches the previous iteration.

**Line 141**

```python
                    same += 1
```

Increments the stability counter.

**Line 142**

```python
                    if same >= patience:
```

Checks whether the policy has remained unchanged long enough.

**Line 143**

```python
                        break
```

Stops value iteration early if the patience threshold is reached.

**Line 144**

```python
                else:
```

Handles a changed policy.

**Line 145**

```python
                    same = 0
```

Resets the stability counter.

**Line 146**

```python
                prev = act
```

Stores the current action vector.

**Line 147**

```python
        action_active = q_active >= q_passive
```

Computes the final preferred action for every state at this subsidy.

**Line 148**

```python
        if first and check_first_passive and not action_active.all():
```

If this is the first subsidy and some state is already passive, checks for an unsafe trimmed start.

**Line 149**

```python
            return whittle, False
```

Signals that the sweep must be rerun from the full subsidy range.

**Line 150**

```python
        first = False
```

Marks that the first subsidy has been processed.

**Line 151**

```python
        newly_passive = still_active & ~action_active
```

Finds states that were active before but have just become passive.

**Line 152**

```python
        whittle[newly_passive] = m
```

Assigns the current subsidy as the Whittle index for those states.

**Line 153**

```python
        still_active &= action_active
```

Removes newly passive states from the active-state set.

**Line 154**

```python
        if early_exit and not still_active.any():
```

Checks whether every state has already become passive.

**Line 155**

```python
            break  # every state has flipped; remaining (larger) m cannot change anything
```

Stops the sweep because larger subsidies cannot reverse a passive decision under indexability.

**Line 156**

```python
    return whittle, True
```

Returns the computed index array and success status.

**Lines 157–158**

Blank lines.

---

# `solve_whittle_indices()`

## Function documentation and setup: lines 159–186

**Line 159**

```python
def solve_whittle_indices(p01: float, p11: float, n_truncate: int = 60,
```

Defines the public solver function.

**Line 160**

```python
                           m_lo: float = -0.5, m_hi: float = 1.5, n_grid: int = 120,
```

Defines the subsidy range and grid resolution.

`m_lo` is retained for compatibility with the original full-sweep design.

**Line 161**

```python
                           vi_tol: float = 1e-6, vi_max_iter: int = 500, m_grid=None,
```

Adds value-iteration tolerance, iteration limit, and optional custom subsidy grid.

**Line 162**

```python
                           fast: bool = True, patience: int = 0):
```

Adds:

- Optimized-sweep option
- Optional policy-stability shortcut

**Line 163**

```python
    """Returns (dict {belief: whittle}, omegas, whittle) via the warm-started
```

Starts the public function documentation.

**Line 164**

```
    ascending-m sweep described in the module docstring.
```

References the algorithm described earlier.

**Line 165**

Blank documentation line.

**Line 166**

```
    fast=True (default) gives the same result as fast=False, a little quicker
```

Explains that the optimized path is intended to be numerically equivalent.

**Line 167**

```
    (verified by randomized equality tests, see whittle_equiv_test.py):
```

References the equivalence test.

**Line 168**

```
      * early exit once every state has flipped to passive, and
```

Lists the first optimization.

**Line 169**

```
      * start the sweep near the smallest reachable belief instead of at
```

Lists the second optimization: trim the lower subsidy range.

**Line 170**

```
        m_lo. Safe by indexability (the passive set only grows with m): if no
```

Explains why trimming is theoretically safe.

**Line 171**

```
        state is passive at the trimmed start, none was passive below it. If
```

If no state has flipped at the trimmed starting point, no lower state could have flipped.

**Line 172**

```
        that check ever fails the solver silently redoes the full sweep.
```

The solver falls back to the full sweep if the assumption fails.

**Line 173**

```
    fast=False is the original full sweep (kept for verification).
```

The full reference mode remains available.

**Line 174**

Blank documentation line.

**Line 175**

```
    patience>0 additionally stops each VI solve once the policy is unchanged for
```

Documents the optional approximate shortcut.

**Line 176**

```
    that many iterations. It is ~2-3x faster but NOT exact (13-32 of 293 random
```

The shortcut is faster but can produce different results.

**Line 177**

```
    cases differ, worst by 0.25 in index), so it is off by default."""
```

It is disabled by default because numerical exactness is preferred.

**Line 178**

```python
    omegas, succ_passive, idx_p01, idx_p11 = build_belief_chain(p01, p11, n_truncate)
```

Builds the reachable belief chain and transition mappings.

**Line 179**

```python
    # Subsidy grid. The old uniform linspace(-0.5, 1.5, 120) has a step of
```

Introduces the improved subsidy grid.

**Line 180**

```python
    # ~0.0168, COARSER than the belief range of a sparse band (p01 ~ 1e-3 or
```

A uniform grid was too coarse for low-probability bands.

**Line 181**

```python
    # lower), so every low-belief state was quantised to the same first grid
```

Many sparse states received the same approximate index.

**Line 182**

```python
    # point above 0 (0.0042) and all sparse bands tied. A log-spaced low end
```

This caused poor discrimination between sparse bands.

**Line 183**

```python
    # resolves indices down to 1e-6; the linear tail keeps the old resolution.
```

The new grid uses fine logarithmic spacing near zero and linear spacing afterward.

**Line 184**

```python
    if m_grid is None:
```

Checks whether a custom subsidy grid was supplied.

**Line 185**

```python
        m_grid = _default_m_grid(m_hi, n_grid)
```

Creates the default grid if none was supplied.

**Line 186**

```python
    m_grid = np.asarray(m_grid, dtype=float)
```

Converts the grid to a floating-point NumPy array.

---

## Fast and full solving paths: lines 188–204

**Line 188**

```python
    whittle = None
```

Initializes the result as unavailable.

**Line 189**

```python
    if fast:
```

Enters the optimized solving path when requested.

**Line 190**

```python
        i0 = int(np.searchsorted(m_grid, 0.5 * float(omegas.min())))
```

Finds a lower starting point based on the smallest reachable belief.

**Line 191**

```python
        i0 = max(0, min(i0, len(m_grid) - 1))
```

Clamps the starting index to the valid grid range.

**Line 192**

```python
        whittle, ok = _sweep(omegas, succ_passive, idx_p01, idx_p11, m_grid[i0:],
```

Runs the subsidy sweep from the trimmed starting point.

**Line 193**

```python
                             vi_tol, vi_max_iter, early_exit=True,
```

Enables convergence tolerance, iteration limit, and early exit.

**Line 194**

```python
                             check_first_passive=(i0 > 0), patience=patience)
```

If the grid was trimmed, checks that no state was already passive at the first tested subsidy.

**Line 195**

```python
        if not ok:
```

Checks whether the trimmed sweep detected an unsafe starting point.

**Line 196**

```python
            whittle = None
```

Discards the result and prepares to rerun the full sweep.

**Line 197**

```python
    if whittle is None:
```

Runs the full fallback path when necessary.

**Line 198**

```python
        whittle, _ = _sweep(omegas, succ_passive, idx_p01, idx_p11, m_grid,
```

Sweeps the entire subsidy grid.

**Line 199**

```python
                            vi_tol, vi_max_iter, early_exit=fast, patience=patience if fast else 0)
```

Preserves early-exit behavior and only uses patience in fast mode.

**Line 200**

Blank line.

**Line 201**

```python
    # Any state never flipped within the grid gets the upper bound as a safe
```

Introduces the handling of unresolved indices.

**Line 202**

```python
    # fallback rather than NaN propagating into scoring.
```

Prevents missing values from corrupting the scheduler.

**Line 203**

```python
    whittle[np.isnan(whittle)] = float(m_grid[-1])
```

Assigns the largest tested subsidy to states that never became passive.

**Line 204**

```python
    return dict(zip(omegas.tolist(), whittle.tolist())), omegas, whittle
```

Returns:

1. A dictionary mapping belief values to Whittle indices
2. The belief-state array
3. The raw index array

**Lines 205–206**

Blank lines.

---

# Built-in self-test

## Lines 207–219

**Line 207**

```python
if __name__ == "__main__":
```

Checks whether the module is being executed directly.

**Line 208**

```python
    print("=== Self-test: whittle_index.py ===")
```

Prints a self-test heading.

**Line 209**

```python
    for p01, p11 in [(0.1, 0.8), (0.3, 0.6), (0.05, 0.95), (0.6, 0.3)]:
```

Tests four different Markov transition configurations.

They include:

- Persistent ON behavior
- Less persistent behavior
- Very sparse activation
- A case where ON persistence is lower than OFF-to-ON probability

**Line 210**

```python
        table, omegas, whittle = solve_whittle_indices(p01, p11)
```

Computes the Whittle-index table for the current transition probabilities.

**Line 211**

```python
        w_at_p11 = table[min(table, key=lambda w: abs(w - p11))]
```

Finds the table entry whose belief is closest to `p11`.

**Line 212**

```python
        print(f"p01={p01}, p11={p11}:")
```

Prints the transition parameters.

**Line 213**

```python
        print(f"  ANCHOR CHECK  W(p11) computed={w_at_p11:.4f}  vs known closed-form W(p11)=p11={p11:.4f}"
```

Prints the known analytical anchor and the computed value.

**Line 214**

```python
              f"  {'OK' if abs(w_at_p11 - p11) < 0.03 else 'MISMATCH -- investigate'}")
```

Reports whether the computed value is within `0.03` of the expected value.

**Line 215**

```python
        order = np.argsort(omegas)
```

Sorts the belief states before checking monotonicity.

**Line 216**

```python
        monotone = np.all(np.diff(whittle[order]) >= -1e-9)
```

Checks that the Whittle index does not decrease as belief increases.

The tiny negative tolerance allows negligible floating-point noise.

**Line 217**

```python
        print(f"  monotone non-decreasing in belief: {monotone}")
```

Prints the monotonicity result.

**Line 218**

```python
        print(f"  index range: [{whittle.min():.3f}, {whittle.max():.3f] over "
```

Begins printing the range of computed indices.

**Line 219**

```python
              f"{len(omegas)} reachable belief states\n")
```

Completes the range and reports the number of reachable belief states.

---

# Overall purpose of `whittle_index.py`

This file computes a principled priority value for each Markov belief state.

Its process is:

```
Estimate p01 and p11
        ↓
Build reachable belief states
        ↓
Solve the subsidized single-band MDP
        ↓
Sweep passive-action subsidies
        ↓
Record where each state changes from active to passive
        ↓
Use that crossover as the Whittle index
```

The result is used by `scan_scheduler_whittle.py` as an alternative to the heuristic belief-plus-UCB score.



Completed and checked off `whittle_index_optimized_v2.py`.

# `whittle_index_optimized_v2.py` — line-by-line explanation

## Module documentation and imports

### Lines 1–16

**Line 1**

```python
"""Drop-in optimized Whittle-index solver.
```

Starts the module documentation and states that this file replaces the original solver without changing its public API.

**Line 2**

Blank documentation line.

**Line 3**

```
API and numerical algorithm are kept compatible with the original module.
```

Promises that callers can use the same functions and parameters.

**Line 4**

```
The main optimization is a Numba-compiled implementation of the existing
```

Explains that the primary speedup comes from compiling the numerical sweep with Numba.

**Line 5**

```
warm-started subsidy sweep. No policy-iteration shortcut, approximation,
```

The algorithm remains the same warm-started subsidy sweep.

**Line 6**

```
or closed-form replacement is used.
```

Clarifies that it does not change the mathematical approach.

**Line 7**

```python
"""
```

Ends the module documentation.

**Line 8**

Blank line.

**Line 9**

```python
import numpy as np
```

Imports NumPy for arrays and numerical operations.

**Line 10**

Blank line.

**Line 11**

```python
try:
```

Starts a guarded optional import.

**Line 12**

```python
    from numba import njit
```

Attempts to import Numba's `njit` compiler decorator.

**Line 13**

```python
    _NUMBA_AVAILABLE = True
```

Records that Numba is available.

**Line 14**

```python
except Exception:
```

Handles any failure to import Numba.

**Line 15**

```python
    _NUMBA_AVAILABLE = False
```

Records that the optimized compiler is unavailable.

**Line 16**

Blank line.

---

# Optimized belief-chain construction

## `build_belief_chain()`: lines 18–53

**Line 18**

```python
def build_belief_chain(p01: float, p11: float, n_truncate: int = 60, tol: float = 1e-7):
```

Defines the optimized version of the belief-chain builder.

**Line 19**

```python
    def T(w):
```

Defines the passive belief-transition function.

**Line 20**

```python
        return w * p11 + (1 - w) * p01
```

Calculates the next belief after not scanning the band.

**Line 21**

Blank line.

**Line 22**

```python
    fixed_point = p01 / (1 - p11 + p01) if abs(1 - p11 + p01) > 1e-12 else 0.5
```

Calculates the stationary belief of the Markov process, with `0.5` as a degenerate-case fallback.

**Line 23**

Blank line.

**Line 24**

```python
    def build_branch(start):
```

Defines a helper for generating one chain branch.

**Line 25**

```python
        vals = [start]
```

Starts the branch with its initial belief.

**Line 26**

```python
        w = start
```

Stores the current belief.

**Line 27**

```python
        for _ in range(n_truncate):
```

Limits the number of passive transitions.

**Line 28**

```python
            w = T(w)
```

Advances the belief by one passive transition.

**Line 29**

```python
            if abs(w - fixed_point) < tol:
```

Checks whether the belief has converged to the fixed point.

**Line 30**

```python
                break
```

Stops the branch when convergence is close enough.

**Line 31**

```python
            vals.append(w)
```

Adds the new belief to the branch.

**Line 32**

```python
        return vals
```

Returns the branch.

**Line 33**

Blank line.

**Line 34**

```python
    branch_a = build_branch(p01)
```

Builds the branch starting after an OFF observation.

**Line 35**

```python
    branch_b = build_branch(p11)
```

Builds the branch starting after an ON observation.

**Line 36**

```python
    raw = branch_a + branch_b + [fixed_point]
```

Combines both branches and explicitly includes the fixed point.

**Line 37**

```python
    rounded = np.round(np.array(raw), 9)
```

Converts the values to NumPy and rounds them to nine decimal places.

**Line 38**

```python
    omegas = np.unique(rounded)
```

Removes duplicate belief values and sorts them.

**Line 39**

Blank line.

**Line 40**

```python
    def nearest_idx(w):
```

Defines a helper that finds the closest chain index to a target belief.

**Line 41**

```python
        return int(np.argmin(np.abs(omegas - w)))
```

Computes the absolute distance to all chain values and returns the closest index.

**Line 42**

Blank line.

**Line 43**

```python
    # Exact nearest-neighbour mapping, but without an O(n) scan for every state.
```

Explains the optimization that follows.

**Line 44**

```python
    targets = omegas * p11 + (1.0 - omegas) * p01
```

Computes the passive-successor belief for every chain state at once.

**Line 45**

```python
    pos = np.searchsorted(omegas, targets, side="left")
```

For each target, finds the insertion position in the sorted belief array.

**Line 46**

```python
    pos = np.clip(pos, 0, len(omegas) - 1)
```

Clamps insertion positions so they are valid array indices.

**Line 47**

```python
    left = np.maximum(pos - 1, 0)
```

Calculates the index immediately to the left of each insertion position.

**Line 48**

```python
    choose_left = np.abs(targets - omegas[left]) <= np.abs(omegas[pos] - targets)
```

Determines whether the left neighbor is closer than the insertion-position neighbor.

**Line 49**

```python
    succ_passive = np.where(choose_left, left, pos).astype(np.int64)
```

Selects the closest belief index for every passive transition.

This replaces an individual nearest-neighbor scan for every state.

**Line 50**

Blank line.

**Line 51**

```python
    idx_p01 = nearest_idx(p01)
```

Finds the chain index for `p01`.

**Line 52**

```python
    idx_p11 = nearest_idx(p11)
```

Finds the chain index for `p11`.

**Line 53**

```python
    return omegas, succ_passive, idx_p01, idx_p11
```

Returns the belief chain and transition mappings.

**Lines 54–55**

Blank lines.

---

# Subsidy grid

## Lines 56–58

**Line 56**

```python
def _default_m_grid(m_hi: float, n_grid: int):
```

Defines the default subsidy grid.

**Line 57**

```python
    return np.concatenate([np.geomspace(1e-6, 1e-2, 60),
```

Creates fine logarithmic resolution near zero.

**Line 58**

```python
                           np.linspace(1e-2, m_hi, n_grid)[1:]])
```

Adds a linear grid for larger subsidies while avoiding a duplicate `1e-2`.

**Line 59**

Blank line.

---

# Numba-compiled sweep

## Lines 61–127

**Line 61**

```python
if _NUMBA_AVAILABLE:
```

Only defines the compiled implementation when Numba is installed.

**Line 62**

```python
    @njit(cache=True, fastmath=False)
```

Decorates the function with Numba's JIT compiler.

Options:

- `cache=True`: reuse compiled machine code
- `fastmath=False`: preserve normal floating-point semantics

**Line 63**

```python
    def _sweep_numba(omegas, succ_passive, idx_p01, idx_p11, m_grid,
```

Defines the compiled subsidy-sweep function.

**Line 64**

```python
                     vi_tol, vi_max_iter, early_exit, check_first_passive):
```

Receives the same core parameters as the original solver, excluding the approximate `patience` mode.

**Line 65**

```python
        n = len(omegas)
```

Stores the number of belief states.

**Line 66**

```python
        ref = n - 1
```

Uses the final chain state as the relative-value reference state.

**Line 67**

```python
        whittle = np.empty(n, dtype=np.float64)
```

Allocates an output array for Whittle indices.

**Line 68**

```python
        for i in range(n):
```

Iterates over every index entry.

**Line 69**

```python
            whittle[i] = np.nan
```

Initializes every index as unresolved.

**Line 70**

```python
        still_active = np.ones(n, dtype=np.bool_)
```

Tracks which states still prefer activation.

**Line 71**

```python
        V = np.zeros(n, dtype=np.float64)
```

Initializes the relative value function.

**Line 72**

Blank line.

**Line 73**

```python
        first = True
```

Tracks whether the current subsidy is the first grid point.

**Line 74**

```python
        for gm in range(len(m_grid)):
```

Iterates over subsidy-grid indices.

**Line 75**

```python
            m = m_grid[gm]
```

Reads the current subsidy value.

**Line 76**

Blank line.

**Line 77**

```python
            # These arrays deliberately mirror the original implementation:
```

Explains that the compiled implementation preserves the original operation order.

**Line 78**

```python
            # q_* are from the V at the START of the iteration, and the action
```

The action values are calculated from the old value function.

**Line 79**

```python
            # after the loop is based on the q_* from the final iteration.
```

This detail preserves numerical equivalence with the original implementation.

**Line 80**

```python
            q_active = np.empty(n, dtype=np.float64)
```

Allocates the active-action value array.

**Line 81**

```python
            q_passive = np.empty(n, dtype=np.float64)
```

Allocates the passive-action value array.

**Line 82**

```python
            V_new = np.empty(n, dtype=np.float64)
```

Allocates the next value-function array.

**Line 83**

Blank line.

**Line 84**

```python
            for _ in range(vi_max_iter):
```

Begins value iteration for the current subsidy.

**Line 85**

```python
                v11 = V[idx_p11]
```

Reads the value after an ON observation.

**Line 86**

```python
                v01 = V[idx_p01]
```

Reads the value after an OFF observation.

**Line 87**

```python
                maxdiff = 0.0
```

Initializes the maximum value-function change for this iteration.

**Line 88**

Blank line.

**Line 89**

```python
                for i in range(n):
```

Iterates over all belief states.

**Line 90**

```python
                    w = omegas[i]
```

Reads the current belief.

**Line 91**

```python
                    qa = w + w * v11 + (1.0 - w) * v01
```

Calculates the active-action value:

- Immediate reward `w`
- Expected future value after ON
- Expected future value after OFF

**Line 92**

```python
                    qp = m + V[succ_passive[i]]
```

Calculates the passive-action value:

- Subsidy `m`
- Future value at the passive-successor state

**Line 93**

```python
                    q_active[i] = qa
```

Stores the active value.

**Line 94**

```python
                    q_passive[i] = qp
```

Stores the passive value.

**Line 95**

```python
                    vn = (qa if qa >= qp else qp) - V[ref]
```

Chooses the better action and normalizes relative to the reference state.

**Line 96**

```python
                    V_new[i] = vn
```

Stores the new value for the state.

**Line 97**

```python
                    d = abs(vn - V[i])
```

Calculates the value change for this state.

**Line 98**

```python
                    if d > maxdiff:
```

Checks whether this is the largest change so far.

**Line 99**

```python
                        maxdiff = d
```

Updates the maximum change.

**Line 100**

Blank line.

**Line 101**

```python
                # Match the original: assign V before breaking.
```

Documents an important equivalence detail.

**Line 102**

```python
                for i in range(n):
```

Iterates over all states.

**Line 103**

```python
                    V[i] = V_new[i]
```

Copies the new values into the current value array.

**Line 104**

```python
                if maxdiff < vi_tol:
```

Checks whether value iteration has converged.

**Line 105**

```python
                    break
```

Stops iteration if convergence is reached.

**Line 106**

Blank line.

**Line 107**

```python
            if first and check_first_passive:
```

Checks whether this is the first subsidy and whether the trimmed-grid validation is enabled.

**Line 108**

```python
                for i in range(n):
```

Examines every belief state.

**Line 109**

```python
                    if not (q_active[i] >= q_passive[i]):
```

Checks whether any state is already passive at the first subsidy.

**Line 110**

```python
                        return whittle, False
```

Reports that the trimmed grid began too high.

**Line 111**

```python
            first = False
```

Marks that the first subsidy has been processed.

**Line 112**

Blank line.

**Line 113**

```python
            any_active = False
```

Tracks whether any state still prefers activation.

**Line 114**

```python
            for i in range(n):
```

Iterates over belief states.

**Line 115**

```python
                action_active = q_active[i] >= q_passive[i]
```

Determines the preferred action for the current state.

**Line 116**

```python
                if still_active[i] and not action_active:
```

Checks whether this state just changed from active to passive.

**Line 117**

```python
                    whittle[i] = m
```

Records the current subsidy as the state's Whittle index.

**Line 118**

```python
                    still_active[i] = False
```

Marks the state as permanently passive for larger subsidies.

**Line 119**

```python
                if still_active[i]:
```

Checks whether the state remains active.

**Line 120**

```python
                    any_active = True
```

Records that at least one state still needs to be processed.

**Line 121**

Blank line.

**Line 122**

```python
            if early_exit and not any_active:
```

Checks whether all states have changed to passive.

**Line 123**

```python
                break
```

Stops the sweep early if possible.

**Line 124**

Blank line.

**Line 125**

```python
        return whittle, True
```

Returns the compiled sweep results and a success flag.

**Line 126**

```python
else:
```

Handles the case where Numba is unavailable.

**Line 127**

```python
    _sweep_numba = None
```

Sets the compiled function reference to `None`.

---

# NumPy fallback sweep

## `_sweep_numpy()`: lines 130–169

**Line 130**

```python
def _sweep_numpy(omegas, succ_passive, idx_p01, idx_p11, m_grid, vi_tol,
```

Defines the NumPy/Python fallback implementation.

**Line 131**

```python
                 vi_max_iter, early_exit=True, check_first_passive=False,
```

Adds the main sweep controls.

**Line 132**

```python
                 patience=0):
```

Adds the optional policy-stability shortcut.

**Line 133**

```python
    """Original numerical sweep, retained as a fallback and for patience>0."""
```

Documents that this is the original-style implementation.

**Line 134**

```python
    n = len(omegas)
```

Stores the number of belief states.

**Line 135**

```python
    ref = n - 1
```

Selects the relative-value reference state.

**Line 136**

```python
    whittle = np.full(n, np.nan)
```

Initializes all Whittle indices as unresolved.

**Line 137**

```python
    still_active = np.ones(n, dtype=bool)
```

Tracks states that have not yet become passive.

**Line 138**

```python
    V = np.zeros(n)
```

Initializes the value function.

**Line 139**

```python
    first = True
```

Tracks the first subsidy-grid point.

**Line 140**

```python
    for m in m_grid:
```

Loops over subsidy values.

**Line 141**

```python
        same = 0
```

Initializes the policy-stability counter.

**Line 142**

```python
        prev = None
```

Stores the previous action vector.

**Line 143**

```python
        for _ in range(vi_max_iter):
```

Begins relative value iteration.

**Line 144**

```python
            q_active = omegas + omegas * V[idx_p11] + (1 - omegas) * V[idx_p01]
```

Calculates active-action values for all states.

**Line 145**

```python
            q_passive = m + V[succ_passive]
```

Calculates passive-action values.

**Line 146**

```python
            V_new = np.maximum(q_active, q_passive) - V[ref]
```

Updates the relative value function.

**Line 147**

```python
            if np.max(np.abs(V_new - V)) < vi_tol:
```

Checks convergence.

**Line 148**

```python
                V = V_new
```

Stores the converged value.

**Line 149**

```python
                break
```

Stops the iteration.

**Line 150**

```python
            V = V_new
```

Continues with the new values when not converged.

**Line 151**

```python
            if patience:
```

Enables the approximate policy-stability shortcut.

**Line 152**

```python
                act = q_active >= q_passive
```

Computes the current action policy.

**Line 153**

```python
                if prev is not None and np.array_equal(act, prev):
```

Checks whether it matches the previous policy.

**Line 154**

```python
                    same += 1
```

Increments the unchanged-policy count.

**Line 155**

```python
                    if same >= patience:
```

Checks whether enough unchanged iterations have occurred.

**Line 156**

```python
                        break
```

Stops early if the policy is stable.

**Line 157**

```python
                else:
```

Handles policy changes.

**Line 158**

```python
                    same = 0
```

Resets the stability counter.

**Line 159**

```python
                prev = act
```

Stores the current policy.

**Line 160**

```python
        action_active = q_active >= q_passive
```

Determines the final policy at this subsidy.

**Line 161**

```python
        if first and check_first_passive and not action_active.all():
```

Checks whether the trimmed sweep started too high.

**Line 162**

```python
            return whittle, False
```

Reports failure so the caller can rerun the full sweep.

**Line 163**

```python
        first = False
```

Marks that the first subsidy has been processed.

**Line 164**

```python
        newly_passive = still_active & ~action_active
```

Finds states that just changed from active to passive.

**Line 165**

```python
        whittle[newly_passive] = m
```

Assigns the current subsidy as their index.

**Line 166**

```python
        still_active &= action_active
```

Retains only states that remain active.

**Line 167**

```python
        if early_exit and not still_active.any():
```

Checks whether every state has flipped.

**Line 168**

```python
            break
```

Ends the sweep early when all indices are known.

**Line 169**

```python
    return whittle, True
```

Returns the index array and success status.

**Lines 170–171**

Blank lines.

---

# Choosing the sweep implementation

## Lines 172–184

**Line 172**

```python
def _sweep(omegas, succ_passive, idx_p01, idx_p11, m_grid, vi_tol, vi_max_iter,
```

Defines the dispatch function for the numerical sweep.

**Line 173**

```python
           early_exit=True, check_first_passive=False, patience=0):
```

Accepts all sweep controls.

**Line 174**

```python
    # Default path: compiled version of the SAME Bellman sweep.
```

Documents that Numba is the normal optimized path.

**Line 175**

```python
    # patience>0 is intentionally kept on the original path because that mode
```

The approximate patience mode is not compiled.

**Line 176**

```python
    # is already approximate by design and is not the performance-critical
```

This keeps the compiled path focused on the exact default behavior.

**Line 177**

```python
    # default.
```

Completes the rationale.

**Line 178**

```python
    if _NUMBA_AVAILABLE and patience == 0:
```

Uses Numba when available and when exact/default mode is requested.

**Line 179**

```python
        return _sweep_numba(omegas, succ_passive, idx_p01, idx_p11, m_grid,
```

Calls the compiled sweep.

**Line 180**

```python
                            vi_tol, vi_max_iter, early_exit,
```

Passes convergence and early-exit settings.

**Line 181**

```python
                            check_first_passive)
```

Passes the trimmed-grid validation flag.

**Line 182**

```python
    return _sweep_numpy(omegas, succ_passive, idx_p01, idx_p11, m_grid,
```

Uses the NumPy/Python fallback when Numba is unavailable or patience is enabled.

**Line 183**

```python
                        vi_tol, vi_max_iter, early_exit,
```

Passes the numerical controls.

**Line 184**

```python
                        check_first_passive, patience)
```

Passes the remaining options.

**Lines 185–186**

Blank lines.

---

# Public solver

## `solve_whittle_indices()`: lines 187–216

**Line 187**

```python
def solve_whittle_indices(p01: float, p11: float, n_truncate: int = 60,
```

Defines the public drop-in replacement.

**Line 188**

```python
                           m_lo: float = -0.5, m_hi: float = 1.5, n_grid: int = 120,
```

Accepts the original subsidy parameters.

**Line 189**

```python
                           vi_tol: float = 1e-6, vi_max_iter: int = 500, m_grid=None,
```

Accepts numerical convergence controls.

**Line 190**

```python
                           fast: bool = True, patience: int = 0):
```

Accepts optimized-mode and patience settings.

**Line 191**

```python
    """Drop-in replacement for the original solve_whittle_indices()."""
```

Documents API compatibility.

**Line 192**

```python
    omegas, succ_passive, idx_p01, idx_p11 = build_belief_chain(p01, p11, n_truncate)
```

Builds the reachable belief chain.

**Line 193**

Blank line.

**Line 194**

```python
    if m_grid is None:
```

Checks whether a custom grid was provided.

**Line 195**

```python
        m_grid = _default_m_grid(m_hi, n_grid)
```

Creates the default grid if needed.

**Line 196**

```python
    m_grid = np.asarray(m_grid, dtype=float)
```

Converts the grid to a NumPy float array.

**Line 197**

Blank line.

**Line 198**

```python
    whittle = None
```

Initializes the result.

**Line 199**

```python
    if fast:
```

Enters the optimized trimmed-grid path.

**Line 200**

```python
        i0 = int(np.searchsorted(m_grid, 0.5 * float(omegas.min())))
```

Chooses an approximate safe starting subsidy based on the smallest belief.

**Line 201**

```python
        i0 = max(0, min(i0, len(m_grid) - 1))
```

Clamps the starting index to valid bounds.

**Line 202**

```python
        whittle, ok = _sweep(
```

Starts the optimized sweep.

**Line 203**

```python
            omegas, succ_passive, idx_p01, idx_p11, m_grid[i0:],
```

Passes only the trimmed portion of the grid.

**Line 204**

```python
            vi_tol, vi_max_iter, early_exit=True,
```

Enables convergence checks and early termination.

**Line 205**

```python
            check_first_passive=(i0 > 0), patience=patience)
```

Validates the trimmed start and forwards patience.

**Line 206**

```python
        if not ok:
```

Checks whether the trimmed sweep was invalid.

**Line 207**

```python
            whittle = None
```

Discards the result so the full sweep can run.

**Line 208**

Blank line.

**Line 209**

```python
    if whittle is None:
```

Runs the fallback full-grid sweep if necessary.

**Line 210**

```python
        whittle, _ = _sweep(
```

Calls the selected sweep implementation.

**Line 211**

```python
            omegas, succ_passive, idx_p01, idx_p11, m_grid,
```

Passes the complete grid.

**Line 212**

```python
            vi_tol, vi_max_iter, early_exit=fast,
```

Uses early exit when fast mode is enabled.

**Line 213**

```python
            patience=patience if fast else 0)
```

Uses the patience optimization only in fast mode.

**Line 214**

Blank line.

**Line 215**

```python
    whittle[np.isnan(whittle)] = float(m_grid[-1])
```

Assigns the maximum tested subsidy to any state whose index was never resolved.

**Line 216**

```python
    return dict(zip(omegas.tolist(), whittle.tolist())), omegas, whittle
```

Returns the same three-part result as the original solver:

1. Belief-to-index dictionary
2. Belief-state array
3. Index array

**Lines 217–218**

Blank lines.

---

# Self-test

## Lines 219–230

**Line 219**

```python
if __name__ == "__main__":
```

Checks whether the file is being run directly.

**Line 220**

```python
    print("=== Self-test: optimized whittle_index.py ===")
```

Prints a self-test heading.

**Line 221**

```python
    for p01, p11 in [(0.1, 0.8), (0.3, 0.6), (0.05, 0.95), (0.6, 0.3)]:
```

Tests four different Markov transition configurations.

**Line 222**

```python
        table, omegas, whittle = solve_whittle_indices(p01, p11)
```

Computes the optimized Whittle table.

**Line 223**

```python
        w_at_p11 = table[min(table, key=lambda w: abs(w - p11))]
```

Finds the computed index closest to the post-ON belief `p11`.

**Line 224**

```python
        print(f"p01={p01}, p11={p11}:")
```

Prints the current transition parameters.

**Line 225**

```python
        print(f"  ANCHOR CHECK  W(p11) computed={w_at_p11:.4f}  vs known closed-form W(p11)=p11={p11:.4f}"
```

Prints the calculated value and expected analytical anchor.

**Line 226**

```python
              f"  {'OK' if abs(w_at_p11 - p11) < 0.03 else 'MISMATCH -- investigate'}")
```

Reports whether the difference is within the allowed tolerance.

**Line 227**

```python
        order = np.argsort(omegas)
```

Sorts belief-state indices.

**Line 228**

```python
        monotone = np.all(np.diff(whittle[order]) >= -1e-9)
```

Checks whether the Whittle index is nondecreasing with belief.

**Line 229**

```python
        print(f"  monotone non-decreasing in belief: {monotone}")
```

Prints the monotonicity result.

**Line 230**

```python
        print(f"  index range: [{whittle.min():.3f}, {whittle.max():.3f] over {len(omegas)} reachable belief states\n")
```

Prints the minimum and maximum index and the number of reachable belief states.

---

# Overall purpose

`whittle_index_optimized_v2.py` keeps the original Whittle solver's algorithm but improves performance by:

- Compiling the main Bellman sweep with Numba
- Vectorizing belief-chain successor construction
- Preserving the original NumPy fallback
- Retaining the exact/full-sweep verification path
- Keeping the optional approximate patience mode separate

One important project-level detail: the main `scan_scheduler_whittle.py` currently imports the original `whittle_index.py`, so this optimized file is a compatible standalone replacement rather than the automatically active solver.
