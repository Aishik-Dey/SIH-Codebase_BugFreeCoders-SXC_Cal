# Smart Scan Scheduler — Technical Explanation Report

**Subject:** Line-by-line analysis of the SIH Smart Scan Scheduler codebase (18 Python source files and 3 result CSVs)

---

## Abstract

This report documents, line by line, the design and evolution of a spectrum-scanning
scheduler simulator built for the Smart India Hackathon (SIH) problem statement. The
codebase simulates a receiver that must repeatedly decide which frequency band to scan
against a mixed population of emitters (bursty communications, a periodic beacon, and a
frequency-agile threat), and compares several scheduling strategies — round robin, random,
belief-based (Markov/UCB), and PRI-aware (pulse-repetition-interval) approaches — across
synthetic and PDW (Pulse Descriptor Word) data.

The codebase progresses through four versions (V1–V4) plus a PDW-based replay pipeline and
a series of diagnostic and validation scripts, each addressing one of four recurring
problems in the design: **prediction** (what will each band do), **exploration** (which
under-observed bands deserve attention), **characterization** (how to reliably learn sparse
periodic emitters), and **resource allocation** (when to stop chasing one emitter and scan
elsewhere).

## Document conventions

Each source file is walked in build order. For every executable line, the report gives:

- What the syntax means and what Python actually does
- What each variable contains and where its value came from
- Why the line exists and what it connects to elsewhere in the file
- The relevant Python concept, and any mathematical or statistical reasoning involved
- Bugs, edge cases, or design trade-offs where the code has them

Example of the decomposition depth used for non-trivial lines:

```python
idx = (t // self.dwell) % len(self.band_sequence)
```

- `t` — current simulation timestep
- `self.dwell` — number of timesteps spent on one frequency
- `t // self.dwell` — integer division, giving the current position in the cycle
- `len(self.band_sequence)` — number of available frequencies
- `%` — wraps the index around when the sequence ends
- Result stored in `idx`, then used as `self.band_sequence[idx]` to retrieve the current frequency

Result CSVs are treated as experimental data rather than source code and are analyzed
separately after the Python files.

## Contents

**Source files (build order):**

1. `scan_scheduler_prototype.py` — 312 lines — baseline prototype (round robin, random, belief-based schedulers)
2. `scan_scheduler_v2.py` — 377 lines — adds UCB-style exploration and multi-channel scanning
3. `scan_scheduler_v3_pri.py` — 489 lines — adds PRI-aware scheduling for periodic emitters
4. `scan_scheduler_v4_persistent.py` — 149 lines — adds persistent characterization
5. `pdw_loader.py` — 94 lines — loads Pulse Descriptor Word data
6. `pdw_environment.py` — 53 lines — converts PDWs into a scheduler-compatible environment
7. `run_on_turing_dataset.py` — 240 lines — runs the schedulers against a real/synthetic dataset
8. `diagnose_beacon_regression.py` — diagnostic script
9. `diagnose_pri_lockon.py` — diagnostic script
10. `multi_seed_robustness.py` — robustness validation across seeds
11. `tune_confidence_threshold.py` — parameter tuning script
12. `validate_offbyone_fix.py` — regression validation
13. `validate_plateau_fix.py` — regression validation
14. `validate_warmup_dwell_fix.py` — regression validation
15. `validate_beacon_switchcost_dwell.py` — regression validation
16. `switch_cost_comparison.py` — comparison experiment
17. `settle_fix_interaction.py` — interaction validation
18. `validate_pdw_multiseed.py` — multi-seed PDW validation

**Result data:**

- CSV 1 — `multi_seed_results.csv`
- CSV 2 — `pdw_multiseed_results.csv`
- CSV 3 — `plateau_validation_results.csv`

---

# File 1 - `scan_scheduler_prototype.py`


It is **312 lines**.

---

## Lines 1-27: module docstring

### Line 1

```python
"""
```

This starts a **triple-quoted string**.

Because this string occurs at the very beginning of the Python file, Python treats it as the **module docstring**.

A module docstring is documentation describing what an entire `.py` file is for.

It isn't an executable algorithm.

---

### Line 2

```python
Smart Scan Strategy for Electronic Warfare - Working Prototype
```

This is simply text inside the module docstring.

It tells us the purpose/name of this program.

---

### Line 3

```python
================================================================
```

Also documentation.

The `=` characters have no special Python meaning here because we're inside the triple-quoted string.

---

### Line 4

```python
Simulates a spectrum-scanning receiver deciding, at each time step,
```

This tells us what the program simulates.

Important concept:

The program doesn't have a real RF receiver.

Instead, it creates a **simulation** in which an imaginary receiver repeatedly has to decide:

> "Which frequency band should I listen to right now?"

---

### Line 5

```python
which single frequency band to listen to, against a mixed population
```

The original prototype allows the receiver to select **one band per time step**.

For example, suppose there are 8 bands:

```text
Band:     0 1 2 3 4 5 6 7
```

At time `t = 0`, scheduler might choose:

```text
3
```

At the next time:

```text
1
```

etc.

The scheduler's job is to choose intelligently.

---

### Lines 6-7

```python
of emitters (bursty comms, a periodic beacon, and a frequency-agile
threat) sharing the same band pool.
```

This tells us the simulation contains several kinds of transmitters:

- **bursty communications**
- **periodic beacon**
- **frequency-agile threat**

They all operate using the same collection of frequency bands.

This becomes important later because different emitter behaviors require different prediction strategies.

---

### Line 8

Blank line.

No executable effect.

It improves readability.

---

### Line 9

```python
Pipeline (the "workflow"):
```

Documentation describing the program's architecture.

---

### Line 10

```python
    1. Environment  -> ground-truth emitter ON/OFF state per band per step
```

This describes stage 1.

The **Environment** knows reality.

For every timestep it can answer:

```text
Band 0 → OFF
Band 1 → ON
Band 2 → OFF
...
```

This is called **ground truth**.

The scheduler doesn't necessarily know all of this.

---

### Line 11

```python
    2. Scheduler    -> picks ONE band to scan this step (this is the part
```

Stage 2.

The scheduler makes the decision.

This is the intelligence being tested.

---

### Line 12

```python
                        SIH wants "smart"/ML-driven instead of open-loop)
```

The comment explains the motivation.

An open-loop scheduler might simply do:

```text
0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 0 → ...
```

without considering what it has observed.

The project wants something capable of adapting.

---

### Line 13

```python
    3. Update       -> scheduler learns from the hit/miss it just observed
```

After choosing a band, the scheduler receives feedback.

Example:

```text
Scheduler chose band 4
Band 4 was ON
→ HIT
```

or:

```text
Scheduler chose band 4
Band 4 was OFF
→ MISS
```

The smart scheduler can use this information to update its internal model.

---

### Line 14

```python
    4. Metrics      -> interception ratio, avg reward/step, avg intercept delay
```

Finally, the program measures performance.

Three important metrics:

**Interception ratio**

How often transmissions were successfully intercepted.

**Average reward per step**

Average of the hit/miss reward.

**Average interception delay**

How long it took to catch a transmission after it began.

---

### Line 15

Blank line.

No effect.

---

### Line 16

```python
Three schedulers are compared head-to-head on the identical scenario:
```

The program compares three algorithms.

"Identical scenario" is important: ideally, each scheduler should face the same environment conditions so comparison is meaningful.

---

### Line 17

```python
    - RoundRobinScheduler   : open-loop baseline (sweeps bands in order)
```

First algorithm:

**Round Robin**

It cycles through bands.

Example with 4 bands:

```text
0 → 1 → 2 → 3 → 0 → 1 → ...
```

No learning.

---

### Line 18

```python
    - RandomScheduler       : naive baseline
```

Second algorithm.

It chooses a random band every time.

---

### Lines 19-24

```python
    - BeliefScheduler       : closed-loop, learns a 2-state Markov model
                              per band online and scans whichever band it
                              currently believes is most likely ON
                              (a practical/myopic approximation of the
                              Whittle index used for restless-bandit
                              scheduling problems)
```

Third algorithm.

This is the interesting one.

It learns something about each band.

For each band it estimates:

```text
P(ON | previously OFF)
P(ON | previously ON)
```

That's a **two-state Markov model**.

The scheduler also maintains a belief such as:

```text
Band 0: 0.15
Band 1: 0.82
Band 2: 0.04
Band 3: 0.51
...
```

Then it tends to choose the band with the largest belief.

The docstring also says this is an approximation of a **Whittle-index approach** rather than claiming this implementation is the exact optimal Whittle-index algorithm.

That's an important distinction.

---

### Line 25

Blank.

---

### Line 26

```python
Run:  python3 scan_scheduler_prototype.py
```

Documentation telling us how to execute the file from a terminal.

---

### Line 27

```python
"""
```

Ends the module docstring.

Everything from line 1 through line 27 was documentation.

---

# Imports

### Line 29

```python
import random
```

Imports Python's built-in `random` module.

This gives the program functions such as:

```python
random.random()
random.randrange(...)
random.choice(...)
```

The project needs randomness to simulate unpredictable emitter behavior.

---

### Line 30

```python
import statistics
```

Imports Python's built-in `statistics` module.

Later the program uses:

```python
statistics.mean(...)
```

to calculate averages.

---

### Line 31

```python
from dataclasses import dataclass, field
```

This imports two things from Python's `dataclasses` module:

```python
dataclass
field
```

`@dataclass` later lets us create classes primarily intended to store data without manually writing all the boilerplate constructor code.

`field(...)` is needed later for:

```python
field(default_factory=list)
```

which creates a separate list for each object.

That's important because using one shared list accidentally would cause bugs.

---

### Line 32

```python
from typing import List, Dict, Optional
```

Imports type-hinting constructs.

They don't normally change the algorithm.

They make declarations such as:

```python
List[Emitter]
```

mean:

> "This should be a list containing `Emitter` objects."

And:

```python
Optional[int]
```

means:

> "This may contain an `int`, or it may be `None`."

---

### Lines 33-34

Blank lines.

Readability only.

---

# `Emitter`

### Line 35

```python
# ----------------------------------------------------------------------
```

Comment.

Python ignores it during execution.

It's a visual section separator.

---

### Line 36

```python
# 1. RF Environment: Emitters
```

Comment indicating section 1.

---

### Line 37

Another separator comment.

---

### Line 39

```python
class Emitter:
```

This defines a **class** named `Emitter`.

Think of a class as a blueprint.

We're saying:

> "Every emitter in this simulation will follow this basic interface."

Later we create specialized emitters:

```python
MarkovEmitter
PeriodicEmitter
AgileEmitter
```

which inherit from `Emitter`.

---

### Lines 40-41

```python
    """Base class. Occupies one band at a time (band may change for
    hoppers) and is either transmitting or silent at that band."""
```

Class docstring.

It explains what an emitter represents.

An emitter has:

- a band
- an ON/OFF state

Some emitters stay on one band.

Others can hop between bands.

---

### Line 42

```python
    def __init__(self, name: str):
```

This defines the class constructor.

`__init__` runs when we create an object.

For example:

```python
Emitter("test")
```

causes Python to call:

```python
__init__(...)
```

`name: str` is a type hint saying `name` is expected to be a string.

---

### Line 43

```python
        self.name = name
```

Creates an instance attribute called `name`.

Suppose:

```python
Emitter("comm-1")
```

Then:

```python
self.name
```

becomes:

```text
"comm-1"
```

`self` refers to **this particular object**.

So two emitters can have different names:

```text
emitter1.name → "comm-1"
emitter2.name → "beacon"
```

---

### Line 44

```python
        self.band: int = -1
```

Creates an instance variable named `band`.

The type hint says:

```python
int
```

The initial value is:

```python
-1
```

Why `-1`?

Because no actual band has been assigned yet.

It's being used as a sentinel value meaning roughly:

> "No valid band assigned."

Subclasses later replace it with an actual band.

---

### Line 45

```python
        self.on: bool = False
```

Creates another instance attribute:

```python
self.on
```

with Boolean type.

Initially:

```python
False
```

meaning:

> emitter isn't transmitting.

---

### Line 47

```python
    def step(self, t: int):
```

Defines a method named `step`.

This represents:

> Advance emitter's state by one timestep.

`t` is the current time.

The base class doesn't know how a particular emitter behaves.

---

### Line 48

```python
        raise NotImplementedError
```

This deliberately throws an exception if someone tries to use the base class's `step()` implementation.

Why?

Because `Emitter` is meant to be a **base/interface class**.

A subclass is supposed to provide its own behavior.

For example:

```python
MarkovEmitter.step()
```

will implement Markov behavior.

This prevents accidental use of an undefined generic emitter.

---

### Line 49

Blank.

---

# `MarkovEmitter`

### Line 51

```python
class MarkovEmitter(Emitter):
```

Defines `MarkovEmitter`.

The important part is:

```python
(Emitter)
```

This means:

> `MarkovEmitter` inherits from `Emitter`.

Therefore it gets things such as:

```python
self.name
self.band
self.on
```

and can override `step()`.

---

### Lines 52-53

```python
    """Fixed-band emitter. ON/OFF governed by a 2-state Markov chain -
    models bursty comms traffic in a known channel."""
```

Class documentation.

This emitter stays on one band but changes between:

```text
ON
OFF
```

according to probabilities dependent on its previous state.

That is a **two-state Markov chain**.

---

### Line 54

```python
    def __init__(self, name, band, p_on_given_off=0.15, p_on_given_on=0.85):
```

Constructor accepts four values:

```text
name
band
p_on_given_off
p_on_given_on
```

The last two have defaults.

So:

```python
MarkovEmitter("comm-1", 1)
```

automatically means:

```text
p_on_given_off = 0.15
p_on_given_on  = 0.85
```

Interpretation:

If currently OFF:

```text
15% chance → ON
```

If currently ON:

```text
85% chance → remain ON
```

This creates **bursty/sticky** behavior.

---

### Line 55

```python
        super().__init__(name)
```

This is important Python inheritance.

`super()` gives access to the parent class.

So this calls:

```python
Emitter.__init__(name)
```

which initializes:

```python
self.name
self.band
self.on
```

Without this, those base-class attributes wouldn't automatically be initialized.

---

### Line 56

```python
        self.band = band
```

The base class initially set:

```python
self.band = -1
```

Now the subclass replaces that with the supplied band.

For:

```python
MarkovEmitter("comm-1", band=1)
```

we get:

```python
self.band == 1
```

---

### Line 57

```python
        self.p_on_given_off = p_on_given_off
```

Stores the probability of turning ON when currently OFF.

Example:

```text
0.05
```

means 5%.

---

### Line 58

```python
        self.p_on_given_on = p_on_given_on
```

Stores the probability of staying ON when currently ON.

Example:

```text
0.90
```

means 90%.

---

### Line 59

```python
        self.on = random.random() < 0.3
```

This is worth understanding carefully.

First:

```python
random.random()
```

generates a floating-point number in approximately:

```text
[0.0, 1.0)
```

Suppose it generates:

```text
0.17
```

Then:

```python
0.17 < 0.3
```

is:

```python
True
```

So:

```python
self.on = True
```

If it generates:

```text
0.72
```

then:

```python
0.72 < 0.3
```

is:

```python
False
```

Therefore this line gives the emitter:

```text
30% probability → initially ON
70% probability → initially OFF
```

This is how a random starting state is generated.

---

### Line 61

```python
    def step(self, t):
```

Overrides the `step()` method inherited from `Emitter`.

Now this emitter has its own state-transition logic.

Notice that `t` isn't actually used inside this implementation.

It is still accepted because the emitter interface expects `step(t)`.

---

### Line 62

```python
        p = self.p_on_given_on if self.on else self.p_on_given_off
```

This is a Python **conditional expression**.

Equivalent longer version:

```python
if self.on:
    p = self.p_on_given_on
else:
    p = self.p_on_given_off
```

So:

### If currently ON

```python
p = self.p_on_given_on
```

Example:

```text
p = 0.90
```

### If currently OFF

```python
p = self.p_on_given_off
```

Example:

```text
p = 0.05
```

This implements the Markov transition rule.

---

### Line 63

```python
        self.on = random.random() < p
```

Again generate a random number.

Then compare it with `p`.

Suppose:

```text
currently ON
p = 0.90
random = 0.73
```

Then:

```python
0.73 < 0.90
```

→ `True`

So emitter stays ON.

If:

```text
random = 0.95
```

then:

```python
0.95 < 0.90
```

→ `False`

so emitter turns OFF.

---

### Line 64

```python
        return self.band, self.on
```

Returns a **tuple** containing two values:

```python
(band, on)
```

For example:

```python
(1, True)
```

means:

> emitter is transmitting on band 1.

Later the environment receives these two values.

---

### Line 65

Blank.

---

# `PeriodicEmitter`

### Line 67

```python
class PeriodicEmitter(Emitter):
```

Defines another subclass of `Emitter`.

This one behaves deterministically.

---

### Lines 68-69

```python
    """Hops through a fixed cyclic sequence of bands, `dwell` steps per
    band (e.g. a periodic scanning radar / cyclic beacon)."""
```

The emitter follows a fixed sequence.

Example:

```python
[2, 5, 6]
```

with:

```python
dwell = 4
```

means:

```text
time 0-3   → band 2
time 4-7   → band 5
time 8-11  → band 6
time 12-15 → band 2
...
```

---

### Line 70

```python
    def __init__(self, name, band_sequence: List[int], dwell=3):
```

Constructor.

Arguments:

```text
name
band_sequence
dwell
```

`List[int]` says `band_sequence` should be a list of integers.

---

### Line 71

```python
        super().__init__(name)
```

Calls the parent `Emitter` constructor.

Initializes common emitter state.

---

### Line 72

```python
        self.band_sequence = band_sequence
```

Stores the sequence.

Example:

```python
[2, 5, 6]
```

---

### Line 73

```python
        self.dwell = dwell
```

Stores how many timesteps the emitter stays at each band.

---

### Line 74

```python
        self.on = True
```

Unlike `MarkovEmitter`, this emitter is always transmitting.

It doesn't randomly turn OFF.

---

### Line 76

```python
    def step(self, t):
```

Defines periodic emitter's timestep behavior.

---

### Line 77

```python
        idx = (t // self.dwell) % len(self.band_sequence)
```

**This is one of the most important lines in the file.**

Let's break it apart.

Suppose:

```text
t = 9
dwell = 4
band_sequence = [2, 5, 6]
```

First:

```python
t // self.dwell
```

means integer/floor division:

```text
9 // 4 = 2
```

So we're in sequence slot 2.

Then:

```python
len(self.band_sequence)
```

is:

```text
3
```

Therefore:

```python
2 % 3 = 2
```

So:

```python
idx = 2
```

and:

```python
band_sequence[2] = 6
```

Thus time 9 corresponds to band 6.

At time 12:

```text
12 // 4 = 3
3 % 3 = 0
```

so it wraps back to:

```text
band_sequence[0] = 2
```

That's how the cycle repeats forever.

---

### Line 78

```python
        self.band = self.band_sequence[idx]
```

Use calculated index to select the current band.

---

### Line 79

```python
        self.on = True
```

Guarantees the emitter is ON at every timestep.

---

### Line 80

```python
        return self.band, self.on
```

Returns current state.

---

# `AgileEmitter`

### Line 83

```python
class AgileEmitter(Emitter):
```

Defines third emitter type.

---

### Lines 84-86

```python
    """Frequency-agile emitter: hops to a random band from its pool every
    `dwell` steps, with a duty cycle. No exploitable periodicity -
    represents an LPI/LPD-style threat."""
```

This emitter behaves differently from `PeriodicEmitter`.

Instead of:

```text
2 → 5 → 6 → 2 → 5 → 6
```

it randomly chooses bands.

Therefore predicting its next location is much harder.

---

### Line 87

```python
    def __init__(self, name, bands: List[int], dwell=2, duty=0.6):
```

Constructor accepts:

- name
- list of possible bands
- hopping interval
- duty cycle

---

### Line 88

```python
        super().__init__(name)
```

Initialize parent class.

---

### Line 89

```python
        self.bands = bands
```

Store possible band pool.

---

### Line 90

```python
        self.dwell = dwell
```

Store hopping interval.

---

### Line 91

```python
        self.duty = duty
```

Store transmission probability.

For:

```text
duty = 0.6
```

each timestep has a 60% chance of transmitting.

---

### Line 92

```python
        self.band = random.choice(bands)
```

Randomly selects one band from the list.

Unlike `random.random()`, `random.choice()` directly returns an element.

Example:

```python
bands = [0, 3, 6, 7]
```

could produce:

```text
6
```

---

### Line 94

```python
    def step(self, t):
```

Defines behavior for each timestep.

---

### Line 95

```python
        if t % self.dwell == 0:
```

Checks whether it's time to hop.

Example:

```text
dwell = 2
```

Then hopping occurs at:

```text
t = 0, 2, 4, 6, 8, ...
```

because those values satisfy:

```text
t % 2 == 0
```

---

### Line 96

```python
            self.band = random.choice(self.bands)
```

If it's a hopping timestep, randomly select a new band.

---

### Line 97

```python
        self.on = random.random() < self.duty
```

Independently decides whether emitter is transmitting.

If:

```text
duty = 0.6
```

then:

```text
60% → ON
40% → OFF
```

---

### Line 98

```python
        return self.band, self.on
```

Returns current state.

---

# Lines 99–116 — `Environment`

### Line 99
```python
```

Blank line.

Used to visually separate `AgileEmitter` from the next section.

---

### Lines 100–101
```python
@dataclass
class Environment:
```

### Line 100
```python
@dataclass
```

This is a **decorator**.

`dataclass` was imported earlier:

```python
from dataclasses import dataclass, field
```

The decorator tells Python:

> Treat `Environment` as a data-oriented class and automatically generate useful methods such as `__init__()`.

Without `@dataclass`, we'd have to manually write something like:

```python
class Environment:
    def __init__(self, n_bands, emitters, t=0):
        self.n_bands = n_bands
        self.emitters = emitters
        self.t = t
```

With `@dataclass`, Python generates this constructor automatically.

---

### Line 101
```python
class Environment:
```

Defines class `Environment`.

This class represents **entire RF simulation environment**.

It contains:

- number of frequency bands
- emitters occupying those bands
- current simulation time

---

### Lines 102–104
```python
    n_bands: int
    emitters: List[Emitter]
    t: int = 0
```

These are dataclass fields.

### Line 102
```python
n_bands: int
```

`n_bands` stores number of frequency bands.

The `: int` is a **type annotation**.

It tells readers/tools:

> Expected type is `int`.

It doesn't force Python to reject another type at runtime.

---

### Line 103
```python
emitters: List[Emitter]
```

Stores collection of emitters.

`List[Emitter]` means:

> This should be a list whose elements are `Emitter` objects or subclasses of `Emitter`.

For example:

```python
[
    MarkovEmitter(...),
    MarkovEmitter(...),
    PeriodicEmitter(...),
    AgileEmitter(...)
]
```

Notice polymorphism here.

All four objects have different classes, but all inherit from `Emitter`, so `Environment` can treat them uniformly by calling:

```python
e.step(...)
```

---

### Line 104
```python
t: int = 0
```

Stores simulation time.

Initial value:

```text
t = 0
```

So when environment is first created:

```python
Environment(...)
```

it starts at timestep 0.

---

## What `@dataclass` generates here

Conceptually, Python creates something similar to:

```python
Environment(
    n_bands,
    emitters,
    t=0
)
```

So later:

```python
Environment(n_bands=n_bands, emitters=emitters)
```

works without manually defining `__init__`.

---

### Line 105
```python
```

Blank line.

---

### Line 106
```python
    def step(self) -> Dict[int, bool]:
```

Defines method `step()`.

This is the method used to advance simulation by **one timestep**.

Return type:

```python
Dict[int, bool]
```

Meaning dictionary mapping:

```text
band number → whether band is currently ON
```

Example:

```python
{
    0: False,
    1: True,
    2: False,
    3: True,
    4: True,
    5: False,
    6: False,
    7: False
}
```

So this gives scheduler's simulation world state.

---

### Lines 107–109
```python
        """Advance all emitters one step. Returns ground-truth ON/OFF
        status for every band this step (OR-combined if bands collide)."""
```

Method docstring.

Important phrase:

> **ground-truth**

This means this dictionary contains information that, in real EW operation, receiver would **not automatically know**.

The simulation knows exactly which bands contain active signals.

The scheduler only gets to observe:

```python
status[band]
```

for whichever band it chooses to scan.

---

### Line 110
```python
        status = {b: False for b in range(self.n_bands)}
```

This is a **dictionary comprehension**.

Let's break it apart.

```python
range(self.n_bands)
```

If:

```python
self.n_bands = 8
```

then:

```python
range(8)
```

produces:

```text
0 1 2 3 4 5 6 7
```

For every `b`, dictionary comprehension creates:

```python
b: False
```

Therefore:

```python
status = {
    0: False,
    1: False,
    2: False,
    3: False,
    4: False,
    5: False,
    6: False,
    7: False
}
```

Initially every band is assumed silent.

---

### Line 111
```python
        for e in self.emitters:
```

Loop through every emitter.

Suppose:

```python
self.emitters
```

contains:

```text
comm-1
comm-2
beacon
agile-threat
```

Then loop executes four times.

`e` means current emitter.

---

### Line 112
```python
            band, on = e.step(self.t)
```

This is important.

Calls the current emitter's:

```python
step()
```

method.

It passes current environment time:

```python
self.t
```

The emitter returns two values:

```python
(band, on)
```

Python automatically **unpacks** them.

For example:

```python
band, on = (4, True)
```

produces:

```python
band = 4
on = True
```

The actual implementation depends on emitter type.

For example:

### MarkovEmitter

```python
return self.band, self.on
```

### PeriodicEmitter

```python
return self.band, self.on
```

### AgileEmitter

```python
return self.band, self.on
```

This is polymorphism in action.

`Environment` doesn't care which specific emitter it received.

It simply says:


---

### Line 113
```python
            if on:
```

Checks whether current emitter is transmitting.

Equivalent conceptually to:

```python
if on == True:
```

If `on` is `False`, nothing happens.

---

### Line 114
```python
                status[band] = True
```

Marks that frequency band as active.

For example:

```python
band = 4
on = True
```

changes:

```python
status[4]
```

from:

```python
False
```

to:

```python
True
```

---

## Why "OR-combined"?

Suppose two emitters happen to use same band:

```text
Emitter A → band 6 → ON
Emitter B → band 6 → ON
```

The dictionary still contains:

```python
status[6] = True
```

It doesn't count two transmissions.

This is effectively:

```text
False OR True = True
True OR True = True
```

So environment records:

> Is **at least one** emitter active on this band?

not:

> How many emitters are active?

This becomes important later when calculating metrics.

---

### Line 115
```python
        self.t += 1
```

Advance simulation clock by one.

Equivalent to:

```python
self.t = self.t + 1
```

If current timestep was:

```text
0
```

after this:

```text
1
```

---

### Line 116
```python
        return status
```

Return complete ground-truth band status.

Example:

```python
{
    0: False,
    1: True,
    2: True,
    3: False,
    4: True,
    5: False,
    6: False,
    7: True
}
```

This dictionary goes into:

```python
status = env.step()
```

later in `run_episode()`.

---

# Lines 119–133 — Base `Scheduler`

### Line 119
Comment separator.

```python
# ----------------------------------------------------------------------
```

Purely organizational.

### Line 120
```python
# 2. Schedulers
```

Indicates beginning of scheduler section.

The scheduler's job:

> Decide which one frequency band receiver should scan.

---

### Line 123
```python
class Scheduler:
```

Defines base scheduler class.

This establishes common interface for all schedulers.

Later we have:

```python
RoundRobinScheduler
RandomScheduler
BeliefScheduler
```

all inheriting from it.

---

### Line 124
```python
    def __init__(self, n_bands: int):
```

Constructor.

Takes number of bands.

---

### Line 125
```python
        self.n_bands = n_bands
```

Stores number of bands inside object.

For:

```python
Scheduler(8)
```

we get:

```python
self.n_bands = 8
```

---

### Line 127
```python
    def choose_band(self) -> int:
```

Defines interface for selecting next band.

Return expected to be an integer.

Example:

```python
3
```

means:

> Scan band 3.

---

### Line 128
```python
        raise NotImplementedError
```

This method deliberately doesn't provide implementation.

It says:

> Base `Scheduler` doesn't know how to select a band. Subclasses must implement it.

If somebody does:

```python
s = Scheduler(8)
s.choose_band()
```

Python raises:

```text
NotImplementedError
```

This is a common way to create an **abstract-like base class**, although this isn't using Python's formal `abc` mechanism.

---

### Line 130
```python
    def update(self, band: int, observed_on: bool):
```

Defines another scheduler interface.

After scanning a band, scheduler gets feedback:

```text
Which band did I scan?
Was signal ON?
```

Arguments:

```python
band
observed_on
```

---

### Line 131
```python
        """Called with the ground-truth result after scanning `band`."""
```

Docstring.

The key idea:

Scheduler gets feedback **after** its decision.

This makes intelligent scheduling possible.

---

### Line 132
```python
        pass
```

`pass` means:

> Do nothing.

For baseline schedulers, no learning is needed.

`BeliefScheduler` overrides this method.

---

# Lines 135–144 — Round Robin

### Line 135
```python
class RoundRobinScheduler(Scheduler):
```

Defines subclass.

Inheritance:

```text
Scheduler
    ↑
RoundRobinScheduler
```

So it inherits:

```python
self.n_bands
```

and the scheduler interface.

---

### Line 136
```python
"""Open-loop baseline: sweeps every band in fixed order."""
```

Round robin doesn't use observations.

Sequence:

```text
0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 0 → ...
```

That's why it's **open-loop**.

It doesn't learn from hits/misses.

---

### Line 137
```python
    def __init__(self, n_bands):
```

Constructor.

---

### Line 138
```python
        super().__init__(n_bands)
```

Calls parent class constructor.

This executes:

```python
Scheduler.__init__(self, n_bands)
```

and therefore establishes:

```python
self.n_bands = n_bands
```

---

### Line 139
```python
        self.ptr = 0
```

`ptr` = pointer.

It tells scheduler which band should be scanned next.

Initially:

```text
ptr = 0
```

---

### Line 141
```python
    def choose_band(self):
```

Called whenever scheduler needs to decide which band to scan.

---

### Line 142
```python
        b = self.ptr
```

Save current pointer.

Initially:

```python
b = 0
```

---

### Line 143
```python
        self.ptr = (self.ptr + 1) % self.n_bands
```

This advances pointer and wraps around.

Suppose:

```text
n_bands = 8
ptr = 3
```

Then:

```text
(3 + 1) % 8
= 4
```

Next pointer = 4.

At final band:

```text
ptr = 7
```

then:

```text
(7 + 1) % 8
= 0
```

So it wraps around.

---

### Line 144
```python
        return b
```

Returns the band selected **before** pointer advancement.

So first calls produce:

```text
0
1
2
3
4
5
6
7
0
1
...
```

---

# Lines 147–150 — Random Scheduler

### Line 147
```python
class RandomScheduler(Scheduler):
```

Another subclass of `Scheduler`.

---

### Line 148
```python
"""Naive baseline: uniformly random band each step."""
```

No learning.

Every band has equal probability.

With 8 bands:

$$
P(\text{select band }b)=\frac18
$$

---

### Line 149
```python
    def choose_band(self):
```

Defines selection function.

---

### Line 150
```python
        return random.randrange(self.n_bands)
```

Generates random integer from:

```text
0 through n_bands - 1
```

For 8 bands:

```python
random.randrange(8)
```

can return:

```text
0,1,2,3,4,5,6,7
```

Each has equal probability.

Unlike `random.choice(...)`, `randrange()` directly chooses an integer from the specified range.

---

# Lines 153–178 — `BeliefScheduler`

This is where the interesting part begins.

### Line 153
```python
class BeliefScheduler(Scheduler):
```

Defines intelligent/learning scheduler.

Inheritance:

```text
Scheduler
    ↑
BeliefScheduler
```

---

### Lines 154–168

Large docstring describing algorithm.

The central idea is:

> Maintain probability that each band is currently ON.

For example:

```text
Band 0 → 0.10
Band 1 → 0.83
Band 2 → 0.25
Band 3 → 0.71
```

Scheduler prefers band 1 because it has highest estimated probability.

---

### Line 157
```python
For each band it online-learns a 2-state Markov model
```

"2-state" means:

```text
OFF
ON
```

Possible transitions:

```text
OFF → OFF
OFF → ON
ON  → OFF
ON  → ON
```

---

### Line 158
```python
(P(on | off), P(on | on)) via counting
```

Two learned probabilities:

$$
P(ON_{t+1}\mid OFF_t)
$$

and

$$
P(ON_{t+1}\mid ON_t)
$$

For example:

```text
P(ON | OFF) = 0.1
P(ON | ON)  = 0.9
```

would describe bursty traffic:

> If currently ON, likely remain ON; if OFF, unlikely become ON.

---

### Lines 160–162

The scheduler does something important.

When it scans a band, it gets actual observation:

```text
ON → belief = 1
OFF → belief = 0
```

When it **doesn't** scan that band, it can't know actual state.

Instead it predicts its probability using Markov model.

That's partial observability.

---

### Line 164
```python
Each step it scans argmax(belief), with epsilon exploration
```

`argmax` means:

> Find index having maximum value.

If:

```python
belief = [0.2, 0.8, 0.4, 0.6]
```

then:

```text
argmax = 1
```

because:

```text
belief[1] = 0.8
```

is largest.

---

### Lines 165–167

The scheduler also occasionally explores randomly.

Why?

If it always selects currently highest-belief band, some bands might **never be checked again**.

Then it cannot learn whether its belief about those bands is wrong.

So it introduces:

```python
epsilon
```

random exploration.

This is classic **exploration vs exploitation**.

---

# Line 169
```python
    def __init__(self, n_bands, epsilon=0.08):
```

Constructor.

Arguments:

```text
n_bands
epsilon
```

Default:

```python
epsilon = 0.08
```

So approximately:

$$
8\%
$$

of decisions become random exploration decisions.

Approximately:

$$
92\%
$$

use current highest-belief band.

---

### Line 170
```python
        super().__init__(n_bands)
```

Calls parent constructor.

Creates:

```python
self.n_bands = n_bands
```

---

### Line 171
```python
        self.epsilon = epsilon
```

Stores exploration probability.

---

### Line 172
```python
        # Laplace-smoothed transition counts
```

Comment.

"Laplace smoothing" means initial pseudo-counts are added so probability estimates don't start with zero counts.

---

### Line 173
```python
        self.off_on = [1.0] * n_bands
```

Creates list containing `1.0` repeated `n_bands` times.

For 8 bands:

```python
[1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
```

`off_on[b]` represents number of observed/smoothed:

```text
OFF → ON
```

transitions for band `b`.

---

### Line 174
```python
        self.off_tot = [2.0] * n_bands
```

Total denominator associated with transitions beginning in OFF.

Initially each band has:

```text
off_on = 1
off_tot = 2
```

Therefore:

$$
P(ON|OFF)=\frac12=0.5
$$

before learning.

---

### Line 175
```python
        self.on_on = [1.0] * n_bands
```

Smoothed count for:

```text
ON → ON
```

---

### Line 176
```python
        self.on_tot = [2.0] * n_bands
```

Total count for transitions beginning in ON.

Again initially:

$$
P(ON|ON)=\frac12
$$

---

### Line 177
```python
        self.belief = [0.3] * n_bands
```

Initial belief that every band is ON:

$$
P(ON)=0.3
$$

So for 8 bands:

```text
[0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3]
```

Important distinction:

```text
transition probability ≠ belief
```

Transition probability describes **how state changes**.

Belief describes **current probability of being ON**.

---

### Line 178
```python
        self.last_scan_result = [None] * n_bands
```

Stores most recent observation for each band.

Initially:

```python
[None, None, None, None, None, None, None, None]
```

`None` means:

> We haven't observed this band yet.

After observing:

```text
ON
```

it becomes:

```python
True
```

After observing:

```text
OFF
```

it becomes:

```python
False
```

This list becomes important in `update()`.

---

## Lines 180–188 — Probability and belief propagation

### Line 180
```python
    def _p_on_given_off(self, b):
```

Private-by-convention helper method.

The `_` means:

> Intended for internal use.

It calculates:

$$
P(ON_{t+1}\mid OFF_t)
$$

for band `b`.

---

### Line 181
```python
        return self.off_on[b] / self.off_tot[b]
```

Divides:

```text
OFF→ON count
----------------
all OFF-starting transitions
```

Example:

```text
off_on[3] = 4
off_tot[3] = 10
```

gives:

$$
P(ON|OFF)=\frac4{10}=0.4
$$

---

### Line 183
```python
    def _p_on_given_on(self, b):
```

Helper for:

$$
P(ON_{t+1}\mid ON_t)
$$

---

### Line 184
```python
        return self.on_on[b] / self.on_tot[b]
```

Same idea.

Example:

```text
on_on = 8
on_tot = 10
```

gives:

$$
P(ON|ON)=0.8
$$

---

### Line 186
```python
    def _propagate(self, b):
```

Predicts band's next ON probability without directly observing it.

This is one of the most important functions in this file.

---

### Line 187
```python
        bel = self.belief[b]
```

Stores current belief in local variable `bel`.

Suppose:

```python
self.belief[b] = 0.7
```

then:

```python
bel = 0.7
```

Meaning:

$$
P(ON_t)=0.7
$$

---

### Line 188
```python
        self.belief[b] = bel * self._p_on_given_on(b) + (1 - bel) * self._p_on_given_off(b)
```

This is the mathematical heart of the belief model.

Formula:

$$
P(ON_{t+1})
=
P(ON_t)P(ON_{t+1}|ON_t)
+
P(OFF_t)P(ON_{t+1}|OFF_t)
$$

Since:

$$
P(OFF_t)=1-P(ON_t)
$$

the code becomes:

```python
bel * P(ON|ON) + (1-bel) * P(ON|OFF)
```

### Example

Suppose:

```text
belief = 0.7
P(ON|ON) = 0.8
P(ON|OFF) = 0.2
```

Then:

$$
0.7(0.8)+0.3(0.2)
$$

$$
=0.56+0.06
$$

$$
=0.62
$$

So predicted next belief:

```text
0.62
```

This is essentially a **one-step Markov prediction under partial observation**.

---

The decision logic begins here.

And there is an important implementation detail there that is worth examining carefully: **the code's claim about being a "Whittle index" approximation is stronger than what the actual implementation computes.**

# `scan_scheduler_prototype.py` — lines 190–312

We now finish this file. This section contains the **actual scheduling decision, learning update, simulation loop, metrics, scenario, and program entry point**.

---

## Lines 190–195 — `BeliefScheduler.choose_band()`

### Line 190
```python
def choose_band(self):
```

Defines method that decides:

> **Which frequency band should receiver scan right now?**

This method is called once per simulation timestep.

---

### Line 191
```python
for b in range(self.n_bands):
```

Loops through every band.

If:

```python
self.n_bands = 8
```

then:

```text
b = 0
b = 1
b = 2
...
b = 7
```

---

### Line 192
```python
self._propagate(b)
```

For each band, predict its new probability of being ON.

Recall:

```python
self._propagate(b)
```

uses:

$$
P(ON_{t+1})
=
P(ON_t)P(ON_{t+1}|ON_t)
+
P(OFF_t)P(ON_{t+1}|OFF_t)
$$

So before making its decision, scheduler refreshes its beliefs about **all bands**.

### Example

Suppose:

```text
Band 0 → 0.20
Band 1 → 0.70
Band 2 → 0.40
Band 3 → 0.85
```

After propagation they might become:

```text
Band 0 → 0.25
Band 1 → 0.65
Band 2 → 0.45
Band 3 → 0.80
```

Scheduler then decides using these updated values.

---

### Line 193
```python
if random.random() < self.epsilon:
```

This implements **epsilon exploration**.

`random.random()` generates a floating-point number in:

$$
[0,1)
$$

With:

```python
self.epsilon = 0.08
```

there is approximately an 8% chance that:

```python
random.random() < 0.08
```

is true.

Therefore:

```text
8% → explore randomly
92% → exploit current beliefs
```

---

### Line 194
```python
return random.randrange(self.n_bands)
```

If exploration occurs, choose a random band.

For 8 bands:

```text
0,1,2,3,4,5,6,7
```

each has equal probability.

Notice what happens here:

The scheduler **ignores its beliefs temporarily**.

That's intentional.

Without exploration, a bad early estimate could cause scheduler to repeatedly select same bands and neglect others.

---

### Line 195
```python
return max(range(self.n_bands), key=lambda b: self.belief[b])
```

This is the exploitation decision.

This line looks complicated, so let's dismantle it.

### Part 1

```python
range(self.n_bands)
```

For 8 bands:

```text
0 1 2 3 4 5 6 7
```

### Part 2

```python
key=lambda b: self.belief[b]
```

`lambda` creates tiny anonymous function:

```python
lambda b: self.belief[b]
```

Equivalent to:

```python
def get_belief(b):
    return self.belief[b]
```

So Python asks:

> For each candidate band `b`, what is its belief value?

Suppose:

```python
self.belief = [
    0.2,
    0.7,
    0.4,
    0.9,
    0.1,
    0.5,
    0.3,
    0.6
]
```

Then:

```text
band 0 → 0.2
band 1 → 0.7
band 2 → 0.4
band 3 → 0.9
band 4 → 0.1
band 5 → 0.5
band 6 → 0.3
band 7 → 0.6
```

`max()` returns the **band whose belief is largest**.

Therefore:

```text
return 3
```

because:

$$
0.9 = \max(0.2,0.7,0.4,0.9,0.1,0.5,0.3,0.6)
$$

So:

> **BeliefScheduler greedily scans band currently believed most likely to be ON.**

### Important correction

The comments call this a:

> "practical myopic approximation of the Whittle index"

But this code **does not calculate a Whittle index**.

A true Whittle-index implementation involves computing an index based on the restless-bandit model and subsidy/optimality structure.

This implementation simply does:

$$
\boxed{\text{choose band with maximum current belief}}
$$

So it's better understood as a **belief-based greedy/myopic scheduler**.

---

# Lines 197–209 — Learning from observations

Now scheduler has selected a band and actually observed whether it was ON.

```python
def update(self, band, observed_on):
```

---

### Line 197
```python
def update(self, band, observed_on):
```

`band`:

> Which band was scanned?

`observed_on`:

> Was signal detected?

Example:

```python
band = 4
observed_on = True
```

means:

> We scanned band 4 and found it ON.

---

### Line 198
```python
prev = self.last_scan_result[band]
```

Retrieve previous observation of this same band.

Suppose:

```python
self.last_scan_result[4] = False
```

then:

```python
prev = False
```

If we've never scanned it:

```python
prev = None
```

---

### Line 199
```python
if prev is not None:
```

Checks whether this band has been observed before.

Why?

To learn a **transition** you need two observations.

For example:

```text
previous observation → OFF
current observation  → ON
```

gives:

$$
OFF\rightarrow ON
$$

But if this is first-ever observation:

```text
? → ON
```

there is no previous state, so no transition can be counted.

---

### Line 200
```python
if prev:
```

If previous observation was `True`, meaning:

```text
previous state = ON
```

Python treats `True` as true in condition.

---

### Line 201
```python
self.on_tot[band] += 1
```

Increase number of transitions that started from ON.

Equivalent:

```python
self.on_tot[band] = self.on_tot[band] + 1
```

---

### Line 202
```python
if observed_on:
```

Check whether current observation is ON.

---

### Line 203
```python
self.on_on[band] += 1
```

If previous state was ON and current state is also ON:

```text
ON → ON
```

increment its count.

Therefore:

```python
self.on_on[band]
```

helps estimate:

$$
P(ON|ON)
$$

---

### Line 204
```python
else:
```

This belongs to:

```python
if prev:
```

So it means:

> Previous observation was OFF.

---

### Line 205
```python
self.off_tot[band] += 1
```

Increment number of observed transitions beginning from OFF.

---

### Line 206
```python
if observed_on:
```

Check whether current observation is ON.

---

### Line 207
```python
self.off_on[band] += 1
```

If:

```text
previous = OFF
current = ON
```

we have:

```text
OFF → ON
```

Therefore increment:

```python
off_on
```

which estimates:

$$
P(ON|OFF)
$$

---

### Lines 208–209

```python
self.last_scan_result[band] = observed_on
self.belief[band] = 1.0 if observed_on else 0.0
```

These two lines are extremely important.

---

### Line 208
```python
self.last_scan_result[band] = observed_on
```

Store newest observation.

If:

```python
observed_on = True
```

then:

```python
last_scan_result[band] = True
```

If false:

```python
last_scan_result[band] = False
```

This value becomes `prev` the next time this band is scanned.

---

### Line 209
```python
self.belief[band] = 1.0 if observed_on else 0.0
```

This is Python's conditional expression:

```python
A if condition else B
```

Equivalent:

```python
if observed_on:
    self.belief[band] = 1.0
else:
    self.belief[band] = 0.0
```

Why exactly `1.0` and `0.0`?

Because after scanning, the state is no longer uncertain.

If receiver directly observes:

```text
ON
```

then:

$$
P(ON)=1
$$

If receiver observes:

```text
OFF
```

then:

$$
P(ON)=0
$$

Then, on future timesteps when this band isn't scanned, `_propagate()` gradually converts that certainty back into a probability.

---

## One important limitation of this learning implementation

Suppose band 3 is observed:

```text
t=0 → ON
```

Then scheduler doesn't scan band 3 for 5 steps.

At:

```text
t=5 → OFF
```

the code treats the observations as one transition:

```text
ON → OFF
```

But the true sequence might have been:

```text
ON → ON → OFF → OFF → ON → OFF
```

The intermediate states were unknown.

So the learned transition counts are based on **consecutive observations of a band**, not necessarily consecutive timesteps.

That's an important simplification in this prototype.

---

# Lines 212–214 — Simulation section

### Line 212
```python
# ----------------------------------------------------------------------
```

Section separator.

### Line 213
```python
# 3. Simulation loop + metrics
```

Beginning simulation and performance measurement.

### Line 214

Comment separator.

---

# Lines 216–233 — `RunStats`

### Line 216
```python
@dataclass
```

Again, automatically generates constructor and useful dataclass behavior.

---

### Line 217
```python
class RunStats:
```

Stores results from one scheduler's simulation run.

---

### Line 218
```python
total_steps: int = 0
```

Number of simulation steps completed.

For this program:

```text
4000
```

---

### Line 219
```python
total_transmissions: int = 0
```

Comment says:

```text
steps where >=1 band was ON somewhere
```

Important:

This does **not** mean total number of emitter transmissions.

It counts timesteps during which at least one band was active.

---

### Line 220
```python
hits: int = 0
```

Number of times:

> selected/scanned band was actually ON.

---

### Line 221
```python
intercept_delays: List[int] = field(default_factory=list)
```

Stores interception delays.

`default_factory=list` is important.

Each `RunStats` object gets its **own separate list**.

Conceptually:

```python
intercept_delays = []
```

but safely handled by dataclass.

Why not:

```python
intercept_delays: List[int] = []
```

?

Because mutable defaults such as lists can accidentally be shared between instances. `default_factory=list` creates fresh list each time.

---

### Line 222
```python
rewards: List[int] = field(default_factory=list)
```

Stores reward obtained at every timestep.

Each reward is:

```text
1 → hit
0 → miss
```

So after 5 steps it might contain:

```python
[0, 1, 1, 0, 0]
```

---

# `report()`

### Line 224
```python
def report(self):
```

Creates summary of collected statistics.

---

### Line 225
```python
interception_ratio = self.hits / max(1, self.total_transmissions)
```

Calculates:

$$
\text{Interception Ratio}
=
\frac{\text{hits}}
{\text{active timesteps}}
$$

Why:

```python
max(1, self.total_transmissions)
```

?

To avoid division by zero.

If:

```python
total_transmissions = 0
```

then denominator becomes:

```text
1
```

rather than 0.

---

### Important metric nuance

Suppose:

```text
100 active timesteps
20 hits
```

then:

$$
20/100=0.2
$$

or:

```text
20%
```

But because `total_transmissions` counts **active timesteps**, this metric is not literally:

> percentage of all individual emitter transmissions intercepted.

It is closer to:

> fraction of timesteps with at least one transmission where selected band was active.

---

### Line 226
```python
avg_reward = statistics.mean(self.rewards) if self.rewards else 0.0
```

Conditional expression again.

If rewards exist:

```python
statistics.mean(self.rewards)
```

calculates average.

Example:

```python
[1, 0, 1, 1]
```

gives:

$$
\frac{1+0+1+1}{4}=0.75
$$

If list is empty:

```text
0.0
```

---

### Line 227
```python
avg_delay = statistics.mean(self.intercept_delays) if self.intercept_delays else None
```

Average interception delay.

If no interceptions occurred:

```python
avg_delay = None
```

rather than incorrectly reporting zero.

That's a good distinction:

```text
0 delay ≠ no measurement
```

---

### Lines 228–233
```python
return {
    "interception_ratio": round(interception_ratio, 3),
    "avg_reward_per_step": round(avg_reward, 3),
    "avg_intercept_delay": round(avg_delay, 2) if avg_delay is not None else "n/a",
    "hits": self.hits,
}
```

Returns dictionary containing summary.

### Line 229

Rounds interception ratio to 3 decimal places.

Example:

```text
0.237846
```

becomes:

```text
0.238
```

---

### Line 230

Rounds average reward to 3 decimals.

---

### Line 231

Rounds average delay to 2 decimals.

If there were no delays:

```text
"n/a"
```

---

### Line 232

Reports total hits.

---

### Line 233

Closes dictionary.

---

# Lines 236–269 — `run_episode()`

This is the **main simulation engine**.

### Line 236
```python
def run_episode(env_factory, scheduler: Scheduler, n_steps: int, n_bands: int) -> RunStats:
```

Function takes:

- `env_factory` → creates fresh environment
- `scheduler` → scheduling algorithm
- `n_steps` → simulation duration
- `n_bands` → number of frequency bands

Returns:

```python
RunStats
```

---

### Line 237
```python
env = env_factory()
```

Calls environment factory.

Why factory rather than directly passing an environment?

Because each scheduler should receive a **fresh environment**.

Otherwise:

```text
RoundRobin runs → modifies environment
Random runs → starts from modified environment
```

which would be unfair.

---

### Line 238
```python
stats = RunStats()
```

Create empty statistics object.

Initially:

```text
total_steps = 0
hits = 0
...
```

---

### Line 239
```python
on_since: List[Optional[int]] = [None] * n_bands
```

For every band, stores the timestep when its current ON period started.

Initially:

```python
[None, None, None, None, None, None, None, None]
```

Suppose band 4 turns ON at timestep 20:

```python
on_since[4] = 20
```

---

### Line 240
```python
credited = [False] * n_bands
```

Tracks whether current ON episode has already been credited with an interception delay.

Example:

```text
band turns ON at t=10
scheduler detects it at t=13
```

Delay:

$$
13-10=3
$$

After recording that,:

```python
credited[band] = True
```

Further hits during same continuous ON period aren't counted as new interceptions.

---

# Lines 242–269 — timestep loop

### Line 242
```python
for t in range(n_steps):
```

Runs simulation from:

```text
t = 0
```

through:

```text
t = n_steps - 1
```

For:

```python
n_steps = 4000
```

that's:

```text
0 ... 3999
```

---

### Line 243
```python
status = env.step()
```

Advance environment one timestep.

This causes **all emitters** to update.

Then returns something like:

```python
{
    0: True,
    1: False,
    2: True,
    3: False,
    4: True,
    5: False,
    6: False,
    7: False
}
```

---

### Line 245
```python
for b in range(n_bands):
```

Examine every band.

---

### Line 246
```python
if status[b]:
```

Is this band currently ON?

---

### Line 247
```python
if on_since[b] is None:
```

If ON and no previous start time has been recorded, this means:

> This is the beginning of a new ON period.

---

### Line 248
```python
on_since[b] = t
```

Record current timestep as start.

---

### Line 249
```python
credited[b] = False
```

Since this is a new ON episode, interception delay has not yet been credited.

---

### Line 250
```python
else:
```

This `else` belongs to:

```python
if status[b]:
```

So current band is OFF.

---

### Line 251
```python
on_since[b] = None
```

No active ON period.

---

### Line 252
```python
credited[b] = False
```

Reset credit status.

This means if band turns ON again later, a new interception can receive a new delay.

---

### Lines 254–255
```python
if any(status.values()):
    stats.total_transmissions += 1
```

`status.values()` gives all Boolean states.

Example:

```text
False, False, True, False, ...
```

`any(...)` returns `True` if **at least one** is true.

So this asks:

> Is at least one frequency band active this timestep?

If yes:

```python
total_transmissions += 1
```

Again, this counts active **timesteps**, not individual emitters.

---

# Lines 257–259 — Scheduler decision and feedback

### Line 257
```python
band = scheduler.choose_band()
```

Now scheduler decides which band to scan.

Depending on scheduler:

### Round Robin

```text
0 → 1 → 2 → ...
```

### Random

Random band.

### Belief

Highest estimated probability, except during exploration.

---

### Line 258
```python
observed_on = status[band]
```

Look up actual state of selected band.

Example:

```python
band = 4
status[4] = True
```

therefore:

```python
observed_on = True
```

This is scheduler's observation.

---

### Line 259
```python
scheduler.update(band, observed_on)
```

Give observation back to scheduler.

For:

```text
RoundRobin
```

`update()` inherited from base class does nothing.

For:

```text
Random
```

same.

For:

```text
BeliefScheduler
```

this updates its Markov transition counts and belief.

So the architecture is:

```text
Environment
     ↓
current state
     ↓
Scheduler.choose_band()
     ↓
selected band
     ↓
observe selected band
     ↓
Scheduler.update()
     ↓
scheduler learns
     ↓
next timestep
```

That's the fundamental closed-loop architecture.

---

# Lines 261–267 — Rewards and interception delay

### Line 261
```python
stats.rewards.append(1 if observed_on else 0)
```

If selected band was ON:

```text
reward = 1
```

Otherwise:

```text
reward = 0
```

Then append to reward history.

So:

```python
[0, 0, 1, 0, 1, ...]
```

---

### Lines 262–263
```python
if observed_on:
    stats.hits += 1
```

If selected band is active, scheduler successfully detected something.

Increment hit count.

---

### Line 264
```python
if on_since[band] is not None and not credited[band]:
```

Two conditions must both be true.

#### Condition 1

```python
on_since[band] is not None
```

There is an active ON period.

#### Condition 2

```python
not credited[band]
```

This ON period hasn't already been credited.

So this identifies:

> First successful detection during this continuous ON period.

---

### Line 265
```python
stats.intercept_delays.append(t - on_since[band])
```

Calculate delay.

If:

```text
ON started at t=10
detected at t=14
```

then:

$$
14-10=4
$$

So:

```python
intercept_delays.append(4)
```

---

### Line 266
```python
credited[band] = True
```

Mark this ON episode as already credited.

If scheduler detects same signal again at:

```text
t=15
t=16
t=17
```

those don't generate additional interception-delay measurements.

---

### Line 267
```python
stats.total_steps += 1
```

Increment total simulation steps.

---

### Line 269
```python
return stats
```

After all timesteps, return completed statistics.

---

# Lines 272–283 — Building scenario

### Line 272
```python
def make_scenario(n_bands=8):
```

Creates scenario factory.

Default:

```text
8 bands
```

---

### Lines 273–274

Docstring:

```text
two Markov comms
one periodic beacon
one frequency-agile threat
```

So four emitters share eight bands.

---

### Line 275
```python
def factory():
```

Nested function.

This is important.

`make_scenario()` doesn't directly create one environment.

It creates a **function that can create an environment**.

---

### Line 276
```python
emitters = [
```

Start list of emitters.

---

### Line 277
```python
MarkovEmitter("comm-1", band=1, p_on_given_off=0.05, p_on_given_on=0.9),
```

First emitter.

Fixed at:

```text
band 1
```

Transition probabilities:

$$
P(ON|OFF)=0.05
$$

$$
P(ON|ON)=0.9
$$

Interpretation:

- unlikely to start transmitting
- once transmitting, likely to remain transmitting

That's bursty communication behavior.

---

### Line 278
```python
MarkovEmitter("comm-2", band=4, p_on_given_off=0.10, p_on_given_on=0.7),
```

Second Markov emitter.

Fixed:

```text
band 4
```

Transition probabilities:

$$
P(ON|OFF)=0.10
$$

$$
P(ON|ON)=0.70
$$

Compared with `comm-1`, it turns on more easily but is less persistent once ON.

---

### Line 279
```python
PeriodicEmitter("beacon", band_sequence=[2, 5, 6], dwell=4),
```

Beacon cycles:

```text
2 → 5 → 6 → 2 → 5 → 6 → ...
```

Spends:

```text
4 timesteps
```

on each band.

Therefore one complete cycle takes:

$$
3\times4=12
$$

timesteps.

---

### Line 280
```python
AgileEmitter("agile-threat", bands=[0, 3, 6, 7], dwell=2, duty=0.5),
```

Frequency-agile threat chooses randomly among:

```text
0, 3, 6, 7
```

It changes band every:

```text
2 timesteps
```

and has:

$$
P(ON)=0.5
$$

per timestep.

---

### Line 281
```python
]
```

Ends emitter list.

---

### Line 282
```python
return Environment(n_bands=n_bands, emitters=emitters)
```

Creates environment containing those emitters.

Notice keyword arguments:

```python
n_bands=n_bands
emitters=emitters
```

---

### Line 283
```python
return factory
```

This is crucial.

`make_scenario()` returns the **function**, not the environment.

So:

```python
scenario = make_scenario(8)
```

makes:

```text
scenario → factory function
```

Then:

```python
scenario()
```

creates a fresh environment.

---

# Lines 286–310 — `main()`

### Line 286
```python
def main():
```

Defines program's main function.

---

### Line 287
```python
random.seed(7)
```

Sets random-number generator seed.

This makes random behavior **reproducible in principle**.

If same sequence of random calls occurs, same random values occur.

---

### Line 288
```python
n_bands = 8
```

Simulation has 8 bands.

---

### Line 289
```python
n_steps = 4000
```

Each scheduler runs for 4000 timesteps.

---

### Line 290
```python
scenario = make_scenario(n_bands)
```

Creates environment factory.

---

## Lines 292–296 — Scheduler collection

### Line 292
```python
schedulers = {
```

Creates dictionary mapping human-readable scheduler name to scheduler object.

---

### Line 293
```python
"RoundRobin (open-loop baseline)": RoundRobinScheduler(n_bands),
```

Constructs round-robin scheduler.

---

### Line 294
```python
"Random (naive baseline)": RandomScheduler(n_bands),
```

Constructs random scheduler.

---

### Line 295
```python
"BeliefScheduler (learned, closed-loop)": BeliefScheduler(n_bands, epsilon=0.08),
```

Constructs intelligent scheduler.

8% exploration.

---

### Line 296
```python
}
```

Closes dictionary.

---

# Lines 298–299 — Scenario description

```python
print(f"Scenario: {n_bands} bands, {n_steps} steps, 4 concurrent emitters "
      f"(2 Markov comms, 1 periodic beacon, 1 frequency-agile threat)\n")
```

This is an `f-string`.

Values are inserted dynamically.

For example:

```text
Scenario: 8 bands, 4000 steps, 4 concurrent emitters
(2 Markov comms, 1 periodic beacon, 1 frequency-agile threat)
```

The two adjacent f-strings are automatically concatenated inside the function call.

`\n` creates newline.

---

# Line 300 — Table header

```python
header = f"{'Scheduler':40s} | {'Interception %':>15s} | {'Avg Reward/step':>16s} | {'Avg Intercept Delay':>20s}"
```

This constructs formatted table headings.

### `:40s`

```text
Scheduler
```

is a string occupying width 40.

### `:>15s`

Right-align string in width 15.

Likewise:

```text
16
20
```

for remaining columns.

Result looks approximately:

```text
Scheduler                                |  Interception % |  Avg Reward/step |  Avg Intercept Delay
```

---

### Line 301
```python
print(header)
```

Print header.

---

### Line 302
```python
print("-" * len(header))
```

Creates separator.

If header length is 100:

```python
"-" * 100
```

creates 100 hyphens.

---

# Lines 304–308 — Run every scheduler

### Line 304
```python
for name, sched in schedulers.items():
```

Iterates through dictionary.

Each iteration provides:

```text
name
sched
```

Example first:

```text
name = "RoundRobin (open-loop baseline)"
sched = RoundRobinScheduler(...)
```

---

### Line 305
```python
stats = run_episode(scenario, sched, n_steps, n_bands)
```

Run full 4000-step simulation.

Arguments:

```text
scenario
scheduler
4000
8
```

Returns:

```python
RunStats
```

---

### Line 306
```python
r = stats.report()
```

Convert raw statistics into summary dictionary.

---

### Lines 307–308
```python
print(f"{name:40s} | {r['interception_ratio']*100:14.1f}% | "
      f"{r['avg_reward_per_step']:16.3f} | {str(r['avg_intercept_delay']):>20s}")
```

Print one formatted result row.

### `r['interception_ratio']*100`

If:

```text
0.235
```

convert to:

```text
23.5%
```

### `:14.1f`

Format floating-point number with:

```text
1 digit after decimal
```

### `:16.3f`

Average reward with 3 decimal places.

### `str(...)`

Converts average delay to string.

This matters because it might be:

```text
"n/a"
```

rather than a number.

---

# Lines 311–312 — Python entry point

### Line 311
```python
if __name__ == "__main__":
```

Very important Python idiom.

Python sets special variable:

```python
__name__
```

When you execute:

```bash
python scan_scheduler_prototype.py
```

then:

```python
__name__ == "__main__"
```

is true.

Therefore line 312 executes.

But if another script does:

```python
import scan_scheduler_prototype
```

then:

```python
__name__
```

is the module name, not `"__main__"`.

Therefore `main()` isn't automatically executed.

This lets the file function both as:

- executable program
- importable module

---

### Line 312
```python
main()
```

Starts the simulation.

So the complete execution chain is:

```text
Python starts file
       ↓
__name__ == "__main__"
       ↓
main()
       ↓
create scenario factory
       ↓
create 3 schedulers
       ↓
RoundRobin → run_episode()
       ↓
Random → run_episode()
       ↓
BeliefScheduler → run_episode()
       ↓
calculate metrics
       ↓
print comparison table
```

---

# ⚠️ Two important issues in this prototype


## 1. "Identical scenario" isn't quite identical

The file's opening description says:

> "Three schedulers are compared head-to-head on the identical scenario"

But each call to:

```python
run_episode(scenario, ...)
```

does:

```python
env = env_factory()
```

and the emitters use the **global random-number generator**.

Because `random.seed(7)` is called only once, RoundRobin consumes some random numbers, then Random starts from the RNG's changed state, then BeliefScheduler starts from an even later state.

So they have:

> **same scenario configuration/distributions**

but not necessarily:

> **same exact random realization**

For a rigorous comparison, controlled/common random numbers or a reset seed should be used before each run.

That's something we'll watch for in later validation scripts.

---

## 2. The scheduler's "learning" is limited

The code learns:

$$
P(ON|OFF)
$$

and

$$
P(ON|ON)
$$

from observations.

But it only updates when a band is observed again. If band isn't scanned between two observations, all hidden intermediate transitions are ignored.

So this is a useful prototype, but not a full hidden-state inference system.

---

# Complete architecture of this first file

The entire 312-line program can be reduced to the following conceptual flow:

```text
                 ┌──────────────────────┐
                 │      Emitters        │
                 │                      │
                 │ Markov comms         │
                 │ Periodic beacon      │
                 │ Agile threat         │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │     Environment      │
                 │                      │
                 │ band → ON/OFF        │
                 └──────────┬───────────┘
                            │
                            ▼
                 ┌──────────────────────┐
                 │      Scheduler       │
                 │                      │
                 │ RoundRobin           │
                 │ Random               │
                 │ Belief               │
                 └──────────┬───────────┘
                            │
                     choose one band
                            │
                            ▼
                    ┌──────────────┐
                    │ Observation  │
                    │   ON / OFF   │
                    └──────┬───────┘
                           │
                           ▼
                    scheduler.update()
                           │
                           ▼
                    learn / next decision
```

### Core mathematical idea

For `BeliefScheduler`:

$$
\boxed{
b_{t+1}
=
b_tP(ON|ON)
+
(1-b_t)P(ON|OFF)
}
$$

Then:

$$
\boxed{
\text{scan}=\arg\max_b b_t
}
$$

with probability `epsilon` of random exploration.

---

This is where things become much more interesting, because we can compare it **line by line against this prototype** and identify exactly what the author changed, rather than learning the second 377-line file from scratch without context.

# `scan_scheduler_v2.py` — line-by-line

This file is **377 lines**. It builds directly on `scan_scheduler_prototype.py`, but introduces two major upgrades:

1. **UCB-style exploration** instead of fixed epsilon-greedy.
2. **Multi-channel scanning** — receiver can scan `k` bands per timestep instead of exactly one.

---

# Lines 1–18 — File documentation

### Line 1
```python
"""
```

Starts a multiline string.

Because it appears at the very beginning of the file, this becomes the **module docstring**.

---

### Line 2
```python
scan_scheduler_v2.py
```

Human-readable name of the file.

---

### Lines 3–4
```text
======================
Two concrete upgrades over BeliefScheduler in scan_scheduler_prototype.py:
```

Documentation only.

It explicitly establishes that V2 is intended as an upgrade to the previous `BeliefScheduler`.

---

### Lines 6–10

```text
1. UCB-style exploration bonus instead of fixed epsilon-greedy.
Each band gets a bonus that shrinks as it's scanned more...
```

This describes the first major change.

Previous scheduler:

```python
if random.random() < epsilon:
    random band
else:
    highest belief
```

V2 instead gives every band a mathematical **exploration bonus**.

A rarely scanned band gets a larger bonus.

A frequently scanned band gets a smaller bonus.

---

### Lines 12–15

Second upgrade:

> Multi-channel scanning.

Previous:

```python
choose_band()
```

returns one band.

V2:

```python
choose_bands(k)
```

returns up to `k` bands.

For example:

```python
choose_bands(3)
```

could return:

```python
[1, 4, 7]
```

So receiver has three simultaneous channels/slots.

---

### Lines 17–18

```text
Run: python3 scan_scheduler_v2.py
"""
```

Documentation showing how to execute file.

---

# Lines 20–24 — Imports

### Line 20
```python
import math
```

Imports Python's `math` module.

Later needed for:

```python
math.sqrt(...)
math.log(...)
```

for UCB calculation.

---

### Line 21
```python
import random
```

Random-number functionality.

Used for:

- random scheduler
- warmup shuffling
- dwell jitter
- reproducibility via `random.seed()`

---

### Line 22
```python
import statistics
```

Used to calculate averages:

```python
statistics.mean(...)
```

---

### Line 23
```python
from dataclasses import dataclass, field
```

Imports:

- `dataclass` → automatically generates dataclass methods
- `field` → allows controlled defaults such as `default_factory=list`

Same mechanism used in V1.

---

### Line 24
```python
from typing import List, Dict, Optional  # Dict already used by run_episode below
```

Imports type annotations.

`List`:

```python
List[int]
```

`Dict`:

```python
Dict[int, bool]
```

`Optional`:

```python
Optional[List[float]]
```

means value can either be the specified type or `None`.

The comment explains why `Dict` is imported: it is used later in `run_episode()`.

---

# Lines 26–28 — Importing V1

### Line 26
```python
from scan_scheduler_prototype import (
```

Imports things from previous file.

This means V2 **reuses existing code** rather than rewriting emitters and environment.

---

### Line 27
```python
MarkovEmitter, PeriodicEmitter, AgileEmitter, Environment, make_scenario
```

Imports five names:

```text
MarkovEmitter
PeriodicEmitter
AgileEmitter
Environment
make_scenario
```

These are all defined in `scan_scheduler_prototype.py`.

Notice something interesting:

`MarkovEmitter`, etc. are imported even though this file doesn't directly instantiate them.

They're part of the reusable simulation infrastructure.

---

### Line 28
```python
)
```

Closes import statement.

---

# Lines 31–33 — Scheduler section

### Lines 31–33

Comments dividing source into sections.

```text
Schedulers (multi-channel interface)
```

This signals a major architectural change.

---

# Lines 35–65 — `recommended_warmup_dwell()`

This function is new and deserves careful attention.

### Line 35
```python
def recommended_warmup_dwell(switch_cost_steps: int, warmup_steps: int, margin: int = 2):
```

Defines helper function.

Inputs:

```text
switch_cost_steps
warmup_steps
margin
```

Example:

```python
recommended_warmup_dwell(2, 100)
```

---

### `switch_cost_steps`

Number of timesteps lost when receiver switches frequency.

For example:

```text
switch_cost_steps = 2
```

means after switching, receiver needs two settling steps before valid observation.

---

### `warmup_steps`

How long initial exploration/warmup should last.

---

### `margin=2`

Extra safety margin.

---

### Lines 36–39

Docstring explains what function returns:

```text
(warmup_dwell_steps, scaled_warmup_steps)
```

The purpose is to preserve roughly comparable numbers of **valid observations** when switching isn't free.

---

### Lines 41–47

This documents empirical validation.

It says:

```text
dwell = switch_cost_steps + 1
```

isn't enough.

Instead:

```text
dwell = switch_cost_steps + margin
```

with default:

```text
margin = 2
```

performed better in their validation.

This is important: this isn't a mathematical theorem encoded in the function. The docstring says it was found through a separate experiment:

```text
validate_warmup_dwell_fix.py
```

So later, when we reach that file, we'll be able to inspect exactly how this claim was validated.

---

### Lines 49–53

Core idea:

If each visit spends some time settling, fewer timesteps are available for actual observations.

Suppose:

```text
dwell = 4
switch cost = 2
```

Then only:

$$
4-2=2
$$

steps per visit are useful.

Therefore a fixed warmup budget needs scaling.

The approximate scaling factor is:

$$
\frac{\text{dwell}}
{\text{dwell}-\text{switch cost}}
$$

---

### Lines 55–59

These explain **dwell jitter**.

Without jitter, fixed dwell duration can synchronize badly with periodic emitters.

For example, imagine:

```text
scanner:
settle → valid → settle → valid → ...

emitter:
ON → OFF → ON → OFF → ...
```

If scanner's valid observations always line up with emitter OFF states, it can systematically miss it.

This is an **aliasing/parity problem**.

Randomizing dwell length breaks that deterministic synchronization.

We'll see the actual implementation around lines 181–217.

---

### Line 61
```python
if switch_cost_steps <= 0:
```

If switching costs nothing or is negative.

Negative doesn't make physical sense, but `<= 0` safely handles both zero and invalid negative input.

---

### Line 62
```python
return 1, warmup_steps
```

If no switching cost:

```text
dwell = 1
warmup duration = unchanged
```

Returns a tuple:

```python
(1, warmup_steps)
```

---

### Line 63
```python
dwell = switch_cost_steps + margin
```

For example:

```text
switch cost = 2
margin = 2
```

then:

```text
dwell = 4
```

---

### Line 64
```python
scaled_warmup = int(round(warmup_steps * dwell / (dwell - switch_cost_steps)))
```

This is the main formula.

Suppose:

```text
warmup_steps = 100
dwell = 4
switch cost = 2
```

Then:

$$
100\times\frac4{4-2}
$$

$$
=100\times2
$$

$$
=200
$$

Then:

```python
round(...)
```

rounds the result.

`int(...)` converts it to integer.

---

### Line 65
```python
return dwell, scaled_warmup
```

Returns both calculated values.

Example:

```python
(4, 200)
```

---

# Lines 68–76 — Base `Scheduler`

### Line 68
```python
class Scheduler:
```

Defines new base scheduler.

Unlike V1, interface is now multi-channel.

---

### Lines 69–70
```python
def __init__(self, n_bands: int):
    self.n_bands = n_bands
```

Same concept as V1.

Stores number of frequency bands.

---

### Line 72
```python
def choose_bands(self, k: int) -> List[int]:
```

Major change.

V1:

```python
choose_band()
```

V2:

```python
choose_bands(k)
```

Returns a list of selected bands.

Example:

```python
choose_bands(3)
```

→

```python
[1, 4, 6]
```

---

### Line 73
```python
raise NotImplementedError
```

Base class doesn't define actual selection strategy.

Subclasses must implement it.

---

### Lines 75–76
```python
def update(self, band: int, observed_on: bool):
    pass
```

This is inherited interface for feedback.

However, notice a design issue already:

The new scheduler can scan **multiple bands**, but `update()` still accepts only:

```python
band
observed_on
```

one pair at a time.

The simulation will therefore call `update()` separately for each selected band.

---

# Lines 79–87 — Multi-channel Round Robin

### Line 79
```python
class RoundRobinScheduler(Scheduler):
```

Defines round-robin subclass.

---

### Lines 80–82
```python
def __init__(self, n_bands):
    super().__init__(n_bands)
    self.ptr = 0
```

Same basic mechanism as V1.

`ptr` tracks where sweep begins.

---

### Line 84
```python
def choose_bands(self, k):
```

Now selects **k bands**, not one.

---

### Line 85
```python
bands = [(self.ptr + i) % self.n_bands for i in range(k)]
```

This is a list comprehension.

Suppose:

```text
ptr = 5
n_bands = 8
k = 3
```

Then:

```text
i=0 → (5+0)%8 = 5
i=1 → (5+1)%8 = 6
i=2 → (5+2)%8 = 7
```

Result:

```python
[5, 6, 7]
```

If:

```text
ptr = 7
k = 3
```

then:

```text
(7+0)%8 = 7
(7+1)%8 = 0
(7+2)%8 = 1
```

Result:

```python
[7, 0, 1]
```

So wrapping still works.

---

### Line 86
```python
self.ptr = (self.ptr + k) % self.n_bands
```

Advance pointer by number of channels consumed.

If:

```text
ptr = 5
k = 3
n = 8
```

then:

$$
(5+3)\%8=0
$$

Next call starts at 0.

---

### Line 87
```python
return bands
```

Return selected list.

---

# Lines 90–92 — Multi-channel Random

### Line 90
```python
class RandomScheduler(Scheduler):
```

Random baseline.

---

### Line 91
```python
def choose_bands(self, k):
```

Select `k` bands.

---

### Line 92
```python
return random.sample(range(self.n_bands), min(k, self.n_bands))
```

This is different from V1's:

```python
random.randrange(...)
```

`random.sample()` selects **distinct** elements.

For:

```text
n_bands = 8
k = 3
```

possible result:

```python
[1, 7, 3]
```

but never:

```python
[1, 1, 3]
```

because sampling is without replacement.

`min(k, self.n_bands)` prevents requesting more distinct bands than exist.

---

# Lines 95–112 — `BeliefUCBScheduler`

Now main new algorithm.

### Line 95
```python
class BeliefUCBScheduler(Scheduler):
```

New intelligent scheduler.

It combines:

```text
Markov belief
+
UCB exploration
+
priority weights
+
multi-channel selection
+
optional warmup
```

---

## Lines 96–112 — Class documentation

### Lines 97–100

It still learns the same two-state Markov model as V1.

But instead of:

```text
epsilon-greedy
```

it uses UCB-style score:

$$
\boxed{
score(b)
=
priority(b)\times belief(b)
+
c\sqrt{
\frac{\log(t+1)}
{scans(b)+1}
}
}
$$

This is the central formula of V2.

---

### Understanding the two terms

#### Exploitation

$$
priority(b)\times belief(b)
$$

High if:

- band is believed likely ON
- band has high importance

#### Exploration

$$
c\sqrt{
\frac{\log(t+1)}
{scans(b)+1}
}
$$

High if:

- band has been scanned rarely

As `scans(b)` increases, denominator increases, so bonus decreases.

---

### Lines 102–111 — `priority`

Priority allows different bands to have different importance.

For example:

```python
priority = [
    1.0,
    3.0,
    1.0,
    1.0,
    0.5,
    ...
]
```

Band 1 can be favored even if its raw probability isn't highest.

This addresses an important problem:

> Maximizing raw interception count may favor loud, frequently transmitting communications instead of rare but important radar signals.

---

# Lines 113–130 — Constructor

### Lines 113–115
```python
def __init__(self, n_bands, ucb_c: float = 0.5, warmup_steps: int = 0,
             priority: Optional[List[float]] = None,
             warmup_dwell_steps: int = 1, warmup_dwell_jitter: int = 1):
```

Many parameters.

### `n_bands`

Number of frequencies.

### `ucb_c=0.5`

Controls exploration strength.

Higher:

```text
more exploration
```

Lower:

```text
more exploitation
```

### `warmup_steps=0`

By default no special warmup.

### `priority=None`

Optional list of priorities.

### `warmup_dwell_steps=1`

How many calls a warmup slot stays on each band.

### `warmup_dwell_jitter=1`

Random extra dwell:

```text
0 or 1
```

when enabled.

---

### Line 116
```python
super().__init__(n_bands)
```

Initialize base scheduler.

---

### Line 117
```python
self.ucb_c = ucb_c
```

Store exploration coefficient.

---

### Line 118
```python
self.warmup_steps = warmup_steps
```

Store warmup duration.

---

### Line 119
```python
self.priority = list(priority) if priority is not None else [1.0] * n_bands
```

Important conditional expression.

If caller supplies priorities:

```python
priority=[1,2,1,3]
```

then:

```python
list(priority)
```

creates a list copy.

If no priority supplied:

```python
priority is None
```

then:

```python
[1.0] * n_bands
```

creates equal priority for every band.

So default is:

$$
priority_b=1
$$

for every band.

---

### Lines 120–123

Exactly the same Laplace-smoothed transition counters as V1:

```python
self.off_on = [1.0] * n_bands
self.off_tot = [2.0] * n_bands
self.on_on = [1.0] * n_bands
self.on_tot = [2.0] * n_bands
```

Initial:

$$
P(ON|OFF)=0.5
$$

$$
P(ON|ON)=0.5
$$

---

### Line 124
```python
self.belief = [0.3] * n_bands
```

Initial ON probability = 0.3 for every band.

---

### Line 125
```python
self.last_scan_result = [None] * n_bands
```

No observations initially.

---

### Line 126
```python
self.scan_count = [0] * n_bands
```

**New in V2.**

Tracks how many times each band has been scanned.

Example:

```python
[10, 3, 25, 0, ...]
```

This is needed by UCB.

Rarely scanned band:

```text
scan_count = 0
```

gets high exploration bonus.

---

### Line 127
```python
self.t = 0
```

Scheduler's internal timestep counter.

---

### Line 128
```python
self._warmup_order: List[int] = []
```

Stores shuffled order of bands during warmup.

Initially empty.

---

### Line 129
```python
self._warmup_idx = 0
```

Current position in warmup order.

---

### Line 130
```python
# --- warm-up dwell (for use with switch_cost_steps>0) ---
```

Comment introducing substantial warmup logic.

The reason is hardware switching cost.

---

# Lines 131–155 — Warmup design

These comments are long, but they describe an actual design problem.

### Lines 131–136

Default:

```python
warmup_dwell_steps = 1
```

means each warmup call selects a fresh band.

That's equivalent to original behavior.

But if switching costs time, doing:

```text
band 1
band 2
band 3
band 4
...
```

means receiver switches every step.

If each switch requires settling, it may never obtain a valid observation.

---

### Lines 138–141

Setting:

```text
warmup_dwell_steps > 1
```

causes receiver to remain on each band for multiple consecutive calls.

Example:

```text
band 3
band 3
band 3
band 7
band 7
band 7
...
```

This gives hardware time to settle.

---

### Lines 142–149

But fixed dwell introduces another problem.

A fixed dwell can synchronize with periodic emitter timing.

This creates deterministic blind spots.

The code therefore introduces random jitter.

---

### Lines 149–153

Each dwell gets:

```text
0..warmup_dwell_jitter
```

additional steps.

So with:

```text
warmup_dwell_steps = 3
warmup_dwell_jitter = 1
```

each dwell lasts either:

```text
3 or 4
```

steps.

This breaks fixed timing relationships.

---

### Lines 154–155
```python
self.warmup_dwell_steps = warmup_dwell_steps
self.warmup_dwell_jitter = warmup_dwell_jitter
```

Store these settings.

---

### Line 156
```python
self._warmup_slots: List[Dict[str, int]] = []
```

New structure.

Each warmup slot stores dictionary like:

```python
{
    "band": 3,
    "remaining": 2
}
```

With multiple channels, each receiver channel needs its **own warmup state**.

---

# Lines 158–166 — Markov functions

### Lines 158–162
```python
def _p_on_given_off(self, b):
    return self.off_on[b] / self.off_tot[b]

def _p_on_given_on(self, b):
    return self.on_on[b] / self.on_tot[b]
```

Same as V1.

They estimate:

$$
P(ON|OFF)
$$

and:

$$
P(ON|ON)
$$

---

### Lines 164–166
```python
def _propagate(self, b):
    bel = self.belief[b]
    self.belief[b] = bel * self._p_on_given_on(b) + (1 - bel) * self._p_on_given_off(b)
```

Again same Markov prediction.

Mathematically:

$$
b_{t+1}
=
b_tP(ON|ON)
+
(1-b_t)P(ON|OFF)
$$

---

# Lines 168–179 — Warmup band generator

### Line 168
```python
def _next_warmup_band(self):
```

Internal helper.

Returns next band in warmup sequence.

---

### Lines 169–172

Docstring says order is freshly shuffled each lap.

This is important because fixed rotation can synchronize with periodic emitters.

---

### Line 173
```python
if self._warmup_idx >= len(self._warmup_order):
```

Checks whether current shuffled list has been exhausted.

Initially:

```text
idx = 0
len(order) = 0
```

so condition is true.

---

### Line 174
```python
self._warmup_order = list(range(self.n_bands))
```

Creates:

```text
[0,1,2,3,4,5,6,7]
```

for 8 bands.

---

### Line 175
```python
random.shuffle(self._warmup_order)
```

Randomly rearranges list **in place**.

Example:

```text
[3,7,1,5,0,6,2,4]
```

---

### Line 176
```python
self._warmup_idx = 0
```

Start at beginning of newly shuffled order.

---

### Line 177
```python
band = self._warmup_order[self._warmup_idx]
```

Retrieve current band.

---

### Line 178
```python
self._warmup_idx += 1
```

Advance pointer.

---

### Line 179
```python
return band
```

Return selected warmup band.

---

# Lines 181–217 — `_warmup_bands()`

This is one of the most complicated sections.

### Line 181
```python
def _warmup_bands(self, k):
```

Returns `k` bands for multi-channel warmup.

---

### Lines 182–202

Docstring explains:

Each channel/slot independently cycles through shuffled band order.

Each slot stays on current band for:

$$
warmup\_dwell\_steps + jitter
$$

calls.

---

### Line 203
```python
if len(self._warmup_slots) < k:
```

If we don't yet have enough slot state for requested number of channels.

Suppose:

```text
currently slots = 1
k = 3
```

need two more.

---

### Lines 204–206
```python
self._warmup_slots.extend(
    {"band": -1, "remaining": 0} for _ in range(k - len(self._warmup_slots))
)
```

This extends list.

For two missing slots:

```python
[
    {"band": -1, "remaining": 0},
    {"band": -1, "remaining": 0}
]
```

`-1` means no band assigned yet.

---

### Line 207
```python
bands = []
```

Output list.

---

### Line 208
```python
for slot in self._warmup_slots[:k]:
```

Process only first `k` slots.

`[:k]` is list slicing.

---

### Line 209
```python
if slot["remaining"] <= 0:
```

If current slot has no remaining dwell time, assign a new band.

---

### Line 210
```python
slot["band"] = self._next_warmup_band()
```

Get next shuffled band.

---

### Line 211
```python
jitter = (random.randint(0, self.warmup_dwell_jitter)
```

Generate random integer between:

```text
0
```

and:

```text
warmup_dwell_jitter
```

inclusive.

---

### Lines 212–213
```python
if self.warmup_dwell_steps > 1 and self.warmup_dwell_jitter > 0
else 0)
```

Jitter is enabled only when:

```text
dwell > 1
AND
jitter > 0
```

Otherwise:

```python
jitter = 0
```

This preserves original behavior when dwell is 1.

---

### Line 214
```python
slot["remaining"] = self.warmup_dwell_steps + jitter
```

Determine how many calls this slot stays on band.

Example:

```text
base dwell = 3
jitter = 1
```

then:

```text
remaining = 4
```

---

### Line 215
```python
bands.append(slot["band"])
```

Add selected band to output.

---

### Line 216
```python
slot["remaining"] -= 1
```

One dwell call has now been consumed.

If remaining was 4:

```text
4 → 3
```

---

### Line 217
```python
return bands
```

Return selected warmup bands.

Example:

```python
[3, 7, 1]
```

---

# Lines 219–233 — Main UCB decision

Now the heart of V2.

### Line 219
```python
def choose_bands(self, k):
```

Select up to `k` bands.

---

### Line 220
```python
self.t += 1
```

Advance scheduler's internal time.

First call:

```text
t = 1
```

rather than 0.

---

### Line 221
```python
if self.t <= self.warmup_steps:
```

If still in warmup period.

Example:

```text
warmup_steps = 100
```

then calls 1–100 use warmup.

---

### Lines 222–223
```python
for b in range(self.n_bands):
    self._propagate(b)
```

Propagate beliefs for all bands even during warmup.

---

### Line 224
```python
return self._warmup_bands(k)
```

Instead of UCB scoring, choose warmup bands.

---

### Line 225
```python
for b in range(self.n_bands):
```

After warmup, propagate every band's belief.

---

### Line 226
```python
self._propagate(b)
```

Update predicted probability.

---

## Lines 227–231 — UCB score

### Line 227
```python
scores = [
```

Start list comprehension.

It will create one score per band.

---

### Line 228
```python
self.priority[b] * self.belief[b]
```

First component:

$$
priority_b\times belief_b
$$

This is exploitation.

---

### Line 229
```python
+ self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
```

Second component is UCB exploration bonus:

$$
c\sqrt{
\frac{\ln(t+1)}
{N_b+1}
}
$$

where:

- $c$ = `ucb_c`
- $t$ = current time
- $N_b$ = number of scans of band b

The `+1`s prevent:

- `log(0)` problems
- division by zero

---

### Lines 230–231
```python
for b in range(self.n_bands)
]
```

Compute score for every band.

So mathematically:

$$
\boxed{
S_b =
p_bB_b
+
c\sqrt{\frac{\ln(t+1)}{N_b+1}}
}
$$

---

### Line 232
```python
order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
```

Sort band indices according to their scores.

Suppose:

```text
scores = [0.2, 0.9, 0.5, 0.7]
```

then:

```python
order
```

becomes:

```text
[1, 3, 2, 0]
```

because:

```text
score[1] = .9
score[3] = .7
score[2] = .5
score[0] = .2
```

`reverse=True` means descending order.

---

### Line 233
```python
return order[:k]
```

Take top `k`.

If:

```text
order = [1,3,2,0]
k = 2
```

returns:

```python
[1,3]
```

Therefore multi-channel receiver scans the top two UCB-scored bands.

---

# Lines 235–248 — Update

### Line 235
```python
def update(self, band, observed_on):
```

Receives one observation.

---

### Lines 236–247

This is essentially the V1 learning logic:

```python
prev = self.last_scan_result[band]
```

then update appropriate transition counts:

```text
ON → ON
ON → OFF
OFF → ON
OFF → OFF
```

and then:

```python
self.last_scan_result[band] = observed_on
self.belief[band] = 1.0 if observed_on else 0.0
```

So after observation, belief becomes certain.

---

### Line 248
```python
self.scan_count[band] += 1
```

This is V2's key addition to `update()`.

Every valid scan increments the count.

For example:

```text
scan_count[4] = 10
```

means band 4 has been observed 10 times.

That count directly controls UCB exploration.

As:

$$
N_b\rightarrow\infty
$$

the exploration term:

$$
\sqrt{\frac{\ln(t+1)}{N_b+1}}
$$

shrinks.

---

# Lines 251–253

Section separator.

Now simulation supports multi-channel scanning and hardware switching costs.

---

# Lines 255–264 — New `RunStats`

### Line 255
```python
@dataclass
```

Dataclass.

---

### Line 256
```python
class RunStats:
```

Stores simulation metrics.

---

### Line 257
```python
total_steps: int = 0
```

Number of simulation timesteps.

---

### Line 258
```python
total_band_transmissions: int = 0
```

This differs from V1.

V1 counted:

> timestep where at least one band was active.

V2 counts:

> **sum of number of active bands across all timesteps.**

Example:

```text
t=0 → 3 active bands
t=1 → 1 active band
t=2 → 2 active bands
```

Then:

$$
total\_band\_transmissions=3+1+2=6
$$

---

### Line 259
```python
hits: int = 0
```

Number of:

$$
(\text{band},\text{time})
$$

pairs where scanned band was ON.

Since receiver can scan multiple bands, there can be multiple hits per timestep.

---

### Line 260
```python
intercept_delays: List[int] = field(default_factory=list)
```

Stores interception delays.

---

### Line 261
```python
step_hit_rewards: List[int] = field(default_factory=list)
```

Different reward definition from V1.

V1 recorded one reward per scan.

V2 records:

> `1` if **at least one selected band** produced a hit during timestep; otherwise `0`.

---

### Line 262
```python
switches: int = 0
```

Number of channel-switch events.

---

### Line 263
```python
wasted_scans: int = 0
```

Number of scans spent during hardware settling.

These are scans that cannot produce valid observations.

---

# Lines 265–275 — Reporting

### Line 265
```python
def report(self):
```

Generate summary.

---

### Line 266
```python
interception_ratio = self.hits / max(1, self.total_band_transmissions)
```

Now:

$$
\text{interception ratio}
=
\frac{\text{detected band-time pairs}}
{\text{active band-time pairs}}
$$

This is more precise than V1's timestep-level denominator.

---

### Line 267
```python
avg_reward = statistics.mean(self.step_hit_rewards) if self.step_hit_rewards else 0.0
```

Average timestep reward.

If each timestep is:

```text
0,1,1,0
```

average:

$$
0.5
$$

---

### Line 268
```python
avg_delay = statistics.mean(self.intercept_delays) if self.intercept_delays else None
```

Average delay.

No observations → `None`.

---

### Lines 269–275

Return dictionary:

```python
{
    "interception_ratio": ...,
    "avg_reward_per_step": ...,
    "avg_intercept_delay": ...,
    "switches": ...,
    "wasted_scans": ...,
}
```

---

### Line 270

Round interception ratio to 3 decimal places.

### Line 271

Round average reward to 3 decimals.

### Line 272

Round delay to 2 decimals, or `"n/a"`.

### Line 273

Include switch count.

### Line 274

Include wasted scans.

### Line 275

Close dictionary.

---

# Lines 278–345 — `run_episode()`

This is the most important change in the simulation engine.

### Lines 278–279
```python
def run_episode(env_factory, scheduler: Scheduler, n_steps: int, n_bands: int, k_channels: int = 1,
                switch_cost_steps: int = 0) -> RunStats:
```

New parameters:

### `k_channels=1`

Number of simultaneous receiver channels.

Examples:

```text
k=1 → single-channel
k=2 → dual-channel
k=3 → triple-channel
```

### `switch_cost_steps=0`

Hardware retuning cost.

Default zero preserves previous behavior.

---

## Lines 280–299 — Hardware model documentation

The docstring explains:

If receiver switches a channel to a new band:

```text
settling period begins
```

During settling:

- no valid observation
- no scheduler update
- no hit credit
- receiver cannot scan another band with that channel

This is intended to model actual retuning/LO/filter settling.

---

# Lines 300–305 — Initialization

### Line 300
```python
env = env_factory()
```

Fresh environment.

---

### Line 301
```python
stats = RunStats()
```

Empty statistics.

---

### Line 302
```python
on_since = [None] * n_bands
```

Tracks when each band became continuously ON.

---

### Line 303
```python
credited = [False] * n_bands
```

Tracks whether interception delay has already been credited for current ON episode.

---

### Line 304
```python
prev_bands = set()
```

Stores bands selected during previous timestep.

Starts empty.

This is used to detect switching.

---

### Line 305
```python
settling_remaining: Dict[int, int] = {}
```

Dictionary:

```text
band → number of settling steps remaining
```

Example:

```python
{
    3: 2,
    7: 1
}
```

---

# Lines 307–319 — Environment update

### Line 307
```python
for t in range(n_steps):
```

Main timestep loop.

---

### Line 308
```python
status: Dict[int, bool] = env.step()
```

Advance environment.

Get:

```text
band → ON/OFF
```

---

### Line 310
```python
for b in range(n_bands):
```

Inspect every band.

---

### Line 311
```python
if status[b]:
```

If band is active.

---

### Line 312
```python
stats.total_band_transmissions += 1
```

Increment for each active band.

This is why V2 denominator differs from V1.

If 3 bands are active this timestep:

```text
+3
```

---

### Line 313
```python
if on_since[b] is None:
```

Check whether this is beginning of new ON episode.

---

### Line 314
```python
on_since[b] = t
```

Record start timestep.

---

### Line 315
```python
credited[b] = False
```

Reset interception credit.

---

### Lines 316–318

If band is OFF:

```python
on_since[b] = None
credited[b] = False
```

So next time it turns ON, it's treated as a fresh transmission episode.

---

# Lines 320–343 — Multi-channel scanning

### Line 320
```python
bands = scheduler.choose_bands(k_channels)
```

This is the central new call.

For:

```text
k_channels = 3
```

scheduler may return:

```python
[1,4,6]
```

---

### Line 321
```python
step_hit = False
```

Tracks whether **at least one** selected channel detects signal.

---

### Line 322
```python
for band in bands:
```

Process each selected band individually.

---

# Lines 323–330 — Switching cost

### Line 323
```python
if switch_cost_steps > 0:
```

Only apply hardware settling model if nonzero.

---

### Line 324
```python
if band not in prev_bands:
```

Determine whether this band wasn't selected in previous timestep.

If previous bands:

```python
{1,4}
```

and current:

```text
[1,7]
```

then:

```text
1 → already present
7 → new
```

Only band 7 incurs switching cost.

---

### Line 325
```python
settling_remaining[band] = switch_cost_steps
```

Set settling timer.

For cost 2:

```python
settling_remaining[7] = 2
```

---

### Line 326
```python
stats.switches += 1
```

Count switch.

---

### Line 327
```python
if settling_remaining.get(band, 0) > 0:
```

Look up remaining settling steps.

`.get(key, default)` means:

> Return value if key exists; otherwise return 0.

---

### Line 328
```python
settling_remaining[band] -= 1
```

Consume one settling step.

---

### Line 329
```python
stats.wasted_scans += 1
```

This timestep's scan cannot produce valid observation.

---

### Line 330
```python
continue
```

Skip rest of loop for this band.

Therefore:

```python
scheduler.update(...)
```

is **not called**.

This is deliberate.

---

# Lines 332–339 — Valid observation

### Line 332
```python
observed_on = status[band]
```

Read actual state.

---

### Line 333
```python
scheduler.update(band, observed_on)
```

Give valid observation to scheduler.

This updates Markov model and scan count.

---

### Lines 334–335
```python
if observed_on:
    step_hit = True
```

If this selected band was active, timestep counts as hit.

---

### Line 336
```python
stats.hits += 1
```

Increment total hit count.

With multiple channels, this can increment several times in one timestep.

---

### Lines 337–339
```python
if on_since[band] is not None and not credited[band]:
    stats.intercept_delays.append(t - on_since[band])
    credited[band] = True
```

Same interception-delay mechanism as V1.

If signal started at `t=20` and detected at `t=24`:

$$
24-20=4
$$

Store delay `4`.

Only first detection during ON episode receives credit.

---

### Line 341
```python
stats.step_hit_rewards.append(1 if step_hit else 0)
```

At end of timestep:

```text
at least one hit → 1
no hit → 0
```

Important distinction:

Suppose 3 channels scan and all 3 detect:

```text
hits += 3
```

but:

```text
step_hit_reward = 1
```

not 3.

---

### Line 342
```python
stats.total_steps += 1
```

Increment timestep count.

---

### Line 343
```python
prev_bands = set(bands)
```

Store current selected bands for next timestep.

Using `set` makes membership check efficient and ignores ordering.

---

### Line 345
```python
return stats
```

Return results.

---

# Lines 348–373 — `main()`

### Line 348
```python
def main():
```

Program entry function.

---

### Lines 349–350
```python
n_bands = 8
n_steps = 4000
```

Same simulation size as V1.

---

### Line 351
```python
scenario = make_scenario(n_bands)
```

Create environment factory from V1.

---

### Lines 353–354

Print scenario description.

Same four emitter types as V1.

---

# Lines 356–373 — Compare 1, 2, 3 channels

### Line 356
```python
for k in (1, 2, 3):
```

This is a major experiment.

The program runs three receiver configurations:

```text
k = 1
k = 2
k = 3
```

So it asks:

> What happens when receiver can scan one, two, or three bands simultaneously?

---

### Line 357
```python
random.seed(7)
```

Reset random generator **for each k**.

This is intended to make experiments comparable between `k=1`, `k=2`, and `k=3`.

---

### Line 358
```python
print(f"--- k_channels = {k} (receiver scans {k} band(s) per step) ---")
```

Print current experiment configuration.

---

### Lines 359–363

Construct three schedulers:

```text
RoundRobin
Random
BeliefUCB
```

For BeliefUCB:

```python
BeliefUCBScheduler(n_bands, ucb_c=0.5)
```

So:

```text
ucb_c = 0.5
warmup = 0
priority = all 1
```

---

### Lines 364–365

Build result-table header.

Same formatting idea as V1.

---

### Line 366
```python
print(header)
```

Print header.

---

### Line 367
```python
print("-" * len(header))
```

Print separator.

---

### Line 368
```python
for name, sched in schedulers.items():
```

Run each scheduler.

---

### Line 369
```python
stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
```

Run 4000-step simulation using current number of channels.

---

### Line 370
```python
r = stats.report()
```

Convert raw statistics to summary.

---

### Lines 371–372

Print:

- scheduler
- interception %
- average reward
- average interception delay

---

### Line 373
```python
print()
```

Blank line separating `k=1`, `k=2`, and `k=3` results.

---

# Lines 376–377 — Entry point

### Line 376
```python
if __name__ == "__main__":
```

Only execute `main()` when file is directly run.

---

### Line 377
```python
main()
```

Start experiment.

---

# What V2 actually changed

The examination of all 377 lines shows the evolution from V1.

| Feature | V1 | V2 |
|---|---|---|
| Channels | 1 | 1, 2, or 3 |
| Exploration | ε-greedy | UCB bonus |
| Exploration parameter | `epsilon` | `ucb_c` |
| Band priority | No | Yes |
| Scan count | No | Yes |
| Warmup | No | Yes |
| Warmup shuffle | No | Yes |
| Warmup dwell | No | Yes |
| Warmup jitter | No | Yes |
| Switching cost model | No | Yes |
| Transmission metric | active timesteps | active band-time pairs |
| Reward | every scan | any hit during timestep |

## The central V2 equation

Everything new in the intelligent scheduler revolves around:

$$
\boxed{
S_b =
P_b B_b
+
c\sqrt{\frac{\ln(t+1)}{N_b+1}}
}
$$

where:

- $B_b$ = estimated probability band $b$ is ON
- $P_b$ = priority of band $b$
- $N_b$ = number of valid observations of band $b$
- $c$ = exploration strength
- $t$ = scheduler timestep

Then:

$$
\boxed{
\text{select top }k\text{ bands by }S_b
}
$$

---

## One especially important design interaction

V2 now has **three separate mechanisms** that can affect whether a band gets observed:

```text
                 UCB score
                    ↓
             which bands chosen
                    ↓
              switch cost
                    ↓
          whether observation valid
                    ↓
             scan_count update
                    ↓
             future UCB bonus
```

That means hardware switching cost isn't merely an output metric. It can **change what the learning algorithm learns**, because settling scans don't call:

```python
scheduler.update()
```

and therefore don't increase `scan_count` or update beliefs.

This interaction becomes very important in the later files—especially the ones named:

- `validate_warmup_dwell_fix.py`
- `validate_beacon_switchcost_dwell.py`
- `settle_fix_interaction.py`

Those files appear to be investigating exactly these failure modes.

**Next in the sequence is `scan_scheduler_v3_pri.py` (489 lines), where the priority/PRI logic gets considerably more sophisticated.**

## `scan_scheduler_v3_pri.py` — line-by-line explanation


---

# Lines 1–22 — Module documentation

### Line 1
```python
"""
```
Starts a module-level multiline string, used as the file's documentation string.

### Line 2
```python
scan_scheduler_v3_pri.py
```
File/module name.

### Line 3
```python
==========================
```
Visual separator for the documentation.

### Line 4
```python
Adds an explicit Pulse Repetition Interval (PRI) predictor on top of the
```
States V3's main new feature: **PRI prediction**.

PRI = time between repeated radar pulses.

### Line 5
```python
BeliefUCBScheduler from scan_scheduler_v2.py.
```
V3 inherits V2's `BeliefUCBScheduler`.

So conceptually:

```text
V1:
Markov belief

       ↓

V2:
Markov belief + UCB exploration

       ↓

V3:
Markov belief + UCB exploration + PRI prediction
```

### Lines 6–15
These lines explain **why PRI is needed**.

```python
Why: a first-order Markov model only knows "this band was recently
active, so it's probably still active" -- it has no notion of a
repeating cycle...
```

The problem with Markov prediction:

Suppose radar pulses occur at:

```text
t = 0, 12, 24, 36, 48, ...
```

A first-order Markov model doesn't understand:

> "Pulse happened every 12 steps."

It only learns relationships such as:

```text
ON → probably ON
OFF → probably OFF
```

That is bad for sparse radar signals because the radar might be:

```text
ON  OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF OFF
↑
pulse
```

Most observations are OFF.

PRI prediction instead learns:

```text
0 → 12 → 24 → 36 → 48
```

and therefore predicts:

```text
next pulse ≈ 60
```

### Lines 12–15

```python
scheduler tracks the actual gaps between confirmed hits on a band,
estimates the period and its jitter, and predicts the PHASE of the next
expected occurrence
```

Three things are learned:

1. **Gap**
   ```text
   t₂ - t₁
   ```

2. **PRI**
   Approximate repeated gap.

3. **Phase**
   Where we currently are relative to the expected next pulse.

---

### Lines 17–19

```python
For bursty/agile bands (no stable period), the gap variance stays high,
confidence drops to ~0, and the scheduler falls back to the plain
belief+UCB score
```

This is important.

V3 isn't supposed to blindly trust periodicity.

For a random/agile emitter:

```text
hits:
10, 14, 23, 31, 39, 52, 57...
```

there isn't a stable period.

So:

```text
periodicity confidence ↓
```

and the scheduler relies primarily on:

```text
Markov belief + UCB
```

### Line 21
```python
Run:  python3 scan_scheduler_v3_pri.py
```
Command to execute the file.

### Line 22
```python
"""
```
Ends module documentation.

---

# Lines 24–29 — Imports

### Line 24
```python
import math
```
Imports mathematical functions.

Used later for:

- `sqrt`
- `log`
- `exp`
- `gcd`

### Line 25
```python
import random
```
Used for:

- random seeds
- randomized scenarios
- randomized warmup
- random emitter behavior

### Line 26
```python
import statistics
```
Provides statistical operations such as:

```python
statistics.mean(...)
```

### Line 27
```python
from collections import Counter
```

`Counter` counts frequencies.

Example:

```python
Counter([12, 12, 24, 12, 36])
```

conceptually gives:

```text
12 → 3
24 → 1
36 → 1
```

V3 uses this to find the **most common pairwise time difference**.

### Line 28
```python
from functools import reduce
```

`reduce()` repeatedly combines elements.

Used here for:

```python
reduce(math.gcd, diffs)
```

to calculate GCD of many differences.

### Line 29
```python
from typing import List, Optional
```

Used for type annotations.

For example:

```python
List[int]
```

means list of integers.

```python
Optional[float]
```

means:

```text
float OR None
```

---

# Lines 31–37 — Importing previous scheduler versions

### Lines 31–34
```python
from scan_scheduler_v2 import (
    Scheduler, RunStats, run_episode, RoundRobinScheduler, RandomScheduler,
    BeliefUCBScheduler,
)
```

V3 reuses classes/functions from V2.

Specifically:

```text
Scheduler
RunStats
run_episode
RoundRobinScheduler
RandomScheduler
BeliefUCBScheduler
```

This is important software design.

V3 doesn't rewrite V2.

It extends it.

### Lines 35–37
```python
from scan_scheduler_prototype import (
    Emitter, MarkovEmitter, AgileEmitter, Environment, make_scenario
)
```

Imports the environment/emitter classes from V1.

So V3's architecture is:

```text
V1 environment
      ↓
V2 scheduler infrastructure
      ↓
V3 PRI-aware scheduler
```

---

# Lines 40–58 — `SparsePeriodicEmitter`

### Line 40
```python
class SparsePeriodicEmitter(Emitter):
```

Defines a new emitter.

It inherits from:

```python
Emitter
```

from V1.

### Lines 41–49

The docstring explains what this emitter represents.

```text
one short pulse
↓
long OFF period
↓
another pulse
↓
...
```

This is deliberately different from V1's beacon.

V1 beacon stayed ON for multiple steps.

V3 creates a **single-step pulse**.

---

### Line 50
```python
def __init__(self, name, band, pri):
```

Constructor takes:

- `name`
- `band`
- `pri`

Example:

```python
SparsePeriodicEmitter("radar", 5, 12)
```

means:

```text
radar
band = 5
PRI = 12 steps
```

### Line 51
```python
super().__init__(name)
```

Calls parent `Emitter` constructor.

This initializes inherited properties such as:

```python
self.name
self.band
self.on
```

### Line 52
```python
self.band = band
```

Stores fixed frequency band.

### Line 53
```python
self.pri = pri
```

Stores pulse repetition interval.

### Line 54
Blank line.

No executable behavior.

### Line 55
```python
def step(self, t):
```

Defines emitter behavior for timestep `t`.

### Line 56
```python
self.on = (t % self.pri == 0)
```

This is the entire periodic radar model.

Suppose:

```python
pri = 12
```

Then:

```text
t % 12
```

is zero at:

```text
0, 12, 24, 36, 48, ...
```

Therefore:

```text
t=0   → ON
t=1   → OFF
...
t=11  → OFF
t=12  → ON
```

So exactly one timestep per 12-step cycle is ON.

### Line 57
```python
return self.band, self.on
```

Returns:

```text
which band
+
whether emitter is ON
```

### Line 58
Blank.

---

# Lines 60–71 — Sparse scenario

### Line 60
```python
def make_sparse_scenario(n_bands=8):
```

Creates a scenario factory.

Default:

```text
8 bands
```

### Lines 61–62
Documentation says:

- same communications emitters
- same agile emitter
- periodic emitter replaced by sparse radar
- radar PRI = 12
- fixed band

### Line 63
```python
def factory():
```

Defines inner factory function.

Why?

Because `run_episode()` expects something callable that creates a **fresh environment**.

### Line 64
```python
emitters = [
```

Starts emitter list.

### Line 65
```python
MarkovEmitter("comm-1", band=1, p_on_given_off=0.05, p_on_given_on=0.9),
```

Communication emitter on band 1.

Transition probabilities:

```text
P(ON | OFF) = 0.05
P(ON | ON)  = 0.90
```

So once active, it tends to stay active.

### Line 66
```python
MarkovEmitter("comm-2", band=4, p_on_given_off=0.10, p_on_given_on=0.7),
```

Second communication emitter.

Band:

```text
4
```

Transition:

```text
OFF → ON = 0.10
ON  → ON = 0.70
```

### Line 67
```python
SparsePeriodicEmitter("fixed-pri-radar", band=5, pri=12),
```

This is the important emitter.

```text
band = 5
PRI = 12
```

So:

```text
t = 0, 12, 24, 36...
```

produces pulses.

### Line 68
```python
AgileEmitter("agile-threat", bands=[0, 3, 6, 7], dwell=2, duty=0.5),
```

Agile emitter can use:

```text
0, 3, 6, 7
```

It changes band every 2 steps and has 50% duty cycle.

### Line 69
```python
]
```

Ends emitter list.

### Line 70
```python
return Environment(n_bands=n_bands, emitters=emitters)
```

Creates environment containing these emitters.

### Line 71
```python
return factory
```

Returns the factory function rather than directly returning environment.

So:

```python
scenario = make_sparse_scenario()
```

gives a function.

Then:

```python
env = scenario()
```

creates environment.

---

# Lines 74–99 — `PRIAwareScheduler`

This is the heart of V3.

### Line 74
```python
class PRIAwareScheduler(BeliefUCBScheduler):
```

This means:

> `PRIAwareScheduler` is a specialized `BeliefUCBScheduler`.

It inherits all V2 functionality.

So it already has:

- Markov belief
- UCB
- scan counts
- warmup
- priorities
- multi-band scanning

V3 adds periodicity.

---

## Lines 75–83 — Class documentation

The class docstring explains its mathematical model.

### Line 76
```python
Per band, keeps the last `history_len` confirmed-hit step indices,
```

For each band it stores recent hit times.

Example:

```python
[100, 112, 124, 136, 148]
```

### Line 77
```python
estimates PRI = median(gaps) and jitter = stdev(gaps)
```

Originally, the conceptual estimator is:

```text
gaps = differences between hit times
```

Example:

```text
hits = 100, 112, 124, 136

gaps = 12, 12, 12
```

PRI:

```text
12
```

jitter:

```text
0
```

The actual implementation below subsequently uses a more sophisticated candidate/refinement procedure.

### Lines 78–79
```text
periodicity confidence = 1 - coefficient of variation
```

Conceptually:

$$
CV=\frac{\sigma}{\mu}
$$

and:

$$
confidence = 1-CV
$$

then clipped to:

```text
0 ≤ confidence ≤ 1
```

Low variation → high confidence.

High variation → low confidence.

### Lines 80–83

The final score combines:

```text
Markov belief
+
periodic phase prediction
+
UCB exploration
```

This is V3's major innovation.

---

# Lines 85–99 — Important plateau/burst caveat

This section is extremely important because it documents a bug discovered during experimentation.

### Lines 85–94

The scheduler initially used timing residual/jitter to determine how wide the periodic score should be.

Problem:

Suppose beacon is ON for four steps:

```text
t = 100  ON
t = 101  ON
t = 102  ON
t = 103  ON
```

Its **onset** happens exactly at 100 every cycle.

Therefore onset timing jitter might be:

```text
0
```

If jitter = 0, Gaussian phase score becomes extremely narrow:

```text
             peak
              ↓
             /\
            /  \
___________/    \________
```

Scheduler catches first step:

```text
100
```

then thinks:

```text
101 → not likely
```

and switches away.

But actual emitter remains ON.

Markov model would have handled this better because learned:

```text
P(ON | ON) high
```

### Lines 95–98

The fix is:

```python
max_run_ever
```

Track the longest observed consecutive ON run.

If:

```text
max_run_ever = 4
```

then minimum effective jitter becomes:

```text
4 / 2 = 2
```

This widens the phase score into something more like a plateau.

For a true single-pulse radar:

```text
max_run_ever = 1
```

so this doesn't significantly broaden it.

---

# Lines 100–107 — Constructor

### Line 100
```python
def __init__(self, n_bands, ucb_c: float = 0.5, history_len: int = 30,
```

Constructor starts.

Parameters:

- `n_bands`
- UCB coefficient
- number of historical hits to retain

Default history:

```text
30 hits
```

### Line 101
```python
min_confidence: float = 0.75, periodicity_weight: float = 1.5,
```

Two important parameters.

`min_confidence`:

```text
0.75
```

Periodic model must reach at least 75% confidence before being trusted.

`periodicity_weight`:

```text
1.5
```

Makes periodic score stronger.

### Line 102
```python
warmup_steps: int = 0, priority: Optional[List[float]] = None,
```

Inherited V2 controls:

- warmup
- per-band priority

### Line 103
```python
confidence_scale: float = 0.25, switch_lead_steps: int = 0,
```

`confidence_scale` controls how strict confidence calculation is.

`switch_lead_steps` is used when receiver switching has settling time.

### Line 104
```python
warmup_dwell_steps: int = 1, warmup_dwell_jitter: int = 1):
```

Warmup controls inherited from V2.

---

# Lines 105–107 — Parent initialization

### Line 105
```python
super().__init__(n_bands, ucb_c=ucb_c, warmup_steps=warmup_steps, priority=priority,
```

Calls V2's constructor.

### Line 106
```python
warmup_dwell_steps=warmup_dwell_steps,
```

Passes warmup dwell.

### Line 107
```python
warmup_dwell_jitter=warmup_dwell_jitter)
```

Passes warmup jitter and finishes parent constructor call.

---

# Lines 108–110 — PRI parameters

### Line 108
```python
self.history_len = history_len
```

Stores how many recent hit times are retained.

### Line 109
```python
self.min_confidence = min_confidence
```

Stores confidence threshold.

### Line 110
```python
self.periodicity_weight = periodicity_weight
```

Stores periodicity score multiplier.

---

# Lines 111–121 — Confidence scale

### Lines 111–120

Comments explain why `confidence_scale` exists.

The actual confidence formula later is:

$$
C =
1-\frac{RMSE}
{\text{confidence\_scale}\times PRI}
$$

Larger `confidence_scale` means denominator larger, therefore confidence falls more slowly.

Smaller value means stricter requirement.

### Line 121
```python
self.confidence_scale = confidence_scale
```

Stores it.

Default:

```text
0.25
```

---

# Lines 122–136 — Switch lead time

### Lines 122–125

Comments explain the problem caused by hardware/receiver settling.

Suppose:

```text
predicted pulse = t=100
switch settling = 1 step
```

If scheduler switches exactly at t=100:

```text
t=100 → switching
t=100 → cannot capture
```

So scheduler should favor band earlier.

### Lines 126–135

These comments document an experimentally observed failure:

Without lead:

```text
scheduler jumps exactly when pulse arrives
```

which causes a fresh switch and settling loss.

The comment states that setting:

```text
switch_lead_steps = switch_cost_steps
```

addresses this.

### Line 136
```python
self.switch_lead_steps = switch_lead_steps
```

Stores lead time.

Default:

```text
0
```

because changing it would change previous results.

---

# Lines 137–150 — PRI state

### Line 137
```python
self.hit_times: List[List[int]] = [[] for _ in range(n_bands)]
```

Creates one hit-history list per band.

For 8 bands:

```text
band 0 → []
band 1 → []
...
band 7 → []
```

### Line 138
```python
self.pri_estimate: List[Optional[float]] = [None] * n_bands
```

Stores estimated PRI.

Initially:

```text
None
```

because nothing has been learned.

### Line 139
```python
self.jitter_estimate: List[float] = [1.0] * n_bands
```

Initial jitter estimate:

```text
1.0
```

for every band.

### Line 140
```python
self.confidence: List[float] = [0.0] * n_bands
```

Initially:

```text
confidence = 0
```

because no periodicity evidence exists.

### Lines 141–149

Comments explain `max_run_ever`.

This is a **persistent**, non-decreasing estimate.

If it ever observes:

```text
ON ON ON ON
```

then:

```text
max_run_ever = 4
```

It won't later fall to 2 simply because the sliding history changes.

### Line 150
```python
self.max_run_ever: List[int] = [1] * n_bands
```

Initial value for every band:

```text
1
```

because a single isolated hit has run length 1.

---

# Lines 152–155 — `_score_candidate`

### Line 152
```python
@staticmethod
```

This method doesn't require `self`.

### Line 153
```python
def _score_candidate(diffs, candidate, tol):
```

Takes:

- observed differences
- candidate PRI
- tolerance

### Line 154
```python
close = sum(1 for d in diffs if abs(d - max(1, round(d / candidate)) * candidate) <= tol)
```

Dense line. Break it apart.

For each observed difference `d`:

```python
round(d / candidate)
```

finds nearest integer number of candidate periods.

Then:

```python
... * candidate
```

reconstructs the nearest multiple of candidate.

Then:

```python
abs(d - nearest_multiple)
```

measures error.

If error ≤ tolerance:

```text
count as close
```

### Line 155
```python
return close / len(diffs)
```

Returns fraction of differences explained by candidate.

Example:

```text
80% of differences fit
→ score = 0.8
```

**Important:** this helper is defined here but the later `_update_pri_model()` does not ultimately use it for its final candidate selection. The code moved toward refined least-squares selection instead.

---

# Lines 157–188 — `_refine_pri`

This method is mathematically important.

### Line 157
```python
@staticmethod
```

Again, no `self` needed.

### Line 158
```python
def _refine_pri(times, seed_candidate):
```

Inputs:

- observed hit times
- rough PRI candidate

Returns:

```text
refined PRI
RMSE
```

---

### Lines 159–171 — Docstring

The method fits:

$$
t_i=a+b n_i
$$

where:

- `a` = starting phase/intercept
- `b` = estimated PRI
- `n_i` = cycle number

Why?

Because true PRI might not correspond to an integer number of simulation steps.

Example:

```text
true PRI = 32.5 steps
```

Observed integer timestep gaps may alternate:

```text
32, 33, 32, 33...
```

A simple integer estimator would struggle.

Least-squares fitting can recover:

```text
32.5
```

approximately.

---

### Line 173
```python
if len(times) < 4:
```

Requires at least four observations.

### Line 174
```python
return None, None
```

Insufficient data → cannot estimate.

### Line 175
```python
t0 = times[0]
```

Uses first hit as reference.

### Line 176
```python
ns = [round((t - t0) / seed_candidate) for t in times]
```

Assigns each hit to an estimated cycle index.

Example:

```text
times = [100, 132, 165, 197]
candidate = 32.5
```

Then approximately:

```text
n = [0, 1, 2, 3]
```

### Line 177
```python
if len(set(ns)) < 2:
```

Checks whether at least two different cycle indices exist.

### Line 178
```python
return None, None
```

If not, estimation impossible.

### Line 179
```python
n_mean = statistics.mean(ns)
```

Mean cycle index.

### Line 180
```python
t_mean = statistics.mean(times)
```

Mean observed time.

### Line 181
```python
den = sum((n - n_mean) ** 2 for n in ns)
```

Computes denominator of least-squares slope.

Mathematically:

$$
\sum(n_i-\bar n)^2
$$

### Line 182
```python
if den == 0:
```

Protects against division by zero.

### Line 183
```python
return None, None
```

No variation in cycle indices → cannot fit slope.

### Line 184
```python
b = sum((n - n_mean) * (t - t_mean) for n, t in zip(ns, times)) / den
```

Computes least-squares slope:

$$
b =
\frac{\sum(n_i-\bar n)(t_i-\bar t)}
{\sum(n_i-\bar n)^2}
$$

This `b` is the refined PRI.

### Line 185
```python
a = t_mean - b * n_mean
```

Computes intercept:

$$
a=\bar t-b\bar n
$$

### Line 186
```python
residuals = [t - (a + b * n) for n, t in zip(ns, times)]
```

For every observed point, calculates:

```text
actual time - predicted time
```

### Line 187
```python
rmse = (sum(r * r for r in residuals) / len(residuals)) ** 0.5
```

Computes root mean squared error:

$$
RMSE=
\sqrt{\frac{1}{N}\sum r_i^2}
$$

Smaller RMSE means better periodic fit.

### Line 188
```python
return b, rmse
```

Returns:

```text
(refined PRI, fitting error)
```

---

# Lines 190–220 — Beginning `_update_pri_model`

### Line 190
```python
def _update_pri_model(self, band):
```

Recalculates periodicity model for one band.

### Line 191
```python
times = self.hit_times[band]
```

Gets that band's hit history.

### Line 192
```python
if len(times) < 8:
```

Requires at least **8 hits** before attempting PRI learning.

### Line 193
```python
self.pri_estimate[band] = None
```

No PRI estimate yet.

### Line 194
```python
self.confidence[band] = 0.0
```

No confidence.

### Line 195
```python
return
```

Stop.

---

## Lines 196–204 — Pairwise differences

### Lines 196–203

The code explains why it uses **all pairwise time differences** rather than merely consecutive differences.

Suppose:

```text
hits = [0, 12, 24, 36]
```

Pairwise differences include:

```text
12
24
36
12
24
12
```

This provides more evidence.

### Line 204
```python
diffs = [times[j] - times[i] for i in range(len(times)) for j in range(i + 1, len(times))]
```

This creates every positive pairwise difference.

For:

```python
times = [10, 22, 34]
```

you get:

```text
22-10 = 12
34-10 = 24
34-22 = 12
```

Therefore:

```python
diffs = [12, 24, 12]
```

---

## Lines 206–220 — Preventing false periodicity

This is another important fix.

Imagine scheduler keeps scanning an always-on band:

```text
100, 101, 102, 103, 104, ...
```

Then differences contain:

```text
1,2,3,4,5,...
```

Almost any small candidate can appear to explain these differences.

That could falsely convince the scheduler:

> "This band is periodic."

### Line 215
```python
max_run = 1
```

Initial longest consecutive run.

### Line 216
```python
run = 1
```

Current consecutive run.

### Line 217
```python
sorted_times = sorted(times)
```

Sorts hit times.

### Line 218
```python
for a, b in zip(sorted_times[:-1], sorted_times[1:]):
```

Examines adjacent hit times.

Example:

```text
[100,101,102,105]
```

pairs:

```text
100→101
101→102
102→105
```

### Line 219
```python
run = run + 1 if b - a == 1 else 1
```

If hits are exactly one step apart:

```text
b-a == 1
```

extend current run.

Otherwise reset to:

```text
1
```

### Line 220
```python
max_run = max(max_run, run)
```

Keep largest consecutive run found.

---


# Lines 221–229 — Finish detecting long ON runs and build candidate pool

### Line 221
```python
self.max_run_ever[band] = max(self.max_run_ever[band], max_run)
```

Updates the persistent maximum ON-run length.

Suppose previously:

```text
max_run_ever[band] = 2
```

and this analysis discovers:

```text
max_run = 5
```

Then:

```text
max_run_ever = 5
```

If later `max_run = 3`, it stays:

```text
5
```

So this variable only increases.

---

### Line 222
```python
min_candidate = max(8, 2 * max_run)
```

Defines the smallest PRI candidate worth considering.

Two constraints:

```text
minimum = 8
```

and

```text
minimum = 2 × longest consecutive ON run
```

Whichever is larger wins.

Example:

```text
max_run = 1
→ min_candidate = max(8,2) = 8
```

If:

```text
max_run = 6
→ min_candidate = max(8,12) = 12
```

Why exclude very small periods?

Because consecutive/bursty activity can otherwise look like a fake periodic signal.

---

### Line 223
Blank line.

---

### Line 224
```python
candidate_pool = [d for d in diffs if d >= min_candidate]
```

Filters pairwise differences.

Only differences large enough to plausibly represent a meaningful period are retained.

Example:

```text
diffs = [1, 2, 12, 24, 36]
min_candidate = 8
```

becomes:

```text
[12, 24, 36]
```

---

### Line 225
```python
if not candidate_pool:
```

Checks whether filtering removed everything.

`not candidate_pool` means:

```text
candidate_pool == []
```

---

### Line 226
```python
self.pri_estimate[band] = None
```

No usable PRI estimate.

---

### Line 227
```python
self.confidence[band] = 0.0
```

Periodic confidence becomes zero.

---

### Line 228
```python
return
```

Exit `_update_pri_model()`.

---

### Line 229
Blank line.

---

# Lines 230–239 — Generate possible PRI candidates

### Line 230
```python
# Candidate periods to test, from two complementary methods:
```

Introduces candidate-generation strategy.

There are two main sources:

1. GCD
2. mode and its divisors

---

### Lines 231–235

The comments explain the first method.

### Line 231
```python
#  1) GCD of all diffs -- exact and immediate when diffs are
```

GCD = greatest common divisor.

Suppose:

```text
diffs = 12, 24, 36
```

Then:

```text
GCD = 12
```

Excellent if observations are exact integer multiples of true PRI.

---

### Line 232
```python
#     (near) noise-free integer multiples of the true period,
```

Works well when timing is clean.

---

### Line 233
```python
#     which a pure mode/frequency count can miss badly if the
```

Why mode alone can fail:

Suppose true PRI = 12.

Pairwise differences may look like:

```text
12, 24, 36, 48, 60...
```

But perhaps 24 occurs most often.

Then mode gives:

```text
24
```

instead of:

```text
12
```

---

### Line 234
```python
#     most common diff happens to be a large multiple (e.g. 168
```

Concrete example:

```text
true PRI = 12
mode difference = 168
```

Since:

$$
168 = 14\times12
$$

the mode alone doesn't necessarily identify fundamental PRI.

---

### Line 235
```python
#     instead of 12) rather than the period itself.
```

So GCD helps recover the fundamental period.

---

### Line 236
```python
#  2) The pairwise mode and its small-integer divisors -- more
```

Second strategy:

- find most common difference
- test its divisors

---

### Line 237
```python
#     robust when there's timing jitter, where an exact GCD
```

GCD becomes problematic with jitter.

Example:

```text
true PRI ≈ 32.5
```

Observed differences might be:

```text
32, 33, 65, 66...
```

GCD can collapse to:

```text
1
```

which is useless.

---

### Line 238
```python
#     would collapse to 1.
```

Exactly that problem.

---

### Line 239
```python
candidates = set()
```

Creates empty set for candidate PRI values.

Why a `set`?

To avoid duplicates.

---

# Lines 240–249 — GCD, mode and divisors

### Line 240
```python
g = reduce(math.gcd, diffs)
```

Computes GCD across all differences.

For:

```text
[12, 24, 36]
```

conceptually:

```text
gcd(gcd(12,24),36)
```

giving:

```text
12
```

`reduce()` repeatedly applies `math.gcd`.

---

### Line 241
```python
if g >= min_candidate:
```

Only accept GCD if it isn't suspiciously small.

---

### Line 242
```python
candidates.add(g)
```

Adds GCD to candidate set.

---

### Line 243
```python
mode_candidate, _freq = Counter(candidate_pool).most_common(1)[0]
```

Finds most common difference.

Breakdown:

```python
Counter(candidate_pool)
```

counts frequencies.

```python
.most_common(1)
```

asks for most common one.

Example:

```text
[12,12,24,12,36]
```

returns approximately:

```text
[(12,3)]
```

`[0]` extracts tuple:

```text
(12,3)
```

Then unpack:

```text
mode_candidate = 12
_freq = 3
```

The underscore indicates frequency isn't subsequently needed.

---

### Line 244
```python
candidates.add(mode_candidate)
```

Adds mode to candidates.

---

### Line 245
```python
for k in (2, 3, 4, 5, 6, 7, 8):
```

Tests divisors:

```text
2 through 8
```

---

### Line 246
```python
sub = round(mode_candidate / k)
```

Computes approximate submultiple.

If:

```text
mode = 24
k = 2
```

then:

```text
sub = 12
```

---

### Line 247
```python
if sub >= min_candidate:
```

Rejects too-small candidates.

---

### Line 248
```python
candidates.add(sub)
```

Adds valid submultiple.

---

### Line 249
Blank line.

---

# Lines 250–269 — The off-by-one candidate fix

This is one of the most interesting parts of V3.

### Line 250
```python
# Also test each candidate's immediate integer neighbors
```

If candidate is:

```text
33
```

also test:

```text
32
34
```

---

### Lines 251–264

The comments explain a real failure case.

The true PRI was:

```text
32.5
```

but mode produced:

```text
33
```

The problem isn't simply that 33 is "slightly inaccurate."

The candidate is used to calculate cycle indices:

```python
round((t - t0) / candidate)
```

Over many cycles, this error accumulates.

Eventually two actual observations can map to the same integer cycle number.

That's called a:

> **rounding collision**

This corrupts the least-squares fit.

The observed diagnostic:

```text
candidate 33 → relative error ≈ 0.229
candidate 34 → ≈ 0.255
candidate 32 → ≈ 0.029
```

So candidate 32 was dramatically better, but previous candidate-generation methods never produced it.

Therefore V3 explicitly tests ±1 neighbors.

---

### Line 265
```python
for c in list(candidates):
```

Iterates over a snapshot of candidates.

Why `list(candidates)`?

Because the code is going to **modify `candidates` while iterating**.

Directly doing:

```python
for c in candidates:
    candidates.add(...)
```

would cause:

```text
RuntimeError: Set changed size during iteration
```

Using `list(candidates)` avoids that.

---

### Line 266
```python
for neighbor in (c - 1, c + 1):
```

Generates immediate neighbors.

Example:

```text
c = 33
→ 32, 34
```

---

### Line 267
```python
if neighbor >= min_candidate:
```

Rejects neighbor if too small.

---

### Line 268
```python
candidates.add(neighbor)
```

Adds it.

---

### Line 269
Blank.

---

# Lines 270–281 — Refined candidate selection

### Line 270
```python
# Refine EVERY candidate via least-squares and pick whichever
```

This is crucial.

The code does **not** simply choose:

```text
GCD
```

or:

```text
mode
```

Instead every candidate gets refined.

---

### Lines 271–272
```python
# yields the best RELATIVE fit (rmse / refined_pri) -- not
# whichever scores best on the coarse tol=1 exact-multiple test.
```

The comparison metric is:

$$
\frac{RMSE}{PRI}
$$

not a crude exact-match count.

Why relative error?

Because RMSE = 2 means different things for:

```text
PRI = 10
```

versus:

```text
PRI = 100
```

Relative error normalizes it.

---

### Lines 273–281

These comments explain another failure mode.

A true PRI can be fractional:

```text
32.5
```

while simulation timestamps are integer.

GCD may become 1.

Also, a harmonic such as:

```text
65
```

may accidentally look better under a simple tolerance test.

Therefore V3 trusts the least-squares residual more.

---

### Line 282
```python
best_base, best_rmse, best_rel = None, None, None
```

Initializes best candidate state.

Three values:

```text
best_base → refined PRI
best_rmse → RMSE
best_rel  → relative RMSE
```

Initially no candidate has won.

---

### Line 283
```python
for c in candidates:
```

Examines every generated candidate.

---

### Line 284
```python
refined, rmse = self._refine_pri(sorted_times, c)
```

Runs the least-squares fitting method we just studied.

Returns:

```text
refined PRI
RMSE
```

---

### Line 285
```python
if refined is None or rmse is None or refined < min_candidate * 0.5:
```

Reject candidate if:

1. refinement failed
2. RMSE unavailable
3. refined PRI is implausibly small

The third condition allows a refined result below `min_candidate`, but not below half of it.

---

### Line 286
```python
continue
```

Skip rejected candidate.

---

### Line 287
```python
rel = rmse / refined
```

Calculate relative error:

$$
rel=\frac{RMSE}{PRI}
$$

---

### Line 288
```python
if best_rel is None or rel < best_rel:
```

If:

- no winner yet, OR
- this candidate is better,

replace winner.

---

### Line 289
```python
best_base, best_rmse, best_rel = refined, rmse, rel
```

Stores current candidate as best.

---

# Lines 291–300 — Validate final candidate

### Line 291
```python
if best_base is None:
```

No candidate survived.

---

### Line 292
```python
self.pri_estimate[band] = None
```

No PRI.

### Line 293
```python
self.confidence[band] = 0.0
```

No confidence.

### Line 294
```python
return
```

Exit.

---

### Line 295
```python
refined_pri, rmse = best_base, best_rmse
```

Rename best candidate values into meaningful names.

---

### Line 296
Blank.

---

### Line 297
```python
if refined_pri is None or refined_pri < min_candidate * 0.5 or rmse is None:
```

Second safety check.

Reject if:

- no PRI
- implausibly small PRI
- no RMSE

---

### Line 298
```python
self.pri_estimate[band] = None
```

Clear PRI.

### Line 299
```python
self.confidence[band] = 0.0
```

Clear confidence.

### Line 300
```python
return
```

Stop.

---

# Lines 302–314 — Confidence and jitter

### Line 302
```python
confidence = min(1.0, max(0.0, 1.0 - rmse / (self.confidence_scale * refined_pri)))
```

This is V3's periodicity-confidence formula.

First:

$$
\frac{RMSE}{confidence\_scale\times PRI}
$$

Then:

$$
1-\frac{RMSE}{confidence\_scale\times PRI}
$$

Finally clamp to:

```text
0 ≤ confidence ≤ 1
```

Using:

```python
max(0.0, ...)
```

prevents negative confidence.

Then:

```python
min(1.0, ...)
```

prevents confidence above 1.

With default:

```text
confidence_scale = 0.25
```

confidence is:

$$
C=\max\left(0,1-\frac{RMSE}{0.25PRI}\right)
$$

---

### Line 303
```python
if confidence >= self.min_confidence:
```

Default threshold:

```text
0.75
```

So periodic model must be sufficiently reliable.

---

### Line 304
```python
self.pri_estimate[band] = refined_pri
```

Stores learned PRI.

---

### Lines 305–309

These comments explain plateau handling.

A burst may last several steps.

If:

```text
PRI = 12
ON duration = 4
```

the periodic score must remain high across those four steps.

Otherwise scheduler may abandon the band immediately after first hit.

---

### Line 310
```python
self.jitter_estimate[band] = max(0.5, rmse, self.max_run_ever[band] / 2.0)
```

Sets effective jitter to the largest of:

```text
0.5
RMSE
max_run_ever / 2
```

Example:

```text
RMSE = 0.2
max_run_ever = 4
```

then:

```text
jitter = max(0.5, 0.2, 2)
      = 2
```

This widens the periodic Gaussian.

---

### Line 311
```python
self.confidence[band] = confidence
```

Stores confidence.

---

### Line 312
```python
else:
```

Confidence below threshold.

---

### Line 313
```python
self.pri_estimate[band] = None
```

Don't trust periodic estimate.

---

### Line 314
```python
self.confidence[band] = 0.0
```

Disable periodicity contribution.

---

# Lines 316–341 — `_periodicity_score()`

This converts learned PRI into a score for the current timestep.

### Line 316
```python
def _periodicity_score(self, band, t):
```

Arguments:

- band
- current time

Returns a number roughly:

```text
0 → unlikely periodic arrival
1 → exactly at predicted arrival
```

---

### Line 317
```python
pri = self.pri_estimate[band]
```

Retrieve learned PRI.

---

### Line 318
```python
if pri is None or self.confidence[band] <= 0 or not self.hit_times[band]:
```

Periodic score is impossible if:

- PRI not learned
- confidence zero
- no hit history

---

### Line 319
```python
return 0.0
```

No periodic evidence.

---

### Line 320
```python
last = self.hit_times[band][-1]
```

Gets most recent observed hit time.

`[-1]` means last element.

---

### Line 321
```python
phase = (t - last) % pri
```

Calculates current phase within PRI cycle.

Suppose:

```text
last hit = 100
PRI = 12
t = 111
```

then:

```text
phase = 11
```

At:

```text
t = 112
```

phase:

```text
0
```

meaning expected arrival.

---

### Line 322
```python
dist = min(phase, pri - phase)
```

Measures shortest circular distance to predicted pulse.

If:

```text
phase = 11
PRI = 12
```

then:

```text
min(11,1) = 1
```

So t=111 is one step away from expected pulse.

---

### Lines 323–338

These comments document an important **switch-lead bug and fix**.

Original approach:

```text
shift entire Gaussian forward
```

didn't work.

Why?

Suppose expected pulse:

```text
t = 100
```

and switch lead:

```text
1
```

Scheduler switches at:

```text
99
```

but after shifting peak, score can start declining by t=100.

That causes:

```text
99 → switch
100 → real pulse arrives
100 → periodic score already weaker
```

Scheduler may abandon the band exactly when needed.

The fix is instead to **flatten the distance around the predicted arrival window**.

---

### Line 339
```python
dist = max(0.0, dist - self.switch_lead_steps)
```

This is the actual fix.

If:

```text
dist = 1
lead = 1
```

then:

```text
dist = 0
```

Therefore maximum score.

So scheduler gets rewarded for staying around the whole lead-to-arrival window.

---

### Line 340
```python
sigma = self.jitter_estimate[band]
```

`σ` controls width of Gaussian.

Large sigma:

```text
wider prediction
```

Small sigma:

```text
narrow prediction
```

---

### Line 341
```python
return math.exp(-(dist ** 2) / (2 * sigma ** 2))
```

Gaussian score:

$$
e^{-\frac{d^2}{2\sigma^2}}
$$

At:

```text
dist = 0
```

score:

```text
1
```

As distance increases, score approaches zero.

---

# Lines 343–359 — Selecting bands

### Line 343
```python
def choose_bands(self, k):
```

V3's decision function.

Returns up to `k` bands.

---

### Line 344
```python
self.t += 1
```

Advances scheduler's internal time.

---

### Line 345
```python
if self.t <= self.warmup_steps:
```

If still in warmup.

---

### Line 346
```python
for b in range(self.n_bands):
```

Process every band.

### Line 347
```python
self._propagate(b)
```

Predict each band's Markov belief one step forward.

### Line 348
```python
return self._warmup_bands(k)
```

During warmup, don't use learned scheduling.

Use systematic warmup.

---

### Line 349
```python
for b in range(self.n_bands):
```

After warmup, propagate every band.

### Line 350
```python
self._propagate(b)
```

Markov prediction.

---

### Line 351
```python
scores = []
```

Creates empty score list.

---

### Line 352
```python
for b in range(self.n_bands):
```

Calculate score for every band.

---

### Line 353
```python
ucb_bonus = self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
```

V2 UCB exploration bonus.

$$
UCB_b =
c\sqrt{\frac{\ln(t+1)}{N_b+1}}
$$

where:

- `c` = exploration coefficient
- `t` = current time
- `N_b` = number of scans of band b

Less-scanned bands get larger bonus.

---

### Line 354
```python
conf = self.confidence[b]
```

Retrieve periodicity confidence.

---

### Line 355
```python
periodic = self._periodicity_score(b, self.t)
```

Calculate how close current time is to predicted periodic arrival.

---

### Line 356
```python
blended = (1 - conf) * self.belief[b] + conf * self.periodicity_weight * periodic
```

This is V3's central fusion equation:

$$
B_{\text{blend}}
=
(1-C)B
+
C(W_pP)
$$

where:

- $C$ = periodicity confidence
- $B$ = Markov belief
- $W_p$ = periodicity weight
- $P$ = periodicity score

Interpretation:

### Low confidence

If:

```text
conf = 0
```

then:

$$
blended = belief
$$

Pure V2 behavior.

### High confidence

If:

```text
conf ≈ 1
```

then:

$$
blended ≈ periodicity\_weight \times periodic
$$

Periodic model dominates.

---

### Line 357
```python
scores.append(self.priority[b] * blended + ucb_bonus)
```

Final score:

$$
Score_b =
Priority_b\times Blended_b+UCB_b
$$

So three forces compete:

```text
priority
   ×
(Markov + periodicity)
   +
exploration
```

---

### Line 358
```python
order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
```

Sort band indices from highest score to lowest.

`lambda b: scores[b]` tells Python what value to sort by.

`reverse=True` means descending.

---

### Line 359
```python
return order[:k]
```

Return top `k` bands.

For:

```text
scores:
band 0 = .2
band 1 = .9
band 2 = .5
```

then:

```text
order = [1,2,0]
```

and with `k=2`:

```text
[1,2]
```

---

# Lines 361–369 — Updating the scheduler

### Line 361
```python
def update(self, band, observed_on):
```

Called after scanning.

---

### Line 362
```python
super().update(band, observed_on)
```

First execute V2's update.

This updates:

- Markov transition statistics
- belief
- scan count

So V3 retains V2 learning.

---

### Line 363
```python
if observed_on:
```

Only a confirmed ON observation is useful as a pulse timestamp.

---

### Line 364
```python
times = self.hit_times[band]
```

Get that band's history.

---

### Line 365
```python
times.append(self.t)
```

Record current scheduler timestep as a confirmed hit.

Example:

```text
[100, 112, 124]
```

---

### Line 366
```python
if len(times) > self.history_len:
```

If history exceeds maximum size...

---

### Line 367
```python
del times[0]
```

Delete oldest hit.

This implements a sliding window.

---

### Line 368
```python
self._update_pri_model(band)
```

Immediately recompute PRI estimate.

So every new hit can improve the model.

---

### Line 369
Blank.

---

# Lines 371–397 — Normal comparison experiment

### Line 371
```python
def run_comparison():
```

Defines experiment for normal V1-style scenario.

---

### Line 372
```python
n_bands = 8
```

Eight frequency bands.

### Line 373
```python
n_steps = 4000
```

Run simulation for 4000 timesteps.

### Line 374
```python
scenario = make_scenario(n_bands)
```

Uses V1 scenario.

Important: this is **not** the sparse scenario yet.

---

### Lines 376–378

Print experiment description.

The scenario contains:

```text
2 Markov communication emitters
1 periodic beacon
1 agile threat
```

The beacon hops:

```text
2 → 5 → 6
```

with dwell 4.

Therefore its complete cycle is:

```text
2 for 4 steps
5 for 4 steps
6 for 4 steps
```

Total:

$$
4+4+4=12
$$

So true period = 12 steps.

---

### Line 380
```python
for k in (1, 2):
```

Test:

```text
k=1
k=2
```

meaning receiver can scan either one or two bands per timestep.

---

### Line 381
```python
random.seed(7)
```

Sets deterministic random seed.

---

### Line 382
```python
print(f"--- k_channels = {k} ---")
```

Prints current experiment configuration.

---

### Lines 383–387

Creates three schedulers:

### Line 384
```python
"RoundRobin (open-loop baseline)": RoundRobinScheduler(n_bands),
```

Simple fixed scanning.

### Line 385
```python
"BeliefUCB (Markov-only, learned)": BeliefUCBScheduler(n_bands, ucb_c=0.5),
```

V2 scheduler.

### Line 386
```python
"PRIAware (Markov + periodicity, learned)": PRIAwareScheduler(n_bands, ucb_c=0.5),
```

V3 scheduler.

### Line 387
```python
}
```

Ends dictionary.

---

### Lines 388–389
Builds table header:

```text
Scheduler
Interception %
Avg Reward/step
Avg Intercept Delay
```

### Line 390
```python
print(header)
```

Print header.

### Line 391
```python
print("-" * len(header))
```

Print matching separator.

---

### Line 392
```python
for name, sched in schedulers.items():
```

Run each scheduler.

---

### Line 393
```python
stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
```

Runs 4000-step simulation.

---

### Line 394
```python
r = stats.report()
```

Convert statistics into report dictionary.

---

### Lines 395–396

Format and print:

- interception percentage
- average reward
- average delay

---

### Line 397
```python
print()
```

Blank line between experiments.

---

# Lines 399–415 — PRI diagnostic

### Line 399
```python
# Diagnostic: did it actually learn the true beacon period?
```

Now the code tests whether V3 actually learned:

```text
PRI = 12
```

rather than merely achieving good metrics.

---

### Line 400
```python
random.seed(7)
```

Reset random generator.

### Line 401
```python
pri_sched = PRIAwareScheduler(n_bands, ucb_c=0.5)
```

Create V3 scheduler.

### Line 402
```python
run_episode(scenario, pri_sched, n_steps, n_bands, k_channels=1)
```

Run it.

---

### Line 403
```python
print("PRI diagnostic (true beacon period = 12 steps, on bands 2/5/6):")
```

Print expected truth.

---

### Line 404
```python
for b in (2, 5, 6):
```

Inspect beacon's three bands.

---

### Line 405
```python
pri, conf = pri_sched.pri_estimate[b], pri_sched.confidence[b]
```

Retrieve:

- estimated PRI
- confidence

---

### Line 406
```python
if pri is not None:
```

Was PRI learned?

---

### Line 407
```python
print(f"  band {b} (beacon):        estimated PRI = {pri:5.1f}  confidence = {conf:.2f}")
```

Print estimated PRI to one decimal place.

Example:

```text
estimated PRI = 12.0
confidence = 0.94
```

---

### Lines 408–409

If no estimate:

```text
not enough hits observed yet
```

---

### Line 410
```python
for b in (1, 4, 0, 3, 7):
```

Now inspect non-beacon bands:

```text
1,4 → comms
0,3,7 → agile
```

---

### Line 411
```python
pri, conf = pri_sched.pri_estimate[b], pri_sched.confidence[b]
```

Retrieve their periodicity models.

---

### Line 412
```python
if pri is not None:
```

Check whether they learned an apparent PRI.

---

### Line 413
```python
print(f"  band {b} (comm/agile):    estimated PRI = {pri:5.1f}  confidence = {conf:.2f}  (should stay low)")
```

Print diagnostic.

Desired outcome:

```text
confidence low
```

because Markov/agile emitters shouldn't exhibit stable periodicity.

---

### Lines 414–415

Otherwise:

```text
not enough hits observed yet
```

---

# Lines 418–425 — Sparse-radar experiment

### Line 418
```python
def run_sparse_comparison():
```

Defines second experiment.

This is designed specifically to demonstrate why PRI learning matters.

---

### Line 419
```python
n_bands = 8
```

Eight bands.

### Line 420
```python
n_steps = 4000
```

4000 timesteps.

### Line 421
```python
warmup = 800
```

Use first 800 steps as exploration/warmup.

### Lines 422–424

The comments explain why.

The sparse radar only generates one pulse every 12 steps.

Without systematic exploration, scheduler may not obtain enough observations to learn PRI.

This exposes an important ML/RL tradeoff:

```text
exploration
vs
exploitation
```

---

### Line 425
```python
scenario = make_sparse_scenario(n_bands)
```

Creates the sparse-radar scenario.

---

# Lines 427–430 — Print sparse experiment description

The description says:

```text
single pulse per cycle
band 5
true period 12
ON for exactly 1 step/cycle
```

This is intentionally much harder than the normal beacon.

---

# Lines 431–448 — Compare schedulers

### Line 431
```python
for k in (1, 2):
```

Test one-band and two-band scanning.

### Line 432
```python
random.seed(11)
```

Deterministic seed for this experiment.

### Line 433
```python
print(f"--- k_channels = {k} ---")
```

Print current configuration.

---

### Lines 434–438

Creates:

```text
RoundRobin
BeliefUCB
PRIAware
```

but now both learned schedulers receive:

```python
warmup_steps=warmup
```

So they have 800-step exploration period.

---

### Lines 439–442

Creates and prints same metrics table as before.

---

### Line 443
```python
for name, sched in schedulers.items():
```

Runs each scheduler.

### Line 444
```python
stats = run_episode(...)
```

Executes experiment.

### Line 445
```python
r = stats.report()
```

Generate metrics.

### Lines 446–447
Print results.

### Line 448
```python
print()
```

Blank separator.

---

# Lines 450–453 — Why aggregate interception is misleading

This is a very important experimental observation.

### Line 450
```python
print("The blended interception % above can be misleading here -- it's dominated by\n"
```

Overall interception percentage may look excellent.

Why?

Because one emitter can be very easy to catch.

---

### Lines 451–453

The code explains:

```text
comm-1 = loud, near-always-on
```

So a scheduler can spend its time catching comm-1 and obtain good aggregate statistics.

But the actual EW objective may be:

```text
catch difficult threat/radar
```

Therefore:

> Overall interception ≠ per-emitter effectiveness.

---

# Lines 455–475 — Per-emitter capture experiment

### Line 455
```python
def per_emitter_capture(sched_cls, warmup):
```

Defines helper experiment.

It compares capture specifically for:

- radar
- comm-1

---

### Line 456
```python
random.seed(11)
```

Reset deterministic randomness.

---

### Line 457
```python
sched = sched_cls(n_bands, ucb_c=0.5, warmup_steps=warmup)
```

Construct whichever scheduler class was supplied.

For example:

```text
BeliefUCBScheduler
```

or:

```text
PRIAwareScheduler
```

---

### Line 458
```python
env = scenario()
```

Create fresh sparse environment.

---

### Line 459
```python
radar_pulses = radar_caught = 0
```

Initialize radar counters.

---

### Line 460
```python
comm1_on = comm1_caught = 0
```

Initialize comm-1 counters.

---

### Line 461
```python
for t in range(n_steps):
```

Run through all 4000 timesteps.

---

### Line 462
```python
status = env.step()
```

Advance environment.

---

### Line 463
```python
bands = sched.choose_bands(1)
```

Choose exactly one band.

Notice this helper always uses:

```text
k=1
```

regardless of earlier `k` comparison.

---

### Line 464
```python
for b in bands:
```

Iterate selected band(s).

Since k=1, normally one iteration.

---

### Line 465
```python
sched.update(b, status[b])
```

Tell scheduler whether selected band was ON.

---

### Line 466
```python
if t > warmup:
```

Only evaluate capture after warmup.

This prevents the deliberate exploration phase from contaminating post-warmup capture statistics.

---

### Line 467
```python
if status[5]:
```

Was radar active?

Radar is fixed on:

```text
band 5
```

---

### Line 468
```python
radar_pulses += 1
```

Count that radar pulse.

---

### Line 469
```python
if 5 in bands:
```

Did scheduler scan band 5?

---

### Line 470
```python
radar_caught += 1
```

If yes, count successful capture.

---

### Line 471
```python
if status[1]:
```

Was comm-1 active?

---

### Line 472
```python
comm1_on += 1
```

Count active comm-1 timestep.

---

### Line 473
```python
if 1 in bands:
```

Did scheduler scan band 1?

---

### Line 474
```python
comm1_caught += 1
```

Count successful capture.

---

### Line 475
```python
return radar_pulses, radar_caught, comm1_on, comm1_caught, sched
```

Returns five things:

```text
radar pulses
radar caught
comm-1 active
comm-1 caught
scheduler
```

The scheduler is returned so the caller can inspect learned PRI/confidence.

---

# Lines 477–483 — Compare per-emitter results

### Line 477
```python
for name, cls in [("BeliefUCB", BeliefUCBScheduler), ("PRIAware", PRIAwareScheduler)]:
```

Compare only the two learned schedulers.

---

### Line 478
```python
rp, rc, cp, cc, sched = per_emitter_capture(cls, warmup)
```

Run experiment and unpack results:

```text
rp = radar pulses
rc = radar caught
cp = comm-1 active
cc = comm-1 caught
sched = scheduler
```

---

### Line 479
```python
pri = getattr(sched, "pri_estimate", [None] * n_bands)[5]
```

Gets scheduler's `pri_estimate`.

`getattr()` safely handles schedulers that don't have that attribute.

For `BeliefUCB`, it doesn't.

So fallback is:

```python
[None] * n_bands
```

Then `[5]` accesses band 5.

---

### Line 480
```python
conf = getattr(sched, "confidence", [0.0] * n_bands)[5]
```

Same idea for confidence.

BeliefUCB gets:

```text
confidence = 0
```

PRIAware gets actual learned confidence.

---

### Lines 481–483

Print:

```text
radar caught / radar pulses
comm-1 caught / comm-1 active
estimated radar PRI
confidence
```

For example conceptually:

```text
PRIAware:
radar caught 250/300 = 83.3%
comm-1 caught 900/1000 = 90.0%
PRI ≈ 12
confidence ≈ .95
```

This is much more informative than one aggregate interception number.

---

# Lines 486–489 — Program entry point

### Line 486
```python
if __name__ == "__main__":
```

Standard Python entry-point check.

It means:

> Execute following code only when this file is run directly.

If imported by another module:

```python
import scan_scheduler_v3_pri
```

these functions are defined, but the experiments don't automatically execute.

---

### Line 487
```python
run_comparison()
```

Run normal beacon comparison first.

---

### Line 488
```python
print("=" * 100)
```

Print 100 `=` characters as visual separator.

---

### Line 489
```python
run_sparse_comparison()
```

Then run sparse radar experiment.

---

# V3 architecture — put everything together

By the end of this file, scheduler has become:

```text
                  ┌──────────────────────┐
                  │   Environment        │
                  │ emitters / RF truth  │
                  └──────────┬───────────┘
                             │
                             ▼
                    observed ON / OFF
                             │
                             ▼
              ┌──────────────────────────┐
              │   PRIAwareScheduler      │
              └────────────┬─────────────┘
                           │
             ┌─────────────┼──────────────┐
             ▼             ▼              ▼
        Markov belief     UCB        PRI predictor
             │             │              │
             │             │        hit history
             │             │              │
             │             │        PRI estimate
             │             │              │
             │             │        confidence
             │             │              │
             └─────────────┼──────────────┘
                           ▼
                    blended score
                           │
                           ▼
                    priority × score
                           +
                        UCB bonus
                           │
                           ▼
                     top-k bands
```

The key equation is:

$$
\boxed{
Score_b =
Priority_b
\left[
(1-C_b)B_b+
C_bW_pP_b
\right]
+
c\sqrt{\frac{\ln(t+1)}{N_b+1}}
}
$$

where:

- $B_b$ = Markov belief
- $P_b$ = periodicity score
- $C_b$ = confidence in periodicity
- $W_p$ = periodicity weight
- $N_b$ = number of scans
- $c$ = UCB exploration coefficient

### The conceptual progression is now:

```text
V1
Markov belief
      ↓
V2
Markov belief + UCB + multi-channel + warmup + switch cost
      ↓
V3
Markov belief + UCB
        +
PRI estimation
        +
periodic phase prediction
        +
confidence-weighted blending
        +
plateau handling
        +
off-by-one candidate recovery
        +
switch-lead handling
```

**Next file in our planned order: `scan_scheduler_v4_persistent.py` (149 lines).** It takes V3's ideas further by adding **persistent tracking / state across scans**, so that is the next one to dissect line-by-line.

# `scan_scheduler_v4_persistent.py` — line-by-line

V4 is much shorter: **149 lines**.

Its entire purpose is to fix a specific V3 failure:

> A sparse radar may fail to produce 8 confirmed hits during warmup purely because of random sampling. Once warmup ends, V3 may effectively stop looking at that band, so the radar becomes permanently invisible.

V4 adds a **persistent characterization bonus**.

---

## Lines 1–61 — Module documentation

### Line 1
```python
"""
```
Starts module-level documentation.

### Line 2
```python
scan_scheduler_v4_persistent.py
```
Module name.

### Line 3
```python
=================================
```
Documentation separator.

---

### Line 4
```text
Fixes the seed-sensitive lock-on bug diagnosed in diagnose_pri_lockon.py:
```

This tells us V4 is not introducing an unrelated feature.

It is specifically a **bug fix** based on an earlier diagnostic script.

---

### Lines 6–10

The first problem is described:

```text
PRIAwareScheduler requires >= 8 confirmed hits
```

before attempting PRI estimation.

Why?

Because V3 contains:

```python
if len(times) < 8:
    ...
    return
```

So it needs at least 8 observed ON events.

For a sparse radar with:

```text
PRI = 12
```

there are approximately:

$$
800/12 \approx 66.7
$$

possible radar pulse times during an 800-step interval.

But the scheduler only scans band 5 some fraction of the time.

The documentation says the warmup sweep gives roughly:

```text
100 warmup scans / 12 ≈ 8.3 expected hits
```

So expected hits sit almost exactly at the threshold:

```text
8 hits
```

That means random variation matters enormously.

---

### Lines 11–17 — Why seed changes outcome

The key chain:

```text
random sampling
       ↓
maybe 6 hits
       ↓
fails 8-hit threshold
       ↓
no PRI model
       ↓
low belief because radar OFF most of time
       ↓
little/no future scanning
       ↓
never reaches 8 hits
```

This creates a feedback loop.

A seed that gets enough hits:

```text
6 → 7 → 8
```

can learn PRI.

A seed that gets:

```text
5 → warmup ends
```

may never get another opportunity.

The documentation reports:

```text
30.0% ± 48.3% capture across 10 seeds
```

That huge standard deviation is evidence of unstable behavior.

---

# The V4 fix

### Lines 19–25

The fix is to maintain:

```python
total_hits
```

separately from:

```python
hit_times
```

This distinction matters.

V3's `hit_times` is a **sliding window**.

If:

```text
history_len = 30
```

then old hit timestamps are deleted.

But `total_hits` never forgets.

So:

```text
hit_times
```

answers:

> "Which recent hits should I use for PRI estimation?"

while:

```text
total_hits
```

answers:

> "How many confirmed ON samples have I ever collected?"

---

### Lines 27–33 — Characterization bonus

The new bonus is:

$$
\boxed{
char\_bonus(b)
=
c\sqrt{
\frac{\log(t+2)}
{total\_hits[b]+1}
}
}
$$

This is deliberately based on **hit count**, not scan count.

That's the key idea.

Suppose band 5 has:

```text
scan_count = 100
total_hits = 6
```

V2's UCB sees:

```text
100 scans
```

and thinks:

> "Already explored."

V4 sees:

```text
only 6 useful ON samples
```

and thinks:

> "Still needs characterization."

---

# Lines 35–58 — Why two bounds are required

The developers discovered that adding only the hit-count bonus wasn't enough.

Two separate safeguards are needed.

---

## Bound 1 — `total_hits < required_hits`

### Lines 38–45

The bonus only applies while:

```python
total_hits < required_hits
```

not while:

```python
confidence < threshold
```

Why?

Suppose an emitter is genuinely aperiodic.

For example, the agile threat is spread across:

```text
0, 3, 6, 7
```

It may never accumulate enough hits on any single band to establish periodicity.

If the scheduler said:

```text
if confidence < .75:
    keep investigating
```

then an aperiodic band could receive investigation forever.

That causes:

```text
aperiodic band
      ↓
confidence never reaches .75
      ↓
bonus never disappears
      ↓
scheduler keeps chasing it
      ↓
other emitters lose scan budget
```

The documentation reports that this reduced comm-1 capture from roughly:

```text
85% → 21%
```

So confidence alone is a bad stopping condition.

---

# Bound 2 — `give_up_after_scans`

### Lines 47–58

Now imagine a completely silent band.

For example:

```text
band 2
no emitter
```

Then:

```text
total_hits = 0
```

forever.

The characterization bonus:

$$
\sqrt{\frac{\log(t+2)}{0+1}}
$$

doesn't shrink enough.

So the scheduler could repeatedly say:

> "Maybe this band will eventually reveal something."

and waste nearly all its scan budget.

The reported failure:

```text
3300 / 4000 scans
```

went to one always-silent band.

Therefore V4 adds:

```python
give_up_after_scans
```

Once a band has been scanned sufficiently many times without enough confirmed hits, its characterization bonus disappears.

---

# Lines 63–66 — Imports

### Line 63
```python
import math
```

Needed for:

```python
math.sqrt()
math.log()
```

### Line 64
```python
from typing import List
```

Used for the type annotation:

```python
List[int]
```

### Line 65
Blank.

### Line 66
```python
from scan_scheduler_v3_pri import PRIAwareScheduler
```

V4 inherits from V3.

So:

```text
V1 → V2 → V3 → V4
```

V4 therefore gets all of V3's functionality:

- Markov model
- UCB
- multi-band selection
- warmup
- PRI estimation
- periodicity confidence
- phase prediction
- plateau handling
- switch-lead handling

and adds persistent characterization.

---

# Lines 69–93 — `PersistentPRIAwareScheduler`

### Line 69
```python
class PersistentPRIAwareScheduler(PRIAwareScheduler):
```

Defines V4 scheduler.

Inheritance:

```text
PersistentPRIAwareScheduler
            ↑
      PRIAwareScheduler
            ↑
      BeliefUCBScheduler
            ↑
         Scheduler
```

---

## Constructor

### Line 70
```python
def __init__(self, n_bands, char_bonus_c: float = 1.5,
```

Constructor starts.

New parameter:

```text
char_bonus_c = 1.5
```

controls strength of characterization bonus.

---

### Line 71
```python
required_hits: int = 8, give_up_after_scans: int = 300,
```

Two new parameters.

Default:

```text
required_hits = 8
```

matching V3's internal PRI-learning threshold.

And:

```text
give_up_after_scans = 300
```

means don't spend unlimited scans trying to characterize one band.

---

### Line 72
```python
**kwargs):
```

Collects all additional keyword arguments.

For example:

```python
PersistentPRIAwareScheduler(
    8,
    ucb_c=0.5,
    warmup_steps=800
)
```

The constructor receives:

```text
n_bands = 8
char_bonus_c = default
required_hits = default
give_up_after_scans = default
kwargs = {
    ucb_c: 0.5,
    warmup_steps: 800
}
```

Then forwards those to V3.

---

### Line 73
```python
super().__init__(n_bands, **kwargs)
```

Calls V3's constructor.

Therefore all V3 internal state gets initialized first.

---

### Line 74
```python
self.char_bonus_c = char_bonus_c
```

Stores characterization bonus coefficient.

---

### Lines 75–78

The comments emphasize:

```text
required_hits must match V3's threshold.
```

V3 won't attempt PRI estimation before 8 hits.

Therefore V4's bonus exists specifically to help reach those 8 samples.

### Line 78
```python
self.required_hits = required_hits
```

Stores threshold.

---

### Lines 79–87

Comments explain `give_up_after_scans`.

Without this limit, a low-duty-cycle or silent band can remain attractive forever.

### Line 87
```python
self.give_up_after_scans = give_up_after_scans
```

Stores the scan limit.

---

### Lines 88–92

Comments explain `total_hits`.

Important distinction:

```text
hit_times
```

is capped by `history_len`.

For example:

```text
history_len = 30
```

means only 30 timestamps remain.

But:

```text
total_hits
```

never decreases.

Thus:

```text
total_hits = lifetime evidence
hit_times  = recent evidence
```

---

### Line 93
```python
self.total_hits: List[int] = [0] * n_bands
```

Creates one lifetime hit counter per band.

For 8 bands:

```text
[0,0,0,0,0,0,0,0]
```

---

# Lines 95–98 — Updating lifetime hits

### Line 95
```python
def update(self, band, observed_on):
```

V4 overrides V3's `update()`.

---

### Line 96
```python
super().update(band, observed_on)
```

First execute V3's update.

That means V3 still handles:

- Markov transition learning
- belief update
- scan count
- hit timestamp recording
- PRI estimation

---

### Line 97
```python
if observed_on:
```

Only count confirmed ON observations.

---

### Line 98
```python
self.total_hits[band] += 1
```

Increment lifetime hit count.

Example:

```text
before:
total_hits[5] = 6

confirmed ON:

after:
total_hits[5] = 7
```

Once it reaches:

```text
8
```

the characterization bonus shuts off.

---

# Lines 100–123 — V4's decision algorithm

This is the most important section.

### Line 100
```python
def choose_bands(self, k):
```

Selects up to `k` bands.

---

### Line 101
```python
self.t += 1
```

Advance scheduler time.

Same concept as V3.

---

# Warmup

### Line 102
```python
if self.t <= self.warmup_steps:
```

Check whether still inside warmup period.

---

### Line 103
```python
for b in range(self.n_bands):
```

Loop over every band.

### Line 104
```python
self._propagate(b)
```

Advance Markov belief for each band.

---

### Line 105
```python
return self._warmup_bands(k)
```

During warmup, use V2's systematic warmup mechanism.

No characterization bonus is needed here because warmup itself is designed to explore.

---

# Post-warmup

### Line 106
```python
for b in range(self.n_bands):
```

After warmup, iterate over every band.

### Line 107
```python
self._propagate(b)
```

Perform Markov prediction.

---

### Line 108
```python
scores = []
```

Create list for band scores.

---

### Line 109
```python
for b in range(self.n_bands):
```

Calculate score independently for every band.

---

# Existing UCB component

### Line 110
```python
ucb_bonus = self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
```

Same UCB term from V2/V3:

$$
UCB_b =
c\sqrt{
\frac{\ln(t+1)}
{N_b+1}
}
$$

where:

- $c$ = `ucb_c`
- $N_b$ = `scan_count[b]`

A band scanned fewer times gets larger UCB bonus.

---

### Line 111
```python
conf = self.confidence[b]
```

Retrieve V3 periodicity confidence.

---

### Line 112
```python
periodic = self._periodicity_score(b, self.t)
```

Calculate how strongly current time matches expected periodic activity.

---

### Line 113
```python
blended = (1 - conf) * self.belief[b] + conf * self.periodicity_weight * periodic
```

Same V3 fusion.

$$
Blended_b =
(1-C_b)B_b+C_bW_pP_b
$$

So V4 does **not** change V3's periodicity mechanism.

It changes only the exploration/characterization side.

---

# Lines 115–120 — NEW characterization bonus

### Line 115
```python
char_bonus = 0.0
```

Default: no additional bonus.

---

### Lines 116–117
```python
if (self.total_hits[b] < self.required_hits
        and self.scan_count[b] < self.give_up_after_scans):
```

Two conditions must both hold.

### Condition 1

```text
total_hits < required_hits
```

Means:

> "We don't yet have enough confirmed ON evidence to characterize this band."

### Condition 2

```text
scan_count < give_up_after_scans
```

Means:

> "We haven't already tried this band too many times."

Therefore:

```text
                 enough hits?
                    │
             yes ───┴─── no
                         │
                  scans exhausted?
                    │
               yes ──┴── no
                         │
                  bonus applies
```

---

### Lines 118–119
```python
char_bonus = self.char_bonus_c * math.sqrt(
    math.log(self.t + 2) / (self.total_hits[b] + 1))
```

The actual new formula:

$$
\boxed{
CBonus_b=
c_{char}
\sqrt{
\frac{\ln(t+2)}
{H_b+1}
}
}
$$

where:

- $H_b$ = lifetime confirmed hits
- $c_{char}$ = characterization coefficient

Notice denominator uses:

```python
self.total_hits[b]
```

NOT:

```python
self.scan_count[b]
```

That distinction is the entire reason V4 exists.

---

## Why this works

Suppose two bands have:

```text
Band A:
scanned = 100
hits = 2

Band B:
scanned = 100
hits = 20
```

V2's UCB sees both equally:

```text
scan_count = 100
```

V4 sees:

```text
Band A → only 2 useful samples
Band B → already 20 useful samples
```

Therefore:

```text
Band A → high characterization bonus
Band B → no characterization bonus
```

until Band A reaches the required hit count.

---

### Line 120
```python
)
```

Closes the `math.sqrt()` expression.

---

# Line 121 — Final V4 score

```python
scores.append(self.priority[b] * blended + ucb_bonus + char_bonus)
```

This is V4's complete scoring equation:

$$
\boxed{
Score_b =
Priority_b \times Blended_b
+
UCB_b
+
CharacterizationBonus_b
}
$$

Compare to V3:

$$
Score_b =
Priority_b \times Blended_b
+
UCB_b
$$

V4 simply adds:

$$
+CharacterizationBonus_b
$$

---

### Line 122
```python
order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
```

Sort bands by score, highest first.

---

### Line 123
```python
return order[:k]
```

Return top `k`.

Done.

---

# Lines 126–149 — Test harness

Now the file stops defining the scheduler and runs a quick experiment when executed directly.

---

### Line 126
```python
if __name__ == "__main__":
```

Only execute test code when running this file directly.

---

### Line 127
```python
import random
```

Imports random only for the test harness.

---

### Line 128
```python
from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
```

Imports:

- V2 baseline scheduler
- simulation function

---

### Line 129
```python
from scan_scheduler_v3_pri import make_sparse_scenario
```

Imports the sparse radar environment from V3.

So test compares:

```text
V2
vs
V3
vs
V4
```

under exactly the sparse-radar problem V4 was designed to fix.

---

### Line 131
```python
n_bands = 8
```

Eight frequency bands.

### Line 132
```python
n_steps = 4000
```

4000 simulation steps.

### Line 133
```python
warmup = 800
```

First 800 steps are warmup.

### Line 134
```python
scenario = make_sparse_scenario(n_bands)
```

Create sparse fixed-PRI radar scenario.

Radar:

```text
band = 5
PRI = 12
```

---

### Line 135
```python
random.seed(11)
```

Set deterministic seed.

This allows comparison with earlier reports.

---

### Line 136
```python
print("Quick single-seed sanity check (seed=11, matches earlier reports):\n")
```

Print experiment description.

---

# Lines 137–141 — Three schedulers

### Line 137
```python
schedulers = {
```

Create dictionary.

---

### Line 138
```python
"BeliefUCB (Markov-only)": BeliefUCBScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
```

V2 baseline.

It knows:

```text
Markov belief
+
UCB
```

but not PRI.

---

### Line 139
```python
"PRIAware (original)": PRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
```

V3.

It adds:

```text
PRI learning
+
periodic prediction
```

but has the seed-sensitive lock-on problem.

---

### Line 140
```python
"PRIAware (persistent, fixed)": PersistentPRIAwareScheduler(n_bands, ucb_c=0.5, warmup_steps=warmup),
```

V4.

Adds:

```text
persistent total-hit tracking
+
characterization bonus
+
scan cap
```

---

### Line 141
```python
}
```

Ends dictionary.

---

# Lines 142–144 — Results table

### Line 142
```python
header = (f"{'Scheduler':32s} | {'Interception %':>15s} | {'Avg Reward/step':>16s}")
```

Builds formatted table header.

`32s` means reserve 32 characters for scheduler name.

`>15s` means right-align within 15 characters.

---

### Line 143
```python
print(header)
```

Print header.

---

### Line 144
```python
print("-" * len(header))
```

Print separator of matching length.

---

# Lines 145–149 — Run each scheduler

### Line 145
```python
for name, sched in schedulers.items():
```

Loop through all three schedulers.

---

### Line 146
```python
random.seed(11)
```

**Important experimental detail.**

The seed is reset before every scheduler.

That makes the random environment sequence start from the same seed for each scheduler, improving fairness compared with V1/V2's original setup.

However, because scheduler behavior itself can consume random numbers—especially warmup shuffling—the exact subsequent RNG state can still depend on scheduler behavior. So this is better controlled, but not necessarily a mathematically identical environment trajectory in every implementation detail.

---

### Line 147
```python
stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=1)
```

Run 4000-step simulation.

Receiver scans:

```text
1 band/timestep
```

---

### Line 148
```python
r = stats.report()
```

Generate summary metrics.

---

### Line 149
```python
print(f"{name:32s} | {r['interception_ratio']*100:14.1f}% | {r['avg_reward_per_step']:16.3f}")
```

Print:

1. scheduler name
2. interception percentage
3. average reward per step

`interception_ratio` is converted:

```text
0.42 → 42.0%
```

---

# V4 in one picture

The evolution is now:

```text
V1
│
├── Markov belief
│
▼
V2
│
├── Markov belief
├── UCB exploration
├── multi-channel scanning
├── warmup
└── switch-cost handling
│
▼
V3
│
├── everything in V2
├── PRI history
├── PRI estimation
├── phase prediction
├── periodicity confidence
├── plateau handling
├── off-by-one candidate testing
└── switch-lead handling
│
▼
V4
│
├── everything in V3
├── lifetime total_hits
├── hit-count-based characterization bonus
└── give_up_after_scans safety cap
```

The critical V4 feedback loop becomes:

```text
              scan band
                  │
                  ▼
             ON observed?
              /        \
            NO          YES
            │            │
            │       total_hits++
            │            │
            └──────┬─────┘
                   ▼
          enough hits yet?
             /          \
           NO            YES
           │              │
     characterization    normal
         bonus           scoring
           │
           ▼
    eventually reach
       8 hits
           │
           ▼
      PRI estimator
       activates
           │
           ▼
    periodic prediction
```

And the second safety mechanism prevents:

```text
silent band
    ↓
0 hits forever
    ↓
bonus stays high forever
    ↓
infinite wasted scanning
```

by imposing:

```text
scan_count >= 300
        ↓
give up characterization
```

So **V4's central idea is not "make PRI prediction better."**

V3 already has PRI prediction.

V4's idea is:

> **Make sure scheduler gets enough useful observations to reach V3's PRI-learning threshold, while preventing that characterization effort from becoming infinite.**

---

**`pdw_loader.py` — 94 lines**

This changes direction slightly. Instead of synthetic emitters, it introduces **PDW (Pulse Descriptor Word) data loading**, which is important because it connects the scheduler to actual/structured pulse data rather than only simulated emitters.

# `pdw_loader.py` — line-by-line

This file is **94 lines**. Unlike V1–V4, it isn't primarily a scheduler. It provides the bridge between **PDW data** and the rest of the pipeline.

PDW = **Pulse Descriptor Word**: one record describing one received pulse.

---

## Lines 1–28 — Module documentation

### Line 1
```python
"""
```
Starts module-level documentation.

### Line 2
```python
pdw_loader.py
```
Module name.

### Line 3
```text
=============
```
Visual separator.

### Lines 4–6
```text
Loads Pulse Descriptor Word (PDW) streams in the schema used by the Alan
Turing Institute's Turing Synthetic Radar Dataset (TSRD) / Turing
Deinterleaving Challenge:
```

States purpose: load pulse data using the schema associated with the Turing Synthetic Radar Dataset / deinterleaving challenge.

The important idea is that instead of generating:

```text
band 0 ON/OFF
band 1 ON/OFF
...
```

The processing now operates on **individual pulses**.

---

### Lines 8–10 — PDW fields

The expected fields are:

```text
ToA          Time of Arrival
CF           Centre Frequency
PW           Pulse Width
AoA          Angle of Arrival
Amplitude    Signal amplitude
label        Ground-truth emitter identity
```

Units:

```text
ToA → microseconds
CF  → MHz
PW  → microseconds
AoA → degrees
Amplitude → dB
```

For example, one pulse could conceptually be:

```text
ToA = 125000 μs
CF  = 9200 MHz
PW  = 1.2 μs
AoA = 140°
Amp = -55 dB
label = 1
```

---

# Lines 12–15 — Real-data limitation

### Line 12
```python
IMPORTANT — about real vs. synthetic data here:
```

This warns that the file contains **two different data paths**.

### Lines 13–15

The comments state that this environment cannot directly download the TSRD because:

1. the required external host isn't accessible here;
2. the dataset is gated;
3. a Hugging Face token/license is required.

So the code's real-data loader is written for execution on the user's own machine.

This distinction matters:

```text
real TSRD
     ≠
synthetic stream generated below
```

---

# Lines 17–21 — Real loader requirements

### Line 17
```text
`load_real_pulse_train()` below is written against the TSRD's own
```

Introduces the first actual function.

### Line 18
```text
published API (`turing_deinterleaving_challenge.PulseTrain.load`)
```

The expected API is:

```python
PulseTrain.load(...)
```

### Line 19
```text
and will work as-is on the target machine once local setup is complete:
```

The function requires local setup.

### Line 20
```text
pip install git+https://github.com/alan-turing-institute/turing-deinterleaving-challenge.git
```

Install the required Python package directly from its Git repository.

### Line 21
```text
(and downloaded a .h5 pulse train per that repo's instructions)
```

Also requires a local HDF5 pulse-train file.

---

# Lines 23–27 — Synthetic replacement

### Line 23
```text
`generate_synthetic_pdw_stream()` is a local stand-in that mimics the
```

This second function generates fake PDW data locally.

It isn't the actual dataset.

### Lines 24–27

The synthetic data deliberately contains:

```text
fixed-frequency emitters
+
constant/approximately constant PRI
+
frequency-agile emitters
+
interleaving
```

This lets the rest of the pipeline be developed before real data is available.

The intended architecture is:

```text
synthetic generator
        │
        ▼
same PDW schema
        │
        ▼
binning / scheduling / metrics
        │
        ▼
later swap synthetic generator
for real-data loader
```

That's a useful design choice because downstream code doesn't need to care where PDWs came from.

---

# Line 28

```python
"""
```

Ends module documentation.

---

# Line 30 — NumPy

```python
import numpy as np
```

Imports NumPy under conventional alias `np`.

This file uses NumPy for:

- random number generation
- structured arrays
- numerical values

---

# Lines 33–46 — `load_real_pulse_train()`

This is the real-data loader.

### Line 33
```python
def load_real_pulse_train(h5_path: str):
```

Defines function.

Input:

```text
h5_path
```

is expected to be a string containing path to `.h5` file.

Example:

```python
load_real_pulse_train("train_001.h5")
```

---

### Lines 34–40 — Function docstring

The docstring says this loads a real TSRD pulse train.

It also explicitly documents expected errors:

```text
ImportError
```

if package isn't installed.

And:

```text
FileNotFoundError
```

if file path doesn't exist.

This is useful because the function doesn't catch those errors itself; Python/package code will raise them naturally.

---

### Line 41
```python
from turing_deinterleaving_challenge import PulseTrain  # may raise ImportError
```

Imports `PulseTrain`.

Notice the import is **inside the function**, rather than at top of file.

Why?

Because this lets the rest of `pdw_loader.py` work without having the external TSRD package installed.

If it were at line 30:

```python
from turing_deinterleaving_challenge import PulseTrain
```

then even the synthetic generator would fail to import.

By putting it inside the function:

```text
import pdw_loader
      ↓
works
```

and only:

```text
load_real_pulse_train(...)
      ↓
requires external package
```

That's good dependency isolation.

---

### Line 42
```python
pt = PulseTrain.load(h5_path)
```

Calls the package's loader.

The returned object is stored as:

```text
pt
```

Think of `pt` as:

```text
PulseTrain object
├── data
├── labels
└── metadata
```

---

### Line 43
```python
pdw = pt.data          # PDW stream: ToA, CF, PW, AoA, Amplitude
```

Extracts pulse data.

`pdw` contains the actual pulse descriptors.

The comment indicates the five physical fields:

```text
ToA
CF
PW
AoA
Amplitude
```

---

### Line 44
```python
labels = pt.labels     # arbitrary per-file emitter labels (ground truth)
```

Extracts ground-truth emitter labels.

This is extremely useful for evaluating a deinterleaving algorithm.

For example:

```text
Pulse 1 → label 3
Pulse 2 → label 1
Pulse 3 → label 3
Pulse 4 → label 2
```

The scheduler/deinterleaver attempts to infer grouping; labels tell us whether it was correct.

---

### Line 45
```python
meta = pt.metadata     # scan/stare mode, receiver config, etc.
```

Extracts metadata.

This may describe things such as:

- receiver configuration
- scan/stare mode
- other dataset-level information

---

### Line 46
```python
return pdw, labels, meta
```

Returns a 3-tuple:

```text
(
    pulse data,
    ground truth labels,
    metadata
)
```

Caller can write:

```python
pdw, labels, meta = load_real_pulse_train(path)
```

---

# Lines 49–60 — Synthetic PDW generator

### Line 49
```python
def generate_synthetic_pdw_stream(duration_us: float = 2_000_000, seed: int = 0):
```

Defines synthetic-data generator.

Two parameters:

### `duration_us`

Default:

```text
2,000,000 μs
```

which equals:

$$
2\text{ seconds}
$$

because:

$$
1,000,000\ \mu s=1s
$$

### `seed`

Default:

```text
0
```

controls reproducibility.

---

### Lines 50–60 — Docstring

The function returns a synthetic stream with fields:

```text
toa
cf
pw
aoa
amp
label
```

and says data are sorted by ToA.

It also describes two emitter families:

```text
fixed-frequency constant-PRI
frequency-agile
```

This mirrors the intended mix of radar behaviors.

---

# Lines 61–64 — Random generator and storage

### Line 61
```python
rng = np.random.default_rng(seed)
```

Creates NumPy's modern random-number generator.

This is better than relying on global random state.

With:

```python
seed=0
```

the generated sequence is reproducible.

---

### Line 62
```python
pulses = []
```

Creates empty Python list.

Every generated pulse will eventually become one tuple in this list.

---

### Line 63
```python
emitter_id = 0
```

Starts ground-truth emitter labels at 0.

---

### Line 64
Blank.

---

# Lines 65–76 — Fixed-frequency emitters

### Line 65
```python
# Fixed-frequency, roughly-constant-PRI emitters.
```

Comment introducing first group.

These emitters:

- stay at approximately fixed CF
- transmit repeatedly
- have PRI jitter

---

### Line 66
```python
for cf, pri, pw, aoa in [
```

Begins loop over emitter configurations.

Each tuple contains:

```text
CF
PRI
PW
AoA
```

---

### Line 67
```python
(2400, 1000, 2.0, 30),
```

Emitter 0:

```text
CF  = 2400 MHz
PRI = 1000 μs
PW  = 2.0 μs
AoA = 30°
```

---

### Line 68
```python
(9200, 650, 1.2, 140),
```

Emitter 1:

```text
CF  = 9200 MHz
PRI = 650 μs
PW  = 1.2 μs
AoA = 140°
```

---

### Line 69
```python
(14300, 1500, 3.0, 260),
```

Emitter 2:

```text
CF  = 14300 MHz
PRI = 1500 μs
PW  = 3.0 μs
AoA = 260°
```

---

### Line 70
```python
]:
```

Ends emitter configuration list.

---

### Line 71
```python
t = rng.uniform(0, pri)
```

Chooses random initial ToA.

Instead of every emitter starting at:

```text
t=0
```

each begins at a random point between:

```text
0 and PRI
```

This prevents artificial synchronization.

---

### Line 72
```python
while t < duration_us:
```

Keep generating pulses until simulation duration is reached.

---

### Lines 73–74
```python
pulses.append((t, cf + rng.normal(0, 0.5), pw,
                aoa + rng.normal(0, 1), rng.uniform(-70, -40), emitter_id))
```

This creates one pulse tuple.

Six fields:

```text
(t,
 noisy CF,
 PW,
 noisy AoA,
 random amplitude,
 emitter ID)
```

Let's break each out.

#### `t`

Exact pulse arrival time.

#### `cf + rng.normal(0, 0.5)`

Centre frequency gets Gaussian noise.

Mean:

```text
0
```

standard deviation:

```text
0.5 MHz
```

So nominal:

```text
2400 MHz
```

might appear as:

```text
2399.7
2400.2
2400.1
...
```

#### `pw`

Pulse width remains fixed for that emitter.

#### `aoa + rng.normal(0, 1)`

Adds AoA noise with standard deviation 1 degree.

#### `rng.uniform(-70, -40)`

Random amplitude between:

```text
-70 dB and -40 dB
```

#### `emitter_id`

Ground-truth source.

---

### Line 75
```python
t += pri * (1 + rng.normal(0, 0.02))  # small PRI jitter
```

Advance to next pulse.

Nominal increment:

```text
pri
```

but multiplied by:

$$
1+N(0,0.02)
$$

So approximately 2% relative jitter.

For PRI 1000 μs, an increment might be:

```text
997 μs
1012 μs
983 μs
...
```

rather than exactly 1000 every time.

This makes the synthetic data more realistic and tests whether later algorithms can tolerate imperfect periodicity.

---

### Line 76
```python
emitter_id += 1
```

Move to next emitter label.

So after first emitter:

```text
emitter_id = 1
```

---

# Lines 78–89 — Frequency-agile emitters

### Line 78
```python
# Frequency-agile emitters: hop centre frequency pulse-to-pulse.
```

Introduces second emitter type.

Unlike fixed-frequency emitters, these change CF between pulses.

---

### Line 79
```python
for hop_bands, pri, pw, aoa in [
```

Each configuration contains:

```text
possible frequency bands
PRI
PW
AoA
```

---

### Line 80
```python
([500, 3300, 6100, 11800, 16200], 400, 0.8, 70),
```

Agile emitter 3:

Possible CFs:

```text
500
3300
6100
11800
16200 MHz
```

PRI ≈ 400 μs.

PW = 0.8 μs.

AoA = 70°.

---

### Line 81
```python
([1800, 4700, 8600, 12900, 17000], 550, 1.0, 200),
```

Agile emitter 4:

Possible CFs:

```text
1800
4700
8600
12900
17000 MHz
```

PRI ≈ 550 μs.

PW = 1.0 μs.

AoA = 200°.

---

### Line 82
```python
]:
```

Ends configuration list.

---

### Line 83
```python
t = rng.uniform(0, pri)
```

Again choose random starting time within one PRI.

---

### Line 84
```python
while t < duration_us:
```

Continue generating until duration expires.

---

### Line 85
```python
cf = rng.choice(hop_bands) + rng.normal(0, 2)
```

Choose one frequency randomly from allowed hop bands.

Then add Gaussian frequency error:

```text
standard deviation = 2 MHz
```

So if chosen nominal band is:

```text
6100 MHz
```

actual CF might be:

```text
6098.7 MHz
```

or:

```text
6102.3 MHz
```

---

### Lines 86–87
```python
pulses.append((t, cf, pw, aoa + rng.normal(0, 3),
                rng.uniform(-75, -45), emitter_id))
```

Create pulse.

Differences from fixed emitter:

### CF

Already generated with hopping + noise.

### AoA

Noise is larger:

```text
σ = 3°
```

### Amplitude

Range:

```text
-75 to -45 dB
```

### Label

Current emitter ID.

---

### Line 88
```python
t += pri * (1 + rng.normal(0, 0.1))
```

Advance to next pulse.

Now PRI jitter is much larger:

```text
σ = 10%
```

compared with 2% for fixed emitters.

So agile emitter has less stable timing.

---

### Line 89
```python
emitter_id += 1
```

Move to next emitter label.

---

# Lines 91–94 — Build final NumPy structure

### Line 91
```python
pulses.sort(key=lambda p: p[0])
```

Sort all pulses according to first tuple element:

```text
p[0] = ToA
```

This is essential because pulses were generated emitter-by-emitter.

Without sorting, output would look like:

```text
all emitter 0 pulses
all emitter 1 pulses
all emitter 2 pulses
...
```

But real PDW streams are naturally chronological:

```text
pulse at 12 μs
pulse at 18 μs
pulse at 21 μs
pulse at 22 μs
...
```

So sorting interleaves all emitters correctly.

---

### Line 92
```python
dtype = [("toa", "f8"), ("cf", "f8"), ("pw", "f8"),
```

Defines NumPy structured-array schema.

`f8` means:

```text
8-byte floating-point number
```

Equivalent to NumPy `float64`.

Fields:

```text
toa
cf
pw
```

---

### Line 93
```python
("aoa", "f8"), ("amp", "f8"), ("label", "i4")]
```

Remaining fields:

```text
aoa  → float64
amp  → float64
label → int32
```

So final record layout is:

```text
┌───────┬───────┬───────┬───────┬───────┬───────┐
│  toa  │  cf   │  pw   │  aoa  │  amp  │ label │
├───────┼───────┼───────┼───────┼───────┼───────┤
│ float │ float │ float │ float │ float │  int  │
└───────┴───────┴───────┴───────┴───────┴───────┘
```

---

### Line 94
```python
return np.array(pulses, dtype=dtype)
```

Converts ordinary Python list into NumPy structured array using the specified schema.

So:

```python
pdw = generate_synthetic_pdw_stream()
```

returns something that can be accessed like:

```python
pdw["toa"]
pdw["cf"]
pdw["pw"]
pdw["aoa"]
pdw["amp"]
pdw["label"]
```

---

# What `pdw_loader.py` gives us

There are **two interchangeable input paths**:

```text
                  PDW input
                     │
          ┌──────────┴──────────┐
          │                     │
          ▼                     ▼
load_real_pulse_train()   generate_synthetic_pdw_stream()
          │                     │
          ▼                     ▼
      real TSRD             synthetic PDW
          │                     │
          └──────────┬──────────┘
                     ▼
              same basic schema
                     │
                     ▼
            downstream pipeline
```

This is an important architectural decision.

The downstream code can operate on:

```text
ToA
CF
PW
AoA
Amplitude
label
```

without needing to know whether pulses came from:

- real dataset, or
- local simulation.

---

## One subtle but important point

The synthetic data is **schema-faithful**, but it is **not equivalent to the real TSRD**.

It contains only the emitter behaviors deliberately coded here:

```text
3 fixed-frequency emitters
+
2 frequency-agile emitters
```

with manually selected parameters.

So results obtained from:

```python
generate_synthetic_pdw_stream()
```

should be treated as **pipeline validation**, not evidence of performance on the real dataset.

---

That file takes these PDWs and turns them into an **environment suitable for the scheduler**—i.e. it converts pulse-level information into something the scanning/scheduling experiments can interact with.

# `pdw_environment.py` — line-by-line

This file is only **53 lines**, and its job is very important:

> It converts pulse-level PDW data into the same **band ON/OFF per timestep** interface used by the earlier schedulers.

So this is the bridge:

```text
PDW pulses
   ↓
frequency bands + time windows
   ↓
band status at each timestep
   ↓
existing schedulers
```

The key design claim in this file is that the schedulers themselves don't need to be rewritten.

---

# Lines 1–19 — Module documentation

### Line 1
```python
"""
```

Starts module-level docstring.

### Line 2
```text
pdw_environment.py
```

File/module name.

### Line 3
```text
===================
```

Formatting separator.

### Lines 4–6
```text
Adapts a PDW stream (ToA, CF, ...) — real TSRD data or the schema-faithful
synthetic stand-in from pdw_loader.py — into the exact same "band status
per scan step" interface that scan_scheduler_prototype.Environment uses.
```

This is the central purpose.

Earlier, `Environment` generated information like:

```text
time 0 → {0: False, 1: True, 2: False, ...}
time 1 → {0: False, 1: False, 2: True, ...}
```

Now PDW data must be transformed into exactly that kind of representation.

There are two possible sources:

```text
real TSRD PDWs
```

or:

```text
generate_synthetic_pdw_stream()
```

from the previous file.

---

### Lines 8–10
```text
This means RoundRobinScheduler, RandomScheduler, and BeliefScheduler, and
the run_episode()/metrics code, all run UNMODIFIED against real radar
data: only the environment changes.
```

This is an architectural statement.

The intended structure is:

```text
                  Environment
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    RoundRobin       Random      Belief
          │            │            │
          └────────────┼────────────┘
                       ▼
                  run_episode
```

Previously:

```text
synthetic emitter environment
```

Now:

```text
PDW replay environment
```

The scheduler interface stays the same.

This is essentially an **adapter pattern**: convert new data into an interface existing code already understands.

---

# Lines 12–18 — Binning strategy

The next comments explain how continuous radar data becomes discrete scheduler inputs.

### Lines 13–14
```text
- Frequency axis: split [freq_range_mhz] into n_bands equal-width
  channels
```

Suppose:

```python
n_bands = 8
freq_range_mhz = (0, 18000)
```

Then the frequency range:

$$
0 \rightarrow 18000\text{ MHz}
$$

is divided into 8 equal-width bands.

Width:

$$
\frac{18000-0}{8}=2250\text{ MHz}
$$

So approximately:

```text
Band 0: 0–2250 MHz
Band 1: 2250–4500 MHz
Band 2: 4500–6750 MHz
...
Band 7: 15750–18000 MHz
```

These become the receiver's selectable channels.

---

### Lines 15–18
```text
- Time axis: split into fixed `dwell_us` windows
```

Time is also discretized.

If:

```python
dwell_us = 200
```

then:

```text
step 0 → 0–200 μs
step 1 → 200–400 μs
step 2 → 400–600 μs
...
```

A band is considered:

```text
ON
```

during a time window if **at least one pulse** lands in that band during that window.

This is crucial.

The scheduler doesn't see individual pulses.

It sees:

```text
band 0 = ON/OFF
band 1 = ON/OFF
...
```

for each discrete time step.

---

# Line 21 — NumPy

```python
import numpy as np
```

Imports NumPy.

The environment needs it for:

- generating equally spaced frequency boundaries;
- numerical binning;
- arrays;
- boolean status matrices;
- integer conversion.

---

# Lines 24–26 — Class definition

### Line 24
```python
class PDWReplayEnvironment:
```

Defines environment class.

`Replay` means we're replaying an already-recorded/generated sequence of pulses rather than dynamically generating emitters during execution.

---

### Lines 25–26
```python
def __init__(self, pdw, n_bands: int = 8, dwell_us: float = 200.0,
             freq_range_mhz=(0, 18000)):
```

Constructor.

Four inputs.

### `pdw`

The PDW structured NumPy array from `pdw_loader.py`.

It should contain fields:

```text
toa
cf
pw
aoa
amp
label
```

This environment only needs:

```text
toa
cf
```

because its job is to determine:

> When and in which frequency band did pulses occur?

---

### `n_bands: int = 8`

Number of frequency bands.

Default:

```text
8
```

Type annotation says it should be an integer.

---

### `dwell_us: float = 200.0`

Duration of one scheduler time step.

Default:

$$
200\ \mu s
$$

---

### `freq_range_mhz=(0, 18000)`

Frequency range covered by the receiver.

Default:

$$
0\text{ MHz} \rightarrow 18000\text{ MHz}
$$

---

# Lines 27–30 — Create frequency bands

### Line 27
```python
self.n_bands = n_bands
```

Stores number of bands as object attribute.

Later:

```python
env.n_bands
```

will give:

```text
8
```

by default.

---

### Line 28
```python
self.dwell_us = dwell_us
```

Stores time-window size.

---

### Line 29
```python
lo, hi = freq_range_mhz
```

Unpacks tuple:

```python
(0, 18000)
```

into:

```text
lo = 0
hi = 18000
```

---

### Line 30
```python
self.band_edges = np.linspace(lo, hi, n_bands + 1)
```

This creates frequency boundaries.

Why `n_bands + 1`?

Because 8 intervals require **9 boundaries**.

For example:

```text
0     2250    4500    6750    ...    18000
│-------│-------│-------│-------------│
   B0       B1       B2          B7
```

So:

```python
np.linspace(0, 18000, 9)
```

produces the 9 edges.

This array might look approximately like:

```text
[    0,
  2250,
  4500,
  6750,
  9000,
 11250,
 13500,
 15750,
 18000]
```

---

# Lines 32–35 — Empty PDW handling

### Line 32
```python
if len(pdw) == 0:
```

Checks whether there are zero pulses.

This prevents later operations such as:

```python
step_idx.max()
```

from failing on an empty array.

---

### Line 33
```python
self.n_steps = 0
```

No pulses means no replay steps.

---

### Line 34
```python
self._status = np.zeros((0, n_bands), dtype=bool)
```

Creates an empty status matrix.

Shape:

```text
0 × n_bands
```

With 8 bands:

```text
0 × 8
```

Each entry would normally represent:

```text
False = band OFF
True  = band ON
```

There simply aren't any rows because there are no timesteps.

---

### Line 35
```python
else:
```

If at least one PDW exists, process it.

---

# Lines 36–40 — Convert each pulse to band + timestep

This is the heart of the file.

### Line 36
```python
toa = pdw["toa"]
```

Extracts every pulse's time of arrival.

Example:

```text
[100, 230, 250, 401, 900, ...]
```

Units:

$$
\mu s
$$

---

### Line 37
```python
cf = pdw["cf"]
```

Extracts every pulse's centre frequency.

Example:

```text
[2401, 9199, 6102, 14298, ...]
```

Units:

$$
MHz
$$

---

### Line 38
```python
band_idx = np.clip(np.digitize(cf, self.band_edges) - 1, 0, n_bands - 1)
```

This is one of the most important lines.

It converts each pulse's frequency into a band number.

Let's break it apart.

---

## Part 1: `np.digitize(cf, self.band_edges)`

`np.digitize()` determines which interval each frequency belongs to.

Suppose edges are:

```text
0, 2250, 4500, 6750, ...
```

and:

```text
cf = 5000
```

Then 5000 lies between:

```text
4500 and 6750
```

so it belongs to band 2.

---

## Part 2: `- 1`

`np.digitize()` returns a 1-based bin position in this usage.

Subtracting 1 converts it to normal Python/NumPy zero-based band numbering:

```text
0, 1, 2, ...
```

---

## Part 3: `np.clip(..., 0, n_bands - 1)`

This prevents invalid band numbers.

For 8 bands, valid values are:

```text
0 through 7
```

So:

```python
np.clip(x, 0, 7)
```

forces anything below 0 to 0 and anything above 7 to 7.

This is particularly useful for frequencies outside the nominal range or boundary edge cases.

---

### Line 39
```python
step_idx = (toa // dwell_us).astype(np.int64)
```

Converts each pulse's ToA into a discrete timestep.

This uses floor division:

```text
//
```

Suppose:

```text
dwell_us = 200
```

Then:

```text
ToA = 50   → 50 // 200  = 0
ToA = 199  → 199 // 200 = 0
ToA = 200  → 200 // 200 = 1
ToA = 399  → 399 // 200 = 1
ToA = 400  → 400 // 200 = 2
```

Therefore:

```text
0–199 μs    → step 0
200–399 μs  → step 1
400–599 μs  → step 2
...
```

`.astype(np.int64)` converts resulting values to 64-bit integers.

---

# Lines 41–43 — Build ON/OFF matrix

### Line 41
```python
self.n_steps = int(step_idx.max()) + 1
```

Finds the latest timestep.

Suppose:

```text
step_idx = [0, 0, 1, 4, 4, 8]
```

Maximum:

```text
8
```

Therefore there must be:

```text
9 steps
```

because counting starts at zero:

```text
0,1,2,3,4,5,6,7,8
```

Hence:

```python
+ 1
```

---

### Line 42
```python
self._status = np.zeros((self.n_steps, n_bands), dtype=bool)
```

Creates the complete environment status matrix.

For example, if:

```text
n_steps = 5
n_bands = 8
```

shape becomes:

```text
5 × 8
```

Conceptually:

```text
             Bands
          0 1 2 3 4 5 6 7
Step 0 →  F F T F F F F F
Step 1 →  F T F F F F F F
Step 2 →  F F F F T F F F
Step 3 →  F F F F F F F F
Step 4 →  T F F F F F F F
```

Initially everything is `False`.

---

### Line 43
```python
self._status[step_idx, band_idx] = True
```

This is the operation that marks pulses as detected.

For every pulse:

```text
pulse → timestep
pulse → frequency band
```

and then:

```text
status[timestep, band] = True
```

So if a pulse occurs at:

```text
step 4
band 2
```

then:

```python
self._status[4, 2] = True
```

Multiple pulses in same timestep/band don't cause a problem.

Example:

```text
pulse 1 → step 4, band 2
pulse 2 → step 4, band 2
pulse 3 → step 4, band 2
```

All simply produce:

```text
status[4,2] = True
```

The environment only cares whether **at least one pulse occurred**.

This exactly matches the docstring's definition of band ON.

---

# Line 45 — Current timestep

```python
self.t = 0
```

Initial replay position.

The environment starts at:

```text
step 0
```

---

# Lines 47–53 — `step()`

Now the class provides the interface used by schedulers.

### Line 47
```python
def step(self):
```

Defines method for advancing environment by one timestep.

No argument is needed because the environment internally tracks current time with:

```python
self.t
```

---

### Line 48
```python
if self.t >= self.n_steps:
```

Checks whether replay has reached its end.

For example:

```text
n_steps = 100
```

valid steps are:

```text
0–99
```

At:

```text
t = 100
```

the replay is finished.

---

### Line 49
```python
row = np.zeros(self.n_bands, dtype=bool)
```

If replay is finished, create an all-OFF row.

For 8 bands:

```text
[False, False, False, False, False, False, False, False]
```

So calling `step()` after the data ends doesn't crash.

---

### Line 50
```python
else:
```

If replay isn't finished...

---

### Line 51
```python
row = self._status[self.t]
```

Retrieve current timestep's band-status row.

Example:

```text
self.t = 7
```

then:

```python
row = self._status[7]
```

might give:

```text
[False, True, False, False, True, False, False, False]
```

Meaning bands 1 and 4 had at least one pulse during that dwell window.

---

### Line 52
```python
self.t += 1
```

Advance environment time by one step.

So if current:

```text
t = 7
```

after this:

```text
t = 8
```

---

### Line 53
```python
return {b: bool(row[b]) for b in range(self.n_bands)}
```

Returns a Python dictionary mapping every band number to ON/OFF status.

For 8 bands:

```python
{
    0: False,
    1: True,
    2: False,
    3: False,
    4: True,
    5: False,
    6: False,
    7: False
}
```

The `bool(...)` converts NumPy boolean values into ordinary Python `bool`s.

The dictionary comprehension:

```python
{b: bool(row[b]) for b in range(self.n_bands)}
```

means:

> For every band `b` from 0 through `n_bands-1`, create key `b` whose value is that band's ON/OFF status.

---

# Complete data transformation

This file performs:

```text
                 PDW
                  │
        ┌─────────┴─────────┐
        │                   │
       ToA                  CF
        │                   │
        ▼                   ▼
   time binning       frequency binning
        │                   │
        ▼                   ▼
    step_idx             band_idx
        │                   │
        └─────────┬─────────┘
                  ▼
          status[step, band]
                  │
                  ▼
          Environment.step()
                  │
                  ▼
       {band: True/False}
```

So a raw pulse like:

```text
ToA = 430 μs
CF  = 5200 MHz
```

with:

```text
dwell = 200 μs
```

gets:

$$
430 // 200 = 2
$$

so:

```text
step = 2
```

and with 8 bands over 0–18,000 MHz:

```text
5200 MHz
```

falls into:

```text
band 2
```

Therefore:

```python
_status[2, 2] = True
```

and `step()` eventually reports:

```python
{0: False, 1: False, 2: True, ...}
```

---

## Most important conceptual distinction

`pdw_loader.py` gives us **pulse-level information**:

```text
Pulse A: ToA=430, CF=5200
Pulse B: ToA=470, CF=5210
Pulse C: ToA=810, CF=2400
```

`pdw_environment.py` throws away some pulse-level detail and creates:

```text
             band 0  band 1  band 2 ...
step 0          F       F       F
step 1          F       F       F
step 2          F       F       T
step 3          T       F       F
```

So **PDW → environment is a deliberate discretization**.

That matters later when we evaluate the scheduler: its performance depends not only on the scheduler, but also on choices such as:

```text
n_bands = 8
dwell_us = 200
freq_range = 0–18000 MHz
```

Those choices determine what information the scheduler is actually allowed to see.

---

### Next: `run_on_turing_dataset.py`

This is where the project starts putting the **PDW loader + PDW environment + schedulers** together into an actual replay/experiment pipeline.

# `run_on_turing_dataset.py` — line-by-line

This is the **integration script**. The previous files built individual pieces; this one connects them:

```text
PDW loader
   ↓
PDW replay environment
   ↓
RoundRobin / Random / BeliefUCB / PRIAware / PersistentPRIAware
   ↓
run_episode()
   ↓
metrics + PRI diagnostics
```


---

# Lines 1–56 — Module documentation

### Line 1
```python
"""
```
Starts module docstring.

### Line 2
```text
run_on_turing_dataset.py
```
Module name.

### Line 3
```text
==========================
```
Formatting separator.

### Lines 4–9
These describe what the script runs:

- RoundRobin baseline
- Random baseline
- BeliefUCB
- PRIAware
- PersistentPRIAware

And it runs them against a **TSRD PDW pulse train**.

Important: this is where the earlier scheduler work gets connected to PDW data.

---

### Lines 11–20

These explain why this script exists.

Earlier versions apparently used:

```text
old single-channel BeliefScheduler
```

and later:

```text
BeliefUCB / PRIAware
```

but didn't incorporate:

```text
PersistentPRIAwareScheduler
```

after its seed-robustness fix.

The point of this version is therefore:

> Test whether the persistent PRI-lock-on fix works when the input is PDW data rather than merely the toy sparse-radar scenario.

That is an important scientific distinction.

A fix working on a toy simulation doesn't automatically mean it works on the intended dataset.

---

### Lines 22–38 — Switch-cost warning

These comments document several optional mechanisms:

```text
switch_cost_steps
switch_lead_steps
warmup_dwell_steps
warmup_dwell_jitter
```

These values were introduced earlier in the pipeline.

The comments emphasize:

> They were tested on toy scenarios, not real downloaded TSRD data.

Therefore, if someone runs:

```bash
--switch-cost-steps 1
```

they shouldn't interpret the result as validated real-data evidence.

That's a good experimental warning.

---

# Lines 40–55 — Usage examples

### Lines 40–44

Basic usage:

```bash
python3 run_on_turing_dataset.py
```

uses the local synthetic PDW stand-in.

Real data:

```bash
python3 run_on_turing_dataset.py --h5 path.h5
```

uses an actual HDF5 pulse train.

---

### Line 45
```bash
python3 run_on_turing_dataset.py --k-channels 2 --warmup-steps 500
```

Example:

- receiver can scan 2 bands simultaneously;
- warmup lasts 500 steps.

---

### Line 46
```bash
python3 run_on_turing_dataset.py --priority "1,1,1,1,5,1,1,1"
```

Sets per-band priorities.

Band 4 gets:

$$
5\times
$$

priority relative to ordinary bands.

---

### Lines 47–48

Example with switching cost:

```bash
--switch-cost-steps 1
--switch-lead-steps 1
--warmup-dwell-steps 3
--warmup-dwell-jitter 1
```

These model receiver retuning and compensate for settling delay.

---

### Lines 50–55

Alternative:

```bash
--switch-cost-steps 1 --auto-dwell
```

lets:

```python
recommended_warmup_dwell()
```

automatically calculate suitable dwell/warmup settings.

Again, comments warn that this hasn't been validated on real PDW data.

---

### Line 56
```python
"""
```

Ends module documentation.

---

# Lines 58–67 — Imports

### Line 58
```python
import argparse
```

Imports Python's command-line argument parser.

This is what makes commands like:

```bash
--n-bands 16
```

possible.

---

## Lines 60–63

```python
from scan_scheduler_v2 import (
    RoundRobinScheduler, RandomScheduler, BeliefUCBScheduler, run_episode,
    recommended_warmup_dwell
)
```

Imports five things from V2:

### `RoundRobinScheduler`

Simple deterministic baseline.

### `RandomScheduler`

Random baseline.

### `BeliefUCBScheduler`

Markov + UCB scheduler.

### `run_episode`

Experiment driver.

### `recommended_warmup_dwell`

Helper for switch-cost-aware warmup configuration.

---

### Line 64
```python
from scan_scheduler_v3_pri import PRIAwareScheduler
```

Imports PRI-aware scheduler.

---

### Line 65
```python
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
```

Imports the V4 seed-robust scheduler.

This is the key fix that earlier versions omitted.

---

### Line 66
```python
from pdw_loader import load_real_pulse_train, generate_synthetic_pdw_stream
```

Imports both data sources:

```text
real PDW
synthetic PDW
```

---

### Line 67
```python
from pdw_environment import PDWReplayEnvironment
```

Imports the adapter that turns PDWs into scheduler-compatible ON/OFF states.

---

# Lines 70–87 — `load_pdw()`

### Line 70
```python
def load_pdw(args):
```

Defines helper function.

It receives the parsed command-line arguments.

---

### Line 71
```python
if args.h5:
```

Checks whether user supplied:

```bash
--h5 something.h5
```

If `args.h5` is not `None`/empty, try real data.

---

### Line 72
```python
try:
```

Starts exception-handling block.

---

### Line 73
```python
pdw, labels, meta = load_real_pulse_train(args.h5)
```

Calls the real loader from `pdw_loader.py`.

It returns:

```text
pdw
labels
metadata
```

But notice this script only uses:

```python
pdw
```

The labels and metadata are loaded but discarded here.

That's significant: this script's current evaluation is **scheduler interception**, not detailed emitter-label deinterleaving accuracy.

---

### Line 74
```python
print(f"Loaded real TSRD pulse train: {args.h5}  ({len(pdw)} pulses)")
```

Reports:

- file path
- number of pulses loaded

Example:

```text
Loaded real TSRD pulse train: train.h5 (12483 pulses)
```

---

### Line 75
```python
return pdw
```

Returns real PDW data.

---

### Line 76
```python
except ImportError:
```

Handles missing external package.

---

### Lines 77–80

Prints installation instructions:

```bash
pip install git+https://github.com/alan-turing-institute/turing-deinterleaving-challenge.git
```

Then says it will fall back to synthetic data.

---

### Line 81
```python
except FileNotFoundError:
```

Handles missing `.h5` file.

---

### Line 82
```python
print(f"'{args.h5}' not found. Falling back to the local synthetic PDW stand-in.\n")
```

Reports that the requested file doesn't exist.

---

### Lines 84–86

Prints that the local synthetic PDW generator will be used.

So even if:

```bash
--h5 nonexistent.h5
```

is supplied, the script doesn't necessarily terminate.

It falls back.

---

### Line 87
```python
return generate_synthetic_pdw_stream(seed=args.seed)
```

Generates synthetic PDW data using the requested seed.

Thus:

```text
real file works
      ↓
use real data

real file unavailable
      ↓
synthetic fallback
```

---

# Lines 90–96 — `parse_priority()`

### Line 90
```python
def parse_priority(spec, n_bands):
```

Defines function to convert command-line priority text into a Python list.

---

### Line 91
```python
if not spec:
```

If no priority string was supplied...

---

### Line 92
```python
return None
```

No weighting.

Schedulers then use their default priorities.

---

### Line 93
```python
values = [float(x) for x in spec.split(",")]
```

Suppose user enters:

```text
"1,1,1,1,5,1,1,1"
```

First:

```python
spec.split(",")
```

produces:

```text
["1","1","1","1","5","1","1","1"]
```

Then each is converted to `float`:

```text
[1.0,1.0,1.0,1.0,5.0,1.0,1.0,1.0]
```

---

### Line 94
```python
if len(values) != n_bands:
```

Checks that exactly one priority exists per band.

---

### Line 95
```python
raise ValueError(...)
```

If `n_bands=8` but user gives 7 values, execution stops with a meaningful error.

Example:

```text
--priority needs exactly 8 comma-separated values, got 7
```

---

### Line 96
```python
return values
```

Returns priority list.

---

# Lines 99–156 — `main()` and command-line options

### Line 99
```python
def main():
```

Defines main program.

---

### Line 100
```python
ap = argparse.ArgumentParser(description=__doc__)
```

Creates argument parser.

`description=__doc__` means the giant module documentation becomes the command's help description.

So:

```bash
python3 run_on_turing_dataset.py --help
```

gets useful documentation.

---

## Lines 101–123 — Basic arguments

### Line 101
```python
ap.add_argument("--h5", default=None, ...)
```

Optional path to real `.h5` PDW data.

Default:

```text
None
```

---

### Line 102
```python
ap.add_argument("--n-bands", type=int, default=8, ...)
```

Number of receiver frequency bands.

Default:

$$
8
$$

---

### Lines 103–104
```python
ap.add_argument("--dwell-us", type=float, default=200.0, ...)
```

Each scan step covers:

$$
200\ \mu s
$$

by default.

---

### Lines 105–106
```python
ap.add_argument("--k-channels", type=int, default=1, ...)
```

Number of bands scanned simultaneously.

Default:

$$
k=1
$$

If:

```bash
--k-channels 2
```

the scheduler can choose two bands each step.

---

### Lines 107–109
```python
ap.add_argument("--warmup-steps", type=int, default=0, ...)
```

Number of initial exploration/warmup steps.

Default:

```text
0
```

The explanation notes why warmup matters:

> rare/low-duty emitters may need many observations before their PRI can be estimated.

---

### Line 110
```python
ap.add_argument("--ucb-c", type=float, default=0.5, ...)
```

Controls UCB exploration strength.

Higher:

```text
ucb_c ↑
```

means stronger exploration.

---

### Lines 111–118 — PRI confidence scale

```python
ap.add_argument("--confidence-scale", ...)
```

Default:

```text
0.25
```

The underlying confidence formula is:

$$
\text{confidence}
=
1-\frac{\text{RMSE}}
{\text{confidence\_scale}\times\text{period}}
$$

So smaller scale means:

```text
stricter fit required
```

Larger scale:

```text
easier to accept PRI
```

This parameter was explored in `tune_confidence_threshold.py`.

---

### Lines 119–122 — Priority

```python
ap.add_argument("--priority", default=None, ...)
```

Accepts comma-separated weights.

Example:

```text
1,1,1,1,5,1,1,1
```

means band 4 receives weight 5.

This allows a deliberate trade-off:

```text
general interception
        vs.
guaranteed attention to important band
```

---

### Line 123
```python
ap.add_argument("--seed", type=int, default=0, ...)
```

Synthetic-data seed.

Default:

```text
0
```

---

# Lines 124–155 — Switching/warmup arguments

### Lines 124–129

```python
--switch-cost-steps
```

Models receiver retuning delay.

If:

```text
switch_cost_steps = 1
```

then changing to a new band causes one settling step.

Default:

```text
0
```

meaning no switching penalty.

---

### Lines 130–136 — `switch_lead_steps`

Only affects:

```text
PRIAware
PersistentPRIAware
```

It makes scheduler start favoring a periodic band before its expected pulse.

If:

```text
switch_cost = 1
switch_lead = 1
```

the scheduler tries to arrive one step early so settling completes when the pulse arrives.

RoundRobin/Random/BeliefUCB don't use it because they don't have a PRI model.

---

### Lines 137–143 — Warmup dwell

```python
--warmup-dwell-steps
```

Controls how long warmup remains on each selected band.

Default:

```text
1
```

With:

```text
3
```

one band can remain selected for approximately three warmup steps, subject to jitter.

This is useful when switching costs exist.

---

### Lines 144–149 — Warmup jitter

```python
--warmup-dwell-jitter
```

Adds a random number:

$$
0\ldots N
$$

of additional dwell steps.

The comments explain why jitter matters:

> Fixed dwell with zero jitter can synchronize badly with pulse phase.

So:

```text
jitter = 0
```

can create deterministic blind spots.

---

### Lines 150–155 — `--auto-dwell`

```python
ap.add_argument("--auto-dwell", action="store_true", ...)
```

Boolean flag.

Without it:

```text
False
```

With:

```bash
--auto-dwell
```

it becomes:

```text
True
```

When switching cost > 0, the script automatically derives:

- warmup dwell
- warmup length
- switch lead

using:

```python
recommended_warmup_dwell()
```

---

### Line 156
```python
args = ap.parse_args()
```

Actually parses command-line arguments.

For example:

```bash
python3 run_on_turing_dataset.py --k-channels 2 --warmup-steps 500
```

becomes approximately:

```python
args.k_channels == 2
args.warmup_steps == 500
```

---

# Lines 158–173 — Load data and configure auto-dwell

### Line 158
```python
pdw = load_pdw(args)
```

Load either:

```text
real PDW
```

or:

```text
synthetic PDW
```

---

### Line 159
```python
priority = parse_priority(args.priority, args.n_bands)
```

Convert priority string into numeric list.

---

### Lines 161–164

Copies command-line values into local variables:

```python
warmup_steps
warmup_dwell_steps
warmup_dwell_jitter
switch_lead_steps
```

Why copy them?

Because `--auto-dwell` may modify these values.

---

### Line 165
```python
if args.switch_cost_steps > 0 and args.auto_dwell:
```

Auto calculation happens only if:

1. switching cost exists;
2. user explicitly requested auto-dwell.

---

### Lines 166–167
```python
warmup_dwell_steps, warmup_steps = recommended_warmup_dwell(
    args.switch_cost_steps, args.warmup_steps, margin=2)
```

Calls the V2 helper.

It returns two values:

```text
recommended dwell
recommended warmup duration
```

with margin:

$$
2
$$

---

### Line 168
```python
warmup_dwell_jitter = 1
```

Automatically enables one-step random jitter.

---

### Line 169
```python
switch_lead_steps = args.switch_cost_steps
```

Makes lead equal to switching cost.

So if:

```text
switch cost = 2
```

then:

```text
switch lead = 2
```

---

### Lines 170–173

Prints exactly what auto-dwell calculated.

For example:

```text
--auto-dwell: derived warmup_dwell_steps=...
warmup_steps=...
switch_lead_steps=...
```

Useful for reproducibility.

---

# Lines 175–181 — Environment factory

### Line 175
```python
def env_factory():
```

Defines a small function that creates a fresh environment.

---

### Line 176
```python
return PDWReplayEnvironment(
    pdw,
    n_bands=args.n_bands,
    dwell_us=args.dwell_us
)
```

Creates a new PDW replay environment using the loaded pulse stream.

Why a **factory** rather than one environment object?

Because each scheduler must start from:

```text
time = 0
```

If the same environment object were reused, the first scheduler would consume all its steps and later schedulers would start at the end.

So:

```text
env_factory()
```

creates a fresh replay for every scheduler.

Very important experimental detail.

---

### Line 178
```python
n_steps = env_factory().n_steps
```

Creates one temporary environment just to discover how many replay steps exist.

---

### Line 179
```python
if n_steps == 0:
```

Checks whether PDW stream is empty.

---

### Line 180
```python
print("No pulses found in the loaded data -- nothing to replay.")
```

Reports empty input.

---

### Line 181
```python
return
```

Stops `main()`.

---

# Lines 183–190 — Experiment summary

### Lines 183–186

Prints experiment configuration:

```text
number of scan steps
number of bands
dwell duration
total data duration
number of channels
warmup
switching cost
```

The duration calculation is:

```python
n_steps * args.dwell_us / 1e6
```

because:

$$
1\,000\,000\ \mu s=1s
$$

---

### Lines 187–190

If switching cost > 0, prints another warning:

> These settings have only been validated on toy scenarios.

Again, the code deliberately prevents the user from forgetting this limitation.

---

# Lines 192–206 — Construct all schedulers

This is one of the most important sections.

### Line 192
```python
schedulers = {
```

Creates dictionary mapping names to scheduler objects.

---

### Line 193
```python
"RoundRobin (open-loop baseline)": RoundRobinScheduler(args.n_bands),
```

Creates deterministic baseline.

No learning.

---

### Line 194
```python
"Random (naive baseline)": RandomScheduler(args.n_bands),
```

Creates random baseline.

---

### Lines 195–197
```python
"BeliefUCB (Markov + UCB, learned)": BeliefUCBScheduler(...)
```

Creates V2 scheduler.

Receives:

```text
n_bands
ucb_c
warmup_steps
priority
warmup dwell
warmup jitter
```

So it combines:

```text
Markov belief
+
UCB exploration
+
optional priorities
+
warmup
```

---

### Lines 198–201
```python
"PRIAware (Markov + periodicity, learned)": PRIAwareScheduler(...)
```

Creates V3 scheduler.

Additional parameters:

```text
confidence_scale
switch_lead_steps
```

So it can exploit detected periodicity.

---

### Lines 202–205
```python
"PersistentPRIAware (seed-robust fix)": PersistentPRIAwareScheduler(...)
```

Creates V4 scheduler.

This is intended to solve the seed-sensitive PRI lock-on problem.

It receives the same important parameters as PRIAware.

---

### Line 206
```python
}
```

Ends scheduler dictionary.

At this stage, the available information is:

```text
5 schedulers
   │
   ├── RoundRobin
   ├── Random
   ├── BeliefUCB
   ├── PRIAware
   └── PersistentPRIAware
```

---

# Lines 208–212 — Results table

### Lines 208–210

Builds table header:

```text
Scheduler
Interception %
Avg Reward/step
Avg Intercept Delay
Switches
Wasted (settling)
```

These metrics come from `RunStats.report()`.

---

### Line 211
```python
print(header)
```

Prints header.

---

### Line 212
```python
print("-" * len(header))
```

Prints separator whose length equals header length.

---

# Lines 213–223 — Run every scheduler

### Line 213
```python
pri_scheds = {}
```

Creates dictionary to store schedulers that have PRI models.

---

### Line 214
```python
for name, sched in schedulers.items():
```

Loop through all five schedulers.

Each iteration gets:

```text
name
scheduler object
```

---

### Lines 215–216
```python
stats = run_episode(
    env_factory,
    sched,
    n_steps,
    args.n_bands,
    k_channels=args.k_channels,
    switch_cost_steps=args.switch_cost_steps
)
```

This actually runs experiment.

Notice:

```python
env_factory
```

rather than:

```python
env
```

As explained earlier, this ensures each scheduler gets a fresh environment.

Arguments tell `run_episode()`:

- which environment to create;
- which scheduler to use;
- number of steps;
- number of bands;
- simultaneous channels;
- switching cost.

---

### Line 217
```python
r = stats.report()
```

Converts collected statistics into report dictionary.

---

### Lines 218–220

Prints one result row.

For example conceptually:

```text
PersistentPRIAware | 85.2% | 0.852 | 1.4 | 120 | 100
```

The values are formatted for readability.

---

### Line 221
```python
if isinstance(sched, PRIAwareScheduler):
```

Checks whether scheduler is an instance of `PRIAwareScheduler`.

Here's a subtle Python point:

`PersistentPRIAwareScheduler` inherits from `PRIAwareScheduler`.

Therefore:

```python
isinstance(
    persistent_scheduler,
    PRIAwareScheduler
)
```

returns:

```text
True
```

So both:

```text
PRIAware
PersistentPRIAware
```

are collected.

---

### Line 222
```python
pri_scheds[name] = sched
```

Stores PRI-aware scheduler for later diagnostics.

---

### Line 223
Blank.

---

# Lines 224–236 — PRI diagnostics

Now the script asks:

> Did the PRI-aware schedulers actually discover any periodic bands?

### Line 224
```python
for name, sched in pri_scheds.items():
```

Loop over:

```text
PRIAware
PersistentPRIAware
```

---

### Lines 225–226

Prints diagnostic heading.

It explains that bands without detected PRI might either be:

```text
aperiodic
```

or:

```text
insufficiently sampled
```

That distinction matters.

No PRI estimate does **not** necessarily mean:

> band isn't periodic.

It could simply mean:

> scheduler didn't collect enough useful hits.

---

### Line 227
```python
found_any = False
```

Tracks whether at least one band has a PRI estimate.

Initially:

```text
False
```

---

### Line 228
```python
for b in range(args.n_bands):
```

Check every band.

---

### Line 229
```python
pri, conf = sched.pri_estimate[b], sched.confidence[b]
```

Retrieve:

```text
estimated PRI
confidence
```

for current band.

---

### Line 230
```python
if pri is not None:
```

Check whether a valid PRI was detected.

---

### Line 231
```python
found_any = True
```

At least one PRI exists.

---

### Lines 232–233

Print:

```text
band number
estimated PRI in scan steps
approximate PRI in microseconds
confidence
```

The conversion:

```python
pri * args.dwell_us
```

is:

$$
\text{PRI}_{\mu s}
=
\text{PRI}_{steps}
\times
\text{dwell}_{\mu s}
$$

For example:

```text
PRI = 3.5 steps
dwell = 200 μs
```

gives:

$$
3.5\times200=700\mu s
$$

---

### Line 234
```python
if not found_any:
```

If no band had a valid PRI estimate...

---

### Lines 235–236
```python
print("  none -- try --warmup-steps and/or a longer run ...")
```

Suggests more data/exploration.

Again, absence of estimate isn't automatically proof of absence of periodicity.

---

# Lines 239–240 — Program entry point

### Line 239
```python
if __name__ == "__main__":
```

Standard Python entry-point check.

When running:

```bash
python3 run_on_turing_dataset.py
```

`__name__` becomes:

```text
"__main__"
```

so the condition is true.

When imported:

```python
import run_on_turing_dataset
```

the condition is false, so `main()` isn't automatically executed.

---

### Line 240
```python
main()
```

Starts the complete experiment.

---

# The entire file's execution flow

Now we can see what happens from start to finish:

```text
python run_on_turing_dataset.py
              │
              ▼
       parse command line
              │
              ▼
         load_pdw()
          /       \
       --h5       no --h5
        │             │
        ▼             ▼
    real TSRD     synthetic PDW
        │             │
        └──────┬──────┘
               ▼
          parse priority
               │
               ▼
       configure dwell/lead
               │
               ▼
         env_factory()
               │
               ▼
       determine n_steps
               │
               ▼
       create 5 schedulers
               │
               ▼
        run_episode()
         for each one
               │
               ▼
          statistics
               │
               ▼
         print results
               │
               ▼
      PRI diagnostics
```

## Most important architectural point

This file proves that the earlier scheduler code is intended to be **data-source independent**.

The scheduler doesn't directly consume:

```text
PDW
```

Instead:

```text
PDW
 ↓
PDWReplayEnvironment
 ↓
Environment-like interface
 ↓
scheduler
```

So the separation is:

```text
DATA LAYER
pdw_loader.py

        ↓

ENVIRONMENT / ADAPTER LAYER
pdw_environment.py

        ↓

SCHEDULING LAYER
scan_scheduler_v2/v3/v4

        ↓

EXPERIMENT LAYER
run_on_turing_dataset.py
```

That's the core architecture of this project.

### One important limitation

Although `load_real_pulse_train()` retrieves:

```text
pdw + labels + metadata
```

this script only passes:

```text
pdw
```

forward.

Therefore, **the `label` ground truth isn't currently used to calculate emitter-level classification/deinterleaving accuracy** in this script. Its metrics are primarily about whether scheduled bands coincide with pulse activity.

---

**Next file: `diagnose_beacon_regression.py` (173 lines).** This starts the diagnostic/experimental phase of the project: instead of building the scheduler, it investigates a specific regression where changes intended to help sparse periodic emitters affected beacon capture.

# `diagnose_beacon_regression.py` — line-by-line

This file is a **diagnostic experiment**, not a new scheduler.

Its question is very specific:

> **Why does `PRIAwareScheduler` beat `BeliefUCBScheduler` when `k_channels=1`, but lose when `k_channels=2`?**

The file tries to prove/disprove a particular hypothesis: with two available scan channels, PRIAware may waste both channels on beacon-related bands simultaneously.

---

# Lines 1–38 — Module documentation

### Line 1
```python
"""
```
Starts module-level documentation.

### Line 2
```text
diagnose_beacon_regression.py
```
File name.

### Line 3
```text
================================
```
Formatting separator.

---

### Lines 4–6

```text
Digs into WHY PRIAwareScheduler loses to BeliefUCBScheduler on the beacon
scenario ... specifically at k_channels=2
```

This establishes the experiment's purpose.

Earlier experiments found:

```text
k=1 → PRIAware better
k=2 → PRIAware worse
```

The interesting part is that **only the number of simultaneous scan channels changed**.

---

### Lines 8–9

The reported results are:

```text
k=1:
PRIAware +1.5 percentage points
wins 8/10 seeds

k=2:
PRIAware -1.5 percentage points
wins 1/10 seeds
```

`pp` means **percentage points**, not percent relative improvement.

For example:

```text
BeliefUCB = 80%
PRIAware  = 81.5%
```

is:

$$
+1.5\text{ percentage points}
$$

---

### Lines 11–14

The comments emphasize:

```text
same scheduler
same scenario
different k
```

and reject one possible explanation:

> Maybe PRI-awareness has a fixed computational/learning cost.

Why rejected?

Because if the cost were fixed, it should hurt at:

```text
k=1
```

too.

Instead:

```text
k=1 → helps
k=2 → hurts
```

Therefore the suspected problem is specifically related to **having multiple simultaneous choices**.

---

# Lines 16–25 — Two structural causes

The script identifies two unusual properties of the scenario.

### Lines 19–21

Three bands:

```text
2, 5, 6
```

belong to one periodic beacon.

The beacon sequence is:

```text
2 → 5 → 6 → 2 → ...
```

with:

```text
dwell = 4
```

So one physical emitter appears on **three different frequency bands**.

But PRIAware treats each band separately.

That means:

```text
physical beacon
      │
      ├── band 2 → own PRI model
      ├── band 5 → own PRI model
      └── band 6 → own PRI model
```

The scheduler doesn't explicitly know:

> "These three bands are actually one emitter."

---

### Lines 22–25

Band 6 contains two things:

```text
beacon
+
frequency-agile threat
```

So band 6 is a genuine collision.

That means observations from band 6 can look less cleanly periodic.

Conceptually:

```text
Band 6 observations
       │
       ├── beacon pulses
       │
       └── agile-threat pulses
```

The second source can contaminate the periodicity signal.

---

# Lines 27–35 — Main hypothesis

The hypothesis is:

### With `k=1`

Scheduler must select exactly one band.

So if beacon band 2 currently has the strongest periodicity score:

```text
choose 2
```

It can't simultaneously choose another beacon band.

---

### With `k=2`

Scheduler can select two bands:

```text
choose [2, 5]
```

The hypothesis says the periodicity scoring may make **two beacon bands look attractive simultaneously**, even though only one is currently useful.

Therefore:

```text
PRIAware:
slot 1 → beacon
slot 2 → beacon
```

while:

```text
BeliefUCB:
slot 1 → productive beacon/comm band
slot 2 → productive comm band
```

The second PRIAware slot may therefore be wasted.

This is what the script calls a:

> **"double beacon bet."**

---

### Lines 37–38

Command to run:

```bash
python3 diagnose_beacon_regression.py
```

Ends module documentation.

---

# Lines 40–45 — Imports

### Line 40
```python
import random
```

Used to seed the simulation.

---

### Line 41
```python
import statistics
```

Used for:

- mean
- standard deviation

across seeds.

---

### Line 42
```python
from typing import List
```

Imports `List`.

**Important:** this import isn't meaningfully used in the visible code below. It appears to be leftover/unused.

---

### Line 44
```python
from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
```

Imports:

- `BeliefUCBScheduler`
- `run_episode`

`run_episode` is also not used in this file's actual `per_band_capture()` implementation.

So `run_episode` appears to be another unused import.

---

### Line 45
```python
from scan_scheduler_v3_pri import PRIAwareScheduler, make_scenario
```

Imports:

- PRI-aware scheduler
- original beacon scenario generator

---

# Lines 47–51 — Experiment constants

### Line 47
```python
N_BANDS = 8
```

Simulation has 8 frequency bands.

---

### Line 48
```python
N_STEPS = 4000
```

Each experiment lasts:

$$
4000
$$

timesteps.

---

### Line 49
```python
BEACON_BANDS = {2, 5, 6}
```

A Python `set`.

These three bands are the beacon bands.

Using a set makes membership checks efficient:

```python
b in BEACON_BANDS
```

---

### Line 50
```python
COMM_BANDS = {1, 4}
```

Bands 1 and 4 are communication bands.

---

### Line 51
```python
N_SEEDS = 10
```

Experiment repeats over 10 random seeds.

This matters because one seed can produce misleading results.

---

# Lines 54–107 — `per_band_capture()`

This is the core diagnostic function.

### Line 54
```python
def per_band_capture(sched_cls, k, seed):
```

Three parameters:

### `sched_cls`

Scheduler class.

For example:

```python
BeliefUCBScheduler
```

or:

```python
PRIAwareScheduler
```

It is a **class**, not an already-created object.

---

### `k`

Number of simultaneous scan channels.

Either:

```text
1
```

or:

```text
2
```

---

### `seed`

Random seed.

---

## Lines 55–58 — Docstring

The function tracks:

1. capture per band;
2. how often both `k=2` channels are beacon bands;
3. how often such a double bet catches at least one pulse;
4. how often it misses both.

So it isn't merely measuring final interception.

It's trying to identify **why** interception changes.

---

### Line 59
```python
random.seed(seed)
```

Sets Python's global RNG.

This makes the scenario/scheduler randomness reproducible for this run.

---

### Line 60
```python
scenario = make_scenario(N_BANDS)
```

Creates the scenario factory from V3.

Remember: `make_scenario()` describes the beacon environment.

---

### Line 61
```python
sched = sched_cls(N_BANDS, ucb_c=0.5)
```

Instantiates whichever scheduler class was supplied.

For example:

```python
sched_cls = PRIAwareScheduler
```

becomes conceptually:

```python
PRIAwareScheduler(8, ucb_c=0.5)
```

---

### Line 62
```python
env = scenario()
```

Creates actual environment instance.

So:

```text
make_scenario()
      ↓
scenario factory
      ↓
scenario()
      ↓
Environment
```

---

# Lines 64–68 — Diagnostic counters

### Line 64
```python
pulses = {b: 0 for b in range(N_BANDS)}
```

Creates dictionary:

```python
{
    0: 0,
    1: 0,
    ...
    7: 0
}
```

It will count how many times each band is actually ON.

---

### Line 65
```python
caught = {b: 0 for b in range(N_BANDS)}
```

Same structure, but counts how many ON events were successfully scanned.

So:

```text
pulses[b]
```

= opportunities.

```text
caught[b]
```

= captured opportunities.

---

### Line 66
```python
double_beacon_bets = 0
```

Counts steps where both available channels are beacon bands.

Only relevant when:

```text
k=2
```

---

### Line 67
```python
double_beacon_hits = 0
```

Counts double-beacon-bet steps where at least one selected beacon band was actually ON.

---

### Line 68
```python
double_beacon_full_miss = 0
```

Counts double-beacon-bet steps where **both** selected beacon bands were OFF.

This directly measures wasted double bets.

---

# Lines 70–90 — Main simulation loop

### Line 70
```python
for t in range(N_STEPS):
```

Run:

```text
t = 0,1,2,...,3999
```

4000 iterations.

---

### Line 71
```python
status = env.step()
```

Advance environment by one timestep.

Returns:

```python
{
    0: True/False,
    1: True/False,
    ...
    7: True/False
}
```

---

### Lines 72–74
```python
for b in range(N_BANDS):
    if status[b]:
        pulses[b] += 1
```

For every band:

```text
if band is ON:
    increment its opportunity count
```

So this measures total ON timesteps, not raw physical pulse count.

---

### Line 75
```python
bands = sched.choose_bands(k)
```

Ask scheduler which bands to scan.

If:

```text
k=1
```

could return:

```python
[5]
```

If:

```text
k=2
```

could return:

```python
[5, 1]
```

---

### Lines 76–79

```python
for b in bands:
    sched.update(b, status[b])
    if status[b]:
        caught[b] += 1
```

For every selected band:

1. tell scheduler whether it was ON;
2. if ON, count it as caught.

So scheduler learning and performance measurement happen together.

---

# Lines 81–90 — Detect "double beacon bets"

### Line 81
```python
if k == 2 and len(bands) == 2:
```

Only examine this behavior when exactly two channels are being used.

---

### Line 82
```python
b0, b1 = bands
```

Unpack the two selected band numbers.

Example:

```python
bands = [2, 5]
```

becomes:

```text
b0 = 2
b1 = 5
```

---

### Line 83
```python
if b0 in BEACON_BANDS and b1 in BEACON_BANDS:
```

Check whether **both** selected bands belong to:

```text
{2,5,6}
```

If yes, it's a double beacon bet.

---

### Line 84
```python
double_beacon_bets += 1
```

Count it.

---

### Line 85
```python
hits = int(status[b0]) + int(status[b1])
```

Convert booleans to integers.

Example:

```text
True + False
```

becomes:

```text
1 + 0 = 1
```

Possible results:

```text
0 → neither band ON
1 → one band ON
2 → both ON
```

---

### Line 86
```python
if hits >= 1:
```

At least one selected beacon band was active.

---

### Line 87
```python
double_beacon_hits += 1
```

Count successful double bets.

---

### Lines 88–89
```python
else:
    double_beacon_full_miss += 1
```

Neither selected band was active.

Therefore both available scan slots were wasted **on that step**.

---

# Lines 91–94 — Aggregate beacon and communication performance

### Line 91
```python
beacon_pulses = sum(pulses[b] for b in BEACON_BANDS)
```

Adds ON opportunities from bands:

```text
2 + 5 + 6
```

---

### Line 92
```python
beacon_caught = sum(caught[b] for b in BEACON_BANDS)
```

Adds successful captures across those bands.

---

### Lines 93–94

Same calculation for communication bands:

```text
1 + 4
```

So we can determine whether PRIAware's beacon behavior is stealing resources from communication capture.

---

# Lines 96–107 — Return diagnostic results

### Lines 96–98

Returns:

```python
"beacon_capture":
    beacon_caught / beacon_pulses
```

This is:

$$
\text{Beacon capture}
=
\frac{\text{beacon ON events caught}}
{\text{beacon ON events}}
$$

Similarly:

```python
"comm_capture"
```

for communication bands.

The conditional:

```python
if beacon_pulses else 0.0
```

prevents division by zero.

---

### Lines 99–101

Returns the three double-bet counters:

```text
double_beacon_bets
double_beacon_hits
double_beacon_full_miss
```

---

### Line 102
```python
"confidence": getattr(sched, "confidence", None),
```

`getattr()` safely retrieves scheduler confidence.

If scheduler has:

```python
sched.confidence
```

return it.

If it doesn't, return:

```text
None
```

This allows the function to work with both:

```text
BeliefUCBScheduler
PRIAwareScheduler
```

even though only PRIAware has confidence.

---

### Lines 103–105

Builds per-band capture dictionary, but **only for beacon bands**:

```python
{
    2: ...,
    5: ...,
    6: ...
}
```

Each value is:

$$
\frac{\text{caught}}
{\text{opportunities}}
$$

---

### Line 106
```python
"scan_count": list(getattr(sched, "scan_count", [0] * N_BANDS)),
```

Returns scheduler's number of times each band was scanned.

`getattr()` again provides fallback:

```python
[0] * N_BANDS
```

if scheduler doesn't have `scan_count`.

`list(...)` ensures the returned value is an ordinary Python list.

---

### Line 107
```python
}
```

Ends result dictionary.

---

# Lines 110–111 — `summarize()`

### Line 110
```python
def summarize(vals):
```

Defines formatting helper.

---

### Line 111
```python
return f"{statistics.mean(vals)*100:5.1f}% +/- {statistics.stdev(vals)*100:4.1f}%" if len(vals) > 1 else f"{vals[0]*100:5.1f}%"
```

This line is dense, so break it down.

If there are multiple values:

```python
statistics.mean(vals)
```

calculates average.

Then:

```python
* 100
```

converts a ratio into percentage.

For example:

```text
0.853 → 85.3%
```

And:

```python
statistics.stdev(vals)
```

calculates sample standard deviation.

Output might be:

```text
85.3% +/- 4.8%
```

If only one value exists, standard deviation isn't meaningful, so it prints just:

```text
85.3%
```

---

# Lines 114–150 — `main()`

### Line 114
```python
def main():
```

Main diagnostic experiment.

---

### Lines 115–117

Prints scenario description.

It explicitly states:

```text
Beacon bands = 2,5,6
Band 6 also has agile threat
Communication bands = 1,4
Seeds = 10
Steps = 4000
```

This makes the experiment self-documenting.

---

# Lines 119–124 — Prepare k=1 / k=2 experiments

### Line 119
```python
for k in (1, 2):
```

Run two experiments:

```text
k=1
k=2
```

---

### Line 120
```python
print(f"=== k_channels = {k} ===")
```

Print section heading.

---

### Lines 121–122

Create lists for storing each seed's results:

```text
beacon_belief
beacon_pri

comm_belief
comm_pri
```

So after 10 seeds:

```text
beacon_belief = [seed1, seed2, ..., seed10]
```

---

### Lines 123–124

Two more lists:

```text
double_bet_counts
double_bet_hit_rates
```

Only meaningful for:

```text
k=2
```

---

# Lines 126–138 — Ten seeds

### Line 126
```python
for seed in range(1, N_SEEDS + 1):
```

Seeds are:

```text
1 through 10
```

not 0 through 9.

---

### Line 127
```python
r_belief = per_band_capture(BeliefUCBScheduler, k, seed)
```

Run BeliefUCB.

---

### Line 128
```python
r_pri = per_band_capture(PRIAwareScheduler, k, seed)
```

Run PRIAware using same seed.

This is important for comparison.

---

### Lines 129–132

Extract:

```text
beacon capture
communication capture
```

from both schedulers and append to corresponding lists.

After 10 seeds:

```text
10 measurements per scheduler
```

---

### Line 133
```python
if k == 2:
```

Only gather double-bet statistics for two-channel case.

---

### Line 134
```python
double_bet_counts.append(r_pri["double_beacon_bets"])
```

Store how many double-beacon-bet steps occurred.

---

### Line 135
```python
total = r_pri["double_beacon_bets"]
```

Copy count to local variable.

---

### Line 136
```python
if total > 0:
```

Avoid division by zero.

---

### Line 137
```python
double_bet_hit_rates.append(r_pri["double_beacon_hits"] / total)
```

Calculate:

$$
\frac{\text{successful double bets}}
{\text{all double bets}}
$$

This answers:

> When PRIAware spends both channels on beacon bands, how often does at least one of them actually pay off?

---

# Lines 139–150 — Print experiment results

### Line 139

Print average beacon capture:

```text
BeliefUCB vs PRIAware
```

across 10 seeds.

---

### Line 140

Print communication capture comparison.

This is particularly important because a scheduler could increase beacon capture by sacrificing communication capture.

---

### Line 141
```python
if k == 2:
```

Print double-bet diagnostics only for two-channel experiment.

---

### Lines 142–144

Calculate average number of double-beacon-bet steps:

```python
statistics.mean(double_bet_counts)
```

Then express as:

```text
mean number / 4000 steps
```

and percentage:

$$
\frac{\text{mean double bets}}{4000}\times100
$$

Example:

```text
400 / 4000 = 10%
```

would mean PRIAware used both channels on beacon bands on about 10% of steps.

---

### Lines 145–149

If there were any double bets:

```python
if double_bet_hit_rates:
```

print their average success rate.

The explanatory text says:

> If this hit rate is lower than what a communication-band bet would achieve, then double-beacon behavior has a measurable opportunity cost.

This is the direct test of the hypothesis.

---

### Line 150
```python
print()
```

Blank line separating experiment sections.

---

# Lines 152–169 — Detailed seed-1 confidence investigation

The first experiment tells us **whether** double betting happens.

This second experiment asks:

> **Why does PRIAware consider multiple beacon bands attractive?**

The comments specifically propose checking confidence.

---

### Lines 152–154

The stated question is:

> Does band 6's collision with the agile threat suppress its PRI confidence compared with bands 2 and 5?

Expected possibility:

```text
band 2 → clean periodic signal → high confidence
band 5 → clean periodic signal → high confidence
band 6 → collision → lower confidence
```

---

### Line 155
```python
print("Per-band confidence detail, seed=1, k=2 (PRIAware):")
```

Print heading.

---

### Line 156
```python
random.seed(1)
```

Fix seed to 1.

---

### Line 157
```python
scenario = make_scenario(N_BANDS)
```

Create beacon scenario.

---

### Line 158
```python
sched = PRIAwareScheduler(N_BANDS, ucb_c=0.5)
```

Create PRIAware scheduler.

---

### Line 159
```python
env = scenario()
```

Create environment.

---

### Lines 160–164

Run 4000 steps with `k=2`.

```python
for t in range(N_STEPS):
```

At every step:

```python
status = env.step()
```

Then:

```python
bands = sched.choose_bands(2)
```

Then update scheduler for both selected bands:

```python
for b in bands:
    sched.update(b, status[b])
```

Notice this diagnostic does **not** collect capture statistics here. Its only purpose is to let the scheduler finish learning so its final confidence/PRI state can be inspected.

---

# Lines 165–169 — Print confidence for beacon bands

### Line 165
```python
for b in sorted(BEACON_BANDS):
```

Sort:

```text
{2,5,6}
```

into:

```text
2,5,6
```

---

### Line 166
```python
pri = sched.pri_estimate[b]
```

Retrieve estimated PRI for current band.

Could be:

```text
None
```

if no valid estimate exists.

---

### Line 167
```python
conf = sched.confidence[b]
```

Retrieve confidence.

---

### Line 168
```python
tag = " (also hosts agile threat)" if b == 6 else ""
```

Only band 6 gets explanatory label.

So output for band 6 will say:

```text
band 6 (also hosts agile threat)
```

---

### Line 169
```python
print(f"  band {b}{tag}: pri_estimate={pri}, confidence={conf:.2f}")
```

Print final diagnostic.

Example conceptually:

```text
band 2: pri_estimate=4.0, confidence=0.93
band 5: pri_estimate=4.0, confidence=0.91
band 6 (also hosts agile threat): pri_estimate=4.0, confidence=0.72
```

That would support the collision hypothesis.

---

# Lines 172–173 — Entry point

### Line 172
```python
if __name__ == "__main__":
```

Only execute automatically when this file is run directly.

---

### Line 173
```python
main()
```

Starts the diagnostic experiment.

---

# What this file is actually testing

The entire experiment can be summarized as:

```text
                    PRIAware regression
                           │
                 k=1 better, k=2 worse
                           │
                           ▼
                Is k=2 double betting?
                           │
                 ┌─────────┴─────────┐
                 │                   │
                NO                  YES
                 │                   │
          hypothesis false          ▼
                              Measure payoff
                                   │
                         ┌─────────┴─────────┐
                         │                   │
                       pays               misses
                         │                   │
                    acceptable?       wasted scan slot
```

And separately:

```text
Beacon
 ├── Band 2 ── periodic
 ├── Band 5 ── periodic
 └── Band 6 ── periodic + agile threat
                       │
                       ▼
                 noisy observations
                       │
                       ▼
                PRI confidence?
```

## Why this file matters

This is a good example of **diagnostic experimental code**.

It doesn't blindly say:

> "PRIAware is worse."

Instead it decomposes the result into:

1. **overall beacon capture**
2. **communication capture**
3. **frequency of double-beacon decisions**
4. **success rate of those decisions**
5. **per-band PRI confidence**
6. **effect of the band-6 collision**

That allows the author to move from:

```text
"PRIAware performs worse"
```

toward a causal explanation such as:

```text
PRIAware performs worse
        ↓
k=2 causes frequent double-beacon selections
        ↓
many double selections have no hit
        ↓
second channel opportunity is wasted
        ↓
communication capture falls
        ↓
overall result falls
```

That is the exact kind of experiment needed before modifying the scheduler.

**Next file: `diagnose_pri_lockon.py` (169 lines).** This investigates a different failure mode: the sparse-PRI radar can fail to accumulate enough hits during warmup, after which the original PRIAware scheduler effectively stops giving it opportunities.

# `diagnose_pri_lockon.py` — line-by-line

This file investigates a **different failure mode** from `diagnose_beacon_regression.py`.

Its question:

> Why is PRIAware's ability to lock onto sparse radar band 5 so dependent on random seed?

The file says earlier testing found roughly:

$$
30.0\% \pm 48.3\%
$$

capture across 10 seeds — enormous variation.

The suspected reason is a threshold effect:

```text
warmup scans
    ↓
confirmed radar hits
    ↓
need ≥ 8 hits
    ↓
PRI estimation starts
    ↓
periodicity score becomes strong
    ↓
scheduler keeps scanning radar
```

If the scheduler gets fewer than 8 confirmed hits during warmup, it may fail to discover the radar and then barely scan it afterward.

---

# Lines 1–14 — Module documentation

### Line 1
```python
"""
```

Starts module docstring.

### Line 2
```text
diagnose_pri_lockon.py
```

File name.

### Line 3
```text
=======================
```

Formatting separator.

---

### Lines 4–6
```text
Digs into WHY PRIAwareScheduler's lock-on on the sparse fixed-PRI radar
(band 5, true period 12, single-step pulse) is so seed-sensitive --
30.0% +/- 48.3% capture across 10 seeds, per multi_seed_robustness.py.
```

Defines exact target:

```text
radar band = 5
true PRI = 12 steps
pulse width = 1 step
```

The radar is therefore very sparse.

If it transmits once every 12 steps:

$$
P(\text{ON})=\frac1{12}\approx8.33\%
$$

The important number is **8 confirmed hits**.

---

### Lines 8–11

The diagnostic will inspect:

- scan counts;
- hit counts;
- intermediate PRI-model results;
- differences between successful and unsuccessful seeds.

This is more invasive than merely looking at final interception percentage.

---

### Lines 13–14
```text
Run: python3 diagnose_pri_lockon.py
"""
```

Documents how to execute the script and closes the module docstring.

---

# Lines 16–21 — Imports

### Line 16
```python
import random
```

Used to control simulation randomness.

---

### Line 17
```python
import statistics
```

Used later for:

- mean;
- standard deviation.

---

### Line 18
```python
from collections import Counter
```

Imports `Counter`.

**But it is never used in this file.**

So this is an unused import.

---

### Line 20
```python
from scan_scheduler_v2 import BeliefUCBScheduler
```

Imports `BeliefUCBScheduler`.

Again, this is **not directly used later**.

Likely leftover from an earlier version of the diagnostic.

---

### Line 21
```python
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
```

These are the important imports:

- `PRIAwareScheduler` — scheduler being investigated;
- `make_sparse_scenario` — creates the sparse-radar test environment.

---

# Lines 23–28 — Experiment constants

### Line 23
```python
N_BANDS = 8
```

There are 8 frequency bands.

---

### Line 24
```python
N_STEPS = 4000
```

Each seed is simulated for 4000 steps.

---

### Line 25
```python
WARMUP = 800
```

First 800 steps are warmup.

---

### Line 26
```python
RADAR_BAND = 5
```

The sparse radar occupies band 5.

---

### Line 27
```python
TRUE_PRI = 12
```

Ground-truth radar period:

$$
12\text{ steps}
$$

This is known because this is synthetic data.

The scheduler itself, of course, does **not** know this value.

---

### Line 28
```python
N_SEEDS = 40
```

This experiment uses **40 seeds**, rather than the 10 used in the earlier reported experiment.

That gives a better picture of seed sensitivity.

---

# Lines 31–48 — Instrumented scheduler

This is the most important code section.

### Line 31
```python
class InstrumentedPRIAware(PRIAwareScheduler):
```

Creates a subclass of the normal PRIAware scheduler.

Inheritance:

```text
InstrumentedPRIAware
        ↓ inherits
PRIAwareScheduler
        ↓ inherits
BeliefUCBScheduler
        ↓ inherits
...
```

It behaves like PRIAware, but records additional information.

---

### Lines 32–34 — Class docstring

The class documentation explains that it logs every call to:

```python
_update_pri_model()
```

for radar band 5.

It records:

```text
seed candidate
refined PRI
RMSE
confidence
```

The actual stored log below records the resulting PRI and confidence, while the parent method internally handles the candidate/refinement calculations.

---

### Line 35
```python
def __init__(self, *a, **kw):
```

Constructor accepts arbitrary positional and keyword arguments.

`*a` collects positional arguments.

`**kw` collects keyword arguments.

So this works:

```python
InstrumentedPRIAware(
    N_BANDS,
    ucb_c=0.5,
    warmup_steps=800
)
```

without having to reproduce PRIAware's entire constructor signature.

---

### Line 36
```python
super().__init__(*a, **kw)
```

Calls the parent constructor:

```python
PRIAwareScheduler.__init__()
```

Therefore all normal PRIAware state gets created:

```text
belief
confidence
hit_times
pri_estimate
scan_count
...
```

---

### Line 37
```python
self.log = []
```

Creates empty list for diagnostic records.

Each future call to `_update_pri_model(5)` will append one dictionary.

---

### Line 39
```python
def _update_pri_model(self, band):
```

Overrides PRIAware's existing method.

This is a classic instrumentation technique:

```text
original method
     ↓
wrap/override it
     ↓
record information
     ↓
call original implementation
```

---

### Line 40
```python
before_len = len(self.hit_times[band])
```

Records how many hits were already in the sliding `hit_times` history **before** updating the PRI model.

This is important because the parent method may:

- inspect history;
- calculate candidates;
- update PRI;
- change confidence.

---

### Line 41
```python
super()._update_pri_model(band)
```

Calls the real PRIAware implementation.

So this diagnostic does **not change the scheduler's algorithm**.

It merely observes it.

That's crucial for a valid diagnostic.

---

### Line 42
```python
if band == RADAR_BAND:
```

Only record information for:

```text
band 5
```

No need to log all eight bands.

---

### Lines 43–48
```python
self.log.append({
    "t": self.t,
    "n_hits_so_far": before_len,
    "pri_estimate": self.pri_estimate[band],
    "confidence": self.confidence[band],
})
```

Appends dictionary containing:

### `"t"`

Current scheduler time.

### `"n_hits_so_far"`

Number of hits in the hit history before this update.

### `"pri_estimate"`

Current estimated PRI.

Could be:

```text
None
```

if no model exists.

### `"confidence"`

Current confidence value.

Example log entry:

```python
{
    "t": 743,
    "n_hits_so_far": 8,
    "pri_estimate": 12.0,
    "confidence": 0.91
}
```

This allows the script to reconstruct **when lock-on happened**.

---

# Lines 51–99 — `run_one()`

This runs one complete seed.

### Line 51
```python
def run_one(seed):
```

Input:

```text
seed
```

Output:

```text
dictionary of diagnostics
```

---

### Line 52
```python
scenario = make_sparse_scenario(N_BANDS)
```

Creates sparse-radar scenario factory.

Important: it doesn't yet create the environment.

---

### Line 53
```python
random.seed(seed)
```

Sets random seed.

Therefore this particular experiment is reproducible.

---

### Line 54
```python
sched = InstrumentedPRIAware(
    N_BANDS,
    ucb_c=0.5,
    warmup_steps=WARMUP
)
```

Creates instrumented PRIAware:

```text
bands = 8
UCB coefficient = 0.5
warmup = 800
```

No explicit `switch_cost` etc. here, so defaults from V3 apply.

---

### Line 55
```python
env = scenario()
```

Creates actual environment.

---

# Lines 57–62 — Counters

Six counters are created.

### Line 57
```python
scans_on_band5_warmup = 0
```

How many times scheduler selected band 5 during first 800 steps.

---

### Line 58
```python
hits_on_band5_warmup = 0
```

How many of those band-5 scans actually found radar ON.

So:

```text
scan
+
radar ON
=
confirmed hit
```

---

### Line 59
```python
actual_pulses_warmup = 0
```

Counts how many times radar band 5 was actually ON during warmup, **regardless of whether scheduler scanned it**.

This is the denominator for potential radar capture.

---

### Line 60
```python
scans_on_band5_post = 0
```

Band-5 scans after warmup.

---

### Line 61
```python
hits_on_band5_post = 0
```

Successful band-5 scans after warmup.

---

### Line 62
```python
actual_pulses_post = 0
```

Total actual radar opportunities after warmup.

---

# Lines 64–84 — Main simulation

### Line 64
```python
for t in range(N_STEPS):
```

Runs:

$$
0,\ldots,3999
$$

---

### Line 65
```python
status = env.step()
```

Gets current environment state.

---

### Line 66
```python
bands = sched.choose_bands(1)
```

Scheduler chooses exactly one band.

This is deliberately:

$$
k=1
$$

because this diagnostic isolates the lock-on problem from the multi-channel regression.

---

### Lines 67–68
```python
for b in bands:
    sched.update(b, status[b])
```

For selected band:

1. obtain ON/OFF status;
2. give observation back to scheduler.

Because `k=1`, loop executes once.

---

# Lines 70–75 — Count actual radar pulses

### Line 70
```python
in_warmup = t < WARMUP
```

Determines whether current timestep belongs to warmup.

For:

```text
t = 799
```

true.

For:

```text
t = 800
```

false.

This means warmup covers:

$$
t=0,\ldots,799
$$

---

### Line 71
```python
if status[RADAR_BAND]:
```

Check whether band 5 is actually ON.

---

### Lines 72–75

If ON:

```text
warmup → actual_pulses_warmup += 1
post-warmup → actual_pulses_post += 1
```

Notice this doesn't care whether band 5 was selected.

This is measuring **available opportunities**, not captured opportunities.

---

# Lines 76–84 — Count scans and hits

### Line 76
```python
if RADAR_BAND in bands:
```

Check whether scheduler selected band 5.

---

### Lines 77–80 — During warmup

Increment:

```python
scans_on_band5_warmup
```

Then, if radar is ON:

```python
hits_on_band5_warmup
```

So the ratio:

$$
\frac{\text{hits\_on\_band5\_warmup}}
{\text{scans\_on\_band5\_warmup}}
$$

would be empirical probability that a band-5 scan finds the radar during warmup.

---

### Lines 81–84 — After warmup

Same logic, but goes into:

```text
scans_on_band5_post
hits_on_band5_post
```

---

# Lines 86–99 — Return all results

The function returns one dictionary.

### Line 87
```python
"seed": seed,
```

Stores which seed produced result.

---

### Lines 88–93

Stores six counters:

```text
scans_warmup
hits_warmup
pulses_warmup
scans_post
hits_post
pulses_post
```

This gives enough information to distinguish:

```text
scheduler didn't scan radar
```

from:

```text
scheduler scanned radar but radar happened to be OFF
```

---

### Line 94
```python
"final_hit_times_len": len(sched.hit_times[RADAR_BAND]),
```

How many hits remain in the scheduler's **sliding hit history** at end.

Important distinction:

This is **not necessarily total lifetime hits**.

V3 limits hit history to:

```text
history_len
```

so old observations can disappear.

---

### Line 95
```python
"final_pri": sched.pri_estimate[RADAR_BAND],
```

Final estimated PRI.

Could be:

```text
12.0
```

or:

```text
None
```

---

### Line 96
```python
"final_confidence": sched.confidence[RADAR_BAND],
```

Final PRI confidence.

The lock-on threshold being examined is:

$$
0.75
$$

---

### Line 97
```python
"log": sched.log,
```

Returns complete instrumentation history.

---

### Line 98
```python
"radar_capture_pct":
    hits_on_band5_post / actual_pulses_post
    if actual_pulses_post else 0.0,
```

Calculates post-warmup radar capture:

$$
\boxed{
\frac{\text{captured radar ON events}}
{\text{all actual radar ON events}}
}
$$

If there were no radar pulses, returns 0 instead of dividing by zero.

---

# Lines 102–114 — `main()` theory check

### Line 102
```python
def main():
```

Starts diagnostic program.

---

### Lines 103–104

Prints experiment parameters:

```text
radar band = 5
true PRI = 12
warmup = 800
total = 4000
seeds = 40
```

---

## Lines 105–110 — Calculate expected warmup hits

This is the key mathematical argument.

### Line 105
```python
print("Theory check: warmup uses a shuffled full sweep over 8 bands each lap, "
```

During warmup, scheduler sweeps through all 8 bands.

---

### Lines 106–107

Band 5 gets approximately:

$$
\frac{800}{8}=100
$$

scans.

The code actually says approximately because scheduler warmup mechanics include the sweep behavior.

---

### Lines 107–110

Radar is ON:

$$
\frac1{12}
$$

of steps.

Therefore expected confirmed hits:

$$
100\times\frac1{12}
=
8.333...
$$

So:

$$
\boxed{E[\text{warmup hits}]\approx8.3}
$$

---

# Lines 111–114 — The actual diagnosis

The script points out:

```text
_update_pri_model requires >= 8 confirmed hits
```

But expected hits are only:

$$
8.3
$$

Therefore the threshold is sitting almost exactly at the expected value.

This creates a statistical problem.

Conceptually:

```text
Expected = 8.3
Threshold = 8

seed A → 6 hits → FAIL
seed B → 7 hits → FAIL
seed C → 8 hits → PASS
seed D → 10 hits → PASS
seed E → 5 hits → FAIL
...
```

The difference isn't necessarily due to scheduler quality.

It can simply be **random sampling variation**.

That is the central diagnosis.

---

# Lines 116–126 — Run 40 seeds

### Line 116
```python
results = [run_one(s) for s in range(1, N_SEEDS + 1)]
```

List comprehension.

Runs:

```text
run_one(1)
run_one(2)
...
run_one(40)
```

and stores all 40 dictionaries.

---

### Line 118
```python
hits_warmup_vals = [r["hits_warmup"] for r in results]
```

Extracts warmup hit counts.

Example:

```text
[6, 9, 7, 12, 8, ...]
```

---

### Line 119
```python
scans_warmup_vals = [r["scans_warmup"] for r in results]
```

Extracts warmup scan counts.

---

### Lines 120–122

Print:

- mean;
- standard deviation;
- minimum;
- maximum.

This tells us how variable warmup sampling actually is.

---

### Lines 123–124

Print average number of scans of band 5.

Expected:

$$
800/8=100
$$

---

### Line 125
```python
below_8 = sum(1 for h in hits_warmup_vals if h < 8)
```

Counts how many seeds had:

$$
h<8
$$

confirmed hits.

Python expression:

```python
1 for h in ...
```

contributes 1 whenever condition is true.

Then `sum()` counts them.

---

### Line 126

Prints:

```text
seeds with < 8 confirmed hits
```

This directly tests whether warmup frequently fails to cross the threshold.

---

# Lines 128–131 — Define lock-on vs failure

### Line 128
```python
locked = [
    r for r in results
    if r["final_confidence"] >= 0.75
]
```

A seed is classified as **locked** if final confidence is at least:

$$
0.75
$$

---

### Line 129
```python
not_locked = [
    r for r in results
    if r["final_confidence"] < 0.75
]
```

Everything below 0.75 is classified as not locked.

---

### Lines 130–131

Print counts:

```text
X/40 locked
Y/40 never locked
```

---

# Lines 133–139 — Per-seed result table

### Lines 133–134

Creates columns:

```text
seed
hits@warmup
final_hits
final_pri
confidence
radar_capture%
```

---

### Line 135
```python
print("-" * 75)
```

Separator.

---

### Line 136
```python
for r in results:
```

Process each seed.

---

### Line 137
```python
pri_s = f"{r['final_pri']:.2f}" if r['final_pri'] is not None else "None"
```

If PRI exists:

```text
12.00
```

Otherwise:

```text
None
```

This avoids trying to format `None` as a floating-point number.

---

### Lines 138–139

Print one row per seed.

A conceptual result might look like:

```text
seed | hits@warmup | final_hits | final_pri | confidence | radar_capture%
  1  |      6      |      6     | None      |    0.00    |     0.0%
  2  |     10      |     30     | 12.00     |    0.94    |    92.0%
```

This makes the seed sensitivity immediately visible.

---

# Lines 141–153 — When did lock-on occur?

This section asks an excellent follow-up question.

Maybe a seed gets fewer than 8 hits during warmup but eventually gets enough hits later.

If so, the problem isn't necessarily:

> warmup alone is insufficient.

It could be:

> post-warmup exploration happens to rescue lucky seeds.

---

### Lines 141–144

The comments state the hypothesis:

If lock-on occurs much later than:

$$
t=800
$$

then the warmup itself isn't the entire story.

---

### Line 145
```python
print("\nFor seeds that DID lock on ...")
```

Print heading.

---

### Line 147
```python
for r in locked:
```

Only inspect successful seeds.

---

### Line 148
```python
first_lock = next(
    (e for e in r["log"] if e["confidence"] >= 0.75),
    None
)
```

This is a dense but useful Python expression.

It searches the scheduler log for the **first event** where:

$$
confidence\ge0.75
$$

`next(...)` returns the first matching entry.

If none exists:

```text
None
```

---

### Line 149
```python
if first_lock:
```

Only print if a matching log entry was found.

---

### Lines 150–152

Print:

- seed;
- first lock time;
- whether it happened during warmup;
- if after warmup, how far after;
- number of hits at that point.

For example:

```text
seed 7: first locked at t=812
(AFTER warmup, delta=12)
n_hits at that point = 8
```

That would strongly suggest post-warmup exploration supplied the final required hit.

---

# Lines 154–165 — What happened to failed seeds?

Now the script investigates failures.

### Lines 154–155

The comments define two possible failure types:

### Failure A

Not enough hits:

```text
never reached 8
```

### Failure B

Enough hits, but bad periodicity estimate:

```text
candidate PRI wrong
or
RMSE too high
or
confidence never reached 0.75
```

This distinction is scientifically important.

---

### Line 156
```python
print("\nFor seeds that NEVER locked on, what happened instead?")
```

Print heading.

---

### Line 157
```python
for r in not_locked:
```

Process failed seeds.

---

### Line 158
```python
if not r["log"]:
```

If scheduler never called `_update_pri_model()` successfully enough to produce a log entry...

---

### Lines 159–160

Print:

```text
never reached 8 confirmed hits at all
```

and final count.

This is strong evidence for **insufficient exploration**.

---

### Line 161
```python
else:
```

The seed did generate at least one PRI-model attempt.

---

### Line 162
```python
best = max(r["log"], key=lambda e: e["confidence"])
```

Finds log entry with **highest confidence**.

`lambda e: e["confidence"]` tells `max()` what value to compare.

So:

```text
log:
confidence .30
confidence .62
confidence .48
confidence .71
```

produces the `.71` entry.

---

### Lines 163–165

Print:

- best confidence;
- PRI estimate at that point;
- time;
- number of hits;
- final history count.

This tells whether failure was:

```text
not enough data
```

or:

```text
data existed, but model never became sufficiently confident
```

---

# Lines 168–169 — Entry point

### Line 168
```python
if __name__ == "__main__":
```

Run only when executed directly.

---

### Line 169
```python
main()
```

Starts the experiment.

---

# The diagnosis this file is designed to establish

The most important chain is:

```text
Warmup = 800 steps
       ↓
8 bands
       ↓
~100 scans of band 5
       ↓
Radar active 1/12 of time
       ↓
Expected hits ≈ 8.3
       ↓
PRI model requires ≥ 8 hits
       ↓
threshold ≈ expected value
       ↓
ordinary random variation decides whether threshold is crossed
       ↓
if crossed:
    PRI model appears
    confidence rises
    scheduler favors radar
    more hits arrive
    lock-on reinforces itself

if NOT crossed:
    no PRI model
    band remains low priority
    few post-warmup scans
    few additional hits
    never reaches threshold
```

That final feedback loop is the actual **lock-on failure**.

It is effectively a **rich-get-richer problem**:

```text
early lucky sampling
       ↓
PRI discovered
       ↓
more scans
       ↓
more hits
       ↓
stronger PRI confidence
       ↓
even more scans
```

versus:

```text
early unlucky sampling
       ↓
PRI not discovered
       ↓
few scans
       ↓
few hits
       ↓
PRI still not discovered
       ↓
few scans forever
```

And this diagnosis is exactly what motivates **`scan_scheduler_v4_persistent.py`**, which we already examined: V4 adds a persistent characterization bonus based on **lifetime confirmed hits**, so a band with 6 hits after warmup still gets pushed toward the remaining 2 required hits instead of being considered "already explored" merely because it was scanned 100 times.

---

**Next: `multi_seed_robustness.py` — 412 lines.** This is a much larger experiment harness. It systematically compares schedulers across many random seeds and produces the CSV results that later diagnostic/fix scripts use.

# `multi_seed_robustness.py` — line-by-line explanation

This is the **main robustness-testing harness** in project.

Its purpose is not to introduce a new scheduler. It takes schedulers already built in earlier files and asks:

> **Do claimed improvements still hold across many random seeds, or did earlier results happen because one particular random seed was lucky?**

It tests six suites:

```text
A → original V1 prototype
B → V2 multi-channel
C → V3 beacon + PRI
D → V3 sparse fixed-PRI radar
E → synthetic PDW/Turing-style data
F → V4 PersistentPRIAware fix
```

It also writes every raw per-seed result to a CSV.

---

# Lines 1–28 — Module documentation

### Line 1
```python
"""
```

Starts module-level docstring.

---

### Line 2
```text
multi_seed_robustness.py
```

Documents filename.

### Line 3
```text
=========================
```

Formatting separator.

---

### Lines 4–8

These lines explain the primary purpose:

The script reruns comparisons from:

- `scan_scheduler_prototype.py`
- `scan_scheduler_v2.py`
- `scan_scheduler_v3_pri.py`
- `run_on_turing_dataset.py`

across multiple seeds.

Instead of reporting:

```text
one result
```

it reports:

```text
mean
standard deviation
minimum
maximum
paired win count
```

for each scheduler.

The quantity being summarized is the scheduler's:

```python
interception_ratio
```

---

### Lines 10–16

These lines explain **why multiple seeds matter**.

Earlier claims such as:

```text
BeliefUCB > RoundRobin
PRIAware captures 100% sparse radar
fractional-PRI fix works
```

may have come from one seeded experiment.

A single random seed can accidentally produce favorable:

- emitter behavior;
- exploration decisions;
- pulse timing.

Therefore:

$$
\text{single run} \neq \text{proof of robustness}
$$

The script empirically tests whether effects survive across seeds.

---

### Lines 18–23 — Seeding design

This is an important methodological detail.

The existing scripts do:

```text
random.seed(seed)
        ↓
scheduler A
        ↓
scheduler B
        ↓
scheduler C
```

without resetting the RNG before every scheduler.

So the global random stream continuously advances.

This file intentionally reproduces that behavior.

Why?

Because changing the seeding convention could make the multi-seed results **not directly comparable** with the original single-seed experiments.

---

### Lines 25–27

Examples of running the program:

```bash
python3 multi_seed_robustness.py
```

Default number of seeds is 10.

Or:

```bash
python3 multi_seed_robustness.py --seeds 20
```

Run 20 seeds.

Or:

```bash
python3 multi_seed_robustness.py --seeds 10 --seed-start 100
```

Run:

```text
100,101,...,109
```

---

### Line 28
```python
"""
```

Ends module docstring.

---

# Lines 30–33 — Imports

### Line 30
```python
import argparse
```

Used for command-line arguments.

---

### Line 31
```python
import random
```

Used to seed Python's global random-number generator.

---

### Line 32
```python
import statistics
```

Used for:

- mean;
- standard deviation.

---

### Line 33
```python
from typing import Callable, Dict, List
```

Imports type-hinting names.

`Dict` and `List` are used.

`Callable` is imported but not actually used later.

---

# Lines 35–41 — V1 imports

### Lines 35–41

```python
from scan_scheduler_prototype import (
    RoundRobinScheduler as V1RoundRobin,
    RandomScheduler as V1Random,
    BeliefScheduler,
    run_episode as run_episode_v1,
    make_scenario,
)
```

Imports V1 components.

### `V1RoundRobin`

Aliases V1's `RoundRobinScheduler`.

The alias prevents confusion with V2's RoundRobin.

---

### `V1Random`

Same idea for V1 Random.

---

### `BeliefScheduler`

V1 learned scheduler.

---

### `run_episode_v1`

V1's episode runner.

Again, alias distinguishes it from V2 `run_episode`.

---

### `make_scenario`

Creates original beacon/communication/agile scenario.

---

# Lines 42–47 — V2 imports

### Line 42
```python
from scan_scheduler_v2 import (
```

Starts V2 imports.

### Lines 43–45

Imports:

```text
RoundRobinScheduler
RandomScheduler
BeliefUCBScheduler
```

These are V2 schedulers.

---

### Line 46
```python
run_episode
```

V2 episode runner.

---

### Line 47
```python
)
```

Closes import list.

---

# Lines 48–51 — V3/V4/PDW imports

### Line 48
```python
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
```

Imports:

- PRI-aware scheduler;
- sparse radar scenario.

---

### Line 49
```python
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
```

Imports V4's fixed scheduler.

---

### Line 50
```python
from pdw_loader import generate_synthetic_pdw_stream
```

Imports synthetic PDW generator.

---

### Line 51
```python
from pdw_environment import PDWReplayEnvironment
```

Imports environment that converts PDWs into band/time observations.

---

# Lines 54–56 — Section heading

Comments only.

They label the upcoming helper functions as:

```text
Stats helpers
```

No executable behavior.

---

# Lines 58–66 — `summarize()`

### Line 58
```python
def summarize(values: List[float]) -> Dict:
```

Defines function taking list of floating-point values.

Example:

```python
[0.42, 0.51, 0.47, 0.60]
```

---

### Line 59
```python
n = len(values)
```

Counts observations.

---

### Lines 60–66
```python
return {
    "n": n,
    "mean": statistics.mean(values),
    "stdev": statistics.stdev(values) if n > 1 else 0.0,
    "min": min(values),
    "max": max(values),
}
```

Returns dictionary containing five statistics.

### `"n"`

Number of observations.

### `"mean"`

Arithmetic mean:

$$
\bar{x}=\frac{\sum x_i}{n}
$$

### `"stdev"`

Sample standard deviation.

The conditional:

```python
if n > 1 else 0.0
```

prevents `statistics.stdev()` from failing when only one value exists.

### `"min"`

Smallest value.

### `"max"`

Largest value.

---

# Lines 69–78 — `print_summary_table()`

### Line 69
```python
def print_summary_table(title: str, summaries: Dict[str, Dict], unit: str = "%", scale: float = 100.0):
```

Function prints formatted statistical table.

Arguments:

- `title`
- scheduler summaries
- display unit
- scaling factor.

Default:

```text
ratio 0.75 → 75.0%
```

because scale = 100.

---

### Line 70
```python
print(f"\n{title}")
```

Prints title with blank line first.

---

### Line 71
```python
header = f"{'Scheduler':42s} | {'mean +/- stdev':>18s} | {'min':>8s} | {'max':>8s}"
```

Builds table header.

`42s` means scheduler name occupies width 42.

`>18s` right-aligns the mean/stdev heading.

---

### Line 72
```python
print(header)
```

Prints header.

---

### Line 73
```python
print("-" * len(header))
```

Creates separator exactly as wide as header.

---

### Line 74
```python
for name, s in summaries.items():
```

Iterates over:

```text
scheduler name
summary dictionary
```

---

### Line 75
```python
mean_s = f"{s['mean']*scale:5.1f}{unit}"
```

Converts mean ratio into display form.

Example:

```text
0.8734
```

becomes:

```text
87.3%
```

---

### Line 76
```python
stdev_s = f"{s['stdev']*scale:4.1f}{unit}"
```

Same for standard deviation.

---

### Lines 77–78

Print one formatted row:

```text
Scheduler | mean +/- stdev | min | max
```

The `pp` style isn't used here; this is percentage formatting.

---

# Lines 81–88 — `paired_delta()`

### Line 81
```python
def paired_delta(a_vals: List[float], b_vals: List[float]) -> Dict:
```

Defines comparison function.

It compares scheduler A against scheduler B **seed by seed**.

---

### Line 82
```python
"""a - b, per seed (paired, since both used the same seed sequence)."""
```

Function documentation.

---

### Line 83
```python
diffs = [a - b for a, b in zip(a_vals, b_vals)]
```

For every corresponding seed:

$$
d_i=A_i-B_i
$$

Example:

```text
A = [0.8, 0.6, 0.9]
B = [0.7, 0.65, 0.8]
```

produces:

```text
[+0.1, -0.05, +0.1]
```

---

### Line 84
```python
wins = sum(1 for d in diffs if d > 0)
```

Counts how many seeds had:

$$
A>B
$$

A tie doesn't count as a win.

---

### Line 85
```python
s = summarize(diffs)
```

Calculates mean delta, standard deviation, min, max.

---

### Line 86
```python
s["wins"] = wins
```

Adds number of winning seeds.

---

### Line 87
```python
s["n_seeds"] = len(diffs)
```

Adds total number of paired comparisons.

---

### Line 88
```python
return s
```

Returns statistics.

---

# Lines 91–94 — `print_delta()`

### Line 91
```python
def print_delta(label: str, delta: Dict, scale: float = 100.0):
```

Prints comparison between two schedulers.

---

### Line 92
```python
print(f"  {label:46s}: {delta['mean']*scale:+5.1f}pp +/- {delta['stdev']*scale:4.1f}pp "
```

Displays mean difference in **percentage points**.

If:

$$
A=80\%,\quad B=70\%
$$

then:

$$
A-B=+10\text{ percentage points}
$$

This is `pp`, not percent-relative improvement.

---

### Line 93
```python
f"  (min {delta['min']*scale:+5.1f}pp, max {delta['max']*scale:+5.1f}pp)  "
```

Displays smallest and largest per-seed difference.

---

### Line 94
```python
f"-- won in {delta['wins']}/{delta['n_seeds']} seeds")
```

Shows how many seeds A beat B.

---

# Suite A — Lines 97–120

## Original V1 prototype

### Lines 97–99

Section comments identifying Suite A.

---

### Line 101
```python
def suite_a_prototype(seeds: List[int], n_bands: int = 8, n_steps: int = 4000):
```

Runs V1 experiment.

Defaults:

```text
8 bands
4000 steps
```

---

### Line 102
```python
scenario = make_scenario(n_bands)
```

Creates original scenario factory.

---

### Lines 103–107
```python
builders = {
    "RoundRobin (open-loop)": lambda: V1RoundRobin(n_bands),
    "Random (naive)": lambda: V1Random(n_bands),
    "BeliefScheduler (learned)": lambda: BeliefScheduler(n_bands, epsilon=0.08),
}
```

Dictionary maps display names to scheduler constructors.

Why lambdas?

Because schedulers need to be freshly constructed for every comparison.

`BeliefScheduler` uses:

```text
epsilon = 0.08
```

for exploration.

---

### Line 108
```python
raw: Dict[str, List[float]] = {name: [] for name in builders}
```

Creates:

```python
{
    "RoundRobin...": [],
    "Random...": [],
    "Belief...": []
}
```

Each list will contain one result per seed.

---

### Line 109
```python
for seed in seeds:
```

Iterate through requested seeds.

---

### Line 110
```python
random.seed(seed)
```

Reset global random stream once per seed.

---

### Line 111
```python
for name, build in builders.items():
```

Run every scheduler for that seed.

---

### Line 112
```python
stats = run_episode_v1(scenario, build(), n_steps, n_bands)
```

Creates fresh scheduler with:

```python
build()
```

and runs V1 simulation.

---

### Line 113
```python
raw[name].append(stats.report()["interception_ratio"])
```

Extracts interception ratio and stores it.

---

### Lines 115–117

Prints summary table for Suite A.

The title includes:

- number of seeds;
- number of simulation steps.

---

### Lines 118–119

Computes and prints:

$$
\text{BeliefScheduler}-\text{RoundRobin}
$$

using paired seed results.

---

### Line 120
```python
return raw
```

Returns raw values so caller can export them.

---

# Suite B — Lines 123–148

## V2 multi-channel comparison

### Lines 123–125

Comments identify Suite B.

---

### Line 127
```python
def suite_b_multichannel(seeds: List[int], n_bands: int = 8, n_steps: int = 4000):
```

Runs V2 experiment.

---

### Line 128
```python
scenario = make_scenario(n_bands)
```

Creates scenario factory.

---

### Line 129
```python
all_raw = {}
```

Will eventually contain separate raw results for:

```text
k=1
k=2
k=3
```

---

### Line 130
```python
for k in (1, 2, 3):
```

Tests three simultaneous channels.

---

### Lines 131–135

Creates three V2 schedulers:

```text
RoundRobin
Random
BeliefUCB
```

BeliefUCB uses:

```text
ucb_c = 0.5
```

---

### Line 136
```python
raw: Dict[str, List[float]] = {name: [] for name in builders}
```

Creates fresh result lists for this `k`.

---

### Line 137
```python
for seed in seeds:
```

Loop through seeds.

---

### Line 138
```python
random.seed(seed)
```

Reset RNG once per seed.

---

### Line 139
```python
for name, build in builders.items():
```

Run all three schedulers.

---

### Line 140
```python
stats = run_episode(scenario, build(), n_steps, n_bands, k_channels=k)
```

Runs V2 simulation with:

```text
k_channels = 1, 2, or 3
```

---

### Line 141
```python
raw[name].append(stats.report()["interception_ratio"])
```

Store interception ratio.

---

### Lines 142–144

Print summary for current `k`.

---

### Lines 145–146

Calculate:

$$
\text{BeliefUCB}-\text{RoundRobin}
$$

paired across seeds.

---

### Line 147
```python
all_raw[k] = raw
```

Store current results under:

```python
all_raw[1]
all_raw[2]
all_raw[3]
```

---

### Line 148
```python
return all_raw
```

Return all V2 results.

---

# Suite C — Lines 151–176

## Beacon scenario: V3 PRI-aware scheduler

### Lines 151–153

Comments identify Suite C.

---

### Line 155
```python
def suite_c_beacon(seeds: List[int], n_bands: int = 8, n_steps: int = 4000):
```

Runs beacon experiment.

---

### Line 156
```python
scenario = make_scenario(n_bands)
```

Uses original beacon scenario.

---

### Line 157
```python
all_raw = {}
```

Results grouped by `k`.

---

### Line 158
```python
for k in (1, 2):
```

Tests one and two channels.

---

### Lines 159–163

Creates:

```text
RoundRobin
BeliefUCB
PRIAware
```

PRIAware is configured with:

```text
ucb_c = 0.5
```

---

### Line 164
```python
raw: Dict[str, List[float]] = {name: [] for name in builders}
```

Empty result lists.

---

### Line 165
```python
for seed in seeds:
```

Each seed.

---

### Line 166
```python
random.seed(seed)
```

Reset RNG.

---

### Line 167
```python
for name, build in builders.items():
```

Each scheduler.

---

### Line 168
```python
stats = run_episode(scenario, build(), n_steps, n_bands, k_channels=k)
```

Run experiment.

---

### Line 169
```python
raw[name].append(stats.report()["interception_ratio"])
```

Save interception ratio.

---

### Lines 170–172

Print summary table.

---

### Lines 173–174

Compare:

$$
\boxed{\text{PRIAware}-\text{BeliefUCB}}
$$

---

### Line 175
```python
all_raw[k] = raw
```

Save current channel-count result.

---

### Line 176
```python
return all_raw
```

Return both `k=1` and `k=2`.

---

# Suite D — Lines 179–249

## Sparse fixed-PRI radar

This is one of the most important suites because it exposes the seed-sensitive lock-on bug.

---

### Lines 179–181

Comments explain:

- sparse fixed-PRI radar;
- per-emitter capture;
- V3 PRIAware.

---

### Line 183
```python
def suite_d_sparse(seeds: List[int], n_bands: int = 8, n_steps: int = 4000, warmup: int = 800):
```

Defaults:

```text
8 bands
4000 steps
800-step warmup
```

---

### Line 184
```python
scenario = make_sparse_scenario(n_bands)
```

Creates sparse radar scenario.

Radar:

```text
band 5
PRI 12
single-step pulse
```

---

### Line 185
```python
all_raw = {}
```

Results dictionary.

---

### Line 186
```python
for k in (1, 2):
```

Tests one and two simultaneous channels.

---

### Lines 187–191

Builds:

```text
RoundRobin
BeliefUCB
PRIAware
```

Both learned schedulers receive:

```text
warmup_steps=800
```

This is important because lock-on depends on warmup characterization.

---

### Line 192
```python
raw: Dict[str, List[float]] = {name: [] for name in builders}
```

Initialize result lists.

---

### Line 193
```python
for seed in seeds:
```

Iterate seeds.

---

### Line 194
```python
random.seed(seed)
```

Seed global RNG.

---

### Line 195
```python
for name, build in builders.items():
```

Run each scheduler.

---

### Line 196
```python
stats = run_episode(scenario, build(), n_steps, n_bands, k_channels=k)
```

Run sparse scenario.

---

### Line 197
```python
raw[name].append(stats.report()["interception_ratio"])
```

Save blended interception ratio.

---

### Lines 198–200

Print summary table for current `k`.

---

### Lines 201–202

Compare:

$$
\text{PRIAware}-\text{BeliefUCB}
$$

---

### Line 203
```python
all_raw[k] = raw
```

Store result.

---

### Line 204
```python
return all_raw
```

Return both channel-count results.

---

# Suite D continued — per-emitter measurement

### Lines 206–207

Comments explain why another metric is needed.

A blended interception ratio can hide which emitter is actually being captured.

For example:

```text
Radar capture = 100%
Communication capture = 20%
```

could produce an apparently good aggregate result.

Therefore this section measures individual emitters.

---

### Line 209
```python
def per_emitter_capture(sched_cls, seed):
```

Nested helper.

It takes:

- scheduler class;
- random seed.

---

### Line 210
```python
random.seed(seed)
```

Reset RNG.

---

### Line 211
```python
sched = sched_cls(n_bands, ucb_c=0.5, warmup_steps=warmup)
```

Create scheduler.

---

### Line 212
```python
env = scenario()
```

Create fresh environment.

---

### Line 213
```python
radar_pulses = radar_caught = 0
```

Initialize radar counters.

Python allows chained assignment.

---

### Line 214
```python
comm1_on = comm1_caught = 0
```

Initialize communication-band counters.

---

### Line 215
```python
for t in range(n_steps):
```

Run complete episode.

---

### Line 216
```python
status = env.step()
```

Get current ON/OFF state.

---

### Line 217
```python
bands = sched.choose_bands(1)
```

Only one channel.

---

### Lines 218–219
```python
for b in bands:
    sched.update(b, status[b])
```

Give scheduler selected-band observation.

---

### Line 220
```python
if t > warmup:
```

Only measure emitter capture after warmup.

Note carefully:

```text
t > 800
```

means timestep 800 itself is excluded.

This is slightly different from:

```python
t >= warmup
```

---

### Line 221
```python
if status[5]:
```

Radar is actually transmitting.

---

### Line 222
```python
radar_pulses += 1
```

Count radar opportunity.

---

### Line 223
```python
if 5 in bands:
```

Did scheduler scan radar band?

---

### Line 224
```python
radar_caught += 1
```

Yes → successful interception.

---

### Line 225
```python
if status[1]:
```

Check communication emitter on band 1.

---

### Line 226
```python
comm1_on += 1
```

Count communication opportunity.

---

### Line 227
```python
if 1 in bands:
```

Did scheduler scan band 1?

---

### Line 228
```python
comm1_caught += 1
```

Count successful communication capture.

---

### Line 229
```python
radar_pct = radar_caught / radar_pulses if radar_pulses else 0.0
```

Calculate radar capture:

$$
\frac{\text{radar caught}}
{\text{radar opportunities}}
$$

---

### Line 230
```python
comm1_pct = comm1_caught / comm1_on if comm1_on else 0.0
```

Same for communication emitter.

---

### Line 231
```python
return radar_pct, comm1_pct
```

Return both rates.

---

# Lines 232–249 — Aggregate per-emitter results

### Line 232
```python
radar_raw: Dict[str, List[float]] = {"BeliefUCB": [], "PRIAware": []}
```

Stores radar capture by seed.

---

### Line 233
```python
comm1_raw: Dict[str, List[float]] = {"BeliefUCB": [], "PRIAware": []}
```

Stores communication capture.

---

### Line 234
```python
for seed in seeds:
```

Each seed.

---

### Line 235
```python
for name, cls in [("BeliefUCB", BeliefUCBScheduler), ("PRIAware", PRIAwareScheduler)]:
```

Only compares two learned schedulers here.

---

### Line 236
```python
radar_pct, comm1_pct = per_emitter_capture(cls, seed)
```

Run experiment.

---

### Lines 237–238

Append radar and communication percentages to corresponding lists.

---

### Lines 240–241

Print heading explaining that this is the metric that actually reveals the sparse-radar behavior.

---

### Line 242

Print radar capture summary.

---

### Line 243

Print communication capture summary.

---

### Line 244

Calculate:

$$
\text{PRIAware radar capture}
-
\text{BeliefUCB radar capture}
$$

---

### Lines 245–246

Calculate communication difference:

$$
\text{PRIAware comm capture}
-
\text{BeliefUCB comm capture}
$$

This is described as the **expected cost** of favoring radar.

---

### Lines 247–248

Add the two result dictionaries to `all_raw`.

---

### Line 249
```python
return all_raw
```

Returns Suite D results.

---

# Suite F — Lines 252–303

Interesting ordering: **Suite F appears before Suite E in the source**, even though E is later.

The labels aren't executed in alphabetical order.

Suite F tests the V4 fix.

---

### Lines 252–257

Comments explain:

Compare:

```text
original PRIAware
vs
PersistentPRIAware
```

on sparse radar.

The specific bug being tested is the seed-sensitive lock-on bug discovered in Suite D.

---

### Line 259
```python
def suite_f_persistent_fix(seeds: List[int], n_bands: int = 8, n_steps: int = 4000, warmup: int = 800):
```

Defines fix-validation experiment.

---

### Line 260
```python
scenario = make_sparse_scenario(n_bands)
```

Same sparse scenario as Suite D.

This is important: fix is evaluated under identical conditions.

---

## Nested `per_emitter_capture()`

### Line 262
```python
def per_emitter_capture(sched_cls, seed):
```

Same general measurement idea as Suite D.

---

### Line 263
```python
random.seed(seed)
```

Seed RNG.

---

### Line 264
```python
sched = sched_cls(n_bands, ucb_c=0.5, warmup_steps=warmup)
```

Create either:

```text
PRIAwareScheduler
```

or:

```text
PersistentPRIAwareScheduler
```

---

### Line 265
```python
env = scenario()
```

Fresh environment.

---

### Lines 266–267

Initialize radar and communication counters.

---

### Line 268
```python
for t in range(n_steps):
```

Run all timesteps.

---

### Line 269
```python
status = env.step()
```

Current environment status.

---

### Line 270
```python
bands = sched.choose_bands(1)
```

One-channel scanning.

---

### Lines 271–272

Update scheduler with observations from selected band.

---

### Line 273
```python
if t > warmup:
```

Only count capture after warmup.

Again, timestep 800 is excluded.

---

### Lines 274–277

If radar band 5 is active:

1. count pulse;
2. if scheduler selected band 5, count successful catch.

---

### Lines 278–281

Exactly same logic for communication band 1.

---

### Line 282
```python
radar_pct = radar_caught / radar_pulses if radar_pulses else 0.0
```

Radar capture percentage.

---

### Line 283
```python
comm1_pct = comm1_caught / comm1_on if comm1_on else 0.0
```

Communication capture percentage.

---

### Line 284
```python
return radar_pct, comm1_pct
```

Return both.

---

# Lines 286–293 — Run original vs fixed

### Line 286
```python
radar_raw: Dict[str, List[float]] = {"PRIAware (original)": [], "Persistent (fixed)": []}
```

Two result buckets.

---

### Line 287
```python
comm1_raw: Dict[str, List[float]] = {"PRIAware (original)": [], "Persistent (fixed)": []}
```

Same for communication.

---

### Line 288
```python
for seed in seeds:
```

Every seed.

---

### Lines 289–290

Create two scheduler choices:

```text
original → PRIAwareScheduler
fixed → PersistentPRIAwareScheduler
```

---

### Line 291
```python
radar_pct, comm1_pct = per_emitter_capture(cls, seed)
```

Run each.

---

### Lines 292–293

Store radar and communication capture.

---

# Lines 295–303 — Report V4 fix

### Lines 295–296

Print fix-validation heading.

---

### Line 297

Print radar capture statistics.

---

### Line 298

Print communication capture statistics.

---

### Line 299
```python
orig_locked = sum(1 for v in radar_raw["PRIAware (original)"] if v > 0.5)
```

Counts seeds where original PRIAware captured:

$$
>50\%
$$

of radar pulses.

This is an operational definition of "locked."

---

### Line 300
```python
fixed_locked = sum(1 for v in radar_raw["Persistent (fixed)"] if v > 0.5)
```

Same for fixed scheduler.

---

### Lines 301–302

Print:

```text
Seeds with radar capture > 50%:
original X/N
fixed Y/N
```

This is a very useful robustness measure.

---

### Line 303
```python
return {"radar": radar_raw, "comm1": comm1_raw}
```

Returns both categories.

---

# Suite E — Lines 306–341

## Synthetic Turing/PDW dataset

### Lines 306–308

Comments identify this suite.

---

### Line 310
```python
def suite_e_turing(seeds: List[int], n_bands: int = 8, dwell_us: float = 200.0):
```

Runs scheduler comparison on synthetic PDW data.

Dwell:

$$
200\ \mu s
$$

---

### Lines 311–316

Creates four schedulers:

```text
RoundRobin
Random
BeliefUCB
PRIAware
```

---

### Line 317
```python
raw: Dict[str, List[float]] = {name: [] for name in builders}
```

Empty results.

---

### Line 318
```python
for seed in seeds:
```

Every seed.

---

### Lines 319–321

Important comment:

Each seed generates a **different synthetic PDW stream**.

Therefore this experiment varies two things:

```text
scenario realization
+
scheduler exploration randomness
```

This is stronger than merely changing scheduler randomness against an identical environment.

---

### Line 322
```python
pdw = generate_synthetic_pdw_stream(seed=seed)
```

Generate synthetic pulse train using current seed.

---

### Line 324
```python
def env_factory(pdw=pdw):
```

Defines factory function.

Default argument:

```python
pdw=pdw
```

captures the current generated PDW object.

---

### Line 325
```python
return PDWReplayEnvironment(pdw, n_bands=n_bands, dwell_us=dwell_us)
```

Every call creates a fresh replay environment.

That ensures each scheduler begins at time zero.

---

### Line 327
```python
n_steps = env_factory().n_steps
```

Creates temporary environment and reads number of available timesteps.

---

### Line 328
```python
random.seed(seed)
```

Seed scheduler/exploration randomness.

---

### Line 329
```python
for name, build in builders.items():
```

Each scheduler.

---

### Line 330
```python
stats = run_episode(env_factory, build(), n_steps, n_bands, k_channels=1)
```

Run one-channel scheduler against same PDW stream.

---

### Line 331
```python
raw[name].append(stats.report()["interception_ratio"])
```

Store interception ratio.

---

### Lines 333–336

Print summary for PDW experiment.

It reports:

- dwell time;
- number of seeds;
- fact that each seed has different synthetic pulse stream.

---

### Lines 337–338

Compare:

$$
\text{BeliefUCB}-\text{RoundRobin}
$$

---

### Lines 339–340

Compare:

$$
\text{PRIAware}-\text{BeliefUCB}
$$

---

### Line 341
```python
return raw
```

Return results.

---

# CSV export — Lines 344–358

## `write_csv()`

### Lines 344–346

Comments introduce CSV export.

Purpose:

> Preserve raw per-seed data so someone can perform further analysis later.

---

### Line 348
```python
def write_csv(path: str, suite_label: str, raw: Dict[str, List[float]], seeds: List[int]):
```

Arguments:

- destination path;
- suite name;
- scheduler results;
- seed list.

---

### Line 349
```python
import csv
```

Import CSV module locally.

---

### Line 350
```python
import os
```

Import filesystem module locally.

---

### Line 351
```python
write_header = not os.path.exists(path)
```

If file doesn't exist:

```text
write_header = True
```

Otherwise:

```text
False
```

---

### Line 352
```python
with open(path, "a", newline="") as f:
```

Open file in append mode.

`newline=""` is recommended for Python CSV writing to avoid unwanted blank lines on some platforms.

---

### Line 353
```python
w = csv.writer(f)
```

Creates CSV writer.

---

### Lines 354–355

If this is a new file, write:

```text
suite
scheduler
seed
interception_ratio
```

as header.

---

### Line 356
```python
for name, vals in raw.items():
```

Each scheduler.

---

### Line 357
```python
for seed, v in zip(seeds, vals):
```

Pair:

```text
seed
result
```

by position.

---

### Line 358
```python
w.writerow([suite_label, name, seed, v])
```

Writes one CSV row.

Example:

```text
B_multichannel_k2,BeliefUCB (learned),7,0.842
```

---

# `main()` — Lines 361–408

This is the orchestration layer.

---

### Line 361
```python
def main():
```

Main program function.

---

### Line 362
```python
ap = argparse.ArgumentParser(description=__doc__)
```

Creates CLI argument parser.

The module docstring becomes command-line help description.

---

### Line 363
```python
ap.add_argument("--seeds", type=int, default=10, help="Number of seeds to run")
```

CLI:

```bash
--seeds 20
```

Default:

```text
10
```

---

### Line 364
```python
ap.add_argument("--seed-start", type=int, default=1, help="First seed value (seeds are consecutive integers)")
```

Controls first seed.

Default:

```text
1
```

---

### Line 365
```python
ap.add_argument("--csv", default="multi_seed_results.csv", help="Path to write raw per-seed CSV")
```

Controls CSV filename.

Default:

```text
multi_seed_results.csv
```

---

### Line 366
```python
args = ap.parse_args()
```

Actually parses command-line arguments.

---

### Line 368
```python
seeds = list(range(args.seed_start, args.seed_start + args.seeds))
```

Builds consecutive seed list.

For:

```text
seed-start = 10
seeds = 3
```

result:

```python
[10, 11, 12]
```

---

### Line 369
```python
print(f"Running every comparison across {len(seeds)} seeds: {seeds}\n")
```

Prints experiment configuration.

---

### Line 370
```python
print("=" * 100)
```

Large separator.

---

### Line 372
```python
import os
```

Local import.

---

### Line 373
```python
if os.path.exists(args.csv):
```

Check whether old output CSV exists.

---

### Line 374
```python
os.remove(args.csv)
```

Delete it.

This ensures each run starts with fresh CSV rather than appending duplicate old results.

---

# Execute Suite A — Lines 376–378

### Line 376
```python
raw_a = suite_a_prototype(seeds)
```

Run V1.

---

### Line 377
```python
write_csv(args.csv, "A_prototype", raw_a, seeds)
```

Write V1 results.

---

### Line 378
```python
print("\n" + "=" * 100)
```

Separator.

---

# Execute Suite B — Lines 380–383

### Line 380
```python
raw_b = suite_b_multichannel(seeds)
```

Run V2 experiments.

---

### Line 381
```python
for k, raw in raw_b.items():
```

Iterate through:

```text
k=1
k=2
k=3
```

---

### Line 382
```python
write_csv(args.csv, f"B_multichannel_k{k}", raw, seeds)
```

Write each result set.

Examples:

```text
B_multichannel_k1
B_multichannel_k2
B_multichannel_k3
```

---

### Line 383

Print separator.

---

# Execute Suite C — Lines 385–388

### Line 385
```python
raw_c = suite_c_beacon(seeds)
```

Run beacon tests.

---

### Line 386
```python
for k, raw in raw_c.items():
```

Loop through channel counts.

---

### Line 387
```python
write_csv(args.csv, f"C_beacon_k{k}", raw, seeds)
```

Write:

```text
C_beacon_k1
C_beacon_k2
```

---

### Line 388

Separator.

---

# Execute Suite D — Lines 390–393

### Line 390
```python
raw_d = suite_d_sparse(seeds)
```

Run sparse radar suite.

---

### Line 391
```python
for k, raw in raw_d.items():
```

Iterate over returned dictionary.

But remember Suite D has **two kinds of keys**:

```text
1
2
"per_emitter_radar"
"per_emitter_comm1"
```

---

### Line 392
```python
write_csv(args.csv, f"D_sparse_k{k}" if isinstance(k, int) else f"D_{k}", raw, seeds)
```

This conditional creates different labels.

If key is integer:

```text
k=1 → D_sparse_k1
k=2 → D_sparse_k2
```

If key is string:

```text
per_emitter_radar → D_per_emitter_radar
```

---

### Line 393

Separator.

---

# Execute Suite E — Lines 395–397

### Line 395
```python
raw_e = suite_e_turing(seeds)
```

Run synthetic PDW tests.

---

### Line 396
```python
write_csv(args.csv, "E_turing_pdw", raw_e, seeds)
```

Write PDW results.

---

### Line 397

Separator.

---

# Execute Suite F — Lines 399–402

### Line 399
```python
raw_f = suite_f_persistent_fix(seeds)
```

Run V4 fix comparison.

---

### Line 400
```python
write_csv(args.csv, "F_fix_radar_capture", raw_f["radar"], seeds)
```

Write radar-capture results.

---

### Line 401
```python
write_csv(args.csv, "F_fix_comm1_capture", raw_f["comm1"], seeds)
```

Write communication-capture results.

---

### Line 402

Final separator.

---

# Lines 404–408 — Final conclusion

### Line 404
```python
print(f"\nRaw per-seed results written to {args.csv}")
```

Tells user where raw results went.

---

### Lines 405–408

Prints the project's central statistical interpretation:

A scheduler comparison is more convincing when:

1. mean delta is clearly away from zero;
2. standard deviation isn't enormous relative to mean;
3. scheduler wins in most or all seeds.

In other words:

```text
Mean improvement alone
        ↓
not enough
```

You want:

```text
positive mean
+
reasonable variance
+
many paired wins
```

That is much stronger evidence of a real effect.

---

# Lines 411–412 — Program entry point

### Line 411
```python
if __name__ == "__main__":
```

Only execute `main()` when this file is run directly.

If another Python file imports it:

```python
import multi_seed_robustness
```

the experiment does **not** automatically start.

---

### Line 412
```python
main()
```

Starts the complete six-suite experiment.

---

# Overall architecture of this file

The entire program can now be seen as:

```text
                    multi_seed_robustness.py
                              │
             ┌────────────────┼────────────────┐
             │                │                │
          statistics       experiments       CSV
             │                │                │
       summarize()       Suite A–F        write_csv()
       paired_delta()
       print_summary()
       print_delta()
```

And the six experiments:

```text
A ─ V1 prototype
│
├─ RoundRobin
├─ Random
└─ BeliefScheduler

B ─ V2 multi-channel
│
├─ k=1
├─ k=2
└─ k=3
    │
    ├─ RoundRobin
    ├─ Random
    └─ BeliefUCB

C ─ V3 beacon
│
├─ k=1
└─ k=2
    │
    ├─ RoundRobin
    ├─ BeliefUCB
    └─ PRIAware

D ─ V3 sparse radar
│
├─ k=1
├─ k=2
└─ per-emitter:
    ├─ radar
    └─ comm-1

E ─ synthetic PDW
│
├─ RoundRobin
├─ Random
├─ BeliefUCB
└─ PRIAware

F ─ V4 fix
│
├─ PRIAware original
└─ PersistentPRIAware fixed
```

## One subtle but important issue

The file's comments say each scheduler comparison uses the **same continuously advancing global random stream**, and the code indeed does:

```text
random.seed(seed)
scheduler A
scheduler B
scheduler C
```

rather than:

```text
random.seed(seed)
scheduler A

random.seed(seed)
scheduler B

random.seed(seed)
scheduler C
```

So this is **paired by starting seed**, but it is not a perfectly controlled "identical random decisions" experiment. Scheduler order and how much randomness each scheduler consumes can affect later RNG states.

That distinction matters when interpreting the CSV.

## Most important result this file is designed to establish

The earlier project progression is now:

```text
single-seed experiments
        ↓
multi_seed_robustness.py
        ↓
discover seed-sensitive PRIAware lock-on
        ↓
diagnose_pri_lockon.py
        ↓
identify ≥8-hit threshold + insufficient exploration
        ↓
PersistentPRIAwareScheduler
        ↓
Suite F checks whether fix actually removes seed sensitivity
```

So this file is essentially the project's **statistical stress test**.

---

**Next file: `tune_confidence_threshold.py` — 178 lines.** This one investigates a different design question: how the PRI confidence threshold affects PRIAware's behavior and whether the chosen `0.75` threshold is sensible.

# `tune_confidence_threshold.py` — line-by-line explanation

This file is a **parameter-tuning experiment**.

It asks:

> Can we make PRIAware slightly less eager to lock onto questionable PRI patterns in the beacon scenario, **without breaking the fractional-PRI fix that works on PDW data?**

The key parameter is:

```python
confidence_scale
```

with confidence defined as:

$$
\boxed{
\text{confidence}
=
1-\frac{\text{RMSE}}
{\text{confidence\_scale}\times\text{refined\_PRI}}
}
$$

Current value:

$$
\boxed{0.25}
$$

The experiment tries:

$$
0.25,\;0.20,\;0.17,\;0.15,\;0.12,\;0.10
$$

---

# Lines 1–39 — Module documentation

### Line 1
```python
"""
```

Starts module docstring.

### Line 2
```text
tune_confidence_threshold.py
```

File name.

### Line 3
```text
===============================
```

Formatting separator.

---

### Lines 4–11

These lines describe an earlier discovery from `settle_fix_interaction.py`.

The harmonic-selection fix made PRIAware:

> lock on MORE EAGERLY

That means it can reach high confidence with less evidence.

This is good for the PDW problem, because the scheduler needs to distinguish:

```text
true fractional PRI
```

from:

```text
harmonic PRI
```

But this eagerness has a cost in the beacon scenario.

The reported cost is:

$$
-0.3\text{ percentage points}
$$

with only:

$$
2/30
$$

wins.

So the current implementation may occasionally become too enthusiastic about a beacon-like periodic pattern.

---

### Lines 13–16

These lines identify `confidence_scale` as the direct control knob.

The exact formula given is:

$$
C=1-\frac{RMSE}{S\times PRI}
$$

where:

- $C$ = confidence;
- $S$ = `confidence_scale`;
- $PRI$ = refined period.

---

### Lines 18–20

The direction of the parameter is important.

### Larger scale

Denominator becomes larger:

$$
S\uparrow
\Rightarrow
\frac{RMSE}{S\cdot PRI}\downarrow
$$

Therefore:

$$
C\uparrow
$$

So larger scale is **more forgiving / more eager**.

### Smaller scale

Denominator becomes smaller:

$$
S\downarrow
\Rightarrow C\downarrow
$$

for the same RMSE.

Therefore scheduler requires a tighter fit to achieve high confidence.

So:

```text
scale ↑ → easier lock-on
scale ↓ → harder lock-on
```

---

### Lines 20–21

The script performs a small parameter sweep.

It doesn't blindly optimize one metric.

It tests **both sides of the tradeoff**.

---

### Lines 23–26 — Test 1

Beacon scenario.

It compares:

```text
Current(scale)
vs
PlateauOnly
vs
BeliefUCB
```

at:

```text
k=1
k=2
```

The key question:

> Can lowering the scale recover the small k=2 performance loss without damaging k=1?

---

### Lines 27–30 — Test 2

PDW fractional-PRI scenario.

Band 4 has true period:

$$
32.505\text{ steps}
$$

The script wants to make sure lowering confidence scale doesn't destroy the harmonic-selection fix.

---

### Lines 32–35 — Decision principle

This is arguably the most important methodological statement in the file.

A parameter that improves beacon performance but causes PDW lock-on to fail is **not considered a successful fix**.

Why?

Because it would simply reintroduce the old problem:

```text
old coarse-tolerance selection
        ↓
too conservative
        ↓
fractional PRI often fails
```

through a different parameter.

The desired result is:

```text
Beacon behavior
     ↑ improve

PDW behavior
     = preserve
```

---

### Lines 37–38

Example commands:

```bash
python3 tune_confidence_threshold.py
```

uses defaults.

And:

```bash
python3 tune_confidence_threshold.py --beacon-seeds 30 --pdw-seeds 20
```

runs larger experiments.

---

### Line 39
```python
"""
```

Ends module docstring.

---

# Lines 41–51 — Imports

### Line 41
```python
import argparse
```

Command-line argument parsing.

---

### Line 42
```python
import random
```

Controls random seed.

---

### Line 43
```python
import statistics
```

Used for mean differences.

---

### Line 44
```python
from typing import Dict, List
```

Type annotations.

---

### Line 46
```python
from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
```

Imports:

- baseline BeliefUCB scheduler;
- V2 episode runner.

---

### Line 47
```python
from scan_scheduler_v3_pri import PRIAwareScheduler, make_scenario
```

Imports:

- scheduler under investigation;
- beacon scenario factory.

---

### Line 48
```python
from validate_plateau_fix import PlateauOnlyPRIAware
```

Imports a special PRIAware variant from a previous validation script.

`PlateauOnlyPRIAware` represents the plateau-only behavior being used as comparison.

---

### Line 49
```python
from validate_pdw_multiseed import TRUE_PERIODIC_BANDS, classify
```

Imports:

- known true periodic-band information;
- classification function.

`classify()` later labels a final PRI estimate:

```text
CORRECT
HARMONIC
NO LOCK
WRONG
```

---

### Line 50
```python
from pdw_loader import generate_synthetic_pdw_stream
```

Synthetic PDW generator.

---

### Line 51
```python
from pdw_environment import PDWReplayEnvironment
```

Converts PDW data into scheduler-compatible environment.

---

# Line 53 — Candidate values

### Line 53
```python
CANDIDATE_SCALES = [0.25, 0.20, 0.17, 0.15, 0.12, 0.10]  # 0.25 = current/original
```

Defines six values.

The first:

$$
0.25
$$

is baseline/current.

Everything after it is increasingly conservative.

---

# Lines 56–59 — Check 1 heading

Comments say this experiment follows the methodology from `settle_fix_interaction.py`.

It compares:

```text
Current(scale)
vs PlateauOnly
vs BeliefUCB
```

on identical environments.

"Identical environment" is important because we don't want scheduler A and scheduler B seeing different stochastic emitter trajectories.

---

# Lines 61–66 — `run_identical_env()`

### Line 61
```python
def run_identical_env(seed, sched_cls, n_bands=8, n_steps=4000, k=2, **kw):
```

Runs one scheduler under one seed.

Arguments:

- `seed`
- scheduler class
- number of bands
- number of steps
- number of channels
- arbitrary scheduler keyword arguments.

---

### Line 62
```python
scenario = make_scenario(n_bands)
```

Creates beacon scenario factory.

---

### Line 63
```python
random.seed(seed)
```

Sets random seed.

---

### Line 64
```python
sched = sched_cls(n_bands, ucb_c=0.5, **kw)
```

Creates scheduler.

Every scheduler gets:

```text
ucb_c = 0.5
```

Additional parameters can be passed through `kw`.

For example:

```python
confidence_scale=0.15
```

---

### Line 65
```python
stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
```

Runs simulation.

Important:

`scenario` is passed as a factory, so `run_episode()` can create a fresh environment.

---

### Line 66
```python
return stats.report()["interception_ratio"]
```

Only returns the final interception ratio.

Everything else from `stats.report()` is discarded.

---

# Lines 69–87 — `beacon_check()`

### Line 69
```python
def beacon_check(scale, seeds, k):
```

Runs beacon experiment for one confidence scale and one channel count.

---

### Line 70
```python
results = {"BeliefUCB": [], "PlateauOnly": [], f"Current(scale={scale})": []}
```

Creates three result lists.

For scale `0.15`, key becomes:

```text
Current(scale=0.15)
```

---

### Line 71
```python
for seed in seeds:
```

Run every seed.

---

### Line 72
```python
results["BeliefUCB"].append(run_identical_env(seed, BeliefUCBScheduler, k=k))
```

Run BeliefUCB and store its interception ratio.

---

### Line 73
```python
results["PlateauOnly"].append(run_identical_env(seed, PlateauOnlyPRIAware, k=k))
```

Run plateau-only scheduler.

---

### Lines 74–75
```python
results[f"Current(scale={scale})"].append(
    run_identical_env(seed, PRIAwareScheduler, k=k, confidence_scale=scale))
```

Run actual PRIAware with selected confidence scale.

Example:

```python
confidence_scale=0.12
```

---

### Line 76
```python
cur = results[f"Current(scale={scale})"]
```

Short alias for current scheduler's results.

---

### Line 77
```python
plateau = results["PlateauOnly"]
```

Alias for plateau scheduler.

---

### Line 78
```python
belief = results["BeliefUCB"]
```

Alias for BeliefUCB.

---

### Line 79
```python
d_vs_plateau = [c - p for c, p in zip(cur, plateau)]
```

For each seed:

$$
d_i=C_i-P_i
$$

This is a **paired comparison**.

---

### Line 80
```python
d_vs_belief = [c - b for c, b in zip(cur, belief)]
```

Similarly:

$$
d_i=C_i-B_i
$$

---

### Lines 81–87

Returns:

```text
vs_plateau_mean
vs_plateau_wins
vs_belief_mean
vs_belief_wins
n
```

### Line 82

Mean current-minus-plateau difference, converted to percentage points.

---

### Line 83

Number of seeds where current beats plateau.

---

### Line 84

Mean current-minus-BeliefUCB difference.

---

### Line 85

Number of seeds where current beats BeliefUCB.

---

### Line 86

Number of seeds.

---

### Line 87

Return dictionary.

---

# Lines 90–93 — Check 2 heading

Comments identify second experiment:

> Does the confidence scale preserve correct fractional-PRI lock-on?

Target:

```text
PDW band 4
```

The important failure modes are:

```text
CORRECT
HARMONIC
NO LOCK
WRONG
```

---

# Lines 95–112 — `pdw_check()`

### Line 95
```python
def pdw_check(scale, seeds, n_bands=8, dwell_us=20.0, k=1):
```

Runs PDW test.

Defaults:

```text
8 bands
20 μs dwell
1 channel
```

---

### Line 96
```python
correct = harmonic = no_lock = wrong = 0
```

Initialize four counters.

Python chained assignment gives all four value `0`.

---

### Line 97
```python
for seed in seeds:
```

Each PDW seed.

---

### Line 98
```python
pdw = generate_synthetic_pdw_stream(seed=seed)
```

Generate synthetic PDW stream.

Different seeds produce different pulse streams.

---

### Line 100
```python
def env_factory(pdw=pdw):
```

Creates factory capturing current PDW.

The default argument is evaluated when this function is defined.

So current `pdw` gets retained.

---

### Line 101
```python
return PDWReplayEnvironment(pdw, n_bands=n_bands, dwell_us=dwell_us)
```

Construct fresh environment using same PDW stream.

---

### Line 103
```python
n_steps = env_factory().n_steps
```

Creates temporary environment to determine total simulation length.

---

### Line 104
```python
sched = PRIAwareScheduler(n_bands, ucb_c=0.5, confidence_scale=scale)
```

Creates PRIAware with candidate confidence scale.

---

### Line 105
```python
run_episode(env_factory, sched, n_steps, n_bands, k_channels=k)
```

Runs entire PDW experiment.

The returned statistics aren't needed here.

Why?

Because this check is about **PRI classification**, not aggregate interception percentage.

---

### Lines 106–107
```python
verdict = classify(sched.pri_estimate[4], dwell_us, TRUE_PERIODIC_BANDS[4],
                    sched.confidence[4], sched.min_confidence)
```

This is the critical classification.

Inputs:

1. estimated PRI for band 4;
2. dwell duration;
3. true periodic band-4 period;
4. final confidence;
5. scheduler's minimum confidence threshold.

`classify()` decides whether band 4's result is:

```text
CORRECT
HARMONIC
NO LOCK
WRONG
```

---

### Lines 108–111

Each Boolean expression evaluates to `True` or `False`.

In Python:

```python
True
```

acts numerically like:

$$
1
$$

and:

```python
False
```

acts like:

$$
0
$$

Therefore:

```python
correct += verdict == "CORRECT"
```

increments `correct` by one when appropriate.

Same for:

- harmonic;
- no lock;
- wrong.

---

### Line 112
```python
return {"correct": correct, "harmonic": harmonic, "no_lock": no_lock, "wrong": wrong, "n": len(seeds)}
```

Returns classification counts.

---

# Lines 115–119 — `main()` arguments

### Line 115
```python
def main():
```

Program entry function.

---

### Line 116
```python
ap = argparse.ArgumentParser(description=__doc__)
```

Create CLI parser using module docstring as description.

---

### Line 117
```python
ap.add_argument("--beacon-seeds", type=int, default=20)
```

Beacon experiment default:

$$
20\text{ seeds}
$$

---

### Line 118
```python
ap.add_argument("--pdw-seeds", type=int, default=15)
```

PDW experiment default:

$$
15\text{ seeds}
$$

---

### Line 119
```python
args = ap.parse_args()
```

Read command-line options.

---

# Lines 121–122 — Seed lists

### Line 121
```python
beacon_seeds = list(range(1, args.beacon_seeds + 1))
```

For default 20:

$$
[1,2,\ldots,20]
$$

---

### Line 122
```python
pdw_seeds = list(range(0, args.pdw_seeds))
```

For default 15:

$$
[0,1,\ldots,14]
$$

Notice deliberately different starting points:

```text
Beacon → starts at 1
PDW → starts at 0
```

---

# Lines 124–126 — Experiment description

### Line 124
```python
print(f"Sweeping confidence_scale over {CANDIDATE_SCALES}\n"
```

Print candidate values.

---

### Line 125

Print beacon methodology.

It says:

```text
20 seeds
identical-environment
k=1 and k=2
```

---

### Line 126

Print PDW methodology:

```text
15 seeds
band 4
fractional PRI
classification
```

---

# Lines 128–130 — Output table

### Line 128
```python
print(f"{'scale':>7s} | {'k=1 vs Plateau':>15s} | {'k=2 vs Plateau':>15s} | "
```

Creates first part of table header.

---

### Line 129

Adds columns:

```text
k=2 vs BeliefUCB
PDW band4 correct
PDW harmonic
PDW no-lock
```

---

### Line 130
```python
print("-" * 115)
```

Separator.

---

# Lines 132–137 — Sweep all scales

### Line 132
```python
rows = []
```

Will store results for every candidate.

---

### Line 133
```python
for scale in CANDIDATE_SCALES:
```

Test:

```text
0.25
0.20
0.17
0.15
0.12
0.10
```

---

### Line 134
```python
b1 = beacon_check(scale, beacon_seeds, k=1)
```

Beacon test, one channel.

---

### Line 135
```python
b2 = beacon_check(scale, beacon_seeds, k=2)
```

Beacon test, two channels.

---

### Line 136
```python
p = pdw_check(scale, pdw_seeds)
```

PDW fractional-PRI test.

---

### Line 137
```python
rows.append((scale, b1, b2, p))
```

Store all results together.

Each row:

```text
(scale, k1_results, k2_results, pdw_results)
```

---

# Lines 138–141 — Print each candidate

### Lines 138–141

Print one formatted row per confidence scale.

The output effectively looks like:

```text
 scale | k=1 vs Plateau | k=2 vs Plateau | k=2 vs BeliefUCB | PDW correct | harmonic | no-lock
  0.25 | ...            | ...             | ...               | ...         | ...      | ...
  0.20 | ...            | ...             | ...               | ...         | ...      | ...
```

The beacon numbers are expressed in percentage points and win counts.

The PDW values are counts out of total seeds.

---

# Lines 143–148 — What counts as "better"?

This section explicitly defines the decision criteria.

### Line 143

Introduces interpretation.

---

### Lines 144–145

For `k=2` vs Plateau:

Current baseline cost is described as approximately:

$$
-0.3pp
$$

with roughly:

$$
2\text{–}3/30
$$

wins in the larger validation.

The desired direction:

$$
\text{delta}\rightarrow0
$$

or positive.

---

### Line 146

For `k=1`, don't accept meaningful degradation.

This prevents solving the two-channel issue by breaking one-channel behavior.

---

### Lines 147–148

PDW correct-lock count must remain at least as high as baseline `0.25`.

The comment specifically references the earlier result:

```text
PlateauOnly pre-fix → 14/20
```

The harmonic fix should not be sacrificed.

---

# Lines 150–154 — Establish baseline

### Line 150
```python
baseline = rows[0]
```

First candidate is 0.25.

---

### Line 151
```python
assert baseline[0] == 0.25
```

Safety check.

If someone changes `CANDIDATE_SCALES` and puts another value first, this assertion fails.

---

### Lines 152–154

Print baseline:

- k=1 vs Plateau;
- k=2 vs Plateau;
- PDW correct count.

This gives all later candidates a reference point.

---

# Lines 156–165 — Select best candidate

### Line 156
```python
best = None
```

Initially no candidate selected.

---

### Line 157
```python
for scale, b1, b2, p in rows[1:]:
```

Skip baseline.

Only test alternatives:

```text
0.20
0.17
0.15
0.12
0.10
```

---

### Line 158
```python
improves_k2 = b2["vs_plateau_mean"] > baseline[2]["vs_plateau_mean"]
```

Candidate must have **strictly better** k=2 performance.

For example:

```text
baseline = -0.3pp
candidate = -0.1pp
```

then:

```text
True
```

---

### Line 159
```python
no_worse_k1 = b1["vs_plateau_mean"] >= baseline[1]["vs_plateau_mean"] - 0.5
```

Allows up to:

$$
0.5pp
$$

degradation at k=1.

So this is not mathematically "no worse"; it's:

> no worse than baseline by more than 0.5 percentage points.

---

### Line 160
```python
preserves_pdw = p["correct"] >= baseline[3]["correct"]
```

Candidate must retain at least as many correct PDW lock-ons.

No regression allowed.

---

### Lines 161–163

Print Boolean decision for each candidate:

```text
k=2 improves?
k=1 no-worse?
PDW preserved?
```

---

### Line 164
```python
if improves_k2 and no_worse_k1 and preserves_pdw and best is None:
```

All three conditions must hold.

And:

```python
best is None
```

means **first qualifying candidate wins**.

---

### Line 165
```python
best = scale
```

Select candidate.

Because scales are ordered from largest to smallest, this chooses the **first/least conservative** candidate satisfying all conditions.

That is a deliberate design choice.

---

# Lines 167–172 — Final decision

### Line 167
```python
if best is not None:
```

At least one candidate passed.

---

### Lines 168–169

Print selected scale and explanation:

```text
improves beacon k=2
without regression at k=1
without regression on PDW fractional PRI
```

---

### Line 170
```python
else:
```

No candidate passed all requirements.

---

### Lines 171–172

Keep:

$$
\boxed{confidence\_scale=0.25}
$$

rather than trading away PDW benefits for beacon-only improvement.

This is an important conservative engineering decision.

---

### Line 174
```python
return best
```

Returns:

- selected scale;
- or `None`.

---

# Lines 177–178 — Entry point

### Line 177
```python
if __name__ == "__main__":
```

Only execute when file is run directly.

---

### Line 178
```python
main()
```

Runs entire parameter sweep.

---

# What this file is doing mathematically

The central knob is:

$$
C=1-\frac{RMSE}{S\cdot PRI}
$$

Suppose:

$$
RMSE=1,\quad PRI=10
$$

With current:

$$
S=0.25
$$

we get:

$$
C=1-\frac{1}{0.25(10)}
$$

$$
C=1-0.4
$$

$$
\boxed{C=0.6}
$$

Now make it more conservative:

$$
S=0.10
$$

Then:

$$
C=1-\frac{1}{0.10(10)}
$$

$$
C=1-1
$$

$$
\boxed{C=0}
$$

Same fit, radically lower confidence.

So reducing `confidence_scale` makes PRIAware demand a much cleaner periodic pattern before giving it strong periodicity weight.

---

# Bigger project picture

At this point, the progression is:

```text
V3 PRIAware
    │
    ├── beacon problem
    │      ↓
    │   PRIAware can become too eager
    │
    ├── PDW problem
    │      ↓
    │   must remain eager enough to identify
    │   fractional PRI instead of harmonic
    │
    └── confidence_scale
           ↓
       possible tuning knob
           ↓
    test both scenarios
           ↓
    accept parameter only if:
       ├── beacon k=2 improves
       ├── beacon k=1 doesn't materially regress
       └── PDW correct lock-on doesn't regress
```

So this file is **not simply trying to maximize one score**. It is searching for a parameter that resolves a known tradeoff without undoing an earlier fix.

---

**Next file: `validate_offbyone_fix.py` — 166 lines.** This validates a timing-boundary correction, specifically whether an off-by-one condition changes measured capture behavior at the warmup boundary.

# `validate_offbyone_fix.py`

This file is a **validation/ablation script**. It does not introduce a new scheduler. Its job is to answer one narrow question:

> **Did adding the ±1 neighboring-period candidates to the PRI detector actually improve PRIAwareScheduler on the beacon scenario?**

It compares three schedulers under **identical random conditions**:

1. `BeliefUCB` — baseline.
2. `PreOffByOneFixPRIAware` — reconstructed **before** this session's fix.
3. `PRIAwareScheduler` — current version **with** the fix.

It does this for both `k=1` and `k=2`, across multiple seeds.

---

## Lines 1–27 — Module documentation

### Line 1
```python
"""
```

Starts a **module-level docstring**.

Everything until the next `"""` is documentation for this Python file.

---

### Line 2
```python
validate_offbyone_fix.py
```

Names the script.

This is descriptive documentation, not executable code.

---

### Line 3
```python
===========================
```

Visual separator under the filename.

No computational effect.

---

### Line 4
```python
Multi-seed, identical-environment confirmation of THIS session's fix
```

States purpose.

The script performs:

- **multi-seed testing** → more than one random seed;
- **identical-environment testing** → each scheduler gets same underlying stochastic scenario for each seed;
- confirmation of the current session's fix.

---

### Line 5
```python
(testing each candidate period's +-1 integer neighbors in
```

Describes the specific fix.

The PRI algorithm normally creates candidate periods.

The fix additionally tests:

```text
candidate - 1
candidate
candidate + 1
```

for each candidate.

The `+-1` notation means **±1**.

---

### Line 6
```python
_update_pri_model, added to scan_scheduler_v3_pri.py) on the beacon
```

The modification being tested was made inside:

```python
PRIAwareScheduler._update_pri_model()
```

in `scan_scheduler_v3_pri.py`.

That method is responsible for estimating periodicity/PRI from observed hit times.

---

### Line 7
```python
scenario -- closing the one gap flagged after that fix: it was verified
```

The beacon scenario is the test environment.

The documentation says the fix had already been tested, but there was one remaining validation gap.

---

### Line 8
```python
on 20 PDW seeds and one beacon seed, but never run through the same
```

Earlier validation apparently covered:

- 20 PDW seeds;
- only one beacon seed.

But that isn't enough for robust statistical confirmation on the beacon scenario.

---

### Line 9
```python
25-30 seed identical-environment harness every other fix in this
```

Other fixes in this project were tested with roughly 25–30 seeds under an identical-environment methodology.

This script brings the off-by-one fix into that same methodology.

---

### Line 10
```python
project got (validate_plateau_fix.py, settle_fix_interaction.py).
```

Names two related validation scripts:

```text
validate_plateau_fix.py
settle_fix_interaction.py
```

They serve as methodological precedents.

---

### Line 11
```python

```

Blank line.

No execution.

---

### Lines 12–16

```python
PreOffByOneFixPRIAware below is a reconstruction of PRIAwareScheduler
with ONLY the neighbor-expansion block removed -- everything else
(plateau fix, harmonic-selection-by-best-fit, confidence_scale)
stays exactly as shipped, so this isolates precisely the one change made
this session, the same way PlateauOnlyPRIAware isolated an earlier fix.
```

This is extremely important.

The test wants a **controlled experiment**.

`PreOffByOneFixPRIAware` is supposed to represent:

> Current PRIAware − off-by-one fix.

Everything else remains the same.

So if:

```text
Current > PreOffByOneFix
```

the difference can be attributed to the ±1 candidate expansion, assuming reconstruction is faithful.

The documentation explicitly says other behavior remains unchanged:

- plateau fix;
- harmonic selection by best fit;
- `confidence_scale`.

---

### Lines 18–23

```python
Uses the identical-environment methodology from settle_fix_interaction.py
(reset random.seed(seed) immediately before EACH scheduler's run, not
once per comparison) since that's what a clean isolated comparison on
the beacon scenario requires -- confirmed there that with warmup_steps=0
none of these schedulers consume their own randomness, so this gives
every scheduler the identical ground-truth trajectory for a given seed.
```

This explains an important experimental detail.

For each scheduler:

```python
random.seed(seed)
```

is reset immediately before running it.

Why?

Suppose scheduler A consumes random numbers before scheduler B:

```text
seed
 ↓
A consumes RNG
 ↓
B starts from altered RNG state
```

Then A and B don't necessarily experience the same stochastic trajectory.

Instead:

```text
seed → Scheduler A
seed → Scheduler B
seed → Scheduler C
```

Each starts from identical RNG state.

The documentation further states that with:

```python
warmup_steps = 0
```

these schedulers don't consume scheduler-specific randomness that would destroy this comparison.

Therefore the beacon emitter trajectory can be identical for a given seed.

---

### Lines 25–26
```python
Run: python3 validate_offbyone_fix.py
     python3 validate_offbyone_fix.py --seeds 30
```

Example command-line usage.

Default:

```bash
python3 validate_offbyone_fix.py
```

uses 30 seeds.

A value of 30 can be requested explicitly:

```bash
python3 validate_offbyone_fix.py --seeds 30
```

---

### Line 27
```python
"""
```

Ends module docstring.

---

# Lines 29–35 — Imports

### Line 29
```python
import argparse
```

Imports Python's command-line argument parser.

Used later for:

```bash
--seeds
--seed-start
```

---

### Line 30
```python
import math
```

Provides mathematical functions.

Here it is needed for:

```python
math.gcd
```

---

### Line 31
```python
import random
```

Python's pseudorandom-number generator.

Used to reset:

```python
random.seed(seed)
```

---

### Line 32
```python
import statistics
```

Provides statistical functions such as:

```python
statistics.mean()
statistics.stdev()
```

---

### Line 33
```python
from collections import Counter
```

Imports `Counter`.

A `Counter` counts occurrences of values.

For example:

```python
Counter([12, 12, 24, 36])
```

conceptually gives:

```text
12 → 2
24 → 1
36 → 1
```

Used to find the most common pairwise time difference.

---

### Line 34
```python
from functools import reduce
```

Imports `reduce`.

It repeatedly combines values using a function.

Here:

```python
reduce(math.gcd, diffs)
```

computes the GCD of all values in `diffs`.

For:

```text
[12, 24, 36]
```

it effectively computes:

```text
gcd(gcd(12,24),36)
= gcd(12,36)
= 12
```

---

### Line 35
```python
from typing import Dict, List
```

Imports type-hinting constructs.

Used later for:

```python
Dict[str, List[float]]
```

meaning approximately:

```text
dictionary:
    string → list of floats
```

---

# Lines 37–38 — Project imports

### Line 37
```python
from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
```

Imports two things from V2:

```python
BeliefUCBScheduler
```

and:

```python
run_episode
```

`BeliefUCBScheduler` is the baseline scheduler.

`run_episode` executes a scheduler against an environment/scenario and returns statistics.

---

### Line 38
```python
from scan_scheduler_v3_pri import PRIAwareScheduler, make_scenario
```

Imports:

```python
PRIAwareScheduler
```

—the current PRI-aware scheduler.

And:

```python
make_scenario
```

—the beacon scenario generator.

This is the central dependency of the validation.

---

# Lines 41–109 — Reconstructing the pre-fix scheduler

## Line 41
```python
class PreOffByOneFixPRIAware(PRIAwareScheduler):
```

Defines a new class.

It **inherits** from:

```python
PRIAwareScheduler
```

So it automatically gets all PRIAware behavior unless this class overrides something.

Only one method is overridden:

```python
_update_pri_model()
```

That is exactly what we want for an ablation.

---

### Lines 42–44
```python
"""PRIAwareScheduler as it stood at the START of this session --
candidate generation via gcd + pairwise mode + mode's small-integer
divisors, WITHOUT also testing each candidate's +-1 neighbors."""
```

Class docstring.

It describes the pre-fix candidate-generation algorithm:

1. GCD candidate;
2. pairwise-difference mode;
3. small integer divisors of mode;
4. **no ±1 neighbors**.

Thus this class models the old implementation.

---

## Line 46
```python
def _update_pri_model(self, band):
```

Defines the overridden method.

Arguments:

```python
self
```

→ scheduler object.

```python
band
```

→ band whose PRI model should be updated.

The leading `_` indicates an internal/private-style method.

---

### Line 47
```python
times = self.hit_times[band]
```

Gets observed ON/hit times for this band.

`self.hit_times` is presumably a collection indexed by band.

For example:

```text
band 5 → [0, 12, 24, 36, ...]
```

Then:

```python
times
```

contains those timestamps.

---

### Line 48
```python
if len(times) < 8:
```

Checks whether at least 8 observations exist.

The PRI detector requires a minimum amount of evidence.

---

### Line 49
```python
self.pri_estimate[band] = None
```

No reliable PRI estimate.

`None` means:

> We don't currently have a valid PRI estimate.

---

### Line 50
```python
self.confidence[band] = 0.0
```

Sets confidence to zero.

---

### Line 51
```python
return
```

Immediately exits the method.

So lines 52 onward are not executed when fewer than 8 hits exist.

---

## Line 52
```python
diffs = [times[j] - times[i] for i in range(len(times)) for j in range(i + 1, len(times))]
```

This is one of the densest lines in the file.

It computes **every pairwise positive time difference**.

Suppose:

```python
times = [10, 22, 34]
```

Pairs:

```text
22 - 10 = 12
34 - 10 = 24
34 - 22 = 12
```

So:

```python
diffs = [12, 24, 12]
```

### How the comprehension works

Outer loop:

```python
for i in range(len(times))
```

selects first timestamp.

Inner loop:

```python
for j in range(i + 1, len(times))
```

selects timestamps occurring later in the list.

Expression:

```python
times[j] - times[i]
```

computes their separation.

Because `j > i`, these differences are positive assuming `times` is chronologically ordered.

---

# Lines 54–60 — Consecutive-run detection

### Line 54
```python
max_run = 1
```

Initial maximum consecutive run length = 1.

A run means consecutive observations at adjacent timesteps:

```text
100,101,102,103
```

has run length 4.

This matters because dense consecutive ON periods can fool PRI detection.

---

### Line 55
```python
run = 1
```

Current consecutive-run length starts at 1.

---

### Line 56
```python
sorted_times = sorted(times)
```

Sorts hit timestamps chronologically.

Example:

```text
[24, 10, 12]
```

becomes:

```text
[10, 12, 24]
```

---

### Line 57
```python
for a, b in zip(sorted_times[:-1], sorted_times[1:]):
```

Iterates over adjacent timestamp pairs.

Suppose:

```python
sorted_times = [10, 11, 12, 30]
```

Then:

```python
sorted_times[:-1] = [10,11,12]
sorted_times[1:]  = [11,12,30]
```

`zip()` pairs them:

```text
(10,11)
(11,12)
(12,30)
```

---

### Line 58
```python
run = run + 1 if b - a == 1 else 1
```

Updates current run length.

If:

```python
b - a == 1
```

then observations are consecutive, so:

```python
run = run + 1
```

Otherwise:

```python
run = 1
```

Example:

```text
10 → 11
```

gives run 2.

Then:

```text
11 → 12
```

gives run 3.

Then:

```text
12 → 30
```

resets it to 1.

This is Python's conditional expression:

```python
X if condition else Y
```

---

### Line 59
```python
max_run = max(max_run, run)
```

Keeps the largest run seen so far.

Example:

```text
max_run = 3
run = 5
```

becomes:

```text
max_run = 5
```

---

### Line 60
```python
self.max_run_ever[band] = max(self.max_run_ever[band], max_run)
```

Updates the scheduler's historical maximum run for this band.

Important distinction:

```python
max_run
```

= maximum run in current hit history.

```python
self.max_run_ever[band]
```

= maximum run remembered across updates.

---

# Lines 61–67 — Minimum candidate period

### Line 61
```python
min_candidate = max(8, 2 * max_run)
```

Sets minimum acceptable candidate PRI.

Two restrictions:

```text
minimum = 8
```

and:

```text
minimum = 2 × maximum consecutive run
```

whichever is larger.

Why?

If a dense ON run has length 10, accepting PRI 8 would be suspicious because the supposed period is shorter than the observed dense run.

So:

```text
max_run = 10
2*max_run = 20
min_candidate = 20
```

---

### Line 63
```python
candidate_pool = [d for d in diffs if d >= min_candidate]
```

Filters pairwise differences.

Only differences large enough to be plausible PRI candidates remain.

Example:

```text
diffs = [3, 5, 8, 12, 24]
min_candidate = 8
```

produces:

```text
[8,12,24]
```

---

### Line 64
```python
if not candidate_pool:
```

Checks whether filtering produced nothing.

`not []` is `True`.

---

### Line 65
```python
self.pri_estimate[band] = None
```

No PRI estimate.

---

### Line 66
```python
self.confidence[band] = 0.0
```

No confidence.

---

### Line 67
```python
return
```

Stops method.

---

# Lines 69–79 — Candidate generation

This is the **heart of the ablation**.

### Line 69
```python
candidates = set()
```

Creates an empty set.

Why a set?

To avoid duplicate candidates.

For example:

```text
12, 12, 12
```

is stored once:

```python
{12}
```

---

### Line 70
```python
g = reduce(math.gcd, diffs)
```

Computes GCD of **all pairwise differences**.

Example:

```text
diffs = [12,24,36]
```

gives:

```text
g = 12
```

---

### Line 71
```python
if g >= min_candidate:
```

Only accepts the GCD if it passes the minimum-period constraint.

---

### Line 72
```python
candidates.add(g)
```

Adds GCD to candidate set.

---

### Line 73
```python
mode_candidate, _freq = Counter(candidate_pool).most_common(1)[0]
```

Finds most frequent difference in `candidate_pool`.

Break it apart:

```python
Counter(candidate_pool)
```

counts occurrences.

Then:

```python
.most_common(1)
```

requests the single most common value.

Example:

```text
candidate_pool = [12,12,12,24,36]
```

gives something conceptually like:

```text
[(12, 3)]
```

Then:

```python
[0]
```

takes:

```text
(12,3)
```

Finally:

```python
mode_candidate, _freq
```

assigns:

```text
mode_candidate = 12
_freq = 3
```

The underscore means frequency isn't otherwise needed.

---

### Line 74
```python
candidates.add(mode_candidate)
```

Adds the most common pairwise difference.

---

### Line 75
```python
for k in (2, 3, 4, 5, 6, 7, 8):
```

Tests divisors 2 through 8.

---

### Line 76
```python
sub = round(mode_candidate / k)
```

Computes approximate integer submultiples.

If:

```text
mode_candidate = 120
k = 4
```

then:

```text
120 / 4 = 30
```

so:

```python
sub = 30
```

`round()` converts the result to nearest integer.

---

### Line 77
```python
if sub >= min_candidate:
```

Rejects too-small subperiods.

---

### Line 78
```python
candidates.add(sub)
```

Adds valid submultiple candidate.

---

### Line 79
```python
# NOTE: no +-1 neighbor expansion here -- this is the fix being isolated.
```

**Critical line.**

This class deliberately stops here.

The current implementation additionally tests nearby integer periods.

Conceptually, current V3 does something like:

```text
candidate c
→ c-1
→ c
→ c+1
```

This old reconstruction does **not**.

Therefore the comparison isolates that exact modification.

---

# Lines 81–89 — Select best candidate

### Line 81
```python
best_base, best_rmse, best_rel = None, None, None
```

Initializes three variables:

```text
best_base → best refined PRI
best_rmse → corresponding error
best_rel  → relative error
```

All start as `None`.

---

### Line 82
```python
for c in candidates:
```

Loops through candidate PRI values.

---

### Line 83
```python
refined, rmse = self._refine_pri(sorted_times, c)
```

Calls inherited PRIAware functionality.

This is important:

The pre-fix class does **not** replace the entire PRI algorithm.

It still uses the current:

```python
_refine_pri()
```

method.

That keeps the experiment controlled.

It receives:

```text
sorted observed times
candidate period
```

and returns:

```text
refined PRI
RMSE
```

---

### Line 84
```python
if refined is None or rmse is None or refined < min_candidate * 0.5:
```

Rejects invalid refinements.

Three rejection conditions:

1. `refined is None`
2. `rmse is None`
3. refined PRI is less than half the minimum candidate.

The third condition prevents implausibly small estimates.

---

### Line 85
```python
continue
```

Skip this candidate and move to next.

---

### Line 86
```python
rel = rmse / refined
```

Computes **relative fitting error**.

Example:

```text
RMSE = 1
PRI  = 20
```

then:

```text
rel = 0.05
```

Lower is better.

---

### Line 87
```python
if best_rel is None or rel < best_rel:
```

Accept this candidate if:

- there is no previous best candidate, or
- its relative error is lower.

---

### Line 88
```python
best_base, best_rmse, best_rel = refined, rmse, rel
```

Stores this candidate as the current best.

---

# Lines 90–99 — No valid candidate handling

### Line 90
```python
if best_base is None:
```

Checks whether every candidate failed.

---

### Line 91
```python
self.pri_estimate[band] = None
```

No PRI.

---

### Line 92
```python
self.confidence[band] = 0.0
```

No confidence.

---

### Line 93
```python
return
```

Exit.

---

### Line 94
```python
refined_pri, rmse = best_base, best_rmse
```

Copies best candidate results into descriptive names.

---

### Line 96
```python
if refined_pri is None or refined_pri < min_candidate * 0.5 or rmse is None:
```

Second defensive validation.

Even though earlier selection already checked these properties, this provides another guard before using them.

---

### Line 97
```python
self.pri_estimate[band] = None
```

Reject estimate.

---

### Line 98
```python
self.confidence[band] = 0.0
```

Reject confidence.

---

### Line 99
```python
return
```

Exit.

---

# Lines 101–108 — Confidence and final PRI model

### Line 101
```python
confidence = min(1.0, max(0.0, 1.0 - rmse / (self.confidence_scale * refined_pri)))
```

Calculates confidence.

Start with:

```python
1.0 - rmse / (confidence_scale * refined_pri)
```

So:

- lower RMSE → higher confidence;
- larger PRI → generally higher confidence for same RMSE;
- larger `confidence_scale` → more tolerance for RMSE.

Then:

```python
max(0.0, ...)
```

prevents confidence below 0.

And:

```python
min(1.0, ...)
```

prevents confidence above 1.

Therefore:

```text
0 ≤ confidence ≤ 1
```

---

### Line 102
```python
if confidence >= self.min_confidence:
```

Only accepts model if confidence reaches configured threshold.

In the V3 scheduler, this threshold defaults to a fairly high confidence requirement.

---

### Line 103
```python
self.pri_estimate[band] = refined_pri
```

Stores the estimated PRI.

---

### Line 104
```python
self.jitter_estimate[band] = max(0.5, rmse, self.max_run_ever[band] / 2.0)
```

Estimates timing uncertainty/jitter.

It takes the largest of:

```text
0.5
RMSE
half historical maximum consecutive run
```

This gives the scheduler a tolerance window around predicted periodic events.

---

### Line 105
```python
self.confidence[band] = confidence
```

Stores computed confidence.

---

### Line 106
```python
else:
```

Executed when confidence is too low.

---

### Line 107
```python
self.pri_estimate[band] = None
```

Discard PRI estimate.

---

### Line 108
```python
self.confidence[band] = 0.0
```

Reset confidence.

---

### Line 109

There is **no `return` here**, but the method simply reaches its end.

Python implicitly returns:

```python
None
```

This is valid.

---

# Lines 111–116 — Identical-environment runner

### Line 111
```python
def run_identical_env(seed, sched_cls, n_bands=8, n_steps=4000, k=2, **kw):
```

Defines helper function.

Parameters:

```text
seed       → random seed
sched_cls  → scheduler class
n_bands    → number of bands, default 8
n_steps    → simulation length, default 4000
k          → number channels scanned simultaneously
**kw       → additional scheduler arguments
```

---

### Line 112
```python
scenario = make_scenario(n_bands)
```

Creates beacon scenario.

Important: `make_scenario()` creates the same scenario structure for every scheduler.

---

### Line 113
```python
random.seed(seed)
```

Resets random generator **for this scheduler run**.

This is the key identical-environment mechanism.

---

### Line 114
```python
sched = sched_cls(n_bands, ucb_c=0.5, **kw)
```

Instantiates whichever scheduler class was supplied.

For example:

```python
sched_cls = BeliefUCBScheduler
```

becomes approximately:

```python
BeliefUCBScheduler(8, ucb_c=0.5)
```

For the pre-fix scheduler:

```python
PreOffByOneFixPRIAware(8, ucb_c=0.5)
```

For current:

```python
PRIAwareScheduler(8, ucb_c=0.5)
```

`**kw` passes optional extra parameters.

---

### Line 115
```python
stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
```

Runs the simulation.

Arguments:

```text
scenario → beacon environment
sched → scheduler being tested
n_steps → 4000
n_bands → 8
k_channels → 1 or 2
```

Returns statistics object.

---

### Line 116
```python
return stats.report()["interception_ratio"]
```

Extracts only:

```text
interception_ratio
```

from the report.

That is the main metric used in this experiment.

---

# Lines 119–124 — Command-line interface

### Line 119
```python
def main():
```

Defines main program function.

---

### Line 120
```python
ap = argparse.ArgumentParser(description=__doc__)
```

Creates argument parser.

The description is the module docstring:

```python
__doc__
```

So running:

```bash
python3 validate_offbyone_fix.py --help
```

can show the script documentation.

---

### Line 121
```python
ap.add_argument("--seeds", type=int, default=30)
```

Adds:

```bash
--seeds
```

Number of seeds.

Default:

```text
30
```

Example:

```bash
python3 validate_offbyone_fix.py --seeds 50
```

---

### Line 122
```python
ap.add_argument("--seed-start", type=int, default=1)
```

Adds starting seed.

Default:

```text
1
```

---

### Line 123
```python
args = ap.parse_args()
```

Reads command-line arguments.

Example:

```bash
--seeds 30 --seed-start 10
```

produces approximately:

```python
args.seeds = 30
args.seed_start = 10
```

---

### Line 124
```python
seeds = list(range(args.seed_start, args.seed_start + args.seeds))
```

Constructs consecutive seeds.

Default:

```text
start = 1
count = 30
```

produces:

```text
[1, 2, 3, ..., 30]
```

If:

```text
--seed-start 10 --seeds 5
```

then:

```text
[10,11,12,13,14]
```

---

# Lines 126–127 — Initial report

### Line 126
```python
print(f"Off-by-one-fix confirmation, beacon scenario, identical-environment "
```

Starts formatted output.

`f"..."` allows expressions inside `{}`.

---

### Line 127
```python
f"methodology, {len(seeds)} seeds ({seeds[0]}..{seeds[-1]}), k=1 and k=2.\n")
```

Completes the message.

For 30 seeds:

```text
30 seeds (1..30), k=1 and k=2.
```

`\n` adds an extra newline.

---

# Lines 129–140 — Main experimental loop

### Line 129
```python
for k in (1, 2):
```

Runs two experiments:

```text
k = 1
k = 2
```

Meaning:

- one simultaneous channel;
- two simultaneous channels.

---

### Line 130
```python
results: Dict[str, List[float]] = {
```

Creates dictionary.

Type hint says:

```text
string → list of floating-point values
```

---

### Line 131
```python
"BeliefUCB": [],
```

Creates empty result list for baseline.

---

### Line 132
```python
"PreOffByOneFix (session start)": [],
```

Stores pre-fix PRIAware results.

---

### Line 133
```python
"Current (with off-by-one fix)": [],
```

Stores current PRIAware results.

---

### Line 134
```python
}
```

Closes dictionary.

At this point:

```python
results = {
    "BeliefUCB": [],
    "PreOffByOneFix (session start)": [],
    "Current (with off-by-one fix)": []
}
```

---

### Line 135
```python
for seed in seeds:
```

Runs every scheduler for every seed.

With 30 seeds:

```text
30 seeds × 3 schedulers
```

per `k`.

And there are 2 values of `k`.

Total:

```text
30 × 3 × 2 = 180 scheduler episodes
```

---

### Line 136
```python
results["BeliefUCB"].append(run_identical_env(seed, BeliefUCBScheduler, k=k))
```

Runs baseline.

For each seed:

1. creates beacon scenario;
2. resets RNG;
3. creates `BeliefUCBScheduler`;
4. runs 4000 steps;
5. extracts interception ratio;
6. appends result.

---

### Lines 137–138
```python
results["PreOffByOneFix (session start)"].append(
    run_identical_env(seed, PreOffByOneFixPRIAware, k=k))
```

Same process for reconstructed pre-fix scheduler.

The parentheses are split across lines for readability.

The result is appended to the pre-fix list.

---

### Lines 139–140
```python
results["Current (with off-by-one fix)"].append(
    run_identical_env(seed, PRIAwareScheduler, k=k))
```

Same process for current PRIAware.

This is the actual scheduler containing the ±1 candidate expansion.

---

# Lines 142–147 — Summary statistics

### Line 142
```python
print(f"--- k={k} ---")
```

Prints section heading.

Example:

```text
--- k=1 ---
```

---

### Line 143
```python
print(f"{'Scheduler':32s} | {'mean':>7s} | {'stdev':>6s} | {'min':>6s} | {'max':>6s}")
```

Prints table header.

Formatting:

```python
:32s
```

means string width 32.

```python
:>7s
```

means right-aligned string width 7.

Output resembles:

```text
Scheduler                        |    mean |  stdev |    min |    max
```

---

### Line 144
```python
print("-" * 65)
```

Prints 65 hyphens.

Pure formatting.

---

### Line 145
```python
for name, vals in results.items():
```

Loops through each scheduler and its result list.

Example:

```text
name = "BeliefUCB"
vals = [0.31, 0.28, ...]
```

---

### Line 146
```python
print(f"{name:32s} | {statistics.mean(vals)*100:6.1f}% | {statistics.stdev(vals)*100:5.1f}% | "
```

Computes and displays:

```python
statistics.mean(vals)
```

and:

```python
statistics.stdev(vals)
```

The values are multiplied by 100 because interception ratio is stored as a fraction.

Example:

```text
0.423
```

becomes:

```text
42.3%
```

`.1f` means one decimal place.

---

### Line 147
```python
f"{min(vals)*100:5.1f}% | {max(vals)*100:5.1f}%")
```

Finishes same output line with:

```text
minimum
maximum
```

Again converted from fraction to percentage.

---

# Lines 149–152 — Paired comparison function

### Line 149
```python
def delta(a, b):
```

Defines local helper function.

It compares two schedulers **seed-by-seed**.

---

### Line 150
```python
diffs = [x - y for x, y in zip(results[a], results[b])]
```

Computes paired differences.

Suppose:

```text
Current: [0.50, 0.60, 0.40]
Old:     [0.45, 0.62, 0.35]
```

Then:

```text
diffs = [0.05, -0.02, 0.05]
```

This is better than merely subtracting overall means because each comparison is matched by seed.

---

### Line 151
```python
wins = sum(1 for d in diffs if d > 0)
```

Counts how many seeds where scheduler A beats scheduler B.

For:

```text
[0.05, -0.02, 0.05]
```

two values are positive.

So:

```text
wins = 2
```

Ties don't count as wins.

---

### Line 152
```python
return statistics.mean(diffs), statistics.stdev(diffs), wins, len(diffs)
```

Returns four things:

```text
mean difference
standard deviation of differences
number of wins
number of comparisons
```

---

# Lines 154–159 — Which comparisons are made?

### Line 154
```python
for label, a, b in [
```

Starts loop over predefined comparisons.

---

### Lines 155–156
```python
("Current vs PreOffByOneFix (this session's fix, isolated)",
 "Current (with off-by-one fix)", "PreOffByOneFix (session start)"),
```

First comparison:

```text
Current - PreFix
```

This is the **isolated effect of the fix**.

If positive:

```text
Current > Old
```

on average.

---

### Lines 157–158
```python
("Current vs BeliefUCB (net vs baseline)",
 "Current (with off-by-one fix)", "BeliefUCB"),
```

Second comparison:

```text
Current PRIAware - BeliefUCB
```

This answers:

> Does the final current scheduler beat the conventional BeliefUCB baseline?

---

### Line 159
```python
]:
```

Ends comparison list.

---

# Lines 160–161 — Print paired results

### Line 160
```python
m, s, w, n = delta(a, b)
```

Calls `delta()`.

Assignments:

```text
m = mean difference
s = standard deviation
w = wins
n = number of seeds
```

---

### Line 161
```python
print(f"  {label:58s}: {m*100:+5.1f}pp +/- {s*100:4.1f}pp  -- won {w}/{n}")
```

Prints paired comparison.

Important: `pp` means **percentage points**.

Example:

```text
+3.2pp
```

means:

```text
3.2 percentage-point improvement
```

not a 3.2% relative improvement.

`+` forces positive numbers to show their sign.

Example output:

```text
Current vs PreOffByOneFix ...: +2.4pp +/- 1.8pp -- won 22/30
```

means current scheduler was higher in 22 of 30 matched seeds.

---

### Line 162
```python
print()
```

Blank line separating `k=1` and `k=2` sections.

---

### Line 164
```python

```

Blank line.

---

# Lines 165–166 — Entry point

### Line 165
```python
if __name__ == "__main__":
```

Standard Python entry-point idiom.

When this file is executed directly:

```bash
python3 validate_offbyone_fix.py
```

`__name__` is:

```python
"__main__"
```

Therefore the condition is true.

If another Python file imports this module:

```python
import validate_offbyone_fix
```

then:

```python
__name__ != "__main__"
```

and `main()` does not automatically run.

---

### Line 166
```python
main()
```

Starts the experiment when executed directly.

---

# What this file is experimentally proving

The whole script can be reduced to this experiment:

```text
                 SAME SEED
                    │
          ┌─────────┼─────────┐
          ↓         ↓         ↓
      BeliefUCB   OLD PRI    NEW PRI
                    │         │
             no ±1 search   ±1 search
                    │         │
          └─────────┼─────────┘
                    ↓
          compare interception ratio
```

For each `k`:

```text
k = 1
k = 2
```

it calculates:

### 1. Overall performance
```text
mean
stdev
min
max
```

### 2. Isolated fix effect
```text
Current PRIAware
        -
Pre-fix PRIAware
```

### 3. Baseline comparison
```text
Current PRIAware
        -
BeliefUCB
```

The most important output is therefore:

```text
Current vs PreOffByOneFix
```

because that comparison isolates the **±1 candidate-neighbor modification**.

And because `random.seed(seed)` is reset before **each** scheduler, the experiment is designed so that scheduler differences aren't merely caused by different RNG histories.

---

## One subtle but important point

`PreOffByOneFixPRIAware` does **not** mean "the entire old PRIAware implementation."

It inherits today's:

```python
PRIAwareScheduler
```

and replaces only:

```python
_update_pri_model()
```

with a reconstructed version lacking the ±1 expansion.

So the intended experimental difference is:

```text
same scheduler architecture
same plateau behavior
same harmonic-selection logic
same confidence scaling
same environment
same seed
same episode length
same k
        ↓
ONLY candidate ±1 neighbor expansion differs
```

That makes this an **ablation test** of the off-by-one fix.

**Next file in the project order: `validate_plateau_fix.py` — 301 lines.**

# `validate_plateau_fix.py` — line-by-line

This file is **301 lines**. Its purpose is to isolate and validate **fix #1: burst-plateau jitter widening** in `PRIAwareScheduler`.

The key experimental idea:

```text
Original
   │
   │ + plateau-jitter fix
   ▼
PlateauOnly
   │
   │ + harmonic-selection fix
   ▼
Current
```

That lets us determine how much improvement came specifically from the plateau fix.

---

# Lines 1–41 — Module documentation

### Line 1
```python
"""
```
Starts module-level docstring.

### Line 2
```python
validate_plateau_fix.py
```
Names script.

### Line 3
```python
==========================
```
Formatting separator.

### Lines 4–7
```text
Multi-seed validation of the burst-plateau jitter fix to
PRIAwareScheduler (diagnosed in diagnose_beacon_regression.py), run
through the same rigor as multi_seed_robustness.py's suite C rather
than the informal single-script spot-check this fix originally got.
```

States purpose.

The script validates the **burst-plateau jitter fix** using multiple seeds instead of relying on one or a few spot checks.

The relevant earlier diagnostic is:

```text
diagnose_beacon_regression.py
```

and the methodology being copied is:

```text
multi_seed_robustness.py → suite C
```

---

### Lines 9–15

The docstring explains that **two fixes** were made to V3.

#### Fix 1
```text
burst-plateau jitter fix
```

A burst can remain ON for several consecutive steps.

Instead of treating it as:

```text
       *
```

the scheduler should recognize that it occupies a time interval:

```text
       █████
```

The fix widens the phase-bump/jitter estimate accordingly.

#### Fix 2
```text
harmonic-lock-on fix
```

Instead of choosing a PRI candidate using the old coarse score, the scheduler evaluates refined fitting quality across candidates.

---

### Lines 17–21

These explain why simply comparing:

```text
Original vs Current
```

would be insufficient.

Both fixes modify:

```python
_update_pri_model()
```

Therefore:

```text
Current - Original
```

contains effects from **both fixes**.

To isolate fix 1, the script reconstructs an intermediate scheduler:

```text
PlateauOnly
```

which has:

```text
Fix 1 = YES
Fix 2 = NO
```

---

### Lines 24–27

The four experimental conditions:

```text
BeliefUCB
```

No periodic model.

```text
Original
```

Neither fix.

```text
PlateauOnly
```

Only burst-plateau fix.

```text
Current
```

Both fixes.

This gives an experimental progression:

```text
BeliefUCB
    ↓
Original
    ↓
PlateauOnly
    ↓
Current
```

---

### Lines 29–33

All four use:

- same beacon scenario;
- same seeds;
- same seeding convention.

The seeding convention is specifically:

```text
random.seed(seed)
```

once per comparison block, followed by schedulers running back-to-back.

This is different from `validate_offbyone_fix.py`, which reset the seed before each scheduler.

Here the purpose is to reproduce `multi_seed_robustness.py` suite C as closely as possible.

---

### Lines 35–37

These document previously observed pre-fix results:

```text
k=1: PRIAware +1.5pp vs BeliefUCB, won 8/10
k=2: PRIAware -1.5pp vs BeliefUCB, won 1/10
```

These numbers are historical baseline results from the project's earlier run.

---

### Lines 39–40

Example execution:

```bash
python3 validate_plateau_fix.py
```

or:

```bash
python3 validate_plateau_fix.py --seeds 30
```

---

### Line 41
```python
"""
```

Ends module documentation.

---

# Lines 43–49 — Imports

### Line 43
```python
import argparse
```

Command-line argument parsing.

### Line 44
```python
import math
```

Provides mathematical functions, especially `math.gcd`.

### Line 45
```python
import random
```

Used for RNG seeding.

### Line 46
```python
import statistics
```

Used for:

- mean;
- standard deviation.

### Line 47
```python
from collections import Counter
```

Counts occurrences of pairwise differences.

### Line 48
```python
from functools import reduce
```

Used to calculate GCD across an entire list.

### Line 49
```python
from typing import Dict, List
```

Provides type hints.

---

# Lines 51–52 — Project imports

### Line 51
```python
from scan_scheduler_v2 import RoundRobinScheduler, BeliefUCBScheduler, run_episode
```

Imports:

- `RoundRobinScheduler`
- `BeliefUCBScheduler`
- `run_episode`

from V2.

### Line 52
```python
from scan_scheduler_v3_pri import PRIAwareScheduler, make_scenario
```

Imports:

- current `PRIAwareScheduler`;
- beacon `make_scenario()`.

---

# Lines 55–57 — Section heading

### Lines 55–57
Comments only.

They announce that the next classes are **reconstructed intermediate scheduler states** used to isolate fix #1.

---

# Lines 59–120 — `OriginalPRIAware`

### Line 59
```python
class OriginalPRIAware(PRIAwareScheduler):
```

Defines reconstructed original scheduler.

It inherits from today's `PRIAwareScheduler`.

Only `_update_pri_model()` is replaced.

This is an important experimental technique:

> Keep everything else identical; replace only the behavior being studied.

---

### Lines 60–63

Docstring says this represents the uploaded ZIP's original version.

It has:

- old excess-over-chance candidate selection;
- old narrow RMSE-only jitter;
- no burst plateau widening.

So:

```text
Original = before both fixes
```

---

## Lines 65–70

### Line 65
```python
def _update_pri_model(self, band):
```

Overrides PRI-model update for one band.

### Line 66
```python
times = self.hit_times[band]
```

Gets historical ON/hit times for this band.

Example:

```text
[12, 24, 36, 48]
```

### Line 67
```python
if len(times) < 8:
```

Requires at least 8 hits before trying to estimate PRI.

### Line 68
```python
self.pri_estimate[band] = None
```

No PRI model.

### Line 69
```python
self.confidence[band] = 0.0
```

No confidence.

### Line 70
```python
return
```

Stop update.

---

# Lines 71–79 — Calculate differences and burst length

### Line 71
```python
diffs = [times[j] - times[i] for i in range(len(times)) for j in range(i + 1, len(times))]
```

Computes every pairwise time difference.

For:

```text
times = [10, 22, 34]
```

we get:

```text
12, 24, 12
```

These differences are used to discover periodicity.

---

### Line 73
```python
max_run = 1
```

Initial maximum consecutive ON run.

### Line 74
```python
run = 1
```

Current consecutive run length.

### Line 75
```python
sorted_times = sorted(times)
```

Sorts timestamps.

### Line 76
```python
for a, b in zip(sorted_times[:-1], sorted_times[1:]):
```

Examines neighboring timestamps.

For:

```text
[10, 11, 12, 30]
```

pairs are:

```text
(10,11)
(11,12)
(12,30)
```

### Line 77
```python
run = run + 1 if b - a == 1 else 1
```

If consecutive timestamps differ by exactly 1:

```text
run += 1
```

otherwise:

```text
run = 1
```

### Line 78
```python
max_run = max(max_run, run)
```

Records largest run.

### Line 79
```python
min_candidate = max(8, 2 * max_run)
```

Minimum allowed PRI candidate.

It prevents dense bursts from being mistaken for short periodic signals.

---

# Lines 81–85 — Candidate-pool check

### Line 81
```python
candidate_pool = [d for d in diffs if d >= min_candidate]
```

Keeps sufficiently large pairwise differences.

### Line 82
```python
if not candidate_pool:
```

Checks whether nothing survived.

### Line 83
```python
self.pri_estimate[band] = None
```

No estimate.

### Line 84
```python
self.confidence[band] = 0.0
```

Confidence zero.

### Line 85
```python
return
```

Exit.

---

# Lines 86–97 — Generate candidate PRIs

### Line 86
```python
tol = 1
```

Tolerance of ±1 timestep when testing candidates.

### Line 88
```python
candidates = set()
```

Empty candidate set.

A set automatically removes duplicates.

### Line 89
```python
g = reduce(math.gcd, diffs)
```

Calculates GCD of all differences.

Example:

```text
[12, 24, 36]
→ 12
```

### Lines 90–91
```python
if g >= min_candidate:
    candidates.add(g)
```

Only adds GCD if sufficiently large.

---

### Line 92
```python
mode_candidate, _freq = Counter(candidate_pool).most_common(1)[0]
```

Finds most frequent pairwise difference.

`_freq` receives its frequency but isn't otherwise used.

### Line 93
```python
candidates.add(mode_candidate)
```

Adds mode candidate.

---

### Line 94
```python
for k in (2, 3, 4, 5, 6, 7, 8):
```

Checks integer divisors 2 through 8.

### Line 95
```python
sub = round(mode_candidate / k)
```

Creates possible submultiples.

Example:

```text
mode = 120
k = 4
sub = 30
```

### Line 96
```python
if sub >= min_candidate:
```

Rejects candidates that are too small.

### Line 97
```python
candidates.add(sub)
```

Stores valid submultiple.

---

# Lines 99–105 — Old candidate-selection method

### Line 99
```python
def _excess_over_chance(c):
```

Defines local scoring function.

It evaluates candidate `c`.

### Line 100
```python
score = self._score_candidate(diffs, c, tol)
```

Measures how strongly observed differences support candidate `c`.

### Line 101
```python
chance = min(1.0, (2 * tol + 1) / c)
```

Computes expected accidental-match probability.

With:

```text
tol = 1
```

this is:

```text
3 / c
```

capped at 1.

### Line 102
```python
return score - chance
```

Measures:

```text
observed support − expected chance support
```

Higher is considered better.

---

### Line 104
```python
seed = max(candidates, key=_excess_over_chance)
```

Chooses candidate with highest excess-over-chance score.

This is the **old harmonic-selection mechanism**.

---

### Line 105
```python
refined_pri, rmse = self._refine_pri(sorted_times, seed)
```

Refines chosen candidate using actual timestamps.

Returns:

```text
refined PRI
RMSE
```

---

# Lines 107–110 — Validate refinement

### Line 107
```python
if refined_pri is None or refined_pri < min_candidate * 0.5 or rmse is None:
```

Rejects invalid result if:

- no PRI;
- PRI implausibly small;
- no RMSE.

### Line 108
```python
self.pri_estimate[band] = None
```

Clear PRI.

### Line 109
```python
self.confidence[band] = 0.0
```

Clear confidence.

### Line 110
```python
return
```

Exit.

---

# Lines 112–119 — Original confidence and jitter

### Line 112
```python
confidence = min(1.0, max(0.0, 1.0 - rmse / (0.25 * refined_pri)))
```

Calculates confidence.

Mathematically:

$$
C =
\operatorname{clip}
\left(
1-\frac{\text{RMSE}}{0.25\,PRI},
0,1
\right)
$$

Lower error means higher confidence.

---

### Line 113
```python
if confidence >= self.min_confidence:
```

Only accept model above confidence threshold.

### Line 114
```python
self.pri_estimate[band] = refined_pri
```

Stores PRI.

### Line 115
```python
self.jitter_estimate[band] = max(0.5, rmse)   # OLD: no plateau widening
```

This is the **old behavior**.

Jitter is based only on:

```text
0.5
RMSE
```

It does **not** account for burst length.

So a burst like:

```text
t = 100,101,102,103
```

can still be modeled too narrowly.

### Line 116
```python
self.confidence[band] = confidence
```

Stores confidence.

### Lines 117–119
```python
else:
    self.pri_estimate[band] = None
    self.confidence[band] = 0.0
```

If confidence is insufficient:

- discard PRI;
- reset confidence.

---

# Lines 122–184 — `PlateauOnlyPRIAware`

This is the **most important class in this file**.

It represents:

```text
Fix 1 = YES
Fix 2 = NO
```

---

### Line 122
```python
class PlateauOnlyPRIAware(PRIAwareScheduler):
```

Again inherits current PRIAware.

---

### Lines 123–126

Docstring explicitly states:

- burst-plateau jitter widening is applied;
- harmonic lock-on candidate selection remains old.

Thus this class isolates fix #1.

---

## Lines 128–134

These are essentially identical to the original implementation.

### Line 128
```python
def _update_pri_model(self, band):
```

PRI model update.

### Line 129
```python
times = self.hit_times[band]
```

Get hit history.

### Lines 130–133

Require at least 8 hits; otherwise clear model and return.

### Line 134
```python
diffs = [times[j] - times[i] for i in range(len(times)) for j in range(i + 1, len(times))]
```

Compute pairwise differences.

---

# Lines 136–143 — THE PLATEAU FIX

### Lines 136–141

These calculate current `max_run` exactly as before.

```python
max_run = 1
run = 1
sorted_times = sorted(times)
```

Then adjacent timestamps are inspected.

---

### Line 142
```python
self.max_run_ever[band] = max(self.max_run_ever[band], max_run)   # NEW: persistent tracking
```

**This is the first important change.**

Instead of remembering only the current maximum run, the scheduler maintains:

```text
max_run_ever
```

across updates.

Suppose:

```text
early history → burst of length 6
later history → current burst only length 2
```

Without persistence:

```text
current max = 2
```

With persistence:

```text
max_run_ever = 6
```

This prevents the scheduler from forgetting evidence that bursts can occupy multiple steps.

---

### Line 143
```python
min_candidate = max(8, 2 * max_run)
```

Candidate filtering still uses **current** `max_run`.

Notice:

```python
self.max_run_ever
```

is not used here.

That's deliberate.

The persistent value is specifically used later for jitter widening.

---

# Lines 145–161 — Candidate generation

### Line 145
```python
candidate_pool = [d for d in diffs if d >= min_candidate]
```

Filter differences.

### Lines 146–149

If no candidates survive:

```text
PRI = None
confidence = 0
return
```

Same as Original.

### Line 150
```python
tol = 1
```

Tolerance remains unchanged.

### Line 152
```python
candidates = set()
```

Create candidate set.

### Line 153
```python
g = reduce(math.gcd, diffs)
```

Compute GCD.

### Lines 154–155

Add GCD if valid.

### Line 156
```python
mode_candidate, _freq = Counter(candidate_pool).most_common(1)[0]
```

Find most common difference.

### Line 157
```python
candidates.add(mode_candidate)
```

Add it.

### Lines 158–161

Generate submultiples 2–8 and keep sufficiently large ones.

**All of this is unchanged from `OriginalPRIAware`.**

That matters because we want only one meaningful behavioral change.

---

# Lines 163–169 — Deliberately retain old harmonic selection

### Line 163
```python
def _excess_over_chance(c):   # OLD selection, unchanged from Original
```

The comment makes experimental intent explicit.

The harmonic-selection fix has **not** been applied.

### Line 164
```python
score = self._score_candidate(diffs, c, tol)
```

Candidate support.

### Line 165
```python
chance = min(1.0, (2 * tol + 1) / c)
```

Chance baseline.

### Line 166
```python
return score - chance
```

Excess over chance.

### Line 168
```python
seed = max(candidates, key=_excess_over_chance)
```

Old candidate selection.

### Line 169
```python
refined_pri, rmse = self._refine_pri(sorted_times, seed)
```

Refine selected candidate.

Thus:

```text
Original == PlateauOnly
```

through candidate selection.

---

# Lines 171–174 — Validate PRI

### Line 171
```python
if refined_pri is None or refined_pri < min_candidate * 0.5 or rmse is None:
```

Reject invalid fit.

### Line 172
```python
self.pri_estimate[band] = None
```

Clear PRI.

### Line 173
```python
self.confidence[band] = 0.0
```

Clear confidence.

### Line 174
```python
return
```

Exit.

---

# Lines 176–184 — The actual jitter modification

### Line 176
```python
confidence = min(1.0, max(0.0, 1.0 - rmse / (0.25 * refined_pri)))
```

Same confidence formula as Original.

This is another important control:

> The plateau fix does not change confidence calculation.

---

### Line 177
```python
if confidence >= self.min_confidence:
```

Require adequate confidence.

### Line 178
```python
self.pri_estimate[band] = refined_pri
```

Store PRI.

---

### Line 179
```python
# NEW: plateau-widened jitter floor -- the ONLY change vs Original
```

This comment identifies the intended change.

---

### Line 180
```python
self.jitter_estimate[band] = max(0.5, rmse, self.max_run_ever[band] / 2.0)
```

**Core plateau fix.**

Old:

```python
max(0.5, rmse)
```

New:

```python
max(0.5, rmse, max_run_ever / 2)
```

So if:

```text
max_run_ever = 8
RMSE = 0.7
```

then:

```text
jitter = max(0.5, 0.7, 4)
       = 4
```

The predicted periodic event therefore gets a much wider timing tolerance.

This is useful because a burst isn't an instantaneous event.

---

### Line 181
```python
self.confidence[band] = confidence
```

Store confidence.

### Lines 182–184
```python
else:
    self.pri_estimate[band] = None
    self.confidence[band] = 0.0
```

Reject low-confidence model.

---

# Lines 187–189 — Helper section

Comments only.

They announce generic statistical/printing helpers.

---

# Lines 191–199 — `summarize()`

### Line 191
```python
def summarize(values: List[float]) -> Dict:
```

Function accepts list of floats.

Returns dictionary of summary statistics.

### Line 192
```python
n = len(values)
```

Number of observations.

### Line 193
```python
return {
```

Begins result dictionary.

### Line 194
```python
"n": n,
```

Stores sample count.

### Line 195
```python
"mean": statistics.mean(values),
```

Arithmetic mean.

### Line 196
```python
"stdev": statistics.stdev(values) if n > 1 else 0.0,
```

Sample standard deviation.

If only one value exists, returns `0.0` rather than calling `statistics.stdev()`.

### Line 197
```python
"min": min(values),
```

Smallest value.

### Line 198
```python
"max": max(values),
```

Largest value.

### Line 199
```python
}
```

Closes dictionary.

---

# Lines 202–211 — Summary-table printer

### Line 202
```python
def print_summary_table(title: str, summaries: Dict[str, Dict], unit: str = "%", scale: float = 100.0):
```

Print helper.

Parameters:

```text
title
summaries
unit = "%"
scale = 100
```

The scaling converts ratios such as:

```text
0.42
```

into:

```text
42.0%
```

---

### Line 203
```python
print(f"\n{title}")
```

Print title preceded by blank line.

### Line 204
```python
header = f"{'Scheduler':42s} | {'mean +/- stdev':>18s} | {'min':>8s} | {'max':>8s}"
```

Builds formatted table header.

### Line 205
```python
print(header)
```

Print header.

### Line 206
```python
print("-" * len(header))
```

Prints separator exactly as long as header.

### Line 207
```python
for name, s in summaries.items():
```

Iterates over scheduler summaries.

### Line 208
```python
mean_s = f"{s['mean']*scale:5.1f}{unit}"
```

Formats mean.

### Line 209
```python
stdev_s = f"{s['stdev']*scale:4.1f}{unit}"
```

Formats standard deviation.

### Lines 210–211
```python
print(f"{name:42s} | {mean_s:>8s} +/- {stdev_s:<7s} | "
      f"{s['min']*scale:6.1f}{unit} | {s['max']*scale:6.1f}{unit}")
```

Prints one row:

```text
scheduler | mean ± stdev | min | max
```

---

# Lines 214–220 — Paired differences

### Line 214
```python
def paired_delta(a_vals: List[float], b_vals: List[float]) -> Dict:
```

Compares two schedulers seed-by-seed.

### Line 215
```python
diffs = [a - b for a, b in zip(a_vals, b_vals)]
```

Computes:

$$
d_i=A_i-B_i
$$

for each seed.

### Line 216
```python
wins = sum(1 for d in diffs if d > 0)
```

Counts seeds where A beats B.

### Line 217
```python
s = summarize(diffs)
```

Gets mean/stdev/min/max.

### Line 218
```python
s["wins"] = wins
```

Adds win count.

### Line 219
```python
s["n_seeds"] = len(diffs)
```

Stores number of paired comparisons.

### Line 220
```python
return s
```

Returns dictionary.

---

# Lines 223–226 — Print delta

### Line 223
```python
def print_delta(label: str, delta: Dict, scale: float = 100.0):
```

Formats paired comparison.

### Line 224
```python
print(f"  {label:42s}: {delta['mean']*scale:+5.1f}pp +/- {delta['stdev']*scale:4.1f}pp "
```

Displays mean difference in **percentage points**.

### Line 225
```python
f"  (min {delta['min']*scale:+5.1f}pp, max {delta['max']*scale:+5.1f}pp)  "
```

Displays smallest/largest paired differences.

### Line 226
```python
f"-- won in {delta['wins']}/{delta['n_seeds']} seeds")
```

Displays number of seeds where A won.

---

# Lines 229–233 — Validation suite description

Comments explain that the next function reproduces suite C's beacon methodology.

The important phrase:

```text
one seed per full comparison block
```

means:

```text
seed
 │
 ├─ RoundRobin
 ├─ BeliefUCB
 ├─ Original
 ├─ PlateauOnly
 └─ Current
```

all consume the same continuously advancing RNG stream.

---

# Lines 235–270 — `suite_plateau_validation()`

### Lines 235–236
```python
def suite_plateau_validation(seeds: List[int], n_bands: int = 8, n_steps: int = 4000,
                              csv_path: str = None):
```

Defines validation suite.

Defaults:

```text
8 bands
4000 steps
```

Optional CSV output.

---

### Line 237
```python
scenario = make_scenario(n_bands)
```

Creates beacon scenario once.

### Line 238
```python
all_raw = {}
```

Stores raw results for both `k=1` and `k=2`.

---

### Line 239
```python
for k in (1, 2):
```

Tests:

```text
one channel
two channels
```

---

### Lines 240–246 — Scheduler builders

```python
builders = {
```

Creates dictionary of scheduler constructors.

### Line 241
```python
"RoundRobin (open-loop)": lambda: RoundRobinScheduler(n_bands),
```

Baseline open-loop scheduler.

`lambda` delays construction until needed.

### Line 242
```python
"BeliefUCB (Markov-only)": lambda: BeliefUCBScheduler(n_bands, ucb_c=0.5),
```

Markov/UCB baseline.

### Line 243
```python
"Original (pre-both-fixes)": lambda: OriginalPRIAware(n_bands, ucb_c=0.5),
```

Old PRIAware.

### Line 244
```python
"PlateauOnly (fix 1 only)": lambda: PlateauOnlyPRIAware(n_bands, ucb_c=0.5),
```

Intermediate scheduler.

### Line 245
```python
"Current (both fixes)": lambda: PRIAwareScheduler(n_bands, ucb_c=0.5),
```

Current implementation.

### Line 246
```python
}
```

Closes dictionary.

---

### Line 247
```python
raw: Dict[str, List[float]] = {name: [] for name in builders}
```

Creates empty results list for every scheduler.

Conceptually:

```python
{
    "RoundRobin": [],
    "BeliefUCB": [],
    "Original": [],
    "PlateauOnly": [],
    "Current": []
}
```

---

### Line 248
```python
for seed in seeds:
```

Loops through all requested seeds.

---

### Line 249
```python
random.seed(seed)
```

Resets RNG **once per seed block**.

---

### Line 250
```python
for name, build in builders.items():
```

Runs all five schedulers sequentially.

---

### Line 251
```python
stats = run_episode(scenario, build(), n_steps, n_bands, k_channels=k)
```

Builds scheduler and executes 4000-step episode.

The `k` value controls number of simultaneously selected channels.

---

### Line 252
```python
raw[name].append(stats.report()["interception_ratio"])
```

Extracts interception ratio and stores it.

---

# Lines 254–266 — Print analysis

### Lines 254–256
```python
print_summary_table(
    f"[Plateau validation] Beacon scenario, k_channels={k}, {len(seeds)} seeds "
    f"({n_steps} steps each)", {n: summarize(v) for n, v in raw.items()})
```

Prints mean/stdev/min/max for all schedulers.

---

### Lines 258–259
```python
print_delta("Original vs BeliefUCB (baseline, pre-fix)",
            paired_delta(raw["Original (pre-both-fixes)"], raw["BeliefUCB (Markov-only)"]))
```

Measures:

```text
Original − BeliefUCB
```

This recreates the pre-fix comparison.

---

### Lines 260–261
```python
print_delta("PlateauOnly vs BeliefUCB (fix 1 alone)",
            paired_delta(raw["PlateauOnly (fix 1 only)"], raw["BeliefUCB (Markov-only)"]))
```

Measures:

```text
PlateauOnly − BeliefUCB
```

This tells us whether **fix 1 alone** beats the Markov baseline.

---

### Lines 262–263
```python
print_delta("PlateauOnly vs Original (fix 1's OWN contribution)",
            paired_delta(raw["PlateauOnly (fix 1 only)"], raw["Original (pre-both-fixes)"]))
```

This is the cleanest measurement of fix 1.

It computes:

```text
PlateauOnly − Original
```

Since the only intended behavioral difference is the plateau fix, this estimates that fix's contribution.

---

### Lines 264–265
```python
print_delta("Current vs BeliefUCB (both fixes, shipped state)",
            paired_delta(raw["Current (both fixes)"], raw["BeliefUCB (Markov-only)"]))
```

Measures final shipped scheduler against baseline.

---

### Line 266
```python
all_raw[k] = raw
```

Stores results under:

```text
k = 1
```

or:

```text
k = 2
```

---

# Lines 268–270 — Optional CSV output

### Line 268
```python
if csv_path:
```

Only write CSV if path was provided.

### Line 269
```python
write_csv(csv_path, f"plateau_validation_k{k}", raw, seeds)
```

Writes raw per-seed results.

### Line 270
```python
return all_raw
```

Returns all raw results to caller.

---

# Lines 273–283 — `write_csv()`

### Line 273
```python
def write_csv(path: str, suite_label: str, raw: Dict[str, List[float]], seeds: List[int]):
```

Defines CSV writer.

---

### Line 274
```python
import csv
```

Imports CSV module locally.

### Line 275
```python
import os
```

Needed to check whether file already exists.

### Line 276
```python
write_header = not os.path.exists(path)
```

If file doesn't exist:

```text
write_header = True
```

Otherwise:

```text
False
```

---

### Line 277
```python
with open(path, "a", newline="") as f:
```

Opens CSV in append mode.

`with` automatically closes file afterward.

`newline=""` avoids unwanted blank lines on some systems.

---

### Line 278
```python
w = csv.writer(f)
```

Creates CSV writer.

### Line 279
```python
if write_header:
```

Only write header for new file.

### Line 280
```python
w.writerow(["suite", "scheduler", "seed", "interception_ratio"])
```

CSV columns:

```text
suite
scheduler
seed
interception_ratio
```

---

### Line 281
```python
for name, vals in raw.items():
```

Loop through schedulers.

### Line 282
```python
for seed, v in zip(seeds, vals):
```

Pairs each seed with its result.

Example:

```text
seed=1 → 0.42
seed=2 → 0.38
```

### Line 283
```python
w.writerow([suite_label, name, seed, v])
```

Writes one CSV row.

---

# Lines 286–297 — `main()`

### Line 286
```python
def main():
```

Main driver.

### Line 287
```python
ap = argparse.ArgumentParser(description=__doc__)
```

Creates CLI parser.

Description comes from module docstring.

---

### Line 288
```python
ap.add_argument("--seeds", type=int, default=20, help="Number of seeds to test")
```

Number of seeds.

Default here is **20**, despite the documentation giving 30 as an example.

So:

```bash
python3 validate_plateau_fix.py
```

uses 20 seeds.

---

### Line 289
```python
ap.add_argument("--seed-start", type=int, default=1, help="First seed value")
```

Default starting seed = 1.

---

### Lines 290–291
```python
ap.add_argument("--csv", default="plateau_validation_results.csv",
                 help="Path to append raw per-seed results to (set to '' to skip)")
```

Default CSV:

```text
plateau_validation_results.csv
```

CSV output can be disabled:

```bash
--csv ""
```

---

### Line 292
```python
args = ap.parse_args()
```

Reads CLI arguments.

---

### Line 294
```python
seeds = list(range(args.seed_start, args.seed_start + args.seeds))
```

Builds consecutive seed list.

Default:

```text
[1,2,3,...,20]
```

---

### Lines 295–296
```python
print(f"Validating the burst-plateau jitter fix in isolation from the later "
      f"harmonic-selection fix, across {len(seeds)} seeds ({seeds[0]}..{seeds[-1]}).\n")
```

Prints experiment description.

For defaults:

```text
Validating the burst-plateau jitter fix in isolation from the later
harmonic-selection fix, across 20 seeds (1..20).
```

---

### Line 297
```python
suite_plateau_validation(seeds, csv_path=args.csv or None)
```

Runs the actual experiment.

Interesting expression:

```python
args.csv or None
```

means:

```text
nonempty string → string
empty string    → None
```

Therefore `--csv ""` disables CSV output.

---

# Lines 300–301 — Entry point

### Line 300
```python
if __name__ == "__main__":
```

Only execute main when file is run directly.

### Line 301
```python
main()
```

Starts validation.

---

# The most important conceptual difference

The three PRIAware states are:

| Scheduler | Burst plateau fix | Harmonic-selection fix |
|---|---:|---:|
| `OriginalPRIAware` | ❌ | ❌ |
| `PlateauOnlyPRIAware` | ✅ | ❌ |
| `PRIAwareScheduler` | ✅ | ✅ |

Therefore:

$$
\boxed{\text{Plateau fix contribution}
=
\text{PlateauOnly}
-
\text{Original}}
$$

while:

$$
\boxed{\text{Total improvement}
=
\text{Current}
-
\text{Original}}
$$

and:

$$
\boxed{\text{Harmonic-fix contribution}
\approx
\text{Current}
-
\text{PlateauOnly}}
$$

The last equation is the natural complementary comparison, although **this script does not print it explicitly**.

That distinction is the entire reason `validate_plateau_fix.py` exists.

---

## How this connects to the previous file

`validate_offbyone_fix.py` isolated:

```text
±1 candidate-neighbor expansion
```

This file isolates:

```text
burst-plateau jitter widening
```

So the project's validation chain is now:

```text
V3 PRIAware
   │
   ├── Fix 1: plateau jitter
   │      └── validate_plateau_fix.py
   │
   ├── Fix 2: harmonic candidate selection
   │      └── isolated indirectly by comparing
   │          PlateauOnly vs Current
   │
   └── Off-by-one candidate expansion
          └── validate_offbyone_fix.py
```

**Next file: `validate_warmup_dwell_fix.py` — 166 lines.**

# `validate_warmup_dwell_fix.py`

This file is much more focused than the previous validation scripts.

Its question is:

> **What happens to PRI lock-on when switching has a nonzero cost, and does using a warmup dwell + appropriately scaled warmup budget fix the problem?**

It tests **five variants**, A–E, across **30 seeds**, for switch costs of **1 and 2 steps**.

---

# Lines 1–28 — Module documentation

### Line 1
```python
"""
```
Starts module docstring.

### Line 2
```python
validate_warmup_dwell_fix.py
```
Script name.

### Line 3
```python
==============================
```
Formatting only.

### Lines 4–9
The documentation describes the bug.

The original warmup sweep switches bands **every timestep**.

If:

```text
switch_cost_steps > 0
```

then moving from one band to another causes settling.

But the warmup itself immediately moves again:

```text
t=0 → band 0
t=1 → band 1
t=2 → band 2
t=3 → band 3
...
```

With a switch cost, nearly every observation is consumed by settling.

Therefore the scheduler cannot collect enough **valid post-settling observations** to learn a PRI.

The important distinction:

```text
warmup is not merely less effective
```

but potentially:

```text
warmup cannot produce valid observations at all
```

---

### Lines 11–21 — Five variants

The file explicitly tests five configurations.

#### A — Line 14
```text
dwell=1
```

Original behavior.

Every warmup step switches bands.

Broken when switch cost > 0.

#### B — Line 15
```text
dwell>1, jitter=0, warmup unscaled
```

Adds dwell.

But keeps warmup length at 800.

Tests whether dwell alone is sufficient.

#### C — Line 16
```text
dwell>1, jitter=0, warmup scaled
```

Adds dwell **and** compensates for fewer warmup laps by increasing total warmup duration.

No jitter.

#### D — Line 17
```text
dwell>1, jitter=1, warmup scaled
```

Adds:

- dwell;
- jitter;
- scaled warmup.

This represents the corrected plain `PRIAwareScheduler`.

#### E — Lines 18–21
```text
same as D + PersistentPRIAwareScheduler
```

Adds V4's persistent characterization mechanism.

The stated hypothesis:

```text
D → works on majority, but may remain seed-sensitive
E → closes remaining lock-on gap
```

---

### Lines 23–25

The test runs:

- multiple switch costs;
- many seeds;
- `switch_lead_steps = cost`.

That last setting is important.

`switch_lead_steps` belongs to the **re-acquisition/settling prediction fix**.

By setting:

```python
switch_lead_steps = cost
```

the test tries to ensure it is testing **warmup lock-on**, rather than accidentally testing the separate re-acquisition issue.

---

### Lines 27–28
```text
Run: python3 validate_warmup_dwell_fix.py
"""
```

Documents execution command and closes docstring.

---

# Lines 30–36 — Imports

### Line 30
```python
import random
```

Python random-number generator.

### Line 31
```python
import statistics
```

Used for means and population standard deviation.

### Line 32
```python
from typing import List
```

Type hint for lists.

### Line 34
```python
from scan_scheduler_v2 import BeliefUCBScheduler, recommended_warmup_dwell
```

Imports:

- `BeliefUCBScheduler`;
- `recommended_warmup_dwell()`.

`BeliefUCBScheduler` is actually not used later in this file. The important import here is `recommended_warmup_dwell`.

### Line 35
```python
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
```

Imports:

- plain PRIAware;
- sparse-radar test scenario.

### Line 36
```python
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
```

Imports V4 scheduler.

---

# Lines 38–42 — Constants

### Line 38
```python
N_BANDS = 8
```

Simulation has 8 frequency bands.

### Line 39
```python
N_STEPS = 4000
```

Each simulation lasts 4000 timesteps.

### Line 40
```python
WARMUP = 800
```

Normal warmup length is 800 steps.

### Line 41
```python
SEEDS = list(range(1, 31))
```

Creates:

```text
[1, 2, 3, ..., 30]
```

So 30 random seeds.

### Line 42
```python
# single-seed and even 10-seed reads misleading
```

Comment explains why 30 seeds are being used.

The project has found that small samples can make the scheduler look better/worse than it really is.

---

# Lines 45–84 — `capture()`

This is the core measurement function.

### Line 45
```python
def capture(sched_cls, cost: int, seed: int, warmup: int = WARMUP, **kw):
```

Defines experiment runner.

Parameters:

```text
sched_cls → scheduler class
cost      → switch cost
seed      → random seed
warmup    → warmup duration
**kw      → extra scheduler parameters
```

---

### Lines 46–49 — Function docstring

The important point:

```text
switch cost is applied from t=0
```

That means warmup isn't artificially protected.

The hardware experiences switch cost during warmup exactly as it would after warmup.

This is realistic.

---

### Line 50
```python
scenario = make_sparse_scenario(N_BANDS)
```

Creates sparse radar + communication scenario.

Recall from V3:

- radar band 5 has true PRI 12;
- communication emitter exists on band 1;
- agile emitters occupy other bands.

---

### Line 51
```python
random.seed(seed)
```

Resets random generator.

This makes each `(scheduler, cost, seed)` run deterministic.

---

### Line 52
```python
sched = sched_cls(N_BANDS, ucb_c=0.5, warmup_steps=warmup, **kw)
```

Constructs scheduler.

Common arguments:

```text
n_bands = 8
ucb_c = 0.5
warmup_steps = chosen warmup
```

Then `kw` adds things such as:

```python
warmup_dwell_steps
warmup_dwell_jitter
switch_lead_steps
```

---

### Line 53
```python
env = scenario()
```

Creates fresh environment.

This matters because environment time starts at zero.

---

### Line 54
```python
radar_pulses = radar_caught = 0
```

Initializes two radar counters:

```text
radar_pulses  → number of actual radar pulses after warmup
radar_caught  → number scheduler successfully observed
```

Python chained assignment sets both to zero.

---

### Line 55
```python
comm1_on = comm1_caught = 0
```

Same idea for communication emitter on band 1.

---

### Line 56
```python
prev_bands = set()
```

No previously scanned bands at beginning.

Used to detect switching.

---

### Line 57
```python
settling_remaining = {}
```

Dictionary tracking remaining settling time per band.

Conceptually:

```text
band 5 → 1
band 2 → 0
```

---

# Lines 58–81 — Simulation loop

### Line 58
```python
for t in range(N_STEPS):
```

Runs:

```text
t = 0 ... 3999
```

4000 iterations.

---

### Line 59
```python
status = env.step()
```

Advances environment by one timestep.

Returns dictionary:

```text
band → active/inactive
```

---

### Line 60
```python
bands = sched.choose_bands(1)
```

Scheduler chooses **one band**.

This validation therefore uses:

```text
k = 1
```

---

### Line 61
```python
for band in bands:
```

Process selected band.

---

### Line 62
```python
blocked = False
```

Assume scan is initially valid.

---

# Lines 63–68 — Apply switch cost

### Line 63
```python
if cost > 0:
```

Only settling logic is needed when cost is nonzero.

---

### Line 64
```python
if band not in prev_bands:
```

Checks whether selected band wasn't already selected in previous timestep.

If yes:

> scheduler has switched into this band.

---

### Line 65
```python
settling_remaining[band] = cost
```

Starts settling countdown.

If:

```text
cost = 2
```

then:

```text
settling_remaining[band] = 2
```

---

### Line 66
```python
if settling_remaining.get(band, 0) > 0:
```

Gets remaining settling time.

`.get(band, 0)` means:

```text
if band exists → its value
otherwise → 0
```

Then checks whether settling remains.

---

### Line 67
```python
settling_remaining[band] -= 1
```

Consumes one settling step.

### Line 68
```python
blocked = True
```

Marks observation as invalid.

This is critical:

```text
blocked = True
```

means scheduler sees no usable observation and therefore cannot learn from it.

---

# Lines 69–75 — Valid observations and captures

### Line 69
```python
if not blocked:
```

Only execute if receiver has finished settling.

### Line 70
```python
sched.update(band, status[band])
```

Give scheduler observation.

This updates:

- Markov belief;
- scan counts;
- PRI hit history if band is ON.

So **only valid post-settling scans contribute to learning**.

---

### Line 71
```python
if t > warmup:
```

Only performance after warmup counts.

Notice:

```text
t > warmup
```

rather than:

```text
t >= warmup
```

So timestep exactly equal to `warmup` is excluded.

This is a boundary choice.

---

### Line 72
```python
if band == 5 and status[5] and not blocked:
```

If:

1. scanned radar band 5;
2. radar is active;
3. scan wasn't blocked;

then radar pulse was successfully caught.

---

### Line 73
```python
radar_caught += 1
```

Increment successful radar observations.

---

### Line 74
```python
if band == 1 and status[1] and not blocked:
```

Same logic for communication band 1.

### Line 75
```python
comm1_caught += 1
```

Increment successful communication captures.

---

### Line 76
```python
prev_bands = set(bands)
```

Stores current selected bands for next timestep.

Since `bands` is a collection, `set()` gives membership-based comparison.

---

# Lines 77–81 — Count opportunities

### Line 77
```python
if t > warmup:
```

Only count post-warmup opportunities.

### Line 78
```python
if status[5]:
```

Radar pulse exists.

### Line 79
```python
radar_pulses += 1
```

Count it.

### Line 80
```python
if status[1]:
```

Communication emitter active.

### Line 81
```python
comm1_on += 1
```

Count communication opportunities.

---

# Lines 82–84 — Calculate capture percentages

### Line 82
```python
radar_pct = 100 * radar_caught / radar_pulses if radar_pulses else 0.0
```

Calculates:

$$
\text{Radar capture}
=
100
\frac{\text{caught pulses}}
{\text{actual pulses}}
$$

If no pulses exist, returns 0 instead of dividing by zero.

---

### Line 83
```python
comm1_pct = 100 * comm1_caught / comm1_on if comm1_on else 0.0
```

Same for communication band 1.

---

### Line 84
```python
return radar_pct, comm1_pct, sched.confidence[5]
```

Returns three values:

```text
radar capture %
comm1 capture %
final PRI confidence for radar band 5
```

---

# Lines 87–93 — `summarize()`

### Line 87
```python
def summarize(label: str, vals: List[float]):
```

Formats summary statistics.

### Line 88
```python
mean = statistics.mean(vals)
```

Average capture percentage.

### Line 89
```python
sd = statistics.pstdev(vals)
```

Population standard deviation.

Important difference from:

```python
statistics.stdev()
```

`pstdev()` treats supplied values as the complete population being summarized.

---

### Line 90
```python
locked = sum(1 for v in vals if v > 50.0)
```

Counts seeds where capture exceeds 50%.

This is the script's operational definition of:

```text
locked-on
```

It is not the same as PRI confidence ≥ 0.5.

It means actual radar capture >50%.

---

### Lines 91–93
```python
print(...)
```

Outputs:

```text
mean ± standard deviation
locked-on count
minimum
maximum
```

Example:

```text
D) ... : 72.0% +/- 20.0%
(locked-on >50% in 24/30 seeds, min=..., max=...)
```

---

# Lines 96–114 — Main cost loop

### Line 96
```python
def main():
```

Main function.

### Line 97
```python
for cost in (1, 2):
```

Tests two switch costs:

```text
1 step
2 steps
```

---

### Line 98
```python
lead = cost
```

Sets:

```text
switch_lead_steps = switch_cost_steps
```

This incorporates the previously validated re-acquisition correction.

---

### Lines 100–106

These comments explain why the chosen dwell is:

```text
cost + 2
```

rather than simply:

```text
cost + 1
```

The key problem is warmup budget.

If each band gets more dwell, fewer complete sweeps fit inside 800 steps.

Therefore simply increasing dwell can actually **reduce the number of useful observations per band**.

---

### Line 107
```python
dwell = cost + 2
```

For:

```text
cost = 1 → dwell = 3
cost = 2 → dwell = 4
```

---

### Line 108
```python
warmup_scaled = int(WARMUP * dwell / (dwell - cost))
```

This is the mathematical compensation.

Suppose:

```text
cost = 1
dwell = 3
WARMUP = 800
```

Then:

$$
800 \times \frac{3}{3-1}
=
800 \times 1.5
=
1200
$$

So warmup becomes 1200.

For cost 2:

$$
800\times\frac{4}{4-2}
=1600
$$

Thus:

```text
cost 1 → warmup 1200
cost 2 → warmup 1600
```

---

### Lines 109–110
```python
assert recommended_warmup_dwell(...) == (...)
```

This is a consistency check.

It verifies that V2's helper function returns exactly the values derived here.

If not, Python raises:

```text
AssertionError
recommended_warmup_dwell() drifted from this script's own derivation
```

This protects against the helper and validation script silently disagreeing.

---

### Lines 112–114

Prints a large heading showing:

```text
switch cost
dwell
original warmup
scaled warmup
switch lead
```

For example:

```text
switch_cost_steps = 1
warmup_dwell_steps = 3
warmup_steps scaled 800 -> 1200
switch_lead_steps = 1
```

---

# Lines 116–128 — Define variants A–E

This dictionary is the heart of the experiment.

### Line 116
```python
variants = {
```

Creates mapping from experiment name to configuration.

---

## Variant A — Lines 117–118

```python
"A) dwell=1, warmup=800 (original, broken)"
```

Uses:

```python
warmup_dwell_steps=1
```

and:

```python
switch_lead_steps=lead
```

No jitter specified, so default applies.

This reproduces original warmup behavior.

---

## Variant B — Lines 119–120

```text
dwell = cost + 2
jitter = 0
warmup = 800
```

Tests:

> Does simply holding each band longer solve the problem?

No budget compensation.

---

## Variant C — Lines 121–122

Same dwell and no jitter, but:

```python
warmup = warmup_scaled
```

Tests:

> Is the missing ingredient simply more warmup time?

---

## Variant D — Lines 123–124

Uses:

```text
dwell
jitter = 1
scaled warmup
```

This represents corrected plain PRIAware.

---

## Variant E — Lines 125–127

Uses same settings as D, but:

```python
PersistentPRIAwareScheduler
```

This adds V4's lifetime characterization bonus.

The purpose is to test whether persistence eliminates remaining seed sensitivity.

---

### Line 128
```python
}
```

Closes variant dictionary.

---

# Lines 130–137 — Run all variants

### Line 130
```python
results = {name: {"radar": [], "comm1": [], "conf": []} for name in variants}
```

Creates nested result dictionary.

Each variant gets:

```text
radar → []
comm1 → []
conf  → []
```

---

### Line 131
```python
for seed in SEEDS:
```

30 seeds.

---

### Line 132
```python
for name, (warmup, cls, kw) in variants.items():
```

For every seed, run all five variants.

Total:

```text
30 seeds × 5 variants × 2 costs
= 300 episodes
```

---

### Lines 133–134
```python
radar_pct, comm1_pct, conf = capture(...)
```

Runs one experiment and unpacks three returned values.

---

### Line 135
```python
results[name]["radar"].append(radar_pct)
```

Stores radar capture.

### Line 136
```python
results[name]["comm1"].append(comm1_pct)
```

Stores communication capture.

### Line 137
```python
results[name]["conf"].append(conf)
```

Stores final radar PRI confidence.

---

# Lines 139–152 — Print results

### Line 139
```python
print(f"\nRadar capture (band 5, {len(SEEDS)} seeds):")
```

Begins radar results.

### Lines 140–141
```python
for name in variants:
    summarize(name, results[name]["radar"])
```

Prints summary for each variant.

---

### Line 143
```python
print(f"\nComm-1 capture (band 1, the cost, {len(SEEDS)} seeds):")
```

Begins communication results.

The phrase `"the cost"` appears literally in this output string; it looks like wording carried from the author's notes rather than a special variable.

---

### Lines 144–145
```python
for name in variants:
    summarize(name, results[name]["comm1"])
```

Summarizes communication capture.

This is important because improving radar lock-on shouldn't destroy communication performance.

---

### Line 147
```python
print(f"\nFinal periodicity confidence on band 5 ({len(SEEDS)} seeds):")
```

Starts confidence section.

### Line 148
```python
for name in variants:
```

Loop through variants.

### Line 149
```python
vals = results[name]["conf"]
```

Gets confidence values.

### Lines 150–151
```python
print(...)
```

Reports:

- mean confidence;
- number of seeds where confidence ≥ 0.5.

This provides a **model-confidence view**, complementary to actual radar capture.

---

### Line 152
```python
print()
```

Blank line.

---

# Lines 154–162 — Cost-zero sanity check

This is a very useful control experiment.

### Lines 154–156

The script states expected behavior:

```text
cost = 0
```

should reproduce the existing headline:

```text
100.0% radar
79.0% comm-1
```

And all dwell/jitter variants should collapse to the same result because settling is nonexistent.

This tests whether the new warmup-dwell logic accidentally changes normal zero-cost behavior.

---

### Line 157
```python
for name, kw in {
```

Defines two simple configurations.

### Line 158
```python
"dwell=1 (default)": dict(warmup_dwell_steps=1),
```

Default dwell.

### Line 159
```python
"dwell=2, jitter=1": dict(warmup_dwell_steps=2, warmup_dwell_jitter=1),
```

Alternative dwell with jitter.

### Line 160
```python
}.items():
```

Ends dictionary and starts iteration.

---

### Line 161
```python
radar_pct, comm1_pct, conf = capture(PRIAwareScheduler, 0, seed=11, **kw)
```

Runs PRIAware with:

```text
cost = 0
seed = 11
```

for each configuration.

Because cost is zero, settling should not matter.

---

### Line 162
```python
print(f"  {name:22s}: radar={radar_pct:.1f}%  comm1={comm1_pct:.1f}%  conf={conf:.2f}")
```

Prints radar capture, communication capture and PRI confidence.

---

# Lines 165–166 — Entry point

### Line 165
```python
if __name__ == "__main__":
```

Runs only when script is executed directly.

### Line 166
```python
main()
```

Starts the complete validation.

---

# The experiment in one picture

The five variants are designed to answer progressively narrower questions:

```text
A: dwell=1, warmup=800
        │
        │ Does original fail?
        ▼
B: dwell>1, warmup=800
        │
        │ Is dwell alone enough?
        ▼
C: dwell>1, warmup=SCALED
        │
        │ Is budget compensation enough?
        ▼
D: dwell>1 + jitter + scaled warmup
        │
        │ Does complete plain-PRIAware fix work?
        ▼
E: D + Persistent V4
        │
        │ Does persistence remove remaining seed sensitivity?
        ▼
    final behavior
```

And it tests this under:

```text
switch cost = 1
switch cost = 2
```

with:

```text
30 seeds each
```

---

## The key mathematical insight

Suppose:

- warmup budget = $W$
- dwell = $D$
- switch cost = $C$

Then only approximately:

$$
D-C
$$

steps per dwell cycle are useful for learning.

The script compensates by scaling:

$$
W_{\text{new}}
=
W
\frac{D}{D-C}
$$

That is exactly what line 108 implements:

```python
warmup_scaled = int(WARMUP * dwell / (dwell - cost))
```

For this script:

| Cost | Dwell | Scaled warmup |
|---:|---:|---:|
| 1 | 3 | 1200 |
| 2 | 4 | 1600 |

So the fix isn't simply **"increase dwell."**

It is:

> **Increase dwell enough to obtain valid observations, then increase total warmup enough to compensate for the observation budget consumed by settling.**

And V4's persistence is then layered on top to address the remaining stochastic lock-on problem.

**Next file: `validate_beacon_switchcost_dwell.py` — 162 lines.**

# `validate_beacon_switchcost_dwell.py`

## Lines 1–49: Module documentation

### Line 1
```python
"""
```

Starts a **multi-line string**.

Because this appears at the beginning of the file, Python treats it as the module's **docstring**.

A module docstring documents what entire Python file does.

---

### Line 2
```python
validate_beacon_switchcost_dwell.py
```

Simply the filename written inside documentation.

No executable effect.

---

### Line 3
```python
=====================================
```

Visual separator.

Again, no executable effect.

---

### Line 4
```python
Generalizes validate_warmup_dwell_fix.py's 30-seed methodology from the
```

Explains purpose.

This script takes methodology from:

```text
validate_warmup_dwell_fix.py
```

That earlier script tested the warmup/dwell fix on **sparse single-pulse radar**.

This script applies similar testing to the **beacon scenario**.

---

### Line 5
```python
sparse single-pulse radar to the multi-step BEACON scenario (PeriodicEmitter
```

Clarifies scenario being tested.

The earlier radar emitted only a single pulse periodically.

The beacon is different:

- it stays ON for multiple consecutive timesteps
- it repeats periodically.

The implementation uses `PeriodicEmitter`.

---

### Line 6
```python
on bands [2,5,6], true period 12 steps, ON for 4 consecutive steps per
```

Beacon characteristics:

```text
bands = 2, 5, 6
period = 12 steps
ON duration = 4 steps
```

So conceptually:

```text
12-step cycle:

ON ON ON ON OFF OFF OFF OFF OFF OFF OFF OFF
<------4------> <--------8-------->
```

Then repeats.

---

### Line 7
```python
cycle -- see make_scenario() in scan_scheduler_prototype.py).
```

Points reader to the actual scenario construction.

The function is:

```python
make_scenario()
```

inside:

```text
scan_scheduler_prototype.py
```

So this file does not recreate beacon behavior itself.

It imports the existing scenario.

---

### Line 8
```python

```

Blank line.

No executable effect.

---

### Line 9
```python
Important difference discovered while setting this up, worth stating up
```

Documentation warning.

The sparse-radar experiment and beacon experiment **cannot blindly use same warmup strategy**.

---

### Line 10
```python
front rather than assuming the sparse-radar recipe transfers unchanged:
```

Emphasizes that.

A fix that works for one signal type isn't automatically general.

---

### Line 11
```python
this project has ALWAYS run the beacon comparison with warmup_steps=0 (no
```

Important.

Existing beacon experiments use:

```python
warmup_steps = 0
```

Meaning:

**no dedicated warmup phase.**

The scheduler starts normal adaptive operation immediately.

---

### Line 12
```python
explicit warmup phase at all) -- unlike the sparse radar, which needed an
```

Contrast:

### Beacon
```text
warmup = 0
```

### Sparse radar
```text
warmup = 800
```

Why?

Sparse radar has very few observations, so it needs enough opportunities to detect its periodicity.

---

### Line 13
```python
800-step warmup to have any chance of characterizing a 1-in-12 signal.
```

Sparse radar activates approximately once every 12 steps.

During 800 steps, expected pulses:

$$
\frac{800}{12}\approx66.7
$$

But the scheduler doesn't necessarily scan radar band every timestep.

Hence it may only observe around 8 pulses.

That was near the minimum number required for PRI estimation.

---

### Line 14
```python
Checked directly: even at switch_cost=0 with warmup=0, PRIAware's
```

The author experimentally checked the baseline.

Even with:

```text
switch cost = 0
warmup = 0
```

PRIAware does not consistently build strong periodicity models.

---

### Line 15
```python
periodicity confidence on bands 2/5/6 locks on inconsistently across
```

Bands:

```text
2
5
6
```

are beacon bands.

"Locks on" means PRI detection produces sufficiently high confidence.

---

### Line 16
```python
seeds (often 0.00/0.00/0.00, sometimes one band locks) -- the beacon's
```

Because scheduler/environment randomness changes between seeds, periodicity confidence varies.

Often:

```text
band 2 = 0
band 5 = 0
band 6 = 0
```

Sometimes one gets detected.

---

### Line 17
```python
2-state Markov belief already carries most of the interception weight,
```

This is key.

PRIAware has two information sources:

1. Markov belief
2. periodicity model

For this beacon, ordinary Markov learning is already effective.

Why?

Because beacon stays ON for **4 consecutive steps**.

That gives scheduler repeated observations during each active period.

---

### Line 18
```python
which is exactly why the original beacon-regression work characterized
```

Refers to earlier analysis.

---

### Line 19
```python
PRIAware as "roughly a wash" against plain BeliefUCB there.
```

Meaning PRIAware wasn't dramatically better or worse than BeliefUCB in original beacon tests.

---

### Line 20
```python

```

Blank.

---

### Line 21
```python
So this script checks TWO separate questions, not one:
```

The experiment has two goals.

---

### Line 22
```python
  1. Does switch_cost_steps degrade beacon interception at all under the
```

Question 1:

Does switching itself hurt performance?

---

### Line 23
```python
     project's existing warmup=0 convention (same question asked of
```

This preserves original methodology.

No artificial warmup.

---

### Line 24
```python
     RoundRobin/Random/BeliefUCB in switch_cost_comparison.py, extended
```

The existing switch-cost comparison already studied:

- RoundRobin
- Random
- BeliefUCB

This script extends that investigation to:

- PRIAware
- PersistentPRIAware.

---

### Line 25
```python
     to PRIAware/PersistentPRIAware)?
```

Completes question 1.

---

### Line 26
```python
  2. Does explicitly adding the dwell+jitter+switch_lead+v4 fix combo
```

Question 2:

What happens if we apply the sparse-radar fix?

Components:

```text
dwell
jitter
switch_lead
V4 persistent characterization
```

---

### Line 27
```python
     (validated on the sparse radar) actually help here, or is it a
```

Does same fix improve beacon?

---

### Line 28
```python
     wasted, even counterproductive, warmup investment for a scenario
```

Possibility:

The warmup might consume time without providing useful information.

---

### Line 29
```python
     that doesn't lean on periodicity locking the way the radar does?
```

Exactly.

Sparse radar **needs** periodicity identification.

Beacon may not.

---

### Line 30
```python

```

Blank.

---

### Line 31
```python
RESULT (30 seeds, k=1 and k=2, cost=1 and cost=2): question 2's answer is
```

Experiment result.

Tests:

```text
30 seeds
k = 1
k = 2
switch cost = 1
switch cost = 2
```

Question 2 answer:

**No.**

---

### Line 32
```python
NO -- the fix does NOT generalize, and is actively counterproductive here.
```

Very strong conclusion.

The fix doesn't merely fail to help.

It makes performance worse.

---

### Line 33
```python
Plain PRIAware with the project's existing warmup=0 convention beats every
```

Baseline PRIAware:

```python
warmup_steps=0
```

outperforms all modified variants.

---

### Line 34
```python
"+fix" variant on both interception rate AND periodicity lock-on rate, at
```

The baseline wins on:

1. interception percentage
2. PRI lock-on frequency

---

### Line 35
```python
every (k, cost) combination tested.
```

Across all tested combinations.

---

### Line 36
```python
Isolating the mechanism (see isolate_mechanism() below) shows the artificial
```

Later function:

```python
isolate_mechanism()
```

tries to determine **which component causes damage**.

---

### Line 37
```python
warmup-dwell phase itself is the cost, not switch_lead_steps (which is close
```

Finding:

**warmup/dwell is harmful.**

`switch_lead_steps` isn't the main problem.

---

### Line 38
```python
to neutral here, same as found earlier): the beacon's high duty cycle (ON 4 of every 12 steps,
```

Beacon duty cycle:

$$
\frac{4}{12}=\frac13\approx33.3\%
$$

That's much more frequent than sparse radar.

---

### Line 39
```python
across 3 bands) means the scheduler's ordinary online belief+UCB learning
```

There are three beacon bands.

Because beacon activity is relatively frequent, ordinary adaptive learning gets enough observations.

---

### Line 40
```python
already visits it plenty even under switch cost -- there's no sample-
```

Switching doesn't starve beacon observations sufficiently to require forced warmup.

---

### Line 41
```python
starvation problem to fix. A forced, uniform, blind warmup sweep just
```

Artificial warmup scans bands systematically without using learned information.

That's the problem.

---

### Line 42
```python
burns budget that the adaptive policy would otherwise have spent more
```

Warmup consumes simulation steps.

During those steps, adaptive scheduler could have made smarter choices.

---

### Line 43
```python
productively. The sparse-radar fix is a fix for genuinely rare,
```

Sparse-radar fix should be viewed as targeted.

---

### Line 44
```python
sample-starved periodic signals specifically, not a universal switch-cost
```

Core lesson:

> Fix must match failure mechanism.

---

### Line 45
```python
patch -- applying it to a signal that was never starved in the first
```

If no starvation exists, adding warmup creates unnecessary cost.

---

### Line 46
```python
place is a net loss.
```

Final conclusion.

---

### Line 47
```python
Run: python3 validate_beacon_switchcost_dwell.py
```

Command for executing script.

---

### Line 48
```python
"""
```

Ends module docstring.

---

### Line 49
```python

```

Blank line.

---

# Lines 51–60: Imports

### Line 51
```python
import random
```

Imports Python's standard random-number module.

Used to control stochastic behavior:

```python
random.seed(seed)
```

---

### Line 52
```python
import statistics
```

Imports statistical functions.

Later used for:

```python
statistics.mean(...)
statistics.pstdev(...)
```

---

### Line 53
```python
from typing import List
```

Imports `List` type annotation.

**Important:** in this file, `List` is not subsequently used.

So this is effectively an unused import.

---

### Line 54
```python

```

Blank.

---

### Line 55
```python
from scan_scheduler_v2 import (
```

Starts multi-line import from V2.

---

### Line 56
```python
    RoundRobinScheduler, BeliefUCBScheduler, run_episode, recommended_warmup_dwell
```

Imports four things:

### `RoundRobinScheduler`
Open-loop baseline.

### `BeliefUCBScheduler`
Markov-belief + UCB scheduler.

### `run_episode`
Simulation engine.

### `recommended_warmup_dwell`
Calculates appropriate dwell/warmup values for a switch cost.

---

### Line 57
```python
)
```

Closes import.

---

### Line 58
```python
from scan_scheduler_v3_pri import PRIAwareScheduler
```

Imports V3 scheduler.

This is the normal periodicity-aware scheduler.

---

### Line 59
```python
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
```

Imports V4 scheduler.

This is PRIAware with persistent characterization bonus.

---

### Line 60
```python
from scan_scheduler_prototype import make_scenario
```

Imports scenario generator from V1.

This gives this script the original **beacon scenario**.

---

# Lines 62–65: Constants

### Line 62
```python
N_BANDS = 8
```

Simulation has 8 frequency bands:

```text
0 1 2 3 4 5 6 7
```

---

### Line 63
```python
N_STEPS = 4000
```

Each experiment runs:

$$
4000
$$

timesteps.

---

### Line 64
```python
SEEDS = list(range(1, 31))
```

Creates:

```python
[1, 2, 3, ..., 30]
```

So there are exactly **30 random seeds**.

---

### Line 65
```python
BASE_WARMUP = 800  # only used by the "+fix" variants, matching the radar validation
```

Baseline warmup length:

```text
800 steps
```

But this is **not** used by baseline PRIAware.

Only modified "+fix" variants use it.

This matches sparse-radar validation.

---

# Lines 68–80: `run_one()`

### Line 68
```python
def run_one(cls, seed, k, cost, **kw):
```

Defines helper function.

Parameters:

| Parameter | Meaning |
|---|---|
| `cls` | scheduler class |
| `seed` | random seed |
| `k` | number of simultaneously scanned channels |
| `cost` | switching cost |
| `**kw` | extra scheduler parameters |

Example:

```python
run_one(
    PRIAwareScheduler,
    5,
    2,
    1,
    warmup_steps=1200
)
```

---

### Line 69
```python
    random.seed(seed)
```

Sets Python RNG seed.

This makes stochastic scheduler/environment behavior reproducible for that run.

---

### Line 70
```python
    scenario = make_scenario(N_BANDS)
```

Creates beacon scenario with 8 bands.

Important:

`make_scenario()` itself creates emitter objects.

---

### Line 71
```python
    if cls is RoundRobinScheduler:
```

Checks whether requested scheduler class is **exactly** `RoundRobinScheduler`.

---

### Line 72
```python
        sched = cls(N_BANDS)
```

Creates RoundRobin scheduler.

No `ucb_c` or special parameters are supplied because RoundRobin doesn't need them.

---

### Line 73
```python
    elif cls is BeliefUCBScheduler:
```

Checks whether scheduler is exactly BeliefUCB.

---

### Line 74
```python
        sched = cls(N_BANDS, ucb_c=0.5, **kw)
```

Creates BeliefUCB with:

```python
ucb_c = 0.5
```

plus any additional keyword arguments.

---

### Line 75
```python
    else:
```

Anything other than exact RoundRobin or exact BeliefUCB ends up here.

That includes:

```text
PRIAwareScheduler
PersistentPRIAwareScheduler
```

---

### Line 76
```python
        sched = cls(N_BANDS, ucb_c=0.5, **kw)
```

Constructs whichever PRIAware-class scheduler was requested.

Again:

```python
ucb_c=0.5
```

---

### Line 77
```python
    stats = run_episode(scenario, sched, N_STEPS, N_BANDS, k_channels=k, switch_cost_steps=cost)
```

Runs complete 4000-step simulation.

Arguments:

```text
scenario       → beacon environment
sched          → selected scheduler
N_STEPS        → 4000
N_BANDS        → 8
k_channels     → 1 or 2
switch_cost_steps → 0, 1, or 2
```

The important experiment variables are therefore:

$$
k\in\{1,2\}
$$

and

$$
C\in\{0,1,2\}.
$$

---

### Line 78
```python
    r = stats.report()
```

Converts accumulated statistics into a report dictionary.

Likely contains metrics such as:

```python
r["interception_ratio"]
```

---

### Line 79
```python
    beacon_conf = max(sched.confidence[b] for b in (2, 5, 6)) if hasattr(sched, "confidence") else 0.0
```

This line has several pieces.

First:

```python
hasattr(sched, "confidence")
```

asks:

> Does scheduler have a `confidence` attribute?

PRIAware does.

RoundRobin doesn't.

If it exists:

```python
sched.confidence[b]
```

gets confidence for each beacon band:

```text
2
5
6
```

Then:

```python
max(...)
```

takes the highest confidence.

So if:

```text
band 2 = 0.2
band 5 = 0.7
band 6 = 0.1
```

then:

```text
beacon_conf = 0.7
```

The use of `max` means the script considers the beacon "represented" if **at least one** beacon band has strong periodicity confidence.

If scheduler doesn't have `confidence`, it returns:

```python
0.0
```

---

### Line 80
```python
    return r["interception_ratio"] * 100, beacon_conf
```

Returns two values:

1. interception percentage
2. maximum beacon PRI confidence

Why multiply by 100?

`interception_ratio` is presumably stored as:

```text
0.0 → 1.0
```

while output wants:

```text
0% → 100%
```

Example:

```python
0.734
```

becomes:

```text
73.4%
```

---

# Lines 83–86: `summarize()`

### Line 83
```python
def summarize(label, vals):
```

Defines function to print summary statistics.

Arguments:

```text
label → scheduler name
vals  → list of results
```

---

### Line 84
```python
    mean = statistics.mean(vals)
```

Calculates arithmetic mean:

$$
\bar{x}=\frac{1}{n}\sum_i x_i
$$

Across 30 seeds.

---

### Line 85
```python
    sd = statistics.pstdev(vals)
```

Calculates **population standard deviation**.

`pstdev`, not `stdev`.

So denominator is effectively:

$$
N
$$

rather than:

$$
N-1.
$$

---

### Line 86
```python
    print(f"  {label:52s}: {mean:6.1f}% +/- {sd:5.1f}%   (min={min(vals):5.1f}%  max={max(vals):5.1f}%)")
```

Prints formatted summary.

### `{label:52s}`

String occupies width 52.

### `{mean:6.1f}`

Mean:

- width 6
- one decimal place

### `% +/-`

Displays:

```text
mean ± standard deviation
```

### `min(vals)`

Lowest seed result.

### `max(vals)`

Highest seed result.

Example:

```text
PRIAware ... : 72.3% +/- 4.1% (min=65.0% max=79.2%)
```

---

# Lines 89–125: `main()`

### Line 89
```python
def main(ks=(1, 2)):
```

Defines main experiment.

Default:

```python
ks = (1, 2)
```

So test both:

```text
k=1
k=2
```

---

### Line 90
```python
    for k in ks:
```

Loops over requested channel counts.

---

### Line 91
```python
        print(f"{'='*100}\nBeacon scenario, k_channels={k}  ({len(SEEDS)} seeds)\n{'='*100}")
```

Prints header.

`'=' * 100` creates 100 equals signs.

`\n` creates new lines.

`len(SEEDS)` is:

```text
30
```

Example:

```text
====================================================================================================
Beacon scenario, k_channels=1  (30 seeds)
====================================================================================================
```

---

### Line 92
```python
        for cost in (0, 1, 2):
```

Tests three switch costs:

```text
0
1
2
```

Meaning switching can consume:

```text
0 steps
1 step
2 steps
```

---

### Line 93
```python
            dwell, warmup_scaled = recommended_warmup_dwell(cost, BASE_WARMUP, margin=2) \
```

Calls helper from V2.

The backslash:

```python
\
```

continues expression onto next line.

For positive switch cost, it calculates:

- recommended dwell
- adjusted warmup.

---

### Line 94
```python
                if cost > 0 else (1, 0)
```

Conditional expression.

Equivalent conceptually to:

```python
if cost > 0:
    result = recommended_warmup_dwell(...)
else:
    result = (1, 0)
```

For:

```text
cost = 0
```

it uses:

```python
dwell = 1
warmup = 0
```

because no switch-cost fix is needed.

---

### Line 95
```python
            print(f"\n--- switch_cost_steps = {cost} "
```

Starts printing experiment configuration.

---

### Line 96
```python
                  f"{'(fix variants use warmup_dwell_steps=' + str(dwell) + ', warmup_steps=' + str(warmup_scaled) + ', switch_lead_steps=' + str(cost) + ')' if cost > 0 else '(baseline, no fix applicable)'} ---")
```

This is a dense formatting line.

If:

```text
cost > 0
```

it prints calculated fix parameters.

For cost 1:

```text
warmup_dwell_steps = 3
warmup_steps = 1200
switch_lead_steps = 1
```

For cost 2:

```text
warmup_dwell_steps = 4
warmup_steps = 1600
switch_lead_steps = 2
```

If cost = 0:

```text
(baseline, no fix applicable)
```

---

### Line 97
```python

```

Blank.

---

### Line 98
```python
            variants = {
```

Creates dictionary describing schedulers to test.

---

### Line 99
```python
                "RoundRobin (open-loop reference)": (RoundRobinScheduler, {}),
```

First variant:

```text
RoundRobin
```

with no special kwargs.

Tuple:

```python
(RoundRobinScheduler, {})
```

contains:

1. class
2. keyword arguments.

---

### Line 100
```python
                "BeliefUCB (Markov-only)": (BeliefUCBScheduler, {}),
```

Second:

```text
BeliefUCB
```

No extra kwargs.

"Markov-only" emphasizes that it doesn't use PRI.

---

### Line 101
```python
                "PRIAware, warmup=0 (project's existing convention)": (PRIAwareScheduler, {}),
```

Third:

Baseline PRIAware.

Crucially:

```python
{}
```

means no warmup parameters.

So:

```text
warmup = 0
```

---

### Line 102
```python
            }
```

Closes dictionary.

---

### Line 103
```python
            if cost > 0:
```

Only add fix variants when there is actual switching cost.

---

### Line 104
```python
                fix_kw = dict(warmup_steps=warmup_scaled, warmup_dwell_steps=dwell,
```

Creates dictionary of scheduler configuration.

First two parameters:

```python
warmup_steps=warmup_scaled
warmup_dwell_steps=dwell
```

---

### Line 105
```python
                               warmup_dwell_jitter=1, switch_lead_steps=cost)
```

Adds:

```python
warmup_dwell_jitter=1
switch_lead_steps=cost
```

So full configuration is conceptually:

```python
{
    "warmup_steps": ...,
    "warmup_dwell_steps": ...,
    "warmup_dwell_jitter": 1,
    "switch_lead_steps": ...
}
```

---

### Line 106
```python
                variants["PRIAware + dwell/jitter/lead fix"] = (PRIAwareScheduler, fix_kw)
```

Adds modified PRIAware.

It gets the sparse-radar fix.

---

### Line 107
```python
                variants["PersistentPRIAware(v4) + dwell/jitter/lead fix"] = (
```

Begins adding V4 scheduler.

---

### Line 108
```python
                    PersistentPRIAwareScheduler, fix_kw)
```

V4 receives exactly same `fix_kw`.

So comparison is:

```text
PRIAware + fix
vs
PersistentPRIAware + fix
```

---

### Line 109
```python

```

Blank.

---

### Line 110
```python
            results = {name: {"intercept": [], "conf": []} for name in variants}
```

Creates nested result dictionary.

For each scheduler:

```python
{
    "intercept": [],
    "conf": []
}
```

Example:

```python
results["BeliefUCB (Markov-only)"]["intercept"]
```

will contain 30 interception percentages.

And:

```python
results["PRIAware ..."]["conf"]
```

contains 30 confidence values.

---

### Line 111
```python
            for seed in SEEDS:
```

Loops through:

```text
seed 1 → seed 30
```

---

### Line 112
```python
                for name, (cls, kw) in variants.items():
```

For every seed, run every scheduler variant.

`variants.items()` returns:

```text
name
(class, kwargs)
```

---

### Line 113
```python
                    pct, conf = run_one(cls, seed, k, cost, **kw)
```

Runs experiment.

`**kw` expands dictionary into keyword arguments.

For example:

```python
kw = {
    "warmup_steps": 1200,
    "warmup_dwell_steps": 3
}
```

becomes equivalent to:

```python
run_one(
    cls,
    seed,
    k,
    cost,
    warmup_steps=1200,
    warmup_dwell_steps=3
)
```

---

### Line 114
```python
                    results[name]["intercept"].append(pct)
```

Adds interception percentage to list.

After 30 seeds:

```python
len(results[name]["intercept"]) == 30
```

---

### Line 115
```python
                    results[name]["conf"].append(conf)
```

Stores maximum beacon PRI confidence.

---

### Line 116
```python

```

Blank.

---

### Line 117
```python
            for name in variants:
```

Loops through scheduler names.

---

### Line 118
```python
                summarize(name, results[name]["intercept"])
```

Prints mean/std/min/max interception.

---

### Line 119
```python
            print("  beacon periodicity lock-on (max confidence across bands 2/5/6):")
```

Prints heading explaining confidence metric.

Again, it is:

$$
\max(C_2,C_5,C_6)
$$

not average confidence.

---

### Line 120
```python
            for name in variants:
```

Loops through variants again.

---

### Line 121
```python
                vals = results[name]["conf"]
```

Gets 30 confidence values.

---

### Line 122
```python
                locked = sum(1 for v in vals if v >= 0.5)
```

Counts seeds where confidence is at least:

```text
0.5
```

Breakdown:

```python
for v in vals
```

examines each seed.

```python
if v >= 0.5
```

keeps successful lock-ons.

```python
sum(1 for ...)
```

counts them.

---

### Line 123
```python
                print(f"    {name:50s}: mean_conf={statistics.mean(vals):.2f}  "
```

Prints average confidence with two decimal places.

---

### Line 124
```python
                      f"locked(>=0.5) in {locked}/{len(SEEDS)} seeds")
```

Reports lock-on count.

Example:

```text
locked(>=0.5) in 17/30 seeds
```

---

### Line 125
```python
        print()
```

Blank line between `k=1` and `k=2` sections.

---

# Lines 128–155: Mechanism isolation

This function is especially important.

It asks:

> Is performance loss caused by `warmup+dwell+jitter`, or by `switch_lead_steps`?

---

### Line 128
```python
def isolate_mechanism(cost: int = 1, k: int = 1, seeds=range(1, 11)):
```

Defines diagnostic experiment.

Defaults:

```text
cost = 1
k = 1
seeds = 1..10
```

Type annotation:

```python
cost: int
k: int
```

means these are expected to be integers.

---

### Line 129
```python
    """Which piece of the sparse-radar fix is actually responsible for the
```

Starts function docstring.

---

### Line 130
```python
    beacon regression -- the artificial warmup-dwell phase, or
```

Question:

Does warmup/dwell cause regression?

---

### Line 131
```python
    switch_lead_steps? Isolates them independently."""
```

Or does switch lead cause regression?

Function tests each independently.

---

### Line 132
```python
    scenario = make_scenario(N_BANDS)
```

Creates beacon scenario.

---

### Line 133
```python
    dwell, warmup_scaled = recommended_warmup_dwell(cost, BASE_WARMUP, margin=2)
```

Calculates fix parameters.

For cost 1:

```text
dwell = 3
warmup = 1200
```

---

### Line 134
```python
    configs = {
```

Creates four configurations.

---

### Line 135
```python
        "1) baseline: warmup=0, lead=0": dict(),
```

Configuration 1:

```text
warmup = 0
lead = 0
```

This is normal PRIAware.

Empty dictionary means no optional modifications.

---

### Line 136
```python
        f"2) dwell-fix only: warmup={warmup_scaled},dwell={dwell},jit=1, lead=0": dict(
```

Configuration 2:

Uses:

- warmup
- dwell
- jitter

but:

```text
lead = 0
```

This isolates warmup-related modifications.

---

### Line 137
```python
            warmup_steps=warmup_scaled, warmup_dwell_steps=dwell, warmup_dwell_jitter=1),
```

Actual parameters for config 2.

No `switch_lead_steps`.

Therefore default remains:

```text
0
```

---

### Line 138
```python
        f"3) lead only: warmup=0, lead={cost}": dict(switch_lead_steps=cost),
```

Configuration 3:

No warmup.

Only switch lead.

For cost 1:

```python
switch_lead_steps=1
```

This tests whether lead itself hurts performance.

---

### Line 139
```python
        "4) both (the combo tested above)": dict(
```

Configuration 4 combines everything.

---

### Line 140
```python
            warmup_steps=warmup_scaled, warmup_dwell_steps=dwell, warmup_dwell_jitter=1,
```

Adds warmup/dwell/jitter.

---

### Line 141
```python
            switch_lead_steps=cost),
```

Adds switch lead.

So config 4 is full fix.

---

### Line 142
```python
    }
```

Closes dictionary.

---

### Line 143
```python
    print(f"\n{'='*100}\nMechanism isolation (cost={cost}, k={k}): which piece of the fix "
```

Prints mechanism-isolation header.

---

### Line 144
```python
          f"actually costs interception?\n{'='*100}")
```

Completes header.

Question printed to user:

```text
which piece of fix actually costs interception?
```

---

### Line 145
```python
    for name, kw in configs.items():
```

Loops through four configurations.

---

### Line 146
```python
        intercepts = []
```

Creates empty list for results.

---

### Line 147
```python
        for seed in seeds:
```

Runs selected configuration across seeds.

Default:

```text
1 through 10
```

---

### Line 148
```python
            random.seed(seed)
```

Resets RNG for each seed.

---

### Line 149
```python
            sched = PRIAwareScheduler(N_BANDS, ucb_c=0.5, **kw)
```

Creates PRIAware scheduler.

Notice:

**Only PRIAware is used here.**

Why?

Because this experiment wants to isolate mechanisms inside PRIAware itself.

Configuration-specific kwargs are expanded with:

```python
**kw
```

---

### Line 150
```python
            stats = run_episode(scenario, sched, N_STEPS, N_BANDS, k_channels=k,
```

Runs 4000-step episode.

---

### Line 151
```python
                                 switch_cost_steps=cost)
```

Applies specified switch cost.

---

### Line 152
```python
            intercepts.append(stats.report()["interception_ratio"] * 100)
```

Extracts interception ratio, converts to percentage, stores it.

After all seeds:

```python
intercepts
```

contains 10 values by default.

---

### Line 153
```python
        print(f"  {name:60s}: {statistics.mean(intercepts):5.1f}% +/- "
```

Prints mean and label.

---

### Line 154
```python
              f"{statistics.pstdev(intercepts):4.1f}%")
```

Prints population standard deviation.

So each configuration gets:

```text
mean ± SD
```

---

### Line 155
```python

```

Blank.

---

# Lines 157–162: Program entry point

### Line 157
```python
if __name__ == "__main__":
```

Classic Python entry-point check.

When file is executed directly:

```bash
python3 validate_beacon_switchcost_dwell.py
```

then:

```python
__name__ == "__main__"
```

is true.

If imported from another module, it is false.

---

### Line 158
```python
    import sys
```

Imports `sys` only when executing main.

Used to inspect command-line arguments.

---

### Line 159
```python
    ks = tuple(int(x) for x in sys.argv[1:]) if len(sys.argv) > 1 else (1, 2)
```

This parses optional command-line arguments.

`sys.argv` looks like:

```text
[
    "validate_beacon_switchcost_dwell.py",
    ...
]
```

`sys.argv[1:]` removes script filename.

If user runs:

```bash
python3 validate_beacon_switchcost_dwell.py 1
```

then:

```python
sys.argv[1:]
```

is:

```python
["1"]
```

and:

```python
tuple(int(x) for x in ...)
```

becomes:

```python
(1,)
```

If user runs:

```bash
python3 validate_beacon_switchcost_dwell.py 1 2
```

then:

```python
ks = (1, 2)
```

If no arguments are supplied:

```python
ks = (1, 2)
```

So command-line arguments control which `k_channels` values are tested.

---

### Line 160
```python
    main(ks)
```

Runs main experiment.

---

### Line 161
```python
    if ks == (1, 2) or 1 in ks:
```

Determines whether to run mechanism isolation.

Two cases:

### Default:
```python
ks == (1, 2)
```

True.

### User requested k=1:
```python
1 in ks
```

True.

### User requested only k=2:
```python
ks == (1, 2)  # false
1 in ks       # false
```

So mechanism isolation isn't run.

---

### Line 162
```python
        isolate_mechanism(cost=1, k=1)
```

Runs mechanism-isolation experiment with:

```text
switch cost = 1
k = 1
seeds = 1..10
```

unless different seeds are passed explicitly—which this call doesn't.

---

# What entire file does

Now compress whole program into one flow:

```text
START
  │
  ├── Define beacon scenario constants
  │
  ├── For k = 1, 2
  │     │
  │     ├── For switch cost = 0, 1, 2
  │     │      │
  │     │      ├── Calculate recommended warmup/dwell
  │     │      │
  │     │      ├── Select scheduler variants
  │     │      │     ├── RoundRobin
  │     │      │     ├── BeliefUCB
  │     │      │     ├── PRIAware warmup=0
  │     │      │     ├── PRIAware + fix
  │     │      │     └── PersistentPRIAware + fix
  │     │      │
  │     │      ├── Run each over 30 seeds
  │     │      │
  │     │      ├── Calculate interception %
  │     │      │
  │     │      └── Calculate beacon PRI confidence
  │     │
  │     └── Print statistics
  │
  └── Mechanism isolation
        │
        ├── baseline
        ├── dwell fix only
        ├── lead only
        └── both
```

## Most important conceptual takeaway

This file demonstrates a very important experimental-design principle:

### Sparse radar

```text
Rare signal
     ↓
Too few observations
     ↓
PRI model cannot lock
     ↓
Need deliberate sampling/warmup
```

### Beacon

```text
4 ON steps every 12
     ↓
Much more frequent observations
     ↓
Markov belief learns useful behavior naturally
     ↓
No serious sample starvation
     ↓
Forced warmup wastes adaptive scanning budget
     ↓
Sparse-radar fix hurts
```

So the fix is **not universally "better scheduling."**

It solves a particular problem:

> **periodic-signal sample starvation under switching cost.**

And this file experimentally establishes that the beacon **doesn't suffer that same problem**.

**Next file: `switch_cost_comparison.py` — 158 lines.**

## File 16 of 18: `switch_cost_comparison.py`

This file introduces a **realistic hardware constraint** that earlier experiments ignored: **switching from one frequency band to another takes time**. The code then measures how that affects different schedulers. `ecac83fe-3c41-4824-af84-bf0a23a1f488.md`


---

# Lines 1-29 - Module docstring

### Line 1
```python
"""
```

Starts module-level documentation.

---

### Line 2
```python
switch_cost_comparison.py
```

File name written in documentation.

No runtime effect.

---

### Line 3
```python
============================
```

Visual separator only.

---

### Line 4
```python
Every result in this project so far assumed band-hopping is free and
```

States important assumption of previous experiments:

> Changing frequency bands costs zero time.

---

### Line 5
```python
instant. Real ESM/receiver hardware needs real time to re-tune (local
```

Real Electronic Support Measure/receiver hardware cannot instantly retune.

Physical components such as local oscillators require settling.

---

### Line 6
```python
oscillator settling, filter settling) when moving to a band it wasn't
```

Two examples of physical settling:

- oscillator settling
- filter settling

---

### Line 7
```python
already parked on -- typically low microseconds to low tens of
```

The settling delay can be several microseconds.

---

### Line 8
```python
microseconds for a fast synthesizer, which at a 20us dwell (the
```

The project's PDW experiment uses a:

```text
20 μs dwell
```

If hardware takes, say, several μs to settle, that's a substantial fraction of one dwell.

---

### Line 9
```python
fine-dwell setting used for the fractional-PRI PDW work) is not
```

Reinforces why ignoring switching isn't harmless.

---

### Line 10
```python
negligible relative to a single dwell.
```

Core physical point:

$$
T_\text{settling}\not\ll T_\text{dwell}
$$

So settling must be modeled.

---

### Line 11
```python

```

Blank.

---

### Line 12
```python
scan_scheduler_v2.py's run_episode() now takes a switch_cost_steps
```

The V2 simulation engine was modified to accept:

```python
switch_cost_steps
```

This parameter represents settling delay in simulation steps.

---

### Line 13
```python
parameter (default 0, fully backward compatible -- verified byte-for-
```

Default:

```python
switch_cost_steps = 0
```

Therefore old experiments behave exactly as before.

This is important for backward compatibility.

---

### Line 14
```python
byte identical to every existing headline number in this project). When
```

The project verified that default-zero behavior preserves previous results.

---

### Line 15
```python
> 0: any channel moved to a band it wasn't scanning last step is
```

If:

```text
switch_cost_steps > 0
```

and a channel changes to a band it wasn't scanning previously, that band becomes temporarily unavailable.

---

### Line 16
```python
unobservable for that many steps (busy settling, no update() call, no
```

During settling:

- no observation
- no `update()`
- no hit credit

---

### Line 17
```python
hit credit), even if the band is genuinely transmitting.
```

This is crucial.

Suppose:

```text
band 5 = transmitting
receiver just switched to band 5
settling_remaining = 1
```

The receiver **doesn't count the hit**.

The signal exists physically, but receiver isn't ready.

---

### Line 18
```python

```

Blank.

---

### Line 19
```python
This matters most for scheduling STRATEGY, not just raw numbers:
```

The experiment isn't merely asking:

> "Does interception decrease?"

It asks:

> "Which scheduling strategy handles switching cost better?"

---

### Line 20
```python
RoundRobin moves to a new band on literally every single step by
```

With `k=1`, RoundRobin behaves approximately:

```text
0 → 1 → 2 → 3 → 4 → 5 → 6 → 7 → 0 → ...
```

Therefore every step is a switch.

---

### Line 21
```python
construction, so it should be hurt by a switch cost far more than a
```

Prediction:

RoundRobin should suffer badly.

---

### Line 22
```python
learned scheduler that tends to camp on one productive band once it's
```

BeliefUCB can remain on a useful band for multiple steps.

Therefore fewer switches.

---

### Line 23
```python
found one. This script checks whether that intuition holds, and by how
```

The experiment tests whether prediction actually occurs.

---

### Line 24
```python
much, across the standard comparisons already used throughout the
```

It uses established project scenarios rather than inventing a new benchmark.

---

### Line 25
```python
project (beacon scenario at k=1..3, and the sparse fixed-PRI radar's
```

Two experiments:

1. Beacon scenario, `k=1,2,3`
2. Sparse fixed-PRI radar

---

### Line 26
```python
per-emitter capture).
```

For radar, overall interception isn't enough.

The script specifically measures capture of individual emitters.

---

### Line 27
```python

```

Blank.

---

### Line 28
```python
Run: python3 switch_cost_comparison.py
```

Execution command.

---

### Line 29
```python
"""
```

Ends module docstring.

---

# Lines 31-39 - Imports

### Line 31
```python
import random
```

Imports Python random-number generator.

Used for reproducible scheduler randomness.

---

### Line 32
```python
from typing import Dict, List
```

Imports type-hint classes:

```python
Dict
List
```

These aren't substantially important to runtime behavior.

---

### Line 33
```python

```

Blank.

---

### Line 34
```python
from scan_scheduler_v2 import (
```

Begins multi-line import from V2.

---

### Line 35
```python
    RoundRobinScheduler, RandomScheduler, BeliefUCBScheduler, run_episode,
```

Imports:

- `RoundRobinScheduler`
- `RandomScheduler`
- `BeliefUCBScheduler`
- `run_episode`

These are the main objects needed for the comparison.

---

### Line 36
```python
    recommended_warmup_dwell
```

Imports V2 helper for calculating warmup/dwell values.

This becomes relevant in the sparse-radar experiment.

---

### Line 37
```python
)
```

Closes import.

---

### Line 38
```python
from scan_scheduler_prototype import make_scenario
```

Imports original beacon scenario generator.

---

### Line 39
```python
from scan_scheduler_v3_pri import PRIAwareScheduler, make_sparse_scenario
```

Imports:

- `PRIAwareScheduler`
- `make_sparse_scenario`

The first is needed for sparse-radar scheduling.

The second generates the sparse fixed-PRI scenario.

---

# Line 41 - Switch-cost values

### Line 41
```python
SWITCH_COSTS = [0, 1, 2, 4]  # steps of settling time per switch
```

Defines tested switch costs.

So experiment compares:

```text
0 steps
1 step
2 steps
4 steps
```

Think:

```text
cost = 0 → instantaneous switching
cost = 1 → one simulation step lost
cost = 2 → two steps lost
cost = 4 → four steps lost
```

This lets us see how performance degrades as hardware becomes slower.

---

# Lines 44-66 - `beacon_sweep()`

### Line 44
```python
def beacon_sweep():
```

Defines function testing switch cost on beacon scenario.

---

### Line 45
```python
    n_bands = 8
```

Eight frequency bands.

---

### Line 46
```python
    n_steps = 4000
```

Each experiment lasts 4000 timesteps.

---

### Line 47
```python
    scenario = make_scenario(n_bands)
```

Creates standard beacon scenario.

This is the scenario from the original prototype.

---

### Line 48
```python

```

Blank.

---

### Line 49
```python
    for k in (1, 2, 3):
```

Tests three receiver capacities:

```text
k = 1
k = 2
k = 3
```

Meaning receiver can simultaneously scan 1, 2, or 3 bands.

---

### Line 50
```python
        print(f"--- Beacon scenario, k_channels={k} ---")
```

Prints section header.

For `k=2`:

```text
--- Beacon scenario, k_channels=2 ---
```

---

### Line 51
```python
        header = f"{'switch_cost':>11s} | " + " | ".join(f"{name:>13s}" for name in
```

Builds table header.

`>11s` means right-align string within 11 characters.

---

### Line 52
```python
                  ("RoundRobin", "Random", "BeliefUCB"))
```

Creates three scheduler columns:

```text
RoundRobin
Random
BeliefUCB
```

`" | ".join(...)` produces:

```text
RoundRobin | Random | BeliefUCB
```

---

### Line 53
```python
        print(header)
```

Prints header.

---

### Line 54
```python
        print("-" * len(header))
```

Prints separator exactly as wide as header.

If header has 60 characters:

```text
------------------------------------------------------------
```

---

### Line 55
```python
        for cost in SWITCH_COSTS:
```

Loops through:

```text
0, 1, 2, 4
```

---

### Line 56
```python
            row = [f"{cost:11d}"]
```

Starts table row with switch cost.

`11d` means integer occupying width 11.

---

### Line 57
```python
            for cls, name in [(RoundRobinScheduler, "RoundRobin"), (RandomScheduler, "Random"),
```

Starts looping through scheduler classes.

First two:

```python
(RoundRobinScheduler, "RoundRobin")
(RandomScheduler, "Random")
```

---

### Line 58
```python
                               (BeliefUCBScheduler, "BeliefUCB")]:
```

Adds third:

```python
(BeliefUCBScheduler, "BeliefUCB")
```

So each switch cost gets three scheduler runs.

---

### Line 59
```python
                random.seed(7)
```

Resets RNG to seed 7 **before each scheduler run**.

This is significant.

Each scheduler starts with same seed.

---

### Line 60
```python
                sched = cls(n_bands) if cls is not BeliefUCBScheduler else cls(n_bands, ucb_c=0.5)
```

Conditional object construction.

For RoundRobin or Random:

```python
sched = cls(n_bands)
```

For BeliefUCB:

```python
sched = cls(n_bands, ucb_c=0.5)
```

Why special case?

Because only BeliefUCB expects the `ucb_c` parameter.

---

### Line 61
```python
                stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k,
```

Runs 4000-step simulation.

---

### Line 62
```python
                                     switch_cost_steps=cost)
```

Passes switch cost.

So this is the actual point where hardware settling enters simulation.

---

### Line 63
```python
                r = stats.report()
```

Converts statistics object into report dictionary.

---

### Line 64
```python
                row.append(f"{r['interception_ratio']*100:12.1f}%")
```

Gets:

```python
r["interception_ratio"]
```

Converts:

```text
0.753
```

to:

```text
75.3%
```

and adds it to table row.

---

### Line 65
```python
            print(" | ".join(row))
```

Prints completed row.

Conceptually:

```text
switch_cost | RoundRobin | Random | BeliefUCB
```

---

### Line 66
```python
        print()
```

Blank line after each `k`.

---

# Lines 69-83 - `beacon_switches_breakdown()`

This function doesn't measure interception directly.

It measures **how often each scheduler switches**.

That's the mechanism behind switch-cost sensitivity. The project notes that RoundRobin switches every step while BeliefUCB switches substantially less often. `ecac83fe-3c41-4824-af84-bf0a23a1f488.md`

### Line 69
```python
def beacon_switches_breakdown():
```

Defines diagnostic function.

---

### Line 70
```python
    """How often does each scheduler actually switch bands? This is
```

Starts function documentation.

---

### Line 71
```python
    what determines how much a switch cost hurts it."""
```

Core idea:

$$
\text{more switches}
\Rightarrow
\text{more settling}
\Rightarrow
\text{more wasted time}
$$

---

### Line 72
```python
    n_bands = 8
```

Eight bands.

---

### Line 73
```python
    n_steps = 4000
```

4000 steps.

---

### Line 74
```python
    scenario = make_scenario(n_bands)
```

Creates beacon environment.

---

### Line 75
```python
    print("--- How many band-switches does each scheduler make? (k=1, 4000 steps) ---")
```

Prints diagnostic heading.

This experiment fixes:

```text
k = 1
steps = 4000
switch cost = 1
```

---

### Line 76
```python
    for cls, name in [(RoundRobinScheduler, "RoundRobin"), (RandomScheduler, "Random"),
```

Starts scheduler loop.

---

### Line 77
```python
                       (BeliefUCBScheduler, "BeliefUCB")]:
```

Third scheduler completes list.

---

### Line 78
```python
        random.seed(7)
```

Reproducible random behavior.

---

### Line 79
```python
        sched = cls(n_bands) if cls is not BeliefUCBScheduler else cls(n_bands, ucb_c=0.5)
```

Same constructor distinction as before.

---

### Line 80
```python
        stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=1, switch_cost_steps=1)
```

Runs:

```text
4000 steps
k = 1
switch cost = 1
```

---

### Line 81
```python
        print(f"  {name:12s}: {stats.switches} switches out of {n_steps} steps "
```

Prints raw number of switches.

`stats.switches` was added to V2 specifically to measure this.

---

### Line 82
```python
              f"({100*stats.switches/n_steps:.1f}% of steps trigger a switch)")
```

Converts switches to percentage:

$$
\frac{\text{switches}}{4000}\times100
$$

If RoundRobin switches 4000 times:

$$
\frac{4000}{4000}\times100=100\%
$$

---

### Line 83
```python
    print()
```

Blank line.

---

# Lines 86-152 - `sparse_radar_sweep()`

This is the **most important part of this file**, because it exposes a major weakness in the original sparse-radar result.

### Line 86
```python
def sparse_radar_sweep():
```

Defines sparse radar experiment.

---

### Line 87
```python
    n_bands = 8
```

Eight bands.

---

### Line 88
```python
    n_steps = 4000
```

4000 simulation steps.

---

### Line 89
```python
    warmup = 800
```

PRIAware receives an 800-step warmup.

This is the same sparse-radar setup discussed in later validation.

---

### Line 90
```python
    scenario = make_sparse_scenario(n_bands)
```

Creates sparse fixed-PRI radar scenario.

---

### Line 91
```python
    print("--- Sparse fixed-PRI radar, per-emitter capture, k=1 ---")
```

Prints section title.

This time:

```text
k = 1
```

---

### Line 92
```python
    print(("(\"PRIAware\" uses defaults -- warmup switches every step, so it's\n"
```

Starts explanatory warning.

Default PRIAware warmup changes bands every timestep.

---

### Line 93
```python
          " devastated by switch cost the same way RoundRobin is. \"PRIAware+dwell\"\n"
```

Therefore, under switch cost, default PRIAware's warmup is damaged.

---

### Line 94
```python
          " adds warmup_dwell_steps/jitter + switch_lead_steps -- see\n"
```

Modified version adds:

- warmup dwell
- jitter
- switch lead

These were later properly validated in `validate_warmup_dwell_fix.py`.

---

### Line 95
```python
          " validate_warmup_dwell_fix.py for the 30-seed validation of this fix.)\n")
```

Points reader toward the later rigorous validation.

---

### Line 96
```python
    header = (f"{'switch_cost':>11s} | {'BeliefUCB radar%':>17s} | {'PRIAware radar%':>16s} | "
```

Starts output table.

Columns include:

- switch cost
- BeliefUCB radar capture
- PRIAware radar capture

---

### Line 97
```python
              f"{'PRIAware comm1%':>16s} | {'+dwell radar%':>14s} | {'+dwell comm1%':>14s}")
```

Adds:

- PRIAware communication-band capture
- fixed PRIAware radar capture
- fixed PRIAware communication capture

---

### Line 98
```python
    print(header)
```

Prints table header.

---

### Line 99
```python
    print("-" * len(header))
```

Prints separator.

---

# Lines 101-135 - Nested `capture()` function

### Line 101
```python
    def capture(sched_cls, cost, warmup=warmup, **kw):
```

Defines local helper.

Parameters:

- `sched_cls` → scheduler class
- `cost` → switch cost
- `warmup` → default 800
- `**kw` → optional scheduler configuration

---

### Line 102
```python
        random.seed(11)
```

Uses seed 11.

This entire sparse-radar table is therefore a **single-seed spot check**, not a multi-seed validation.

The file itself warns about this at lines 150-152.

---

### Line 103
```python
        sched = sched_cls(n_bands, ucb_c=0.5, warmup_steps=warmup, **kw)
```

Creates scheduler.

Passes:

```text
n_bands = 8
ucb_c = 0.5
warmup_steps = warmup
```

Additional options are expanded through `**kw`.

---

### Line 104
```python
        env = scenario()
```

Creates a fresh environment.

Important:

Each capture run gets its own environment starting from its initial state.

---

### Line 105
```python
        radar_pulses = radar_caught = 0
```

Creates two counters:

```text
radar_pulses
radar_caught
```

Both start at zero.

---

### Line 106
```python
        comm1_on = comm1_caught = 0
```

Creates counters for communication emitter on band 1.

---

### Line 107
```python
        prev_bands = set()
```

Stores bands scanned during previous timestep.

Initially empty.

---

### Line 108
```python
        settling_remaining = {}
```

Dictionary:

```text
band → remaining settling steps
```

Example:

```python
{5: 1}
```

means band 5 still has one settling step remaining.

---

### Line 109
```python
        for t in range(n_steps):
```

Loops:

```text
t = 0 ... 3999
```

---

### Line 110
```python
            status = env.step()
```

Advances environment one timestep.

Returns band activity:

```python
status[band]
```

---

### Line 111
```python
            bands = sched.choose_bands(1)
```

Scheduler chooses exactly one band.

---

### Line 112
```python
            for band in bands:
```

Processes selected band.

---

### Line 113
```python
                blocked = False
```

Initially assume receiver is ready.

---

### Line 114
```python
                if cost > 0:
```

Only model settling if switch cost exists.

---

### Line 115
```python
                    if band not in prev_bands:
```

Checks whether selected band wasn't being scanned previously.

If yes:

**switch occurred.**

---

### Line 116
```python
                        settling_remaining[band] = cost
```

Starts settling timer.

Example:

```text
cost = 2
```

then:

```python
settling_remaining[band] = 2
```

---

### Line 117
```python
                    if settling_remaining.get(band, 0) > 0:
```

Checks whether selected band is still settling.

`.get(band, 0)` means:

> Return remaining value if present; otherwise return 0.

---

### Line 118
```python
                        settling_remaining[band] -= 1
```

Consumes one settling step.

---

### Line 119
```python
                        blocked = True
```

Marks band unavailable.

---

### Line 120
```python
                if not blocked:
```

Only process actual observation if receiver isn't settling.

---

### Line 121
```python
                    sched.update(band, status[band])
```

Feeds observation back to scheduler.

This is important because learning only happens when receiver can observe.

---

### Line 122
```python
                if t > warmup:
```

Only start capture measurement **after warmup**.

Notice the strict `>` rather than `>=`.

So measurement begins at:

```text
t = warmup + 1
```

---

### Line 123
```python
                    if band == 5 and status[5] and not blocked:
```

If:

- scheduler scanned band 5
- band 5 was active
- receiver wasn't settling

then radar pulse was caught.

---

### Line 124
```python
                        radar_caught += 1
```

Increment successful radar captures.

---

### Line 125
```python
                    if band == 1 and status[1] and not blocked:
```

Checks communication emitter on band 1.

---

### Line 126
```python
                        comm1_caught += 1
```

Counts successful band-1 communication captures.

---

### Line 127
```python
            prev_bands = set(bands)
```

Copies current scheduled bands into previous-band state.

Next iteration uses this to detect switching.

---

### Line 128
```python
            if t > warmup:
```

Again only count opportunities after warmup.

---

### Line 129
```python
                if status[5]:
```

Was radar active?

---

### Line 130
```python
                    radar_pulses += 1
```

If yes, count it as an available radar pulse.

---

### Line 131
```python
                if status[1]:
```

Was communication emitter 1 active?

---

### Line 132
```python
                    comm1_on += 1
```

Counts available communication opportunities.

---

### Line 133
```python
        radar_pct = radar_caught / radar_pulses if radar_pulses else 0.0
```

Calculates radar capture ratio:

$$
\text{radar capture}
=
\frac{\text{radar caught}}
{\text{radar opportunities}}
$$

If there were zero radar pulses, returns `0.0` instead of dividing by zero.

---

### Line 134
```python
        comm1_pct = comm1_caught / comm1_on if comm1_on else 0.0
```

Same calculation for communication emitter 1.

---

### Line 135
```python
        return radar_pct, comm1_pct
```

Returns both ratios.

---

# Lines 137-149 - Run sparse-radar comparisons

### Line 137
```python
    for cost in SWITCH_COSTS:
```

Tests:

```text
0, 1, 2, 4
```

---

### Line 138
```python
        b_radar, _ = capture(BeliefUCBScheduler, cost)
```

Runs BeliefUCB.

Stores radar capture.

Second returned value (communication capture) is ignored using:

```python
_
```

---

### Line 139
```python
        p_radar, p_comm1 = capture(PRIAwareScheduler, cost)
```

Runs default PRIAware.

Stores:

```text
p_radar
p_comm1
```

---

### Line 140
```python
        if cost > 0:
```

For nonzero switching cost, test fixed PRIAware too.

---

### Line 141
```python
            dwell, warmup_scaled = recommended_warmup_dwell(cost, warmup, margin=2)
```

Calculates appropriate dwell and scaled warmup.

For example, cost 1:

$$
D=1+2=3
$$

and:

$$
W'=800\frac{3}{3-1}=1200
$$

So:

```text
dwell = 3
warmup = 1200
```

---

### Line 142
```python
            d_radar, d_comm1 = capture(PRIAwareScheduler, cost, warmup=warmup_scaled,
```

Runs PRIAware again, now using scaled warmup.

---

### Line 143
```python
                                        warmup_dwell_steps=dwell, warmup_dwell_jitter=1,
```

Adds:

```text
dwell = calculated value
jitter = 1
```

Jitter prevents fixed timing/phase aliasing.

---

### Line 144
```python
                                        switch_lead_steps=cost)
```

Adds switch lead.

If cost is 2:

```text
switch_lead_steps = 2
```

This shifts predicted periodic targets earlier so receiver can settle before pulse arrives.

---

### Line 145
```python
            extra = f"{d_radar*100:13.1f}% | {d_comm1*100:13.1f}%"
```

Formats fixed PRIAware's two capture percentages.

---

### Line 146
```python
        else:
```

If:

```text
cost = 0
```

there is no need to run fixed variant.

---

### Line 147
```python
            extra = f"{'n/a':>13s}  | {'n/a':>13s} "
```

Displays:

```text
n/a | n/a
```

---

### Line 148
```python
        print(f"{cost:11d} | {b_radar*100:16.1f}% | {p_radar*100:15.1f}% | "
```

Begins output row.

Prints:

- switch cost
- BeliefUCB radar %
- PRIAware radar %

---

### Line 149
```python
              f"{p_comm1*100:15.1f}% | {extra}")
```

Completes row with:

- PRIAware comm1 %
- fixed PRIAware radar %
- fixed PRIAware comm1 %

---

# Lines 150-152 - Warning about methodology

### Line 150
```python
    print("\n(NOTE: +dwell numbers are single-seed spot checks like everything else in\n"
```

Explicitly warns:

**Don't treat these +dwell numbers as statistically established.**

Only one seed.

---

### Line 151
```python
          " this table -- see validate_warmup_dwell_fix.py for the real 30-seed picture,\n"
```

Points to later validation.

That later file performs proper 30-seed analysis.

---

### Line 152
```python
          " since this project has repeatedly found single-seed reads misleading.)\n")
```

Very important methodological lesson:

> Single-seed experiments can give misleading conclusions.

This is why later files move toward multi-seed validation.

---

# Lines 155-158 - Entry point

### Line 155
```python
if __name__ == "__main__":
```

Runs following code only when this file is executed directly.

---

### Line 156
```python
    beacon_switches_breakdown()
```

First:

**measure how frequently schedulers switch.**

---

### Line 157
```python
    beacon_sweep()
```

Second:

**measure beacon interception under different switch costs.**

---

### Line 158
```python
    sparse_radar_sweep()
```

Third:

**measure sparse-radar interception and demonstrate the switch-cost failure of default PRIAware.**

---

# Entire file in one picture

```text
switch_cost_comparison.py
            │
            ├── 1. beacon_switches_breakdown()
            │       │
            │       ├── RoundRobin
            │       ├── Random
            │       └── BeliefUCB
            │
            │       Measure:
            │       "How often does scheduler switch?"
            │
            ├── 2. beacon_sweep()
            │       │
            │       ├── k=1
            │       ├── k=2
            │       └── k=3
            │
            │       switch cost:
            │       0, 1, 2, 4
            │
            │       Measure:
            │       interception %
            │
            └── 3. sparse_radar_sweep()
                    │
                    ├── BeliefUCB
                    ├── PRIAware
                    └── PRIAware + dwell/jitter/lead
                         │
                         └── measure:
                             radar capture
                             comm-1 capture
```

## The major discovery from this file

The key causal chain is:

```text
Switch cost
     ↓
Every band change causes settling
     ↓
Settling means no observation
     ↓
Schedulers that switch frequently waste more time
```

RoundRobin is especially vulnerable because with `k=1` it changes band every timestep. The diagnostic directly measures switching frequency rather than merely assuming it. `ecac83fe-3c41-4824-af84-bf0a23a1f488.md`

But the **more interesting discovery** is sparse radar:

```text
PRIAware learns PRI
       ↓
predicts exact pulse time
       ↓
switches onto radar band at predicted time
       ↓
receiver starts settling
       ↓
pulse arrives while settling
       ↓
PULSE MISSED
```

The later investigation measured this very specifically: **267 of 285 band-5 visits were fresh switches**, causing the original sparse-radar headline to collapse under a one-step switch cost. `ecac83fe-3c41-4824-af84-bf0a23a1f488.md`

That observation leads directly to:

```text
switch_lead_steps
```

and eventually to the **dwell + jitter + scaled-warmup + persistent-characterization** fixes we already covered.

So this file is the point where the project discovers:

> **A scheduler can be mathematically correct about when a signal arrives and still systematically miss it because its hardware hasn't finished tuning when the signal arrives.**

**Next file: `settle_fix_interaction.py` - 131 lines.**

# File 17 of 18: `settle_fix_interaction.py`

This file is a **methodology/fix-interaction experiment**. It is not introducing a new scheduler. Its job is to answer a very specific question:

> When we compare the **original PRIAware**, **PlateauOnly**, and **Current PRIAware**, are differences genuinely caused by the PRI fixes-or are they partly caused by the schedulers seeing different random environments?

That distinction matters because `run_episode()` creates a fresh environment every time, while `MarkovEmitter` and `AgileEmitter` consume Python's global random stream. The file therefore introduces **identical-environment pairing**. `ecac83fe-3c41-4824-af84-bf0a23a1f488.md`

---

# Lines 1-31 - Module documentation

### Line 1
```python
"""
```

Starts module-level docstring.

---

### Line 2
```python
settle_fix_interaction.py
```

Names this script.

---

### Line 3
```python
============================
```

Visual separator inside documentation.

---

### Line 4
```python
The project's established seeding convention (one random.seed(seed) call,
```

Describes project's normal experiment convention.

Normally, code does:

```python
random.seed(seed)
```

once.

---

### Line 5
```python
then every scheduler in a comparison run back to back off that one
```

Then scheduler A runs, followed by scheduler B, C, D, etc.

They all consume the **same continuously advancing random-number stream**.

---

### Line 6
```python
continuously-advancing stream) is what validate_plateau_fix.py used, and
```

Says this was the methodology used by `validate_plateau_fix.py`.

---

### Line 7
```python
it reproduced the documented numbers exactly. But run_episode()
```

That convention successfully reproduces earlier headline numbers.

But there's a catch.

---

### Line 8
```python
constructs a FRESH environment every call, and MarkovEmitter/AgileEmitter
```

Every invocation of:

```python
run_episode(...)
```

constructs a new environment.

And the stochastic emitters consume randomness.

---

### Line 9
```python
draw from `random` on every single step -- so schedulers running 4th and
```

Emitters call the global random generator repeatedly.

Therefore scheduler ordering matters.

---

### Line 10
```python
5th in that shared sequence (PlateauOnly, Current) are actually facing
```

Suppose:

```text
scheduler A → consumes random numbers
scheduler B → consumes more
scheduler C → consumes more
scheduler D → consumes more
```

By the time D runs, RNG state has changed dramatically.

---

### Line 11
```python
DIFFERENT underlying environment realizations, not the same one. The
```

So D doesn't merely have a different policy.

It is potentially operating against **different emitter trajectories**.

---

### Line 12
```python
aggregate statistics across many seeds are still valid (any position bias
```

Important distinction:

Multi-seed aggregate results can still be useful.

If scheduler D is always fourth, its different random-stream position may average out over many seeds.

---

### Line 13
```python
should wash out over 30 independent trials), but a single-seed deep dive
```

With 30 independent seeds, systematic position effects should largely average out.

But not necessarily for an individual seed.

---

### Line 14
```python
into "why does Current do worse than PlateauOnly on seed 7" is
```

A single-seed explanation becomes questionable.

---

### Line 15
```python
confounded: their scan decisions differ, but so does the ground-truth
```

**Confounded** means two things changed simultaneously.

We wanted:

```text
same environment
different scheduler
```

but instead got:

```text
different environment
different scheduler
```

---

### Line 16
```python
comm/agile activity they're each reacting to.
```

Specifically, communication and agile emitter behavior differs.

Therefore we cannot cleanly attribute performance differences to the PRI algorithm.

---

### Line 18
```python
This script fixes that for the beacon scenario specifically: with
```

This script changes the experimental design.

---

### Line 19
```python
warmup_steps=0 (the beacon suite's setting), NONE of BeliefUCB /
```

The beacon experiment uses:

```python
warmup_steps = 0
```

Therefore no warmup phase occurs.

---

### Line 20
```python
Original / PlateauOnly / Current consume any of their own randomness
```

Because these scheduler variants aren't using their warmup randomness.

---

### Line 21
```python
(random.shuffle only fires inside the warmup branch, which never
```

`random.shuffle()` is only called in the warmup branch.

Since:

```text
warmup_steps = 0
```

that branch isn't entered.

---

### Line 22
```python
triggers). So resetting random.seed(seed) immediately before EACH
```

This gives us a solution:

```python
random.seed(seed)
```

before every scheduler.

---

### Line 23
```python
scheduler's run_episode() call gives every scheduler the IDENTICAL
```

Now every scheduler starts from exactly the same RNG state.

---

### Line 24
```python
environment trajectory for that seed -- isolating the algorithmic
```

Because the schedulers don't consume random numbers themselves in this configuration, the environment gets the same random sequence.

Thus:

```text
same seed
+
same RNG state
+
same emitter logic
=
same environment
```

---

### Line 25
```python
difference cleanly, at the cost of no longer matching the original
```

There is a tradeoff.

The results won't necessarily match the old experiment's numbers.

---

### Line 26
```python
suite_c_beacon numbers exactly (this is a different, stricter pairing,
```

This is deliberately a **stricter experimental methodology**.

---

### Line 27
```python
not a reproduction of the original headline numbers).
```

Important:

> This script is not intended to reproduce Suite C.

It is intended to isolate algorithmic effects.

---

### Line 29
```python
Run: python3 settle_fix_interaction.py
```

Normal execution.

---

### Line 30
```python
     python3 settle_fix_interaction.py --seeds 30
```

Example with 30 seeds.

---

### Line 31
```python
"""
```

Ends module docstring.

---

# Lines 33-36 - Imports

### Line 33
```python
import argparse
```

Provides command-line argument parsing.

---

### Line 34
```python
import random
```

Provides RNG and, critically, `random.seed()`.

---

### Line 35
```python
import statistics
```

Used for:

- mean
- standard deviation

---

### Line 36
```python
from typing import Dict, List
```

Imports type-hinting containers.

---

# Lines 38-40 - Project imports

### Line 38
```python
from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
```

Imports:

- Markov-only baseline scheduler
- simulation engine

---

### Line 39
```python
from scan_scheduler_v3_pri import PRIAwareScheduler, make_scenario
```

Imports:

- current PRI-aware scheduler
- beacon scenario builder

---

### Line 40
```python
from validate_plateau_fix import OriginalPRIAware, PlateauOnlyPRIAware
```

This is particularly interesting.

It imports two **experimental historical variants** created in the plateau-fix validation script:

```text
OriginalPRIAware
PlateauOnlyPRIAware
```

So this script can compare the evolution:

```text
Original
   ↓
PlateauOnly
   ↓
Current
```

---

# Lines 43-52 - `run_identical_env()`

### Line 43
```python
def run_identical_env(seed, sched_cls, n_bands=8, n_steps=4000, k=2, **kw):
```

Defines helper function.

Parameters:

| Parameter | Meaning |
|---|---|
| `seed` | random seed |
| `sched_cls` | scheduler class |
| `n_bands=8` | eight frequency bands |
| `n_steps=4000` | simulation length |
| `k=2` | scan two bands simultaneously |
| `**kw` | extra scheduler arguments |

---

### Line 44
```python
    """Reset the seed immediately before constructing+running this one
```

Begins function documentation.

The important action is resetting the seed immediately before each scheduler.

---

### Line 45
```python
    scheduler, so its environment trajectory is reproducible independent
```

Environment trajectory becomes independent of what scheduler ran previously.

---

### Line 46
```python
    of what ran before it -- the key difference from the project's usual
```

This explicitly contrasts with sequential RNG usage.

---

### Line 47
```python
    sequential-shared-stream convention."""
```

Ends explanation.

---

### Line 48
```python
    scenario = make_scenario(n_bands)
```

Creates beacon scenario factory.

Notice something subtle:

`make_scenario()` constructs emitter objects, but their ongoing random behavior occurs when the environment is stepped.

---

### Line 49
```python
    random.seed(seed)
```

**Critical line.**

Resets global RNG.

Every scheduler receives same initial random state.

---

### Line 50
```python
    sched = sched_cls(n_bands, ucb_c=0.5, **kw)
```

Constructs scheduler.

Every scheduler receives:

```python
n_bands
ucb_c=0.5
```

and any extra keyword arguments.

For example:

```python
run_identical_env(..., warmup_steps=800)
```

would pass that through.

---

### Line 51
```python
    stats = run_episode(scenario, sched, n_steps, n_bands, k_channels=k)
```

Runs simulation.

Parameters:

```text
scenario → environment factory
sched → scheduler
4000 → steps
8 → number of bands
k → simultaneous channels
```

No switch cost is passed here.

So this is a **no-switch-cost beacon comparison**.

---

### Line 52
```python
    return stats.report()["interception_ratio"], sched
```

Returns two things:

1. headline interception ratio
2. scheduler object itself

Why return scheduler?

Because later the script wants to inspect its learned PRI model.

---

# Lines 55-62 - `main()` setup

### Line 55
```python
def main():
```

Main experiment function.

---

### Line 56
```python
    ap = argparse.ArgumentParser(description=__doc__)
```

Creates command-line parser.

`description=__doc__` means the huge module documentation becomes the CLI description.

So running:

```bash
python3 settle_fix_interaction.py --help
```

can show that documentation.

---

### Line 57
```python
    ap.add_argument("--seeds", type=int, default=30)
```

Adds:

```text
--seeds
```

Number of seeds.

Default:

```text
30
```

---

### Line 58
```python
    ap.add_argument("--seed-start", type=int, default=1)
```

Starting seed.

Default:

```text
1
```

---

### Line 59
```python
    ap.add_argument("--k", type=int, default=2)
```

Number of simultaneous scanned channels.

Default:

```text
k = 2
```

---

### Line 60
```python
    args = ap.parse_args()
```

Reads actual command-line arguments.

---

### Line 61
```python
    seeds = list(range(args.seed_start, args.seed_start + args.seeds))
```

Builds seed list.

Default:

```python
seed_start = 1
seeds = 30
```

therefore:

```text
[1, 2, 3, ..., 30]
```

---

### Line 62
```python
    k = args.k
```

Copies CLI `k` into local variable.

---

# Lines 64-68 - Experimental-methodology announcement

### Line 64
```python
    print(f"Paired-identical-environment comparison, beacon scenario, k={k}, "
```

Prints experiment description.

The word **paired** is important.

For each seed, scheduler A and scheduler B are paired against the same environment realization.

---

### Line 65
```python
          f"{len(seeds)} seeds ({seeds[0]}..{seeds[-1]}).\n"
```

Prints number and range of seeds.

---

### Line 66
```python
          f"Every scheduler below sees the EXACT SAME ground-truth environment "
```

States central experimental guarantee.

---

### Line 67
```python
          f"trajectory for a given seed (verified: none of these schedulers "
```

Explains why this guarantee holds.

---

### Line 68
```python
          f"consume their own randomness with warmup_steps=0).\n")
```

Since warmup is zero, schedulers don't alter RNG before environment generation.

---

# Lines 70-75 - Results structure

### Line 70
```python
    results: Dict[str, List[float]] = {
```

Creates dictionary.

Each key maps to a list of interception ratios.

Type annotation:

```text
Dict[str, List[float]]
```

means:

```text
string → list of floating-point numbers
```

---

### Line 71
```python
        "BeliefUCB (Markov-only)": [],
```

Baseline.

No PRI awareness.

---

### Line 72
```python
        "Original (pre-both-fixes)": [],
```

Original PRIAware before both fixes.

---

### Line 73
```python
        "PlateauOnly (fix 1 only)": [],
```

PRIAware with only plateau/jitter fix.

---

### Line 74
```python
        "Current (both fixes)": [],
```

Current PRIAware with both fixes.

---

### Line 75
```python
    }
```

Ends dictionary.

---

### Line 76
```python
    schedulers_by_seed = {}  # seed -> {name: scheduler instance}, for later inspection
```

Stores actual scheduler objects.

Structure becomes approximately:

```python
{
    1: {
        "BeliefUCB ...": scheduler_object,
        "Original ...": scheduler_object,
        ...
    },
    2: {...}
}
```

Why?

To inspect final PRI estimates later.

---

# Lines 78-89 - Run every scheduler on every seed

### Line 78
```python
    for seed in seeds:
```

Outer loop over seeds.

---

### Line 79
```python
        by_name = {}
```

Creates dictionary for this particular seed.

---

### Line 80
```python
        for name, cls in [
```

Starts scheduler list.

---

### Line 81
```python
            ("BeliefUCB (Markov-only)", BeliefUCBScheduler),
```

First scheduler.

---

### Line 82
```python
            ("Original (pre-both-fixes)", OriginalPRIAware),
```

Second.

---

### Line 83
```python
            ("PlateauOnly (fix 1 only)", PlateauOnlyPRIAware),
```

Third.

---

### Line 84
```python
            ("Current (both fixes)", PRIAwareScheduler),
```

Fourth.

---

### Line 85
```python
        ]:
```

Ends scheduler list.

---

### Line 86
```python
            ratio, sched = run_identical_env(seed, cls, k=k)
```

This is the key experiment.

For **each scheduler**, `run_identical_env()` does:

```text
create scenario
reset RNG
construct scheduler
run environment
```

So:

```text
seed 7 + BeliefUCB
seed 7 + Original
seed 7 + PlateauOnly
seed 7 + Current
```

all receive the same environment trajectory.

---

### Line 87
```python
            results[name].append(ratio)
```

Adds interception ratio to scheduler's result list.

---

### Line 88
```python
            by_name[name] = sched
```

Stores scheduler object.

---

### Line 89
```python
        schedulers_by_seed[seed] = by_name
```

Stores all four scheduler objects for this seed.

---

# Lines 91-95 - Summary statistics

### Line 91
```python
    print(f"{'Scheduler':30s} | {'mean':>7s} | {'stdev':>6s} | {'min':>6s} | {'max':>6s}")
```

Prints table header.

Columns:

```text
Scheduler
mean
stdev
min
max
```

---

### Line 92
```python
    print("-" * 65)
```

Table separator.

---

### Line 93
```python
    for name, vals in results.items():
```

Iterates over each scheduler's results.

---

### Line 94
```python
        print(f"{name:30s} | {statistics.mean(vals)*100:6.1f}% | {statistics.stdev(vals)*100:5.1f}% | "
```

Calculates:

$$
\text{mean}\times100
$$

and:

$$
\text{sample stdev}\times100
$$

because interception ratios are stored as fractions.

---

### Line 95
```python
              f"{min(vals)*100:5.1f}% | {max(vals)*100:5.1f}%")
```

Adds minimum and maximum.

---

# Lines 97-100 - Paired-difference function

### Line 97
```python
    def delta(a, b):
```

Defines nested helper.

It calculates:

$$
A-B
$$

for every seed.

---

### Line 98
```python
        diffs = [x - y for x, y in zip(results[a], results[b])]
```

This is a list comprehension.

For corresponding seed results:

```text
seed 1: A1 - B1
seed 2: A2 - B2
seed 3: A3 - B3
...
```

`zip()` pairs corresponding elements.

Because every scheduler ran over exactly the same seed list, pairing is meaningful.

---

### Line 99
```python
        wins = sum(1 for d in diffs if d > 0)
```

Counts how many seeds scheduler A beat scheduler B.

If:

```text
A > B
```

then that's one win.

---

### Line 100
```python
        return statistics.mean(diffs), statistics.stdev(diffs), wins, len(diffs)
```

Returns:

1. mean paired difference
2. standard deviation of differences
3. number of wins
4. number of comparisons

The mean difference is reported in **percentage points** later.

---

# Lines 102-110 - Compare fixes

### Line 102
```python
    print()
```

Blank line.

---

### Line 103
```python
    for label, a, b in [
```

Starts list of comparisons.

---

### Line 104
```python
        ("PlateauOnly vs Original (fix 1's contribution, IDENTICAL envs)", "PlateauOnly (fix 1 only)", "Original (pre-both-fixes)"),
```

Question:

> What did fix 1 contribute?

Mathematically:

$$
\text{PlateauOnly}-\text{Original}
$$

---

### Line 105
```python
        ("Current vs PlateauOnly (fix 2's ADDED effect, IDENTICAL envs)", "Current (both fixes)", "PlateauOnly (fix 1 only)"),
```

Question:

> What additional benefit came from fix 2?

Mathematically:

$$
\text{Current}-\text{PlateauOnly}
$$

This isolates fix 2's incremental effect.

---

### Line 106
```python
        ("Current vs Original (both fixes combined, IDENTICAL envs)", "Current (both fixes)", "Original (pre-both-fixes)"),
```

Question:

> What is total effect of both fixes?

$$
\text{Current}-\text{Original}
$$

---

### Line 107
```python
        ("Current vs BeliefUCB (net vs baseline, IDENTICAL envs)", "Current (both fixes)", "BeliefUCB (Markov-only)"),
```

Question:

> Does final PRIAware beat ordinary BeliefUCB?

---

### Line 108
```python
    ]:
```

Ends comparison list.

---

### Line 109
```python
        m, s, w, n = delta(a, b)
```

Runs paired comparison.

Variables:

```text
m = mean difference
s = stdev difference
w = wins
n = number comparisons
```

---

### Line 110
```python
        print(f"  {label:56s}: {m*100:+5.1f}pp +/- {s*100:4.1f}pp  -- won {w}/{n}")
```

Prints result.

`pp` means **percentage points**.

Example:

```text
+3.2pp
```

means scheduler A's interception ratio is 3.2 percentage points higher on average.

This is not the same as saying "3.2% relative improvement."

---

# Lines 112-120 - Find worst Current-vs-PlateauOnly seed

### Line 112
```python
    # Find the single seed where Current vs PlateauOnly diverges most, and
```

Comment.

---

### Line 113
```python
    # show exactly what differs in their final per-band model state --
```

The script wants to inspect why the two versions differ.

---

### Line 114
```python
    # THIS time on an environment we know is identical between them.
```

This is the whole point of the script.

Now a single-seed investigation is legitimate because environment is controlled.

---

### Line 115
```python
    diffs_cp = [(c - p, seed) for c, p, seed in
```

Builds tuples:

```text
(Current - PlateauOnly, seed)
```

---

### Line 116
```python
                zip(results["Current (both fixes)"], results["PlateauOnly (fix 1 only)"], seeds)]
```

Pairs corresponding Current and PlateauOnly results with seed number.

---

### Line 117
```python
    diffs_cp.sort()
```

Sorts ascending.

Most negative difference comes first.

---

### Line 118
```python
    worst_diff, worst_seed = diffs_cp[0]
```

Takes the worst case.

If:

```text
Current - PlateauOnly = -0.18
```

then Current performed 18 percentage points worse for that seed.

---

### Line 119
```python
    print(f"\nWorst Current-vs-PlateauOnly seed under IDENTICAL environments: "
```

Prints which seed was worst.

---

### Line 120
```python
          f"seed {worst_seed} ({worst_diff*100:+.1f}pp)")
```

Prints exact difference.

---

# Lines 121-127 - Inspect PRI models on worst seed

### Line 121
```python
    plateau_sched = schedulers_by_seed[worst_seed]["PlateauOnly (fix 1 only)"]
```

Retrieves PlateauOnly scheduler object for worst seed.

---

### Line 122
```python
    current_sched = schedulers_by_seed[worst_seed]["Current (both fixes)"]
```

Retrieves Current scheduler object.

---

### Line 123
```python
    for b in (2, 5, 6):
```

Examines beacon bands:

```text
2
5
6
```

These are the known periodic beacon bands.

---

### Line 124
```python
        print(f"  band {b}: PlateauOnly pri={plateau_sched.pri_estimate[b]} "
```

Prints PlateauOnly's estimated PRI for that band.

---

### Line 125
```python
              f"conf={plateau_sched.confidence[b]:.2f} jitter={plateau_sched.jitter_estimate[b]:.2f} | "
```

Prints two additional learned quantities:

```text
confidence
jitter
```

So we can inspect not merely performance, but model state.

---

### Line 126
```python
              f"Current pri={current_sched.pri_estimate[b]} "
```

Prints Current's estimated PRI.

---

### Line 127
```python
              f"conf={current_sched.confidence[b]:.2f} jitter={current_sched.jitter_estimate[b]:.2f}")
```

Prints Current's:

- confidence
- jitter

Thus output lets us compare:

```text
PlateauOnly:
    PRI
    confidence
    jitter

Current:
    PRI
    confidence
    jitter
```

for each periodic band.

---

# Lines 130-131 - Entry point

### Line 130
```python
if __name__ == "__main__":
```

Only execute main when script is run directly.

---

### Line 131
```python
    main()
```

Starts experiment.

---

# What this file contributes to the project

This file is less about improving the scheduler and more about improving **scientific validity**.

The experimental evolution is:

```text
Original PRIAware
       │
       │ fix 1
       ▼
PlateauOnly
       │
       │ fix 2
       ▼
Current PRIAware
```

The problem:

```text
Scheduler A runs
     ↓
consumes random numbers
     ↓
Scheduler B runs
     ↓
gets different environment
```

So comparing one particular seed could be misleading.

This script changes the experiment to:

```text
             seed = 7
                │
       reset random.seed(7)
          ┌─────┼─────┐
          ↓     ↓     ↓
       Env A  Env B  Env C
          │     │     │
       same RNG trajectory
          │     │     │
       Belief Original Current
```

Because `warmup_steps=0`, these scheduler variants don't consume scheduler-side randomness before environment generation, allowing the environment trajectory to be held identical. `ecac83fe-3c41-4824-af84-bf0a23a1f488.md`

### The four questions the script answers

| Comparison | Question |
|---|---|
| PlateauOnly - Original | Did plateau fix help? |
| Current - PlateauOnly | What did second fix add? |
| Current - Original | What did both fixes accomplish? |
| Current - BeliefUCB | Does final PRI-aware approach beat baseline? |

And, importantly, the paired differences are calculated **seed-by-seed**, rather than merely comparing two independent means.

**Next file: `validate_pdw_multiseed.py` - 201 lines.**

# File 18 of 18: `validate_pdw_multiseed.py`

This is the **final Python file** in the ZIP.

It validates one of the project's most important later fixes: the **harmonic-lock-on fix** for the PRI estimator, specifically on the synthetic Turing/PDW dataset.

The problem is subtle:

```text
True PRI = 650 μs
Dwell    = 20 μs

650 / 20 ≈ 32.5 steps
```

The old PRI candidate-selection method could sometimes prefer approximately:

```text
65 steps
```

which is **2 × the true period**—a harmonic. This file checks whether the newer candidate-selection algorithm fixes that across many seeds rather than merely working on one lucky seed.

---

# Lines 1–60 — Module docstring

### Line 1
```python
"""
```

Starts module documentation.

### Line 2
```python
validate_pdw_multiseed.py
```

File name.

### Line 3
```python
============================
```

Formatting separator.

### Lines 4–14
```python
Multi-seed validation of the harmonic-lock-on fix...
```

These lines explain the experiment's motivation.

The key point:

- the new algorithm selects PRI candidates using **best refined-fit RMSE**
- the old algorithm used a **coarse tolerance test**
- the problem was discovered on the synthetic PDW/Turing dataset
- previous testing had only used a few individual seeds
- beacon validation wasn't enough because this is a different dataset

So this script closes a validation gap.

### Lines 16–26

These document the three fixed-frequency PDW emitters:

| Band | Carrier frequency | True PRI |
|---|---:|---:|
| 1 | 2400 MHz | 1000 μs |
| 4 | 9200 MHz | 650 μs |
| 6 | 14300 MHz | 1500 μs |

The important one is **band 4**.

At 20 μs dwell:

$$
\frac{650}{20}=32.5
$$

The exact generated/observed value is described as approximately **32.505 steps** because of the real PRI jitter.

The old algorithm could choose:

$$
65 \approx 2(32.5)
$$

instead of the fundamental.

### Lines 28–31

Document the two frequency-agile emitters.

They are a **negative control**.

They should *not* receive high-confidence periodicity models because they hop unpredictably.

### Lines 33–40

Defines the four scheduler variants:

1. `BeliefUCB`
2. `PlateauOnly`
3. current `PRIAware`
4. `PersistentPRIAware`

The progression is:

```text
BeliefUCB
   ↓
PlateauOnly
   ↓
PRIAware
   ↓
PersistentPRIAware
```

### Lines 42–48

Defines classification categories:

```text
CORRECT
HARMONIC
WRONG
NO LOCK
```

`CORRECT` means:

$$
|\text{estimated}/\text{true}-1|\le0.05
$$

So estimate must be within **5%**.

`HARMONIC` means estimate is approximately:

$$
0.5\times,\quad 2\times,\quad 3\times,\quad \frac13\times
$$

the true period.

### Lines 50–56

Important experimental-control explanation.

The PDW generator uses **NumPy's RNG**, while scheduler randomness comes from Python's `random`.

Because:

```python
warmup_steps = 0
```

these schedulers don't consume their own warmup randomness.

Therefore each scheduler receives the same PDW dataset for a given seed.

This means the environmental confounding problem from `settle_fix_interaction.py` does **not** occur here.

### Lines 58–59
```text
Run: python3 validate_pdw_multiseed.py
     python3 validate_pdw_multiseed.py --seeds 20 --dwell-us 20
```

Example commands.

### Line 60
```python
"""
```

Ends docstring.

---

# Lines 62–72 — Imports

### Line 62
```python
import argparse
```

Command-line argument parsing.

### Line 63
```python
import random
```

Python random generator.

### Line 64
```python
import statistics
```

Used for mean and standard deviation.

### Line 65
```python
from typing import Dict, List
```

Type hints.

### Line 67
```python
from scan_scheduler_v2 import BeliefUCBScheduler, run_episode
```

Gets baseline scheduler and simulation engine.

### Line 68
```python
from scan_scheduler_v3_pri import PRIAwareScheduler
```

Gets current PRI-aware scheduler.

### Line 69
```python
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler
```

Gets V4 persistent version.

### Line 70
```python
from validate_plateau_fix import PlateauOnlyPRIAware
```

Gets historical "fix 1 only" implementation.

### Line 71
```python
from pdw_loader import generate_synthetic_pdw_stream
```

Gets synthetic PDW generator.

### Line 72
```python
from pdw_environment import PDWReplayEnvironment
```

Gets environment that converts PDW records into band activity over time.

---

# Lines 74–77 — Ground-truth PRI table

### Lines 74–76
```python
# (band, true_pri_us) at n_bands=8, freq_range (0,18000) -- see module
# docstring for how these map from generate_synthetic_pdw_stream's fixed
# emitters via PDWReplayEnvironment's band binning.
```

Comments explaining where these known truths come from.

The PDW frequencies are binned into eight receiver bands.

### Line 77
```python
TRUE_PERIODIC_BANDS = {1: 1000.0, 4: 650.0, 6: 1500.0}
```

Dictionary:

```python
band 1 → 1000 μs
band 4 → 650 μs
band 6 → 1500 μs
```

These are ground-truth values used to judge the scheduler's estimates.

---

# Lines 80–90 — `classify()`

This function converts a numerical PRI estimate into a categorical verdict.

### Line 80
```python
def classify(estimated_pri_steps, dwell_us, true_pri_us, confidence, min_confidence):
```

Arguments:

- estimated PRI in simulation steps
- dwell duration in μs
- true PRI in μs
- estimated confidence
- minimum confidence required for lock

---

### Line 81
```python
if confidence < min_confidence or estimated_pri_steps is None:
```

Two ways to fail immediately:

1. confidence too low
2. no PRI estimate exists

---

### Line 82
```python
return "NO LOCK"
```

No reliable periodicity model.

---

### Line 83
```python
true_steps = true_pri_us / dwell_us
```

Converts physical PRI to simulation steps.

For band 4:

$$
650/20=32.5
$$

---

### Line 84
```python
ratio = estimated_pri_steps / true_steps
```

Calculates:

$$
r=\frac{\text{estimated PRI}}{\text{true PRI}}
$$

This makes classification independent of absolute PRI.

---

### Lines 85–86
```python
if abs(ratio - 1.0) <= 0.05:
    return "CORRECT"
```

If estimate is within ±5% of truth:

```text
CORRECT
```

---

### Line 87
```python
for h in (0.5, 2.0, 3.0, 1.0 / 3.0):
```

Tests known harmonic relationships.

---

### Line 88
```python
if abs(ratio - h) <= 0.05:
```

Within 5% of harmonic.

---

### Line 89
```python
return "HARMONIC"
```

Labels it harmonic-locked.

---

### Line 90
```python
return "WRONG"
```

If confidently locked but neither correct nor a known harmonic:

```text
WRONG
```

So classification hierarchy is:

```text
low confidence?
     ↓ yes
NO LOCK

otherwise:
within 5% of truth?
     ↓ yes
CORRECT

otherwise:
near known harmonic?
     ↓ yes
HARMONIC

otherwise:
WRONG
```

---

# Lines 93–103 — `run_one()`

### Line 93
```python
def run_one(seed, cls, n_bands, dwell_us, k, extra_kwargs=None):
```

Runs one scheduler on one PDW dataset.

---

### Line 94
```python
pdw = generate_synthetic_pdw_stream(seed=seed)
```

Generates synthetic PDW data.

Crucially, **NumPy seed** determines the dataset.

---

### Lines 96–97
```python
def env_factory():
    return PDWReplayEnvironment(pdw, n_bands=n_bands, dwell_us=dwell_us)
```

Creates an environment factory.

Each `run_episode()` gets a fresh environment starting from `t=0`.

---

### Line 99
```python
n_steps = env_factory().n_steps
```

Creates temporary environment and determines how many simulation steps exist in the PDW data.

---

### Line 100
```python
random.seed(seed)  # no-op for randomness (warmup_steps=0), kept for clarity/consistency
```

Seeds Python RNG.

The comment explains that it shouldn't materially affect scheduler behavior because warmup is zero.

It is retained for consistency with other experiments.

---

### Line 101
```python
sched = cls(n_bands, ucb_c=0.5, **(extra_kwargs or {}))
```

Creates whichever scheduler class was requested.

If `extra_kwargs` is `None`:

```python
extra_kwargs or {}
```

becomes:

```python
{}
```

Then `**{}` contributes nothing.

---

### Line 102
```python
stats = run_episode(env_factory, sched, n_steps, n_bands, k_channels=k)
```

Runs simulation.

Notice that no switch-cost parameter is passed.

This is specifically validating **PRI estimation/lock-on**, not switching hardware behavior.

---

### Line 103
```python
return stats.report()["interception_ratio"], sched
```

Returns:

1. interception ratio
2. scheduler object

The scheduler object is needed to inspect its learned PRI estimates afterward.

---

# Lines 106–116 — CLI setup

### Line 106
```python
def main():
```

Main function.

### Line 107
```python
ap = argparse.ArgumentParser(description=__doc__)
```

Creates CLI parser and uses module docstring as its description.

### Line 108
```python
ap.add_argument("--seeds", type=int, default=20)
```

Default:

```text
20 seeds
```

### Line 109
```python
ap.add_argument("--seed-start", type=int, default=0)
```

Default starting seed:

```text
0
```

Therefore default seeds are:

```text
0 ... 19
```

### Lines 110–112
```python
ap.add_argument("--dwell-us", type=float, default=20.0,
                 help="Fine dwell to match the fractional-PRI headline test "
                      "(650us/20us = 32.505 steps, non-integer)")
```

Sets default dwell:

$$
20\ \mu s
$$

This is deliberate because it creates the fractional PRI case.

### Line 113
```python
ap.add_argument("--n-bands", type=int, default=8)
```

Eight receiver bands.

### Line 114
```python
ap.add_argument("--k", type=int, default=1)
```

One simultaneous scan channel.

### Line 115
```python
ap.add_argument("--csv", default="pdw_multiseed_results.csv")
```

Output CSV filename.

### Line 116
```python
args = ap.parse_args()
```

Reads CLI arguments.

---

# Lines 118–125 — Experiment configuration

### Line 118
```python
seeds = list(range(args.seed_start, args.seed_start + args.seeds))
```

Builds seed list.

Default:

```text
[0, 1, 2, ..., 19]
```

### Line 119
```python
n_bands = args.n_bands
```

Copies band count.

### Line 120
```python
dwell_us = args.dwell_us
```

Copies dwell.

### Line 121
```python
k = args.k
```

Copies channel count.

### Lines 123–125
```python
print(f"PDW multi-seed validation ...
```

Prints experiment configuration, including:

- number of seeds
- seed range
- dwell
- k
- known periodic bands

---

# Lines 127–132 — Scheduler definitions

### Line 127
```python
builders = {
```

Creates dictionary mapping names to scheduler constructors.

### Line 128
```python
"BeliefUCB": (BeliefUCBScheduler, {}),
```

Baseline.

No periodicity model.

### Line 129
```python
"PlateauOnly (pre-harmonic-fix)": (PlateauOnlyPRIAware, {}),
```

Old candidate-selection method + plateau fix.

### Line 130
```python
"PRIAware (current, both fixes)": (PRIAwareScheduler, {}),
```

Current V3 implementation.

Includes:

- plateau fix
- harmonic-selection fix

### Line 131
```python
"PersistentPRIAware (v4)": (PersistentPRIAwareScheduler, {}),
```

V4 adds persistent characterization/sample-starvation fix.

### Line 132
```python
}
```

Ends dictionary.

---

# Lines 134–138 — Results containers

### Line 134
```python
interception: Dict[str, List[float]] = {name: [] for name in builders}
```

Creates:

```python
{
    "BeliefUCB": [],
    "PlateauOnly...": [],
    "PRIAware...": [],
    "Persistent...": []
}
```

Each list will hold one interception ratio per seed.

---

### Line 135
```python
# classification[name][band] -> list of classify() results, one per seed
```

Explains data structure.

---

### Lines 136–138
```python
classification: Dict[str, Dict[int, List[str]]] = {
    name: {b: [] for b in TRUE_PERIODIC_BANDS} for name in builders
}
```

Nested dictionary.

Conceptually:

```python
classification["PRIAware (current, both fixes)"][4]
```

could contain:

```text
["CORRECT", "CORRECT", "HARMONIC", "NO LOCK", ...]
```

one verdict per seed.

---

# Lines 140–148 — Main experiment loop

### Line 140
```python
for seed in seeds:
```

Outer loop over datasets/seeds.

---

### Line 141
```python
for name, (cls, kw) in builders.items():
```

Runs every scheduler on that seed's dataset.

---

### Line 142
```python
ratio, sched = run_one(seed, cls, n_bands, dwell_us, k, kw)
```

Runs scheduler.

---

### Line 143
```python
interception[name].append(ratio)
```

Stores headline interception ratio.

---

### Line 144
```python
if hasattr(sched, "pri_estimate"):
```

Checks whether scheduler has PRI-estimation machinery.

BeliefUCB doesn't.

---

### Line 145
```python
for band, true_pri in TRUE_PERIODIC_BANDS.items():
```

For each known periodic band:

```text
1
4
6
```

---

### Line 146
```python
verdict = classify(sched.pri_estimate[band], dwell_us, true_pri,
```

Passes estimated PRI and truth into classifier.

---

### Line 147
```python
                    sched.confidence[band], sched.min_confidence)
```

Also supplies confidence and threshold.

---

### Line 148
```python
classification[name][band].append(verdict)
```

Stores result.

At the end, every PRI-aware scheduler has a verdict for every known periodic band for every seed.

---

# Lines 150–153 — Interception statistics

### Line 150
```python
print(f"{'Scheduler':32s} | {'Interception %':>18s}")
```

Prints table header.

---

### Line 151
```python
print("-" * 55)
```

Separator.

---

### Line 152
```python
for name, vals in interception.items():
```

Loops through scheduler results.

---

### Line 153
```python
print(f"{name:32s} | {statistics.mean(vals)*100:8.1f}% +/- {statistics.stdev(vals)*100:4.1f}pp")
```

Prints:

$$
\text{mean interception}\times100
$$

and sample standard deviation.

`pp` here means percentage-point spread.

---

# Lines 155–171 — Per-band lock classification

### Lines 155–158

Print explanation of classification rules:

```text
CORRECT
HARMONIC
WRONG
NO LOCK
```

This makes terminal output self-explanatory.

---

### Line 159
```python
for name in builders:
```

Process every scheduler.

---

### Lines 160–161
```python
if not any(classification[name][b] for b in TRUE_PERIODIC_BANDS):
    continue
```

Skip scheduler if it has no classification data.

This mainly protects against schedulers that don't have PRI models.

---

### Line 162
```python
print(f"{name}:")
```

Print scheduler heading.

---

### Line 163
```python
for band, true_pri in TRUE_PERIODIC_BANDS.items():
```

Process bands 1, 4, 6.

---

### Line 164
```python
verdicts = classification[name][band]
```

Gets all seed verdicts for this scheduler/band combination.

---

### Line 165
```python
counts = {v: verdicts.count(v) for v in ("CORRECT", "HARMONIC", "WRONG", "NO LOCK")}
```

Counts each category.

Example:

```python
{
    "CORRECT": 18,
    "HARMONIC": 1,
    "WRONG": 0,
    "NO LOCK": 1
}
```

---

### Line 166
```python
true_steps = true_pri / dwell_us
```

Converts truth to simulation steps.

---

### Lines 167–170
```python
print(f"  band {band} ...
```

Prints the four counts and total number of seeds.

For band 4, it should explicitly show:

```text
true PRI = 650us = 32.500 steps
```

---

### Line 171
```python
print()
```

Blank line between scheduler sections.

---

# Lines 173–181 — Highlight the harmonic-fix target

### Lines 173–174
```python
# The fractional-PRI case (band 4, non-integer step period) is the one
# the harmonic fix specifically targets -- highlight it directly.
```

Comments identify the most important experiment.

---

### Line 175
```python
print("Headline comparison for the fractional-PRI band (band 4, true = 32.505 steps) -- "
```

Prints headline specifically for band 4.

---

### Line 176
```python
      "this is exactly the case the harmonic-selection fix was built for:")
```

Makes the purpose explicit.

---

### Line 177
```python
for name in ("PlateauOnly (pre-harmonic-fix)", "PRIAware (current, both fixes)"):
```

Only compare:

```text
old candidate-selection method
vs
new candidate-selection method
```

This is the cleanest comparison for the fix.

---

### Line 178
```python
v = classification[name][4]
```

Gets band-4 verdicts.

---

### Line 179
```python
correct = v.count("CORRECT")
```

Counts correct locks.

---

### Line 180
```python
harmonic = v.count("HARMONIC")
```

Counts harmonic locks.

---

### Line 181
```python
print(f"  {name:32s}: {correct}/{len(seeds)} correct, {harmonic}/{len(seeds)} harmonic-locked")
```

Produces the most directly relevant result:

```text
PlateauOnly: X/20 correct, Y/20 harmonic
Current:     X/20 correct, Y/20 harmonic
```

The desired outcome is:

```text
Current:
    more CORRECT
    fewer HARMONIC
```

---

# Lines 183–197 — Write CSV

### Line 183
```python
import csv
```

Imports CSV module locally.

It could have been imported at the top, but this script waits until CSV output is needed.

---

### Line 184
```python
import os
```

Needed to check whether old CSV exists.

---

### Line 185
```python
if os.path.exists(args.csv):
```

Checks whether output file already exists.

---

### Line 186
```python
os.remove(args.csv)
```

Deletes old result file.

Thus each run produces a fresh CSV rather than appending to stale data.

---

### Line 187
```python
with open(args.csv, "w", newline="") as f:
```

Opens output file in write mode.

`newline=""` avoids unwanted blank lines on some platforms.

`with` guarantees the file gets closed.

---

### Line 188
```python
w = csv.writer(f)
```

Creates CSV writer.

---

### Lines 189–190
```python
w.writerow(["scheduler", "seed", "interception_ratio"] +
           [f"band{b}_verdict" for b in TRUE_PERIODIC_BANDS])
```

Creates header:

```text
scheduler
seed
interception_ratio
band1_verdict
band4_verdict
band6_verdict
```

---

### Line 191
```python
for name in builders:
```

For each scheduler.

---

### Line 192
```python
for i, seed in enumerate(seeds):
```

For each seed.

`i` is the index into stored result lists.

---

### Line 193
```python
row = [name, seed, interception[name][i]]
```

Starts row with:

- scheduler
- seed
- interception ratio

---

### Lines 194–195
```python
row += [classification[name][b][i] if classification[name][b] else ""
        for b in TRUE_PERIODIC_BANDS]
```

Adds verdict for each periodic band.

If classification exists:

```text
CORRECT
```

etc.

If empty:

```text
""
```

---

### Line 196
```python
w.writerow(row)
```

Writes row to CSV.

---

### Line 197
```python
print(f"\nRaw per-seed results written to {args.csv}")
```

Tells user where detailed results went.

---

# Lines 200–201 — Program entry point

### Line 200
```python
if __name__ == "__main__":
```

Only execute main when directly run.

---

### Line 201
```python
main()
```

Starts experiment.

---

# The entire final Python file in one conceptual diagram

```text
generate_synthetic_pdw_stream(seed)
              │
              ▼
       PDWReplayEnvironment
              │
              ▼
       same PDW dataset
       for each scheduler
              │
       ┌──────┼──────────┬─────────────┐
       ▼      ▼          ▼             ▼
   BeliefUCB Plateau   PRIAware   Persistent
              Only
       │      │          │             │
       │      └────┬─────┘             │
       │           │                   │
       │       estimate PRI             │
       │           │                   │
       └───────────┼───────────────────┘
                   ▼
        classify each periodic band
                   │
          ┌────────┼─────────┐
          ▼        ▼         ▼
       CORRECT  HARMONIC   WRONG
                   or
                NO LOCK
```

## Why this is the final validation file

The project has now moved through a full engineering loop:

```text
Prototype
   ↓
Belief-based scheduler
   ↓
UCB exploration
   ↓
Multi-channel scanning
   ↓
PRI awareness
   ↓
PRI lock-on discovered
   ↓
Persistent characterization fix
   ↓
Plateau/jitter fix
   ↓
Harmonic-selection fix
   ↓
Switch-cost modeling
   ↓
Warmup dwell + scaled warmup
   ↓
Identical-environment validation
   ↓
Multi-seed PDW validation
```

And this final file specifically closes the remaining validation gap:

> **Does the harmonic-selection fix actually work across multiple synthetic PDW seeds, especially for the 650 μs / 20 μs fractional-PRI case where the old algorithm could select the 2× harmonic?**

That is what `validate_pdw_multiseed.py` is designed to establish.

---

# Results and Data Files

The ZIP also contains **three CSV result files**:

1. `multi_seed_results.csv`
2. `pdw_multiseed_results.csv`
3. `plateau_validation_results.csv`

These are not source-code files; they are the **experimental outputs produced by the code**.

If continuing the full project walkthrough, the natural next step is therefore to go through those **three CSVs**, explaining **every column, every row/result, what experiment generated it, and how to interpret the numbers**, rather than merely summarizing them.

# CSV 1 — `multi_seed_results.csv`

This is the **largest results file**.

It contains:

- **720 data rows**
- 4 columns
- results from **6 experimental suites**
- generally **20 seeds per scheduler/configuration**

The header is:

```text
suite,scheduler,seed,interception_ratio
```

## Column 1 — `suite`

Identifies which experiment produced that row.

There are six suites:

```text
A_prototype
B_multichannel_k1
B_multichannel_k2
B_multichannel_k3
C_beacon_k1
C_beacon_k2
D_sparse_k1
D_sparse_k2
D_per_emitter_radar
D_per_emitter_comm1
E_turing_pdw
F_fix_radar_capture
F_fix_comm1_capture
```

So although there are six broad suites, some suites produce multiple result categories.

---

# Column 2 — `scheduler`

Identifies algorithm being tested.

Examples:

```text
RoundRobin (open-loop)
Random (naive)
BeliefScheduler (learned)
BeliefUCB (learned)
PRIAware (Markov+periodicity)
Persistent (fixed)
```

---

# Column 3 — `seed`

Random seed used for that experiment.

Example:

```text
seed = 1
```

means that row corresponds to stochastic experiment generated with seed 1.

Different seeds create different emitter trajectories and/or PDW datasets.

---

# Column 4 — `interception_ratio`

This is the key metric:

$$
\boxed{
\text{Interception Ratio}
=
\frac{\text{successful intercepted transmission events}}
{\text{total transmission activity}}
}
$$

For example:

```text
0.52975
```

means approximately:

$$
52.975\%
$$

of transmission-active timesteps were intercepted.

---

# Suite A — Prototype

The first rows look like:

```text
A_prototype,RoundRobin (open-loop),1,0.255
A_prototype,RoundRobin (open-loop),2,0.253
A_prototype,RoundRobin (open-loop),3,0.266
...
```

This is the original V1 experiment.

Three schedulers:

- RoundRobin
- Random
- BeliefScheduler

Each gets 20 seeds.

### Aggregate result

| Scheduler | Mean | Std. dev. | Min | Max |
|---|---:|---:|---:|---:|
| RoundRobin | 25.59% | 2.57 pp | 24.9% | 26.6% |
| Random | 25.25% | 0.63 pp | 24.3% | 26.3% |
| **BeliefScheduler** | **52.98%** | 2.57 pp | 49.4% | 58.9% |

This is the first major result.

Belief learning roughly **doubles interception performance**:

$$
\frac{52.98}{25.59}\approx2.07
$$

So the original idea—learning each band's temporal behavior rather than blindly sweeping—clearly works in this simulated environment.

Notice something important:

The original single-seed result was around **49.4%**, but across 20 seeds the mean is **52.98%**.

That tells us the 49.4% result wasn't the only thing happening; it was simply one stochastic realization.

---

# Suite B — Multi-channel

This tests:

```text
k = 1
k = 2
k = 3
```

where `k` means number of bands scanned simultaneously.

## k = 1

| Scheduler | Mean |
|---|---:|
| RoundRobin | 12.50% |
| Random | 12.38% |
| **BeliefUCB** | **28.14%** |

Again learned scheduling wins.

---

## k = 2

| Scheduler | Mean |
|---|---:|
| RoundRobin | 25.02% |
| Random | 25.06% |
| **BeliefUCB** | **54.26%** |

Notice:

$$
28.14\%\rightarrow54.26\%
$$

when going from one to two simultaneous channels.

That is almost exactly a doubling.

---

## k = 3

| Scheduler | Mean |
|---|---:|
| RoundRobin | 37.49% |
| Random | 37.48% |
| **BeliefUCB** | **68.56%** |

So the learned scheduler scales strongly with channel capacity.

The progression is:

```text
k=1 → 28.14%
k=2 → 54.26%
k=3 → 68.56%
```

This is important for the project presentation because it demonstrates that the algorithm isn't only useful in a one-channel toy setup.

---

# Suite C — Beacon

Now we introduce periodic behavior.

This is where `PRIAwareScheduler` enters.

## k = 1

| Scheduler | Mean |
|---|---:|
| RoundRobin | 12.50% |
| BeliefUCB | 27.89% |
| **PRIAware** | **29.20%** |

PRIAware improves over Markov-only UCB:

$$
29.20-27.89=1.31\text{ percentage points}
$$

So periodicity information helps when only one band can be selected.

---

# k = 2

This produces the first important warning.

| Scheduler | Mean |
|---|---:|
| RoundRobin | 25.02% |
| **BeliefUCB** | **54.17%** |
| PRIAware | 51.84% |

Now:

$$
51.84 < 54.17
$$

So PRIAware is **worse** than BeliefUCB when two channels are available.

This became the motivation for:

```text
diagnose_beacon_regression.py
```

The periodicity bonus can make the scheduler over-invest in beacon-related bands.

In other words:

> Better prediction of one emitter does not automatically mean better global scheduling.

That's a very important algorithmic lesson.

---

# Suite D — Sparse radar

This is the experiment where the project's **8-hit lock-on problem** becomes obvious.

## k = 1

| Scheduler | Mean |
|---|---:|
| RoundRobin | 11.66% |
| BeliefUCB | 32.98% |
| **PRIAware** | **34.82%** |

Average PRIAware wins.

But average alone hides something nasty.

Look at per-emitter radar capture.

---

# `D_per_emitter_radar`

| Scheduler | Mean radar capture |
|---|---:|
| BeliefUCB | **0.318%** |
| PRIAware | **50.0%** |

That gigantic difference tells us PRIAware sometimes discovers the sparse radar's PRI and then captures it extremely well.

But:

```text
PRIAware:
min = 0%
max = 100%
```

So different seeds can produce:

```text
seed A → complete failure
seed B → almost perfect lock-on
```

This is exactly why the team couldn't stop after seeing one successful demonstration.

It needed multi-seed validation.

---

# `D_per_emitter_comm1`

| Scheduler | Mean comm-1 capture |
|---|---:|
| BeliefUCB | **87.02%** |
| PRIAware | 74.83% |

This reveals the cost of chasing the sparse radar.

PRIAware improves radar capture enormously, but sacrifices some productive communications capture.

Again:

> Optimizing one target can hurt overall interception.

---

# Suite D, k = 2

| Scheduler | Mean |
|---|---:|
| RoundRobin | 23.29% |
| BeliefUCB | 47.995% |
| **PRIAware** | **50.86%** |

Here PRIAware beats BeliefUCB.

So the sparse scenario differs from the beacon scenario:

```text
Beacon k=2:
PRIAware < BeliefUCB

Sparse radar k=2:
PRIAware > BeliefUCB
```

This is why the project needed separate diagnosis instead of claiming "PRI awareness always improves performance."

---

# Suite E — Turing PDW

This is the bridge from simulation to more realistic pulse data.

The results:

| Scheduler | Mean interception |
|---|---:|
| RoundRobin | 12.495% |
| Random | 12.510% |
| BeliefUCB | 26.410% |
| **PRIAware** | **26.415%** |

The interesting observation is:

$$
26.415\%\approx26.410\%
$$

So PRIAware doesn't provide a meaningful overall interception advantage over BeliefUCB here.

But that does **not** mean PRI learning is useless.

The PDW experiment is also testing whether the scheduler can correctly identify the underlying periodic structures.

That is what the next CSV isolates.

---

# Suite F — Persistent fix

The radar-capture results:

| Scheduler | Mean radar capture |
|---|---:|
| Original PRIAware | 50.00% |
| **Persistent PRIAware** | **93.48%** |

This is one of the strongest results in the entire project.

The V4 persistent characterization mechanism transforms:

```text
50%
```

into:

```text
93.48%
```

while reducing seed-to-seed variability dramatically:

```text
Original std ≈ 51.30 pp
Persistent std ≈ 0.67 pp
```

That is arguably more important than the increase in mean itself.

The algorithm becomes much more **reliable**.

But again there is a tradeoff.

---

# Persistent fix — communication capture

| Scheduler | Mean comm-1 capture |
|---|---:|
| Original PRIAware | 74.83% |
| Persistent | 68.53% |

So persistent characterization improves radar capture:

$$
50.0\%\rightarrow93.48\%
$$

but decreases comm-1 capture:

$$
74.83\%\rightarrow68.53\%
$$

This is not necessarily a bug.

It shows the scheduler is deliberately spending more resources characterizing the sparse radar.

---

# CSV 2 — `pdw_multiseed_results.csv`

This one is much smaller:

```text
40 data rows
6 columns
```

Header:

```text
scheduler,seed,interception_ratio,band1_verdict,band4_verdict,band6_verdict
```

The extra three columns are crucial.

---

## `band1_verdict`

Whether scheduler successfully learned periodicity of band 1.

Ground truth:

$$
PRI=1000\mu s
$$

---

## `band4_verdict`

Whether scheduler learned periodicity of band 4.

Ground truth:

$$
PRI=650\mu s
$$

This is the **main harmonic-fix test**.

At 20 μs dwell:

$$
\frac{650}{20}=32.5
$$

So the true period is fractional in simulation steps.

---

## `band6_verdict`

Ground truth:

$$
PRI=1500\mu s
$$

---

# Why band 4 matters most

Suppose algorithm estimates:

$$
65\text{ steps}
$$

instead of:

$$
32.5\text{ steps}
$$

Then:

$$
65=2(32.5)
$$

The scheduler has found a **harmonic**, not the fundamental.

It may appear highly periodic while still being wrong.

That's the exact failure mode the new candidate-selection algorithm targets.

---

# PDW results

## BeliefUCB

```text
Mean = 17.88%
```

No PRI verdicts, because it doesn't have PRI machinery.

---

## PlateauOnly

Mean:

$$
23.11\%
$$

Band 4:

```text
CORRECT = 7/10
NO LOCK = 3/10
HARMONIC = 0
```

So old candidate selection can work, but doesn't reliably lock.

---

## Current PRIAware

Mean:

$$
27.03\%
$$

Band 4:

```text
CORRECT = 10/10
HARMONIC = 0
NO LOCK = 0
```

**This is the cleanest validation of the harmonic fix.**

The exact target was:

```text
650 μs / 20 μs ≈ 32.5 steps
```

and the current implementation correctly identifies it across **all 10 tested seeds**.

---

## PersistentPRIAware

Mean:

$$
26.48\%
$$

Band 4:

```text
CORRECT = 9/10
NO LOCK = 1/10
HARMONIC = 0
```

So V4 doesn't improve this particular lock statistic over V3.

That's expected: V4's major purpose is **persistent characterization**, not harmonic selection.

---

# Band 6

Interesting result:

### Current PRIAware

```text
CORRECT = 5
NO LOCK = 5
```

### Persistent V4

```text
CORRECT = 7
NO LOCK = 3
```

So persistence helps another periodic emitter too.

---

# CSV 3 — `plateau_validation_results.csv`

This file has:

```text
300 data rows
4 columns
```

Header:

```text
suite,scheduler,seed,interception_ratio
```

It isolates the **plateau/jitter fix**.

Two experiments:

```text
plateau_validation_k1
plateau_validation_k2
```

Each has:

```text
30 seeds
×
5 schedulers
=
150 rows
```

So:

$$
150+150=300
$$

---

# The five algorithms

```text
RoundRobin
BeliefUCB
Original
PlateauOnly
Current
```

Meaning:

```text
Original
   = before both fixes

PlateauOnly
   = plateau fix only

Current
   = plateau + harmonic fixes
```

This lets us ask:

> Did each individual fix help, and what happened when both were combined?

---

# k = 1 results

| Scheduler | Mean | Min | Max |
|---|---:|---:|---:|
| RoundRobin | 12.52% | 12.0% | 13.0% |
| BeliefUCB | 27.70% | — | 29.9% |
| Original | 28.87% | — | 32.1% |
| PlateauOnly | 27.33% | — | 30.7% |
| Current | 27.34% | — | 29.3% |

The striking thing:

```text
Original:     28.87%
PlateauOnly:  27.33%
Current:      27.34%
BeliefUCB:    27.70%
```

So the plateau fix **doesn't increase headline interception ratio** in this particular beacon test.

That is not necessarily surprising.

The fix is aimed at **correctness/stability of periodicity estimation**, not simply maximizing raw interception.

---

# k = 2

| Scheduler | Mean |
|---|---:|
| RoundRobin | 25.01% |
| Original | 51.66% |
| PlateauOnly | 53.28% |
| **BeliefUCB** | **54.22%** |
| Current | 53.16% |

Here PlateauOnly improves over Original:

$$
53.28-51.66=1.62\text{ pp}
$$

But Current is still below BeliefUCB:

$$
53.16<54.22
$$

So the full PRI machinery doesn't win this particular beacon/k=2 benchmark.

Again, that's useful evidence rather than something to hide.

---

# What all three CSVs tell us

The project isn't simply:

```text
"We built PRIAware and it works."
```

The actual engineering story is much more interesting.

## Stage 1 — Basic learning works

```text
BeliefScheduler
≈53%
```

vs

```text
RoundRobin
≈26%
```

in prototype.

---

## Stage 2 — More channels help

BeliefUCB:

```text
k=1 → 28.14%
k=2 → 54.26%
k=3 → 68.56%
```

---

## Stage 3 — Periodicity can help

Beacon:

```text
k=1:
PRIAware 29.20%
BeliefUCB 27.89%
```

But...

```text
k=2:
PRIAware 51.84%
BeliefUCB 54.17%
```

So periodicity introduces **new optimization tradeoffs**.

---

## Stage 4 — Sparse radar exposes lock-on instability

Original PRIAware:

```text
radar capture:
mean 50%
std 51.3 pp
```

That's a giant seed sensitivity.

---

## Stage 5 — Persistent characterization fixes it

V4:

```text
radar:
50.0% → 93.48%

std:
51.3 pp → 0.67 pp
```

Much more stable.

---

## Stage 6 — Plateau problem gets isolated

`PlateauOnly` separates:

```text
burst duration / jitter handling
```

from:

```text
harmonic candidate selection
```

This separation is scientifically important because it identifies **which modification caused each effect**.

---

## Stage 7 — Harmonic fix gets directly validated

Band 4:

$$
650\mu s / 20\mu s=32.5\text{ steps}
$$

Old:

```text
7/10 correct
3/10 no lock
```

Current:

```text
10/10 correct
0/10 harmonic
0/10 no lock
```

That is the cleanest experimental evidence that the new PRI candidate-selection mechanism solves its intended problem.

---

# Final architecture of the project

After walking through **all 18 Python files + 3 CSVs**, the whole codebase can be understood as:

```text
                         SMART SCAN SCHEDULER
                                  │
             ┌────────────────────┴────────────────────┐
             │                                         │
       ENVIRONMENT                               SCHEDULER
             │                                         │
    ┌────────┼────────┐                    ┌───────────┴───────────┐
    │        │        │                    │                       │
 Markov   Periodic   Agile             BeliefUCB               PRIAware
 emitter   beacon   hopper                 │                       │
    │        │        │                    │                 ┌─────┴─────┐
    └────────┴────────┘                    │                 │           │
             │                             │              PRI model   Markov
             ▼                             │                 │
       band activity                      │          plateau fix
             │                             │                 │
             ▼                             │          harmonic fix
       run_episode()                       │                 │
             │                             │                 ▼
             │                             │          Persistent V4
             ▼                             │                 │
       metrics/report                      │          persistent
                                           │       characterization
                                           │                 │
                                           └─────────────────┘
```

And then:

```text
Synthetic simulation
       │
       ├── prototype validation
       ├── multichannel validation
       ├── beacon validation
       ├── sparse-radar validation
       └── switch-cost validation

Real/synthetic PDW
       │
       ├── PDW replay environment
       ├── PRI estimation
       ├── harmonic validation
       └── multi-seed validation
```

## Most important lesson from entire codebase

The project gradually discovered that **"having a smarter prediction model" is not enough**.

Four separate problems must be addressed:

1. **Prediction** — what will each band do?
2. **Exploration** — which poorly understood bands deserve attention?
3. **Characterization** — how do we reliably learn sparse periodic emitters?
4. **Resource allocation** — when should we stop chasing one emitter and spend scans elsewhere?

The V1 → V4 evolution is essentially the codebase progressively solving those four problems.

**That completes the full ZIP walkthrough: 18 Python source files, their algorithms and evolution, plus all 3 CSV result files and what their experimental results mean.**


---
