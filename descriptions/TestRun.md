# Explain Every Code Line

**User:** Anonymous  
**Created:** 9/10/2026 1:25:29  
**Updated:** 9/10/2026 23:53:52  
**Exported:** 9/10/2026 23:55:25  
**Link:** [https://chatgpt.com/c/6aa1b9b0-bf50-83e8-8802-a142dbd0feed](https://chatgpt.com/c/6aa1b9b0-bf50-83e8-8802-a142dbd0feed)  

## Response:
9/10/2026, 8:14:52 PM

Yep. Since we’ve now gone through all 18 Python files, you can execute this project locally. The important thing is **not to run every `.py` file randomly**—some are core implementations, some are experiments/diagnostics, and some depend on earlier modules.

## 1. Extract the ZIP

Extract:

`f0f3198a-ca1b-4c48-afe3-b83e22c9be67.zip`

You should have something like:

```text
SIH/
├── scan_scheduler_prototype.py
├── scan_scheduler_v2.py
├── scan_scheduler_v3_pri.py
├── scan_scheduler_v4_persistent.py
├── pdw_loader.py
├── pdw_environment.py
├── run_on_turing_dataset.py
├── diagnose_beacon_regression.py
├── diagnose_pri_lockon.py
├── multi_seed_robustness.py
├── tune_confidence_threshold.py
├── validate_offbyone_fix.py
├── validate_plateau_fix.py
├── validate_warmup_dwell_fix.py
├── validate_beacon_switchcost_dwell.py
├── switch_cost_comparison.py
├── settle_fix_interaction.py
├── validate_pdw_multiseed.py
├── multi_seed_results.csv
├── pdw_multiseed_results.csv
└── plateau_validation_results.csv
```

---

# 2. Install Python

I'd use **Python 3.10–3.12** for this project.

Check:

```cmd
python --version
```

or:

```cmd
py --version
```

If Windows says Python isn't found, install Python first.

---

# 3. Open CMD in the project folder

For example, if you extracted it to:

```text
D:\Projects\SIH
```

run:

```cmd
cd /d D:\Projects\SIH
```

Verify:

```cmd
dir
```

You should see the `.py` files.

---

# 4. Create a virtual environment

Strongly recommended.

```cmd
python -m venv .venv
```

Activate it:

```cmd
.venv\Scripts\activate
```

You should then see something like:

```text
(.venv) D:\Projects\SIH>
```

---

# 5. Install required Python packages

The project primarily uses Python's standard library plus **NumPy**.

Install:

```cmd
pip install numpy
```

You can also upgrade pip:

```cmd
python -m pip install --upgrade pip
```

So:

```cmd
python -m pip install --upgrade pip
pip install numpy
```

---

# 6. First test: run the original prototype

Start with the simplest implementation:

```cmd
python scan_scheduler_prototype.py
```

This is the V1 simulation.

It should run the three schedulers:

```text
RoundRobin
Random
BeliefScheduler
```

and print their performance statistics.

This is the best first test because it doesn't involve the later PDW machinery.

---

# 7. Run V2

Then:

```cmd
python scan_scheduler_v2.py
```

V2 introduces:

- multi-channel scanning
- `k = 1, 2, 3`
- UCB exploration
- dwell
- switch cost
- warmup handling

You should see comparisons for different numbers of simultaneously selected bands.

---

# 8. Run V3

```cmd
python scan_scheduler_v3_pri.py
```

This adds:

```text
PRIAwareScheduler
```

and PRI detection/prediction.

It runs both:

- normal beacon scenario
- sparse periodic radar scenario

---

# 9. Run V4

```cmd
python scan_scheduler_v4_persistent.py
```

This tests:

```text
BeliefUCB
PRIAware
PersistentPRIAware
```

The important thing here is the persistent characterization mechanism we discussed.

---

# 10. Run the diagnostics

These aren't required for the basic system, but they're useful for understanding why certain results happen.

### Beacon regression

```cmd
python diagnose_beacon_regression.py
```

This investigates:

> Why does PRIAware behave differently for `k=1` versus `k=2`?

---

### PRI lock-on

```cmd
python diagnose_pri_lockon.py
```

This investigates the seed-sensitive sparse-radar lock-on problem.

You'll see results across 40 seeds by default.

---

# 11. Run the multi-seed experiment

This is one of the more important scripts:

```cmd
python multi_seed_robustness.py
```

Default:

```text
20 seeds
```

It runs suites A–F and produces:

```text
multi_seed_results.csv
```

If you want, for example, only 5 seeds:

```cmd
python multi_seed_robustness.py --seeds 5
```

Or 100 seeds:

```cmd
python multi_seed_robustness.py --seeds 100
```

You can also specify starting seed:

```cmd
python multi_seed_robustness.py --seeds 50 --seed-start 1
```

---

# 12. Run the confidence-threshold experiment

```cmd
python tune_confidence_threshold.py
```

This sweeps:

```text
0.25
0.20
0.17
0.15
0.12
0.10
```

for `confidence_scale`.

It tests whether lowering the confidence scale improves the beacon behavior without breaking PDW PRI detection.

---

# 13. Run the individual validation experiments

You can execute them directly.

### Off-by-one PRI fix

```cmd
python validate_offbyone_fix.py
```

### Plateau fix

```cmd
python validate_plateau_fix.py
```

### Warmup/dwell fix

```cmd
python validate_warmup_dwell_fix.py
```

### Beacon + switch-cost investigation

```cmd
python validate_beacon_switchcost_dwell.py
```

### Switch-cost comparison

```cmd
python switch_cost_comparison.py
```

### Seeding/interaction investigation

```cmd
python settle_fix_interaction.py
```

### PDW multi-seed validation

```cmd
python validate_pdw_multiseed.py
```

---

# 14. The interesting part: running on the Turing PDW dataset

This is where things change slightly.

Run:

```cmd
python run_on_turing_dataset.py
```

The script first attempts to load the real HDF5 dataset.

If the required Turing dataset package/file isn't available, the script **falls back to the synthetic PDW generator** we examined.

So you can test it without the real dataset:

```cmd
python run_on_turing_dataset.py
```

---

## 15. Useful options for `run_on_turing_dataset.py`

You can inspect all available options with:

```cmd
python run_on_turing_dataset.py --help
```

You'll see options corresponding to things we studied, including:

```text
--h5
--n-bands
--dwell-us
--k-channels
--warmup-steps
--ucb-c
--confidence-scale
--priority
--seed
--switch-cost-steps
--switch-lead-steps
--warmup-dwell-steps
--warmup-dwell-jitter
--auto-dwell
```

For example:

```cmd
python run_on_turing_dataset.py --k-channels 2
```

or:

```cmd
python run_on_turing_dataset.py --k-channels 1 --seed 42
```

---

# 16. If you have the actual Turing `.h5` dataset

Then you can give it explicitly:

```cmd
python run_on_turing_dataset.py --h5 path\to\dataset.h5
```

For example:

```cmd
python run_on_turing_dataset.py --h5 data\turing_dataset.h5
```

The loader does:

```text
HDF5
 ↓
PulseTrain.load()
 ↓
PDW records
 ↓
PDWReplayEnvironment
 ↓
band/time representation
 ↓
scheduler
 ↓
interception statistics
```

One important point from our code walkthrough:

**The real PDW labels are loaded but aren't being used to calculate emitter/deinterleaving accuracy.**

The current experiment primarily measures **band-level interception/capture**.

---

# 17. Recommended execution order

Don't run 18 files randomly.

I'd do this:

```text
1. scan_scheduler_prototype.py
        ↓
2. scan_scheduler_v2.py
        ↓
3. scan_scheduler_v3_pri.py
        ↓
4. scan_scheduler_v4_persistent.py
        ↓
5. diagnose_beacon_regression.py
        ↓
6. diagnose_pri_lockon.py
        ↓
7. multi_seed_robustness.py
        ↓
8. tune_confidence_threshold.py
        ↓
9. validate_offbyone_fix.py
        ↓
10. validate_plateau_fix.py
        ↓
11. validate_warmup_dwell_fix.py
        ↓
12. validate_beacon_switchcost_dwell.py
        ↓
13. switch_cost_comparison.py
        ↓
14. settle_fix_interaction.py
        ↓
15. validate_pdw_multiseed.py
        ↓
16. run_on_turing_dataset.py
```

`pdw_loader.py` and `pdw_environment.py` are **support modules**, so you normally don't need to execute them directly.

---

# 18. One important Python concept here

You may notice that we're running:

```cmd
python scan_scheduler_v3_pri.py
```

even though that file imports things like:

```python
from scan_scheduler_v2 import ...
```

Python looks in the current directory for:

```text
scan_scheduler_v2.py
```

So **keep all these `.py` files in the same directory** unless you deliberately turn the project into a package.

Don't do this:

```text
SIH/
├── v1/
│   └── scan_scheduler_prototype.py
├── v2/
│   └── scan_scheduler_v2.py
└── ...
```

without modifying imports.

Keep the flat structure for now.

---

# 19. If you get `ModuleNotFoundError: numpy`

Run:

```cmd
pip install numpy
```

If you're using the virtual environment:

```cmd
.venv\Scripts\activate
pip install numpy
```

Then retry.

---

# 20. If `python` doesn't work

Try:

```cmd
py scan_scheduler_prototype.py
```

and:

```cmd
py -m pip install numpy
```

---

## The simplest possible start

If you want to get the project running **right now**, do only this:

```cmd
cd /d D:\path\to\SIH
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install numpy
python scan_scheduler_prototype.py
```

If that works, proceed:

```cmd
python scan_scheduler_v2.py
python scan_scheduler_v3_pri.py
python scan_scheduler_v4_persistent.py
```

Then move on to the validation scripts.

**If your goal is to actually understand and reproduce the project's results rather than merely execute it, I'd recommend we next set it up in VS Code and run the scripts one-by-one, examining the output of each and understanding what each experiment proves.**

## Prompt:
9/10/2026, 8:17:15 PM

Yes! Please! Thank you for suggesting that!

## Response:
9/10/2026, 8:17:18 PM

Absolutely. 😄

Let's do this **properly**, as if we're setting up a real research/code project-not simply firing off `.py` files and hoping they work.

The goal will be:

> **Set up project → run V1 → understand output → run V2 → understand changes → V3 PRI → V4 fix → reproduce experiments → inspect CSV results → finally run PDW dataset.**

And I'll stay with you through each stage.

---

# Part 1 - Set up VS Code

## Step 1: Install VS Code

If you don't already have it, install Visual Studio Code.

Then open VS Code.

---

## Step 2: Open the project folder

In VS Code:

**File → Open Folder**

Select the folder containing:

```text
scan_scheduler_prototype.py
scan_scheduler_v2.py
scan_scheduler_v3_pri.py
...
```

Your Explorer should roughly look like:

```text
SIH
│
├── scan_scheduler_prototype.py
├── scan_scheduler_v2.py
├── scan_scheduler_v3_pri.py
├── scan_scheduler_v4_persistent.py
│
├── pdw_loader.py
├── pdw_environment.py
├── run_on_turing_dataset.py
│
├── diagnose_beacon_regression.py
├── diagnose_pri_lockon.py
│
├── multi_seed_robustness.py
├── tune_confidence_threshold.py
│
├── validate_offbyone_fix.py
├── validate_plateau_fix.py
├── validate_warmup_dwell_fix.py
├── validate_beacon_switchcost_dwell.py
├── switch_cost_comparison.py
├── settle_fix_interaction.py
├── validate_pdw_multiseed.py
│
└── *.csv
```

**Don't rearrange the files yet.**

Their current flat structure is important because the Python files import one another.

---

# Part 2 - Open VS Code terminal

In VS Code:

**Terminal → New Terminal**

You'll get something like:

```text
PS D:\Projects\SIH>
```

Make sure you're actually inside your project directory.

Run:

```powershell
dir
```

You should see the Python files.

---

# Part 3 - Create our isolated Python environment

Run:

```powershell
python -m venv .venv
```

This creates:

```text
SIH
│
├── .venv
│
├── scan_scheduler_prototype.py
├── ...
```

Now activate it:

```powershell
.venv\Scripts\Activate.ps1
```

Your prompt should change to something like:

```text
(.venv) PS D:\Projects\SIH>
```

That `(.venv)` is important.

It means:

> "Commands I'm running now use this project's Python environment."

---

# Part 4 - Install NumPy

Run:

```powershell
python -m pip install --upgrade pip
```

Then:

```powershell
pip install numpy
```

Test it:

```powershell
python -c "import numpy; print(numpy.__version__)"
```

You should get something like:

```text
2.x.x
```

---

# Part 5 - Select Python interpreter in VS Code

This is important.

Press:

```text
Ctrl + Shift + P
```

Search:

```text
Python: Select Interpreter
```

Choose the interpreter inside:

```text
.venv
```

It'll look approximately like:

```text
Python 3.x.x ('.venv': venv)
```

Now VS Code and your terminal should be using the same Python environment.

---

# Part 6 - Our first experiment

We're going to **ignore all the fancy V3/V4 stuff initially**.

Open:

```text
scan_scheduler_prototype.py
```

This is our foundation.

We've already gone through every line, so now we're going to see the code **actually execute**.

---

## Run it from terminal

Don't use the VS Code Run button yet.

Use:

```powershell
python scan_scheduler_prototype.py
```

Why terminal first?

Because I want you to see exactly:

```text
command
    ↓
Python interpreter
    ↓
script
    ↓
imports
    ↓
objects/functions
    ↓
main experiment
    ↓
output
```

That's much more useful for learning.

---

# Part 7 - What we're looking for

When V1 runs, don't worry if the exact numbers aren't immediately obvious.

We're interested in understanding this:

```text
Environment
      │
      ▼
Emitters
      │
      ▼
Current spectrum state
      │
      ▼
Scheduler chooses bands
      │
      ▼
Compare chosen bands with active emitters
      │
      ▼
Update scheduler's beliefs
      │
      ▼
Repeat
```

Three schedulers are being compared:

```text
RoundRobin
Random
BeliefScheduler
```

The interesting question is:

> **Does learning where activity occurs improve interception compared with blindly scanning?**

That's the fundamental experiment.

---

# Part 8 - Don't modify anything yet

This is important.

For our first pass:

**Do not change the code.**

We want to establish a clean baseline.

Write down the output you get.

If you want, paste the complete terminal output here.

I'll then walk you through:

```text
output line
     ↓
which function generated it
     ↓
which variables produced it
     ↓
what the number means
     ↓
why scheduler A differs from scheduler B
```

---

# Part 9 - Then we'll move to V2

Once V1 works, we'll run:

```powershell
python scan_scheduler_v2.py
```

Then we'll compare:

### V1

```text
RoundRobin
Random
BeliefScheduler
```

against V2:

```text
RoundRobin
Random
BeliefUCB
```

and importantly:

```text
k = 1
k = 2
k = 3
```

We'll understand **exactly what changed between V1 and V2**.

---

# Part 10 - Then V3 becomes much easier

Next:

```powershell
python scan_scheduler_v3_pri.py
```

Here we'll watch the project transition from:

```text
"Learn which bands are active"
```

to:

```text
"Learn when a band is likely to become active"
```

That's where PRI enters.

Conceptually:

```text
Normal scheduler

Band 5:
ON ... OFF OFF OFF ... ON ...?
```

versus:

```text
PRI-aware scheduler

Observed hits:
100
112
124
136
148

Differences:
 12
 12
 12
 12

             ↓

Estimated PRI = 12

             ↓

Next predicted hit ≈ 160
```

That's the central idea behind the later code.

---

# Part 11 - Then V4

After understanding V3:

```powershell
python scan_scheduler_v4_persistent.py
```

We'll see why this was necessary.

The problem isn't simply:

> "Can we detect PRI?"

It's:

> **"Can we reliably obtain enough observations to detect PRI in the first place?"**

That distinction is crucial.

The V4 mechanism tries to solve the chicken-and-egg problem:

```text
Need observations
      ↓
Need scans
      ↓
Need scheduler to choose band
      ↓
But scheduler doesn't yet know band is important
      ↓
Need temporary characterization incentive
```

That's what the persistent characterization bonus is doing.

---

# Part 12 - Then reproduce the experiments

Once the four scheduler versions work, we'll run the experiments in this order:

```text
                  V1
                   │
                   ▼
                  V2
                   │
                   ▼
                  V3
                   │
                   ▼
                  V4
                   │
                   ├──────────────┐
                   ▼              ▼
             Beacon tests     Sparse radar
                   │              │
                   ▼              ▼
             PRI diagnostics   Lock-on
                   │              │
                   └──────┬───────┘
                          ▼
                  Multi-seed tests
                          │
                          ▼
                    CSV results
                          │
                          ▼
                    Fix validation
                          │
                          ▼
                   Synthetic PDW
                          │
                          ▼
                    Real Turing
                       dataset
```

---

# Part 13 - One thing I want you to learn from this

Don't think of this project as:

> "18 Python files."

Think of it as:

```text
                    PROJECT
                       │
          ┌────────────┴────────────┐
          │                         │
     CORE SYSTEM                EXPERIMENTS
          │                         │
     V1 → V2 → V3 → V4       diagnostics/validation
          │                         │
          └────────────┬────────────┘
                       │
                       ▼
                  PDW SYSTEM
                       │
                       ▼
              synthetic / real data
```

The validation scripts aren't random programs. Most of them answer **specific scientific questions** about whether a particular modification fixed a particular failure mode.

That makes this much closer to a small research project than a normal programming assignment.

---

## Your first task

For now, do exactly these:

```powershell
python --version
```

then:

```powershell
python -m venv .venv
```

then:

```powershell
.venv\Scripts\Activate.ps1
```

then:

```powershell
pip install numpy
```

then:

```powershell
python scan_scheduler_prototype.py
```

**Paste the output of that last command here.**

We'll treat that as **Experiment 1: establishing the V1 baseline**, and I'll explain the output from the actual execution rather than merely telling you what the source code theoretically does.

## Prompt:
9/10/2026, 8:29:58 PM

![6378d6be-31eb-48b4-8de2-7de7b84a2083.png](https://chatgpt.com/backend-api/estuary/content?id=file_000000000b6881f4ab5a1e67ec0b0201&fn=6378d6be-31eb-48b4-8de2-7de7b84a2083.png&cd=attachment&ts=496962&p=fs&cid=1&sig=75875c8da5e96e30e6905d59891458ae57f60f9bf41f6d40160e4282c822c198&v=0)

Is this what we want?

## Response:
9/10/2026, 8:30:02 PM

Yes! **Exactly what we want.** 👍

Your screenshot shows:

```text
PS D:\Code\SIH\SIH> python -m venv .venv
PS D:\Code\SIH\SIH>
```

That means the virtual environment was created successfully. 🎉

You should now have:

```text
D:\Code\SIH\SIH\
│
├── .venv\                 ← newly created
├── scan_scheduler_prototype.py
├── scan_scheduler_v2.py
├── scan_scheduler_v3_pri.py
├── ...
└── *.csv
```

### Next step: activate it

In **that same terminal**, run:

```powershell
.venv\Scripts\Activate.ps1
```

If successful, your prompt should change from:

```text
PS D:\Code\SIH\SIH>
```

to:

```text
(.venv) PS D:\Code\SIH\SIH>
```

That `(.venv)` is what we're looking for.

Then **don't run the project yet**. Send me a screenshot/output showing the activated prompt, and we'll take the next step together.

## Prompt:
9/10/2026, 8:33:20 PM

Scenario: 8 bands, 4000 steps, 4 concurrent emitters (2 Markov comms, 1 periodic beacon, 1 frequency-agile threat)

Scheduler                                |  Interception % |  Avg Reward/step |  Avg Intercept Delay
----------------------------------------------------------------------------------------------------
RoundRobin (open-loop baseline)          |           26.0% |            0.260 |                 1.48
Random (naive baseline)                  |           26.0% |            0.260 |                 1.42
BeliefScheduler (learned, closed-loop)   |           49.4% |            0.494 |                 1.64

## Response:
9/10/2026, 8:33:24 PM

Perfect. **V1 ran successfully.** 🎉

And these results are actually very useful. Let's understand exactly what they mean before moving on.

### Your V1 result

| Scheduler | Interception | Avg reward/step | Avg intercept delay |
|---|---:|---:|---:|
| RoundRobin | **26.0%** | 0.260 | 1.48 |
| Random | **26.0%** | 0.260 | 1.42 |
| BeliefScheduler | **49.4%** | 0.494 | 1.64 |

## 1. What is "Interception %"?

This is the most important metric.

Roughly:

> **When an emitter is transmitting, how often did the scheduler scan its band?**

So:

```text
RoundRobin → 26.0%
Random     → 26.0%
Belief     → 49.4%
```

The learned scheduler is catching substantially more activity.

The striking number is:

$$
49.4\%-26.0\%=23.4\text{ percentage points}
$$

or approximately:

$$
\frac{49.4}{26.0}\approx1.9
$$

So V1's learned scheduler gets **about 1.9× the interception rate** of the two open-loop baselines in this run.

---

# 2. Why are RoundRobin and Random almost identical?

This is actually not surprising.

You have:

```text
8 bands
```

and the baseline schedulers don't learn anything about emitter behavior.

### RoundRobin

It systematically cycles through the bands:

```text
0 → 1 → 2 → 3 → 4 → 5 → 6 → 7
    → 0 → 1 → ...
```

### Random

It randomly selects bands.

Neither knows:

> "Band 1 tends to have communication."

or:

> "Band 2 contains a beacon."

or:

> "Band 5 is likely to become active."

Therefore, over enough steps, both spend roughly comparable scanning effort across the spectrum.

Hence:

```text
RoundRobin ≈ 26.0%
Random     ≈ 26.0%
```

Don't interpret the tiny difference in delay as Random being substantially better. The interception percentages are essentially the same in this particular run.

---

# 3. Now the interesting one: BeliefScheduler

BeliefScheduler is **closed-loop**.

It observes what happens after scanning a band.

For example, imagine:

```text
Band 1 → ON
Band 1 → ON
Band 1 → OFF
Band 1 → ON
```

The scheduler starts learning:

> "Band 1 seems productive."

Its transition model keeps information about things like:

$$
P(ON_{t+1}\mid ON_t)
$$

and

$$
P(ON_{t+1}\mid OFF_t)
$$

So instead of treating all 8 bands equally, it gradually prioritizes bands whose recent behavior suggests they're likely to be active.

That's why:

$$
26.0\% \rightarrow 49.4\%
$$

is the key V1 result.

---

# 4. But wait — why is BeliefScheduler's delay *worse*?

This is an important observation.

You got:

```text
RoundRobin       1.48
Random           1.42
BeliefScheduler  1.64
```

At first glance, that looks weird:

> "BeliefScheduler catches more signals, so why does it take longer?"

Because **interception rate and interception delay measure different things**.

The learned scheduler is concentrating its scanning effort on bands it believes are productive.

That can produce:

```text
HIGHER capture
       +
LONGER delay for some individual interceptions
```

It's making a strategic trade-off.

Think of it like this:

### RoundRobin

```text
Scan everything fairly

0 1 2 3 4 5 6 7
↑               ↑
equal attention
```

### BeliefScheduler

```text
Learn productive bands

1 1 4 1 4 1 5 1
↑ ↑ ↑ ↑ ↑
more attention where useful
```

It may ignore a low-probability band for longer.

So **average delay alone doesn't tell us which scheduler is better**.

---

# 5. What does "Avg Reward/step" mean?

Your output gives:

```text
RoundRobin       0.260
Random           0.260
BeliefScheduler  0.494
```

In this implementation, reward is essentially tied to successful interception during a timestep.

So:

$$
\text{Avg Reward/step}
=
\frac{\text{total reward}}{4000}
$$

and therefore:

```text
0.260 ≈ 26.0%
0.494 ≈ 49.4%
```

That's why these numbers correspond closely to interception percentage.

---

# 6. What have we proved with Experiment 1?

Not that BeliefScheduler is universally better.

We've established something narrower:

> **Under this particular 8-band, 4000-step stochastic scenario, learning transition behavior substantially improves interception compared with open-loop scanning.**

That's our **baseline finding**.

And this is exactly why V2 exists.

---

# 7. Now let's run V2

Don't change anything yet.

Run:

```powershell
python scan_scheduler_v2.py
```

You should see experiments involving:

```text
k = 1
k = 2
k = 3
```

where `k` means:

> **How many bands can the scheduler scan concurrently at each timestep?**

So:

```text
k = 1

[scan] [ ] [ ] [ ] [ ] [ ] [ ] [ ]
```

versus:

```text
k = 2

[scan] [scan] [ ] [ ] [ ] [ ] [ ] [ ]
```

versus:

```text
k = 3

[scan] [scan] [scan] [ ] [ ] [ ] [ ] [ ]
```

This lets us ask a much more interesting question:

> **What happens when we give the scheduler more simultaneous scanning capacity?**

Run it and paste the complete output here.

Then we'll dissect **V1 → V2 line by line at the experimental level**—what changed, why `BeliefUCBScheduler` was introduced, what `k` does, and how switch cost/dwell enters the picture.

## Prompt:
9/10/2026, 8:36:37 PM

Scenario: 8 bands, 4000 steps, 4 concurrent emitters (2 Markov comms, 1 periodic beacon, 1 frequency-agile threat)

--- k_channels = 1 (receiver scans 1 band(s) per step) ---
Scheduler                                |  Interception % |  Avg Reward/step |  Avg Intercept Delay
----------------------------------------------------------------------------------------------------
RoundRobin (open-loop baseline)          |           12.8% |            0.260 |                 1.48
Random (naive baseline)                  |           12.5% |            0.260 |                 1.42
BeliefUCB (learned, closed-loop)         |           27.4% |            0.562 |                 1.39

--- k_channels = 2 (receiver scans 2 band(s) per step) ---
Scheduler                                |  Interception % |  Avg Reward/step |  Avg Intercept Delay
----------------------------------------------------------------------------------------------------
RoundRobin (open-loop baseline)          |           25.1% |            0.452 |                  1.4
Random (naive baseline)                  |           24.9% |            0.454 |                  1.0
BeliefUCB (learned, closed-loop)         |           54.9% |            0.902 |                  0.9

--- k_channels = 3 (receiver scans 3 band(s) per step) ---
Scheduler                                |  Interception % |  Avg Reward/step |  Avg Intercept Delay
----------------------------------------------------------------------------------------------------
RoundRobin (open-loop baseline)          |           37.5% |            0.614 |                 0.65
Random (naive baseline)                  |           36.8% |            0.601 |                 0.74
BeliefUCB (learned, closed-loop)         |           68.2% |            0.939 |                 0.64

## Response:
9/10/2026, 8:36:40 PM

Excellent. **V2 is running correctly**, and these results show exactly why V2 was introduced.

There is one especially important thing to notice: **Interception % and Avg Reward/step are no longer the same metric in V2.** That's intentional because V2 changed how performance is measured.

Let's dissect this.

---

# 1. First: what changed from V1 → V2?

V1 had:

```text
1 band selected per timestep
```

V2 allows:

```text
k_channels = 1
k_channels = 2
k_channels = 3
```

So the receiver can scan multiple bands simultaneously.

The fundamental experiment is now:

> **How does increasing receiver capacity affect open-loop versus learned scheduling?**

And the answer is very clear:

```text
             k=1       k=2       k=3

RoundRobin   12.8%     25.1%     37.5%
Random       12.5%     24.9%     36.8%
BeliefUCB    27.4%     54.9%     68.2%
```

Let's understand why.

---

# 2. `k_channels = 1`

Your first block:

```text
--- k_channels = 1 ---
receiver scans 1 band(s) per step
```

Results:

```text
RoundRobin     12.8%
Random         12.5%
BeliefUCB      27.4%
```

This makes sense.

There are:

$$
8
$$

bands, but the receiver can inspect only:

$$
1
$$

per timestep.

So an open-loop scheduler can only cover a fraction of the spectrum at any instant.

---

## RoundRobin

It essentially does:

```text
t=0 → band 0
t=1 → band 1
t=2 → band 2
t=3 → band 3
...
```

Eventually it visits everything.

But if an emitter happens to transmit on band 4 while you're scanning band 1:

```text
Emitter:     [4]
Scanner:     [1]

              ✗
```

Miss.

Therefore:

```text
RoundRobin = 12.8%
```

---

# 3. Why is V2 RoundRobin only 12.8%, while V1 RoundRobin was 26%?

This is an important point.

**Don't think the program suddenly became worse.**

The denominator changed.

In V1, the headline interception metric was based on **timesteps in which some transmission was detected**.

V2's `total_band_transmissions` counts:

> active **band-time pairs**.

Suppose one timestep looks like:

```text
Band:       0 1 2 3 4 5 6 7
Emitter:    0 1 0 0 1 0 0 0
```

There are:

$$
2
$$

active band-time pairs.

If receiver scans:

```text
bands = [1]
```

it catches:

$$
1/2
$$

of the active pairs.

V2 therefore measures interception more granularly.

So **don't directly compare V1's 26.0% to V2's 12.8% as though they're the same statistic.**

---

# 4. Now look at BeliefUCB

```text
BeliefUCB = 27.4%
```

versus:

```text
RoundRobin = 12.8%
```

That's:

$$
27.4-12.8=\boxed{14.6}
$$

percentage points improvement.

Or:

$$
\frac{27.4}{12.8}\approx2.14
$$

So with only **one receiver channel**, learning gives roughly **2.1× the interception rate** in this run.

That's the first major V2 result.

---

# 5. Why is it called `BeliefUCB`?

V1's scheduler primarily used its learned belief.

V2 adds **UCB — Upper Confidence Bound** exploration.

Its score is essentially:

$$
\text{score}_b
=
\text{priority}_b\cdot\text{belief}_b
+
c\sqrt{
\frac{\log(t+1)}
{\text{scanCount}_b+1}
}
$$

There are two competing ideas.

### Exploitation

> "I think this band is productive, so scan it."

represented by:

$$
\text{belief}_b
$$

### Exploration

> "I haven't examined this band enough, so I should investigate it."

represented by:

$$
c\sqrt{
\frac{\log(t+1)}
{\text{scanCount}_b+1}
}
$$

So BeliefUCB doesn't simply camp permanently on whichever band initially looks good.

It balances:

```text
EXPLOITATION
     ↕
EXPLORATION
```

That's a major conceptual improvement.

---

# 6. Now the really interesting part: `k = 2`

Your result:

```text
RoundRobin     25.1%
Random         24.9%
BeliefUCB      54.9%
```

Notice something beautiful:

```text
k=1                 k=2

RR       12.8%  →   25.1%
Random   12.5%  →   24.9%
Belief   27.4%  →   54.9%
```

Increasing capacity from 1 → 2 approximately doubles the amount of spectrum you can inspect.

For the learned scheduler:

$$
27.4\%\rightarrow54.9\%
$$

That's almost exactly 2×.

---

# 7. Why does BeliefUCB benefit so strongly?

Imagine the scheduler has learned:

```text
Band 1 → high probability
Band 4 → high probability
Band 5 → moderate probability
```

With:

```text
k=1
```

it has to choose:

```text
[1]
```

or:

```text
[4]
```

It can't have both.

With:

```text
k=2
```

it can choose:

```text
[1, 4]
```

Now it can exploit **two promising locations simultaneously**.

This is precisely where a learned scheduler becomes valuable.

---

# 8. Reward: don't confuse this with interception %

Look at:

```text
k=1

RoundRobin     interception 12.8%    reward 0.260
Random         interception 12.5%    reward 0.260
BeliefUCB      interception 27.4%    reward 0.562
```

Why isn't:

```text
12.8% = 0.128 reward
```

?

Because V2's reward is different.

The episode reward is essentially:

> **1 if at least one scanned band contains an active emitter during that timestep.**

So suppose:

```text
Active bands:   [1, 4]
Scanned bands:  [1, 7]
```

You get:

```text
hit = YES
reward = 1
```

even though you only captured one of the two active band-time pairs.

Therefore:

### Interception %

Measures:

> **How many active band-time opportunities were captured?**

### Reward

Measures:

> **How many timesteps contained at least one successful detection?**

These are different objectives.

---

# 9. This explains the BeliefUCB reward

At `k=1`:

```text
BeliefUCB reward = 0.562
```

Meaning approximately:

$$
56.2\%
$$

of timesteps produced at least one hit.

But its band-level interception is:

$$
27.4\%
$$

Those numbers don't contradict each other.

A timestep can contain multiple active bands.

---

# 10. Now `k = 3`

Your results:

```text
RoundRobin     37.5%
Random         36.8%
BeliefUCB      68.2%
```

Again, increasing receiver capacity helps everybody.

But BeliefUCB remains far ahead:

```text
37.5% → 68.2%
```

Difference:

$$
68.2-37.5=\boxed{30.7\text{ percentage points}}
$$

And relative improvement:

$$
\frac{68.2}{37.5}\approx1.82
$$

So BeliefUCB captures about **1.8×** as many active band-time pairs as RoundRobin in this run.

---

# 11. Put everything into one table

This is probably the most useful way to see V2:

| Channels | RoundRobin | Random | BeliefUCB |
|---:|---:|---:|---:|
| **1** | 12.8% | 12.5% | **27.4%** |
| **2** | 25.1% | 24.9% | **54.9%** |
| **3** | 37.5% | 36.8% | **68.2%** |

And visually, the key pattern is:

```text
Interception %

70 |                         █
60 |                         █
50 |             █           █
40 |             █           █
30 | █           █           █
20 | █           █           █
10 | █     █     █     █     █
 0 +----------------------------
       k=1       k=2       k=3

       RR    Random    BeliefUCB
```

The exact visual isn't important—the trend is.

---

# 12. What about intercept delay?

Your results:

### k = 1

```text
RR          1.48
Random      1.42
BeliefUCB   1.39
```

BeliefUCB is actually **best** here.

That's nice: learning gives both:

```text
higher interception
+
lower average delay
```

in this case.

---

### k = 2

```text
RR          1.4
Random      1.0
BeliefUCB   0.9
```

Now delay falls significantly.

Why?

Because the receiver can watch two bands simultaneously.

---

### k = 3

```text
RR          0.65
Random      0.74
BeliefUCB   0.64
```

Again, more channels means a target doesn't have to wait as long before its band gets scanned.

So there's an intuitive relationship:

$$
k\uparrow
\quad\Rightarrow\quad
\text{coverage}\uparrow
\quad\Rightarrow\quad
\text{delay}\downarrow
$$

generally.

---

# 13. But there's another important lesson

Look at:

```text
k=1 → BeliefUCB 27.4%
k=2 → BeliefUCB 54.9%
k=3 → BeliefUCB 68.2%
```

Notice that going from:

```text
1 → 2
```

gives:

$$
+27.5\text{ pp}
$$

while:

```text
2 → 3
```

gives only:

$$
+13.3\text{ pp}
$$

That's **diminishing returns**.

Why?

Because once you're already scanning multiple high-value bands, adding another channel gives less additional coverage.

Eventually, if:

$$
k=8
$$

you could scan every band and there would be little room for scheduling intelligence to improve interception.

This is a fundamental trade-off:

```text
More hardware capacity
        ↓
Less need for sophisticated scheduling
```

versus:

```text
Limited hardware capacity
        ↓
Scheduling intelligence becomes much more valuable
```

---

# 14. And this sets up V3 perfectly

V2 answers:

> **Which bands should I scan?**

V3 asks a deeper question:

> **Can I predict WHEN a band will become active?**

Suppose we observe:

```text
Band 5:

t=100  ON
t=112  ON
t=124  ON
t=136  ON
```

The scheduler can infer:

$$
PRI\approx12
$$

Then:

```text
next predicted pulse
        ↓
t = 148
```

Instead of merely thinking:

> "Band 5 is good."

it can think:

> **"Band 5 is likely to be good around t=148."**

That's the transition:

```text
V1
Learning transitions
      ↓
V2
Learning + UCB + multiple channels
      ↓
V3
Learning + UCB + PRI prediction
      ↓
V4
Persistent characterization to make PRI lock-on reliable
```

And **that's why I wanted you to run these in sequence**. We're watching the research idea evolve rather than treating the 18 scripts as unrelated programs.

---

## Next

Now run:

```powershell
python scan_scheduler_v3_pri.py
```

Paste its **entire output** here.

This one is particularly important because we'll see the first actual **PRI-aware scheduler** in action, and I'll show you exactly how its output connects to the `_update_pri_model()`, confidence, periodicity score, and `switch_lead_steps` code we already studied.

## Prompt:
9/10/2026, 8:40:31 PM

Scenario: 8 bands, 4000 steps, 4 concurrent emitters (2 Markov comms, 1 periodic beacon [bands 2,5,6 -- true period 12 steps], 1 frequency-agile threat)

--- k_channels = 1 ---
Scheduler                                  |  Interception % |  Avg Reward/step |  Avg Intercept Delay
------------------------------------------------------------------------------------------------------
RoundRobin (open-loop baseline)            |           12.8% |            0.260 |                 1.48
BeliefUCB (Markov-only, learned)           |           28.7% |            0.586 |                 1.46
PRIAware (Markov + periodicity, learned)   |           24.9% |            0.499 |                 1.06

--- k_channels = 2 ---
Scheduler                                  |  Interception % |  Avg Reward/step |  Avg Intercept Delay
------------------------------------------------------------------------------------------------------
RoundRobin (open-loop baseline)            |           25.1% |            0.452 |                  1.4
BeliefUCB (Markov-only, learned)           |           53.5% |            0.895 |                  0.9
PRIAware (Markov + periodicity, learned)   |           54.2% |            0.892 |                 0.87

PRI diagnostic (true beacon period = 12 steps, on bands 2/5/6):
  band 2 (beacon):        not enough hits observed yet
  band 5 (beacon):        not enough hits observed yet
  band 6 (beacon):        not enough hits observed yet
  band 1 (comm/agile):    not enough hits observed yet
  band 4 (comm/agile):    not enough hits observed yet
  band 0 (comm/agile):    not enough hits observed yet
  band 3 (comm/agile):    not enough hits observed yet
  band 7 (comm/agile):    not enough hits observed yet
====================================================================================================
Sparse scenario: 8 bands, 4000 steps (800-step warmup) -- a single-pulse-per-cycle fixed-PRI radar (band 5, true period 12 steps, ON for just 1 step per cycle) alongside 2 Markov comms + 1 agile threat

--- k_channels = 1 ---
Scheduler                                  |  Interception % |  Avg Reward/step |  Avg Intercept Delay
------------------------------------------------------------------------------------------------------
RoundRobin (open-loop baseline)            |           11.8% |            0.135 |                 1.37
BeliefUCB (Markov-only, learned)           |           35.6% |            0.434 |                 0.89
PRIAware (Markov + periodicity, learned)   |           37.1% |            0.450 |                 0.53

--- k_channels = 2 ---
Scheduler                                  |  Interception % |  Avg Reward/step |  Avg Intercept Delay
------------------------------------------------------------------------------------------------------
RoundRobin (open-loop baseline)            |           23.2% |            0.256 |                 0.76
BeliefUCB (Markov-only, learned)           |           50.4% |            0.513 |                  0.4
PRIAware (Markov + periodicity, learned)   |           52.5% |            0.514 |                  0.3

The blended interception % above can be misleading here -- it's dominated by
the loud, near-always-on comm-1 channel. What actually matters for an EW system
is PER-EMITTER capture, especially of the one threat that's genuinely hard to
predict without a periodicity model:

  BeliefUCB : fixed-PRI radar caught    0/267 (  0.0%)   comm-1 caught  876/1005 ( 87.2%)   [band5 estimated PRI=None, confidence=0.00]
  PRIAware  : fixed-PRI radar caught  267/267 (100.0%)   comm-1 caught  794/1005 ( 79.0%)   [band5 estimated PRI=12.0, confidence=1.00]

## Response:
9/10/2026, 8:40:34 PM

**Excellent. V3 is working, and this output is probably the most important one so far.**

This is where the project stops being merely "learn which bands are active" and starts demonstrating the actual **periodicity/PRI idea**.

There are really **two experiments** in this output:

1. **Normal beacon scenario** — periodic emitter is relatively easy to observe.
2. **Sparse radar scenario** — one pulse every 12 steps, only 1 step wide. This is the difficult case that motivates V4.

Let's go through it carefully.

---

# 1. V3's architecture

V3 now has three schedulers:

```text
RoundRobin
    ↓
open-loop

BeliefUCB
    ↓
Markov learning

PRIAware
    ↓
Markov learning
+
periodicity/PRI learning
```

So conceptually:

```text
                         Scheduler
                            │
             ┌──────────────┴──────────────┐
             │                             │
       Markov behaviour              Periodic behaviour
             │                             │
        "Is band likely ON?"        "When will band be ON?"
             │                             │
             └──────────────┬──────────────┘
                            ↓
                        PRIAware
```

---

# 2. Normal beacon scenario

Your first result is:

```text
true beacon period = 12 steps
beacon bands = 2, 5, 6
```

The periodic beacon is ON for several steps because the V3 beacon has dwell 4.

So this isn't the hardest possible periodic signal.

---

## k = 1

You got:

| Scheduler | Interception | Reward | Delay |
|---|---:|---:|---:|
| RoundRobin | 12.8% | 0.260 | 1.48 |
| BeliefUCB | **28.7%** | **0.586** | 1.46 |
| PRIAware | 24.9% | 0.499 | **1.06** |

Interesting result:

> **PRIAware has lower interception than BeliefUCB at k=1, but substantially lower delay.**

That's already telling us something about what PRIAware is doing.

---

# 3. Why does PRIAware have lower delay?

Suppose PRIAware discovers something like:

```text
t = 100 → beacon ON
t = 112 → beacon ON
t = 124 → beacon ON
t = 136 → beacon ON
```

It can infer:

$$
PRI \approx 12
$$

Then it doesn't merely say:

> "Band 2 is interesting."

It says:

> "Band 2 is likely to become interesting around a predictable time."

That's fundamentally different.

Its periodicity score is based on how close the current timestep is to the predicted pulse.

So when the predicted time approaches:

```text
predicted pulse
       ↓
      148
```

the band's score increases.

The scheduler can then jump toward it.

That explains the particularly good:

$$
\boxed{1.06}
$$

average intercept delay.

---

# 4. But why doesn't PRIAware win interception at k=1?

This is an important lesson.

**Prediction isn't automatically better than a good Markov strategy.**

PRIAware has to allocate its one available channel among:

```text
band 1
band 4
beacon bands 2,5,6
agile threat bands 0,3,6,7
```

If it becomes too interested in periodic bands, it can spend scanning opportunities on them that BeliefUCB would have used on productive Markov communication bands.

So:

```text
PRIAware
    ↓
better timing
    ↓
lower delay

but

periodic focus
    ↓
fewer opportunities for other emitters
    ↓
lower total interception
```

That's an important trade-off.

---

# 5. k = 2 changes the picture

You got:

```text
RoundRobin    25.1%
BeliefUCB     53.5%
PRIAware      54.2%
```

Now PRIAware wins:

$$
54.2\% > 53.5\%
$$

although only by:

$$
0.7
$$

percentage points.

Why?

Because with two channels it can hedge its bets.

For example:

```text
Channel 1 → communication band
Channel 2 → predicted periodic band
```

Instead of having to choose one or the other.

This is exactly why `k_channels` matters.

---

# 6. Now the weird-looking PRI diagnostic

You have:

```text
band 2: not enough hits observed yet
band 5: not enough hits observed yet
band 6: not enough hits observed yet
...
```

At first glance you might think:

> "Wait! PRIAware just performed well. Why does it say it didn't learn PRI?"

This is an extremely important distinction.

### Performance

The scheduler can still use:

- Markov belief
- UCB
- recent observations
- priority
- whatever periodic information it has accumulated during execution

### Final diagnostic

The diagnostic is asking whether the scheduler's **final stored PRI model** meets its minimum requirements.

The V3 PRI model requires enough observed hits—specifically, **at least 8 hits**—before fitting a PRI.

So:

```text
observations < 8
        ↓
no reliable PRI model
        ↓
PRI = None
```

That does **not** mean the scheduler never scanned those bands.

It means it never accumulated enough qualifying observations for its explicit PRI estimator.

---

# 7. This is exactly the weakness that the sparse experiment exposes

Now look at your second scenario.

```text
Sparse scenario
8 bands
4000 steps
800-step warmup

Radar:
band 5
PRI = 12 steps
pulse width = 1 step
```

This is much harder.

The radar looks like:

```text
t:       0 1 2 3 4 5 6 7 8 9 10 11 12 13 ...
radar:   X . . . . . . . . .  .  .  X  .  ...
```

Only **one timestep every 12** contains a pulse.

So its duty cycle is approximately:

$$
\frac{1}{12}\approx8.33\%
$$

That's tiny.

Compare that with a communication emitter that can remain ON for many consecutive steps.

---

# 8. Sparse scenario, k = 1

Your results:

```text
RoundRobin     11.8%
BeliefUCB      35.6%
PRIAware       37.1%
```

So PRIAware looks only slightly better:

$$
37.1-35.6=1.5
$$

percentage points.

If we looked only at this table, we'd conclude:

> "PRI awareness gives a tiny improvement."

**That conclusion would be wrong for this experiment.**

And the program itself tells us why:

> "The blended interception % above can be misleading here."

This is one of the most important lines in the entire project.

---

# 9. Why blended interception is misleading

There is a very loud communication emitter.

You have:

```text
comm-1
```

which is active extremely frequently.

Meanwhile:

```text
radar
```

is active only:

$$
1/12
$$

of the time.

Therefore, aggregate interception is dominated by the easy communication target.

Imagine:

```text
Emitter A — 1000 opportunities
Emitter B — 267 opportunities
```

If your scheduler catches:

```text
Emitter A: 870
Emitter B: 0
```

the aggregate result can still look pretty good.

But from an EW perspective, that's potentially terrible.

Why?

Because the hard-to-detect threat is precisely the one you're missing.

So the experiment correctly switches to:

> **PER-EMITTER capture**

---

# 10. And now we reach the killer result

Your output says:

```text
BeliefUCB:
fixed-PRI radar caught 0/267 (0.0%)
comm-1 caught 876/1005 (87.2%)
```

while:

```text
PRIAware:
fixed-PRI radar caught 267/267 (100.0%)
comm-1 caught 794/1005 (79.0%)
```

This is the real V3 result.

---

# 11. BeliefUCB's problem

BeliefUCB sees:

```text
Band 5:

OFF
OFF
OFF
OFF
OFF
OFF
OFF
OFF
OFF
OFF
OFF
OFF
ON
...
```

From a Markov perspective, this band looks terrible.

It is almost always OFF.

So why keep scanning it?

BeliefUCB learns:

> "Band 5 isn't productive."

Therefore it eventually spends very little effort there.

The radar pulses continue:

```text
        ↓             ↓             ↓
...----X-------------X-------------X----...
      12 steps       12 steps       12 steps
```

and BeliefUCB misses every single one.

Result:

$$
\boxed{0/267=0\%}
$$

---

# 12. PRIAware sees something BeliefUCB doesn't

PRIAware can notice:

```text
hit
 ↓
12 steps
 ↓
hit
 ↓
12 steps
 ↓
hit
```

and infer:

$$
\boxed{PRI=12}
$$

Then it can predict the next pulse.

And your output confirms it:

```text
band5 estimated PRI = 12.0
confidence = 1.00
```

That's a perfect lock in this run.

---

# 13. Why confidence = 1.00?

The observed pulse times fit the estimated period extremely well.

Remember the confidence calculation we studied:

$$
\text{confidence}
=
1-
\frac{\text{RMSE}}
{\text{confidenceScale}\times PRI}
$$

with clipping to:

$$
[0,1].
$$

If the observations are almost exactly:

```text
12
12
12
12
12
...
```

then:

$$
RMSE\approx0
$$

so:

$$
confidence\approx1.
$$

Hence:

```text
PRI = 12.0
confidence = 1.00
```

---

# 14. The trade-off is fascinating

Compare:

### BeliefUCB

```text
Radar:  0.0%
Comm:  87.2%
```

### PRIAware

```text
Radar:  100.0%
Comm:   79.0%
```

PRIAware sacrificed:

$$
87.2-79.0=8.2
$$

percentage points of communication capture.

But it gained:

$$
100-0=\boxed{100}
$$

percentage points of radar capture.

For an EW-style objective, that can be an extremely favorable trade.

---

# 15. This is the key research idea

We can now summarize the evolution:

### V1

```text
Can learning help?

BeliefScheduler
        ↓
YES
```

### V2

```text
Can learning work with multiple simultaneous channels?

BeliefUCB
        ↓
YES
```

### V3

```text
Can we exploit periodic emitters?

PRIAware
        ↓
YES
```

But then we discover:

```text
PRI detection
      ↓
requires enough observations
      ↓
sparse radar may provide too few observations
      ↓
seed-sensitive lock-on
```

And **that is why V4 exists.**

---

# 16. The mathematical problem behind the V4 motivation

During the 800-step warmup:

$$
800/12\approx66.67
$$

radar pulses exist in the environment.

But the scheduler doesn't scan band 5 continuously.

If it scans band 5 roughly 100 times during warmup, then expected captured pulses are approximately:

$$
100\times\frac1{12}
\approx8.33
$$

That's almost exactly the PRI estimator's threshold:

$$
\boxed{8\text{ hits}}
$$

So we're sitting right on the boundary:

```text
Expected ≈ 8.33
       ↓
Some seeds → 8+ hits → PRI lock
Some seeds → <8 hits → NO LOCK
```

That means tiny random differences can completely change the outcome.

And that's exactly what we discovered in `diagnose_pri_lockon.py`.

---

# 17. So V3 has revealed a chicken-and-egg problem

This is probably the most important conceptual point to understand.

To learn PRI:

```text
Need ≥ 8 observations
```

To obtain observations:

```text
Need to scan radar band
```

But to decide to scan radar band:

```text
Scheduler wants evidence that band is valuable
```

But before PRI detection:

```text
Radar appears almost always OFF
```

So:

```text
             Need scans
                ↑
                │
          Need observations
                ↑
                │
             Need PRI
                ↑
                │
          Need scans again
```

That's the **lock-on problem**.

---

# 18. And now you know exactly why V4 was written

V4 introduces the persistent characterization bonus.

Its philosophy is:

> "If I haven't characterized this band yet, give it some temporary incentive to investigate it."

Conceptually:

```text
Unknown band
     ↓
characterization bonus
     ↓
more scans
     ↓
more observations
     ↓
enough hits
     ↓
PRI estimation
     ↓
high confidence
     ↓
predict future pulses
```

But we then discovered that this bonus needs **two safeguards**:

### Safeguard 1

Stop characterization once enough hits have been obtained.

Otherwise:

```text
aperiodic band
    ↓
never reaches confidence
    ↓
bonus never disappears
    ↓
scheduler keeps chasing it forever
```

### Safeguard 2

Give up after too many scan attempts.

Otherwise a completely silent band can consume the entire scanning budget.

That's why V4 has:

```python
required_hits = 8
```

and:

```python
give_up_after_scans = 300
```

---

# 19. The entire project now makes much more sense

You can think of the four versions as this:

```text
V1
│
├── Markov emitters
├── learned belief
└── basic scheduler
        │
        ▼
V2
│
├── UCB exploration
├── multiple channels
├── dwell
└── switch cost
        │
        ▼
V3
│
├── PRI estimation
├── periodicity score
├── confidence
└── prediction
        │
        ▼
V4
│
├── persistent characterization
├── required-hit bound
└── maximum-attempt bound
```

And your V3 output has now demonstrated the reason for every major addition.

---

# 20. One subtle thing I want you to remember

Don't say:

> **"PRIAware is better than BeliefUCB."**

That's too broad.

The actual result is more nuanced:

> **PRIAware provides a major advantage for sparse, predictable, low-duty-cycle emitters because it can exploit temporal structure that Markov-only learning cannot capture, but this advantage can come at the cost of reduced capture of other emitters.**

Your numbers demonstrate this beautifully:

$$
\boxed{\text{Radar: }0\%\rightarrow100\%}
$$

while:

$$
\boxed{\text{Comm-1: }87.2\%\rightarrow79.0\%}
$$

That's much more scientifically meaningful than simply saying "PRIAware got 37.1% versus BeliefUCB's 35.6%."

---

## Next: V4

Now we're ready for:

```powershell
python scan_scheduler_v4_persistent.py
```

**This one should be especially satisfying**, because we've just watched V3 expose its weakness experimentally. V4 is the attempted engineering fix for exactly that weakness.

When you run it, paste the output here. Then we'll compare **V3 vs V4** and, most importantly, see whether the persistent characterization bonus actually solves the seed-sensitive radar lock-on problem.

## Prompt:
9/10/2026, 9:02:06 PM

Quick single-seed sanity check (seed=11, matches earlier reports):

Scheduler                        |  Interception % |  Avg Reward/step
---------------------------------------------------------------------
BeliefUCB (Markov-only)          |           33.2% |            0.375
PRIAware (original)              |           36.0% |            0.406
PRIAware (persistent, fixed)     |           34.3% |            0.388

## Response:
9/10/2026, 9:02:09 PM

Yep — **V4 is executing correctly.** And this particular output is a good illustration of why we don't judge the fix from one seed.

Your result:

| Scheduler | Interception | Avg Reward/step |
|---|---:|---:|
| BeliefUCB | 33.2% | 0.375 |
| PRIAware original | **36.0%** | **0.406** |
| Persistent PRIAware | 34.3% | 0.388 |

### What this single seed says

For **seed 11**:

$$
\text{Original PRIAware} > \text{Persistent PRIAware} > \text{BeliefUCB}
$$

So V4's persistent characterization mechanism **does not improve the aggregate interception percentage in this particular run**.

That's not a contradiction with what V4 was designed to fix.

The V4 question is more specific:

> **Does persistent characterization make PRI lock-on more reliable across different random seeds?**

A single seed can't answer that.

In fact, remember what we found earlier: sparse-radar PRIAware is highly seed-sensitive. One seed can happen to give the original scheduler enough radar observations to lock on, while another seed can fail.

So this:

```text
seed 11

Original PRIAware       36.0%
Persistent PRIAware     34.3%
```

does **not** mean:

```text
V4 is worse.
```

It means:

```text
For this particular stochastic trajectory,
original PRIAware happened to perform better.
```

---

## The experiment we actually care about

That's why `multi_seed_robustness.py` and the later validation scripts exist.

We want something like:

```text
Seed     Original     Persistent
---------------------------------
1          ?             ?
2          ?             ?
3          ?             ?
...
40         ?             ?
```

Then ask:

### Radar capture

Does V4 change:

$$
0\%-100\%
$$

seed-to-seed chaos into something like:

$$
\approx93\%
$$

consistently?

That's the real test.

And we already saw from the project's multi-seed results that this is exactly where V4 showed its strength: **radar capture became dramatically higher and less variable**, although it traded away some capture of the easier communication emitter.

---

# One more thing: notice the reward

Same ordering:

```text
Original PRIAware       0.406
Persistent PRIAware    0.388
BeliefUCB               0.375
```

So for seed 11, both headline metrics agree:

```text
Original > Persistent > BeliefUCB
```

Again, perfectly plausible.

---

# Now let's move to the real evidence

Run:

```powershell
python multi_seed_robustness.py
```

That is the experiment I want you to run next.

It will take longer than the individual scripts because it executes many combinations over multiple seeds.

**Don't worry if it produces a lot of output.**

When it finishes, paste the output here.

Then we'll examine:

1. **Suite A** — does learning beat open-loop scanning?
2. **Suite B** — how does performance scale with `k`?
3. **Suite C** — beacon behavior
4. **Suite D** — sparse radar and per-emitter capture
5. **Suite F** — **original PRIAware vs Persistent PRIAware**
6. The generated `multi_seed_results.csv`

That's where we stop asking *"does it work on seed 11?"* and start asking **"does the claimed improvement survive repeated experiments?"**

## Prompt:
9/10/2026, 9:07:27 PM

Quick single-seed sanity check (seed=11, matches earlier reports): 
 
Scheduler                        |  Interception % |  Avg Reward/step 
--------------------------------------------------------------------- 
BeliefUCB (Markov-only)          |           33.2% |            0.375 
PRIAware (original)              |           36.0% |            0.406 
PRIAware (persistent, fixed)     |           34.3% |            0.388 
(.venv) PS D:\Code\SIH\SIH> python multi_seed_robustness.py 
Running every comparison across 10 seeds: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10] 
 
==================================================================================================== 
 
[A] Original prototype, single-channel, 10 seeds (4000 steps each) 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
RoundRobin (open-loop)                     |    25.7% +/-  0.5%   |   24.9% |   26.6% 
Random (naive)                             |    25.5% +/-  0.6%   |   24.5% |   26.3% 
BeliefScheduler (learned)                  |    52.2% +/-  2.7%   |   49.4% |   56.5% 
  BeliefScheduler vs RoundRobin                 : +26.5pp +/-  2.5pp   (min +23.4pp, max +30.6pp)  -- won in 10/10 seeds 
 
==================================================================================================== 
 
[B] Multi-channel (v2), k_channels=1, 10 seeds (4000 steps each) 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
RoundRobin (open-loop)                     |    12.5% +/-  0.2%   |   12.0% |   12.8% 
Random (naive)                             |    12.4% +/-  0.3%   |   12.0% |   12.9% 
BeliefUCB (learned)                        |    28.3% +/-  1.3%   |   25.4% |   29.7% 
  BeliefUCB vs RoundRobin                       : +15.7pp +/-  1.3pp   (min +12.9pp, max +17.4pp)  -- won in 10/10 seeds 
 
[B] Multi-channel (v2), k_channels=2, 10 seeds (4000 steps each) 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
RoundRobin (open-loop)                     |    25.1% +/-  0.2%   |   24.8% |   25.3% 
Random (naive)                             |    24.8% +/-  0.4%   |   24.3% |   25.6% 
BeliefUCB (learned)                        |    54.6% +/-  0.6%   |   53.2% |   55.2% 
  BeliefUCB vs RoundRobin                       : +29.5pp +/-  0.7pp   (min +28.1pp, max +30.3pp)  -- won in 10/10 seeds 
 
[B] Multi-channel (v2), k_channels=3, 10 seeds (4000 steps each) 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
RoundRobin (open-loop)                     |    37.5% +/-  0.2%   |   37.2% |   37.8% 
Random (naive)                             |    37.4% +/-  0.4%   |   36.8% |   38.1% 
BeliefUCB (learned)                        |    68.5% +/-  0.6%   |   67.5% |   69.3% 
  BeliefUCB vs RoundRobin                       : +31.1pp +/-  0.6pp   (min +30.0pp, max +32.0pp)  -- won in 10/10 seeds 
 
==================================================================================================== 
 
[C] Beacon scenario (v3), k_channels=1, 10 seeds (4000 steps each) 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
RoundRobin (open-loop)                     |    12.5% +/-  0.2%   |   12.0% |   12.8% 
BeliefUCB (Markov-only)                    |    27.7% +/-  1.0%   |   26.4% |   29.2% 
PRIAware (Markov+periodicity)              |    27.3% +/-  1.5%   |   24.9% |   28.8% 
  PRIAware vs BeliefUCB                         :  -0.5pp +/-  1.9pp   (min  -3.8pp, max  +2.3pp)  -- won in 4/10 seeds 
 
[C] Beacon scenario (v3), k_channels=2, 10 seeds (4000 steps each) 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
RoundRobin (open-loop)                     |    25.1% +/-  0.2%   |   24.8% |   25.3% 
BeliefUCB (Markov-only)                    |    54.4% +/-  0.7%   |   53.5% |   55.4% 
PRIAware (Markov+periodicity)              |    53.9% +/-  1.0%   |   51.9% |   54.9% 
  PRIAware vs BeliefUCB                         :  -0.5pp +/-  1.2pp   (min  -2.2pp, max  +1.1pp)  -- won in 4/10 seeds 
 
==================================================================================================== 
 
[D] Sparse fixed-PRI radar (v3), k_channels=1, 10 seeds, 800-step warmup (4000 steps each) 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
RoundRobin (open-loop)                     |    11.7% +/-  0.4%   |   10.7% |   12.2% 
BeliefUCB (Markov-only)                    |    32.5% +/-  0.8%   |   31.4% |   33.9% 
PRIAware (Markov+periodicity)              |    33.9% +/-  3.0%   |   29.4% |   37.5% 
  PRIAware vs BeliefUCB (blended %)             :  +1.3pp +/-  3.3pp   (min  -4.1pp, max  +5.2pp)  -- won in 7/10 seeds 
 
[D] Sparse fixed-PRI radar (v3), k_channels=2, 10 seeds, 800-step warmup (4000 steps each) 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
RoundRobin (open-loop)                     |    23.3% +/-  0.3%   |   22.8% |   23.8% 
BeliefUCB (Markov-only)                    |    47.7% +/-  1.0%   |   46.4% |   49.7% 
PRIAware (Markov+periodicity)              |    52.3% +/-  0.8%   |   51.1% |   53.9% 
  PRIAware vs BeliefUCB (blended %)             :  +4.6pp +/-  1.3pp   (min  +2.3pp, max  +6.0pp)  -- won in 10/10 seeds 
 
[D] Per-emitter capture, k_channels=1, 10 seeds, 800-step warmup -- the metric that actually matters (blended % hides this) 
 
  Fixed-PRI radar (band 5) capture rate 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
BeliefUCB                                  |     0.3% +/-  0.8%   |    0.0% |    2.6% 
PRIAware                                   |    30.0% +/- 48.3%   |    0.0% |  100.0% 
 
  Comm-1 (band 1) capture rate 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
BeliefUCB                                  |    86.9% +/-  2.4%   |   82.3% |   90.0% 
PRIAware                                   |    83.1% +/-  7.2%   |   68.2% |   89.6% 
  PRIAware vs BeliefUCB on radar capture        : +29.7pp +/- 47.9pp   (min  +0.0pp, max +100.0pp)  -- won in 3/10 seeds 
  PRIAware vs BeliefUCB on comm-1 capture (expected cost):  -3.9pp +/-  6.2pp   (min -18.2pp, max  +0.3pp)  -- won in 1/10 seeds 
 
==================================================================================================== 
 
[E] Turing synthetic PDW stand-in, k_channels=1, dwell=200.0us, 10 seeds (each seed = a different synthetic pulse stream) 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
RoundRobin (open-loop)                     |    12.4% +/-  0.2%   |   12.1% |   12.8% 
Random (naive)                             |    12.5% +/-  0.2%   |   12.2% |   12.8% 
BeliefUCB (Markov+UCB)                     |    26.4% +/-  0.2%   |   26.2% |   26.7% 
PRIAware (Markov+periodicity)              |    26.5% +/-  0.1%   |   26.3% |   26.7% 
  BeliefUCB vs RoundRobin                       : +14.0pp +/-  0.2pp   (min +13.7pp, max +14.2pp)  -- won in 10/10 seeds 
  PRIAware vs BeliefUCB                         :  +0.0pp +/-  0.1pp   (min  -0.1pp, max  +0.2pp)  -- won in 2/10 seeds 
 
==================================================================================================== 
 
[F] Fix validation: PRIAware (original) vs Persistent (fixed), per-emitter capture, 10 seeds, 800-step warmup 
 
  Fixed-PRI radar (band 5) capture rate 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
PRIAware (original)                        |    30.0% +/- 48.3%   |    0.0% |  100.0% 
Persistent (fixed)                         |    93.3% +/-  0.9%   |   90.6% |   93.6% 
 
  Comm-1 (band 1) capture rate 
Scheduler                                  |     mean +/- stdev |      min |      max 
------------------------------------------------------------------------------------- 
PRIAware (original)                        |    83.1% +/-  7.2%   |   68.2% |   89.6% 
Persistent (fixed)                         |    70.1% +/-  9.0%   |   54.1% |   79.4% 
  Seeds with radar capture > 50%: original 3/10, fixed 10/10 
 
==================================================================================================== 
 
Raw per-seed results written to multi_seed_results.csv 
 
BOTTOM LINE: every 'X beats Y' delta above reports how many of the 10 seeds the win held in. A delta whose mean is well clear of 0 relative to its stdev, and that wins in most/all seeds, is a robust effect rather than a seed-lottery artifact.

## Response:
9/10/2026, 9:07:31 PM

**Perfect. This is exactly the experiment we needed.** You have now reproduced the project's main multi-seed evidence successfully.

And this output lets us make a much stronger conclusion than the single-seed V4 test.

---

# 1. The first major result: learning works

Suite A:

| Scheduler | Mean interception | Std. dev. |
|---|---:|---:|
| RoundRobin | 25.7% | 0.5% |
| Random | 25.5% | 0.6% |
| **BeliefScheduler** | **52.2%** | 2.7% |

BeliefScheduler beats RoundRobin by:

$$
52.2-25.7=\boxed{26.5\text{ percentage points}}
$$

And it wins:

$$
\boxed{10/10\text{ seeds}}
$$

This is strong evidence that the V1 learning mechanism isn't benefiting from one lucky random seed.

So our first hypothesis survives:

> **Learning the environment's temporal behavior substantially improves interception over open-loop scanning.**

---

# 2. V2: multiple channels help everyone, but learning helps even more

### k = 1

```text
RoundRobin  12.5%
BeliefUCB   28.3%
```

Advantage:

$$
\boxed{+15.7\text{ pp}}
$$

and:

```text
10/10 seeds won
```

### k = 2

```text
RoundRobin  25.1%
BeliefUCB   54.6%
```

Advantage:

$$
\boxed{+29.5\text{ pp}}
$$

### k = 3

```text
RoundRobin  37.5%
BeliefUCB   68.5%
```

Advantage:

$$
\boxed{+31.1\text{ pp}}
$$

And BeliefUCB wins **10/10 seeds at every k**.

That's very strong.

---

# 3. Notice the diminishing returns

BeliefUCB:

```text
k=1 → 28.3%
k=2 → 54.6%
k=3 → 68.5%
```

The increases are:

$$
28.3\rightarrow54.6 = +26.3\text{ pp}
$$

then:

$$
54.6\rightarrow68.5 = +13.9\text{ pp}
$$

So doubling capacity from 1 → 2 produces a huge improvement, but another channel gives a smaller incremental benefit.

That's the same trend we saw in your single run, now confirmed across 10 seeds.

---

# 4. Now comes the surprising result: Beacon PRIAware

Suite C:

### k = 1

```text
BeliefUCB  27.7%
PRIAware   27.3%
```

Difference:

$$
\boxed{-0.5\text{ pp}}
$$

PRIAware wins only:

```text
4/10 seeds
```

### k = 2

```text
BeliefUCB  54.4%
PRIAware   53.9%
```

Again:

$$
\boxed{-0.5\text{ pp}}
$$

and again:

```text
4/10 seeds
```

So here's an important correction to what we might have guessed from the earlier single run.

**For the beacon scenario, adding PRI awareness does not improve aggregate interception on average.**

In fact, it slightly hurts it.

---

# 5. Why is that not necessarily a failure?

Because V3 isn't designed merely to maximize:

```text
aggregate interception %
```

It's designed to exploit **temporal predictability**, especially for sparse periodic emitters.

And Suite D demonstrates why aggregate interception can hide the interesting behavior.

---

# 6. Sparse radar: aggregate metric

At k=1:

```text
BeliefUCB  32.5%
PRIAware   33.9%
```

PRIAware advantage:

$$
\boxed{+1.3\text{ pp}}
$$

But variability is:

```text
PRIAware ± 3.0%
```

versus:

```text
BeliefUCB ± 0.8%
```

That's our first warning sign.

PRIAware is much less stable.

It wins:

```text
7/10
```

but loses 3.

---

# 7. k = 2 looks much better

```text
BeliefUCB  47.7%
PRIAware   52.3%
```

Difference:

$$
\boxed{+4.6\text{ pp}}
$$

and:

$$
\boxed{10/10\text{ seeds}}
$$

So at the aggregate level, PRIAware looks quite good here.

But then we get to the **real metric**.

---

# 8. Per-emitter capture completely changes the story

This is arguably the most important table in the entire output.

## Fixed-PRI radar

BeliefUCB:

$$
0.3\%\pm0.8\%
$$

PRIAware:

$$
30.0\%\pm48.3\%
$$

That enormous standard deviation is screaming:

> **Seed sensitivity.**

Look at the range:

```text
PRIAware:
min = 0%
max = 100%
```

That's not a stable radar detector.

It's essentially:

```text
some seeds → perfect lock
some seeds → complete failure
```

And:

$$
3/10
$$

seeds achieve >50% radar capture.

---

# 9. Why does BeliefUCB get almost zero radar?

This is exactly what we predicted.

The radar is:

```text
PRI = 12
pulse width = 1
```

Therefore it's active only about:

$$
\frac1{12}=8.33\%
$$

of the time.

BeliefUCB sees a band that's almost always silent.

So it learns:

> "This band isn't worth much scanning."

Consequently:

$$
\boxed{0.3\%\text{ radar capture}}
$$

---

# 10. PRIAware has discovered something extremely valuable

PRIAware sometimes recognizes:

```text
12
12
12
12
...
```

and concludes:

$$
PRI=12
$$

Then it can predict:

```text
next pulse
     ↓
scan band 5
     ↓
catch radar
```

When it successfully locks on, capture can reach:

$$
100\%.
$$

That's why the maximum is 100%.

---

# 11. But the standard deviation tells us the real problem

This is the key:

$$
30.0\%\pm48.3\%
$$

A mean of 30% sounds moderately useful.

But the distribution is actually something like:

```text
0%
0%
0%
100%
100%
100%
...
```

rather than:

```text
30%
29%
31%
30%
...
```

So **the mean is hiding instability**.

This is precisely why the project performs multi-seed validation.

---

# 12. What does PRIAware sacrifice?

Look at Comm-1.

BeliefUCB:

$$
86.9\%
$$

PRIAware:

$$
83.1\%
$$

Difference:

$$
83.1-86.9=\boxed{-3.9\text{ pp}}
$$

So PRIAware pays approximately 3.9 percentage points in communication capture on average.

That's the cost of spending some scanning budget pursuing periodic structure.

This is an explicit trade-off:

```text
PRIAware

      Radar capture
          ↑
          │
          │
          │
          ↓
      Comm capture
```

More attention to the rare predictable threat can mean less attention to the frequent communication emitter.

---

# 13. Now V4 finally gets its justification

Suite F:

### Radar

Original:

$$
30.0\%\pm48.3\%
$$

Persistent:

$$
93.3\%\pm0.9\%
$$

**That's enormous.**

The mean improvement is:

$$
93.3-30.0=\boxed{63.3\text{ pp}}
$$

And look at the ranges:

### Original

```text
0% → 100%
```

### Persistent

```text
90.6% → 93.6%
```

That's the real success of V4.

---

# 14. The most important number: lock-on success

```text
Original:   3/10 seeds >50% radar capture
Fixed:     10/10 seeds >50%
```

So V4 changes:

$$
\boxed{30\%\rightarrow100\%}
$$

seed-level success.

That's much more important than the single-seed result you ran earlier.

Remember that single seed:

```text
Original       36.0%
Persistent     34.3%
```

That looked like V4 was worse.

Now we understand why that was misleading.

Seed 11 simply wasn't sufficient to evaluate the fix.

---

# 15. But V4 isn't free

Here's the other side:

### Comm-1

Original:

$$
83.1\%
$$

Persistent:

$$
70.1\%
$$

Loss:

$$
83.1-70.1
=
\boxed{13.0\text{ pp}}
$$

So V4 greatly improves radar capture, but it does so by dedicating more scanning effort toward characterization.

That's a **real engineering trade-off**, not a bug.

---

# 16. This is actually a very good research result

You now have a coherent story:

### Problem 1 — Open-loop scanning

```text
RoundRobin ≈ 25%
BeliefScheduler ≈ 52%
```

Learning helps.

### Problem 2 — Limited receiver capacity

```text
k=1 → poor coverage
k=2 → much better
k=3 → better still
```

Multiple channels help.

### Problem 3 — Markov learning can't predict sparse periodic emitters

```text
BeliefUCB radar ≈ 0%
```

It treats the mostly-silent radar as unproductive.

### Problem 4 — PRI awareness can solve this

```text
PRIAware radar → sometimes 100%
```

But...

### Problem 5 — PRI lock-on is seed-sensitive

```text
0% ↔ 100%
```

### Problem 6 — Persistent characterization fixes lock-on reliability

```text
30% ± 48.3%
        ↓
93.3% ± 0.9%
```

But:

```text
Comm capture
83.1%
   ↓
70.1%
```

So the final system makes an explicit **rare-threat detection vs common-emitter coverage trade-off**.

---

# 17. And now I want you to notice something about scientific methodology

The project is doing something very good here.

It doesn't stop at:

> "PRIAware got 37.1%, therefore PRIAware is better."

Instead it asks:

```text
Does result survive multiple seeds?
             ↓
Is aggregate metric appropriate?
             ↓
Does per-emitter performance tell
a different story?
             ↓
Is improvement actually reliable?
             ↓
What does fix cost?
```

That's why you see:

```text
mean
stdev
min
max
win count
per-emitter capture
```

rather than one percentage.

---

# 18. Your generated CSV is now important

The script says:

```text
Raw per-seed results written to multi_seed_results.csv
```

So your execution has generated/overwritten:

```text
multi_seed_results.csv
```

That file contains the individual seed results behind these averages.

**Don't delete it.**

We're going to use it to understand how these means were constructed.

---

# 19. Where we are now

You've successfully reproduced:

```text
                    ✓ V1
                    ✓ V2
                    ✓ V3
                    ✓ V4
                    ✓ Multi-seed validation
```

So far, we've experimentally established:

```text
Open-loop
    ↓
Learning
    ↓
UCB exploration
    ↓
Multiple channels
    ↓
PRI prediction
    ↓
Persistent characterization
```

The next stage is particularly interesting because now we're going to start examining the **individual fixes** rather than the entire scheduler versions.

---

## Next experiment: `validate_offbyone_fix.py`

Run:

```powershell
python validate_offbyone_fix.py
```

This tests one very specific modification:

> **Adding ±1 integer neighbors to the candidate PRI set.**

We'll compare:

```text
Pre-fix
    ↓
Plateau fix
    ↓
Off-by-one/harmonic fix
```

and figure out **why a PRI that should be, say, 32.5 steps can be missed by a candidate search that only considers integer periods**.

That'll take us into one of the more subtle pieces of the project: **harmonics, fractional PRI estimates, and why candidate generation matters even when the fitting code itself is correct.**

## Prompt:
9/10/2026, 9:20:17 PM

Off-by-one-fix confirmation, beacon scenario, identical-environment methodology, 30 seeds (1..30), k=1 and k=2.

--- k=1 ---
Scheduler                        |    mean |  stdev |    min |    max
-----------------------------------------------------------------
BeliefUCB                        |   27.9% |   1.3% |  25.5% |  30.4%
PreOffByOneFix (session start)   |   27.8% |   1.6% |  24.9% |  31.5%
Current (with off-by-one fix)    |   27.9% |   1.7% |  24.9% |  31.5%
  Current vs PreOffByOneFix (this session's fix, isolated)  :  +0.1pp +/-  0.6pp  -- won 1/30
  Current vs BeliefUCB (net vs baseline)                    :  +0.0pp +/-  1.8pp  -- won 16/30

--- k=2 ---
Scheduler                        |    mean |  stdev |    min |    max
-----------------------------------------------------------------
BeliefUCB                        |   54.4% |   0.8% |  52.3% |  55.8%
PreOffByOneFix (session start)   |   53.4% |   1.5% |  48.6% |  55.8%
Current (with off-by-one fix)    |   53.4% |   1.5% |  48.6% |  55.8%
  Current vs PreOffByOneFix (this session's fix, isolated)  :  +0.0pp +/-  0.1pp  -- won 1/30
  Current vs BeliefUCB (net vs baseline)                    :  -1.0pp +/-  1.6pp  -- won 5/30

## Response:
9/10/2026, 9:20:21 PM

Yep. This output **confirms something important about the off-by-one fix: it is not responsible for the beacon-performance difference you were investigating.**

### What this experiment proves

You used:

- **Beacon scenario**
- **Identical environment** for each scheduler/seed
- **30 seeds (1–30)**
- **k = 1 and k = 2**
- `PreOffByOneFix` = everything up to the previous version, **without** `±1` candidate expansion
- `Current` = same scheduler logic, **with** `±1` expansion

That is exactly the right isolation methodology.

---

## k = 1

| Scheduler | Mean | Stdev |
|---|---:|---:|
| BeliefUCB | 27.9% | 1.3% |
| Pre-fix | 27.8% | 1.6% |
| Current | 27.9% | 1.7% |

The isolated difference:

> **Current − Pre-fix = +0.1 percentage points ± 0.6 pp**

That's tiny.

And:

> **Current won only 1/30 seeds.**

So adding `±1` neighbors to the PRI candidate pool **does not materially improve beacon interception at k=1**.

---

## k = 2

| Scheduler | Mean | Stdev |
|---|---:|---:|
| BeliefUCB | 54.4% | 0.8% |
| Pre-fix | 53.4% | 1.5% |
| Current | 53.4% | 1.5% |

The isolated difference:

> **Current − Pre-fix = +0.0 pp ± 0.1 pp**

Again:

> **1/30 wins.**

So at k=2, the off-by-one fix has essentially **zero effect** on this beacon scenario.

---

# Why this happens

The `±1` fix was aimed at a particular PRI-estimation problem.

Suppose true PRI in scheduler time units is something like:

$$
PRI \approx 32.5
$$

but candidate generation only produces coarse integer candidates:

$$
32,\;33
$$

The fix adds neighboring integer candidates around the values already generated, allowing the later least-squares refinement process to reach a better fractional estimate.

So the fix is mainly about:

**candidate coverage → better PRI fitting → better lock-on**

It isn't a general-purpose interception boost.

The beacon scenario has a different characteristic:

- beacon has a relatively frequent period,
- multiple beacon bands exist,
- Markov/UCB already provides substantial interception,
- and the aggregate metric counts **all active band-time pairs**, not merely successful PRI radar capture.

Therefore, improving a PRI candidate by ±1 isn't necessarily going to change the scheduler's final band choices enough to move aggregate interception.

---

# More importantly: this isolates the previous fixes

Your experiments now give us a much clearer progression.

### Fix 1 — Plateau/jitter fix

From your plateau validation:

**k=2**

$$
51.66\% \rightarrow 53.28\%
$$

for Original → PlateauOnly.

So this fix **did affect beacon interception**, although it still didn't beat BeliefUCB.

Its main purpose was also to make burst/plateau observations less likely to produce an unrealistically narrow timing model.

---

### Fix 2 — Harmonic / candidate-selection improvement

Your current PRIAware then uses improved candidate selection and harmonic handling.

That helped particularly with the synthetic PDW case.

Your PDW results showed:

- PlateauOnly band 4: **7/10 correct**
- Current band 4: **10/10 correct**

while overall interception also increased:

- PlateauOnly: **23.11%**
- Current: **27.03%**

So **this family of changes matters for fractional-PRI lock-on in the PDW scenario**.

---

### Fix 3 — Off-by-one candidate expansion

Your newest experiment says:

> **Beacon: essentially no measurable benefit.**

k=1:

$$
+0.1\text{ pp}
$$

k=2:

$$
+0.0\text{ pp}
$$

Therefore, don't attribute the beacon regression/improvement to the off-by-one change.

---

# And the big result remains

For **k=2**, the important comparison is still:

$$
\text{Current PRIAware}=53.4\%
$$

versus

$$
\text{BeliefUCB}=54.4\%
$$

Therefore:

$$
\boxed{\text{PRIAware is about 1.0 pp below BeliefUCB}}
$$

with only:

$$
\boxed{5/30}
$$

paired wins.

So the off-by-one fix **did not solve the k=2 beacon regression**.

And that's actually a useful research result.

---

# Research conclusion

You can now write something like:

> **Off-by-one candidate expansion was independently validated using identical stochastic environments across 30 seeds. On the beacon scenario, adding ±1 integer neighbors to the PRI candidate pool produced negligible changes in aggregate interception: +0.1 percentage points at k=1 and effectively 0.0 percentage points at k=2. Therefore, the observed k=2 PRIAware performance deficit relative to BeliefUCB is not attributable to the off-by-one candidate-generation issue.**

That's a **stronger conclusion than simply saying "the fix didn't work."**

You demonstrated that the experiment was controlled enough to isolate the change.

### Current picture of your project

```text
Open-loop
   ↓
Belief learning
   ↓
Belief + UCB + multi-channel
   ↓
PRI awareness
   ↓
Plateau/jitter fix
   ↓
Harmonic/fractional-PRI fix
   ↓
±1 off-by-one candidate fix
   ↓
Persistent characterization fix
```

And each stage now has a specific empirical purpose rather than being a collection of arbitrary modifications.

The **V4 persistent characterization fix remains the big reliability fix**:

```text
Original PRIAware radar capture:
30.0 ± 48.3%

Persistent PRIAware:
93.3 ± 0.9%

Successful seeds (>50% radar capture):
3/10 → 10/10
```

while the newest test tells us:

```text
±1 candidate fix
        ↓
Beacon interception
essentially unchanged
```

So I'd **not remove the off-by-one fix** based on this result. Its value should be judged primarily against the fractional-PRI/PDW validation it was designed to address, rather than this beacon aggregate metric.



---
Powered by [ChatGPT Exporter](https://www.chatgptexporter.com)