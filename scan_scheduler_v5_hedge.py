"""
scan_scheduler_v5_hedge.py
==========================
HedgeBlendedPRIAwareScheduler: replaces PRIAwareScheduler's hand-tuned
confidence-based blend (`blended = (1-conf)*belief + conf*periodicity`,
conf capped by max_blend_confidence) with a per-band online-learned
trust weight between two "experts" -- the Markov belief score and the
periodicity score -- updated via multiplicative-weights (Hedge) from
each expert's realized prediction error.

WHY: confidence_scale (scan_scheduler_v3_pri.py), max_blend_confidence
(added for the real-data stagger case), and char_bonus_c
(scan_scheduler_v4_persistent.py) have each independently shown the
same pattern under sweep (tune_confidence_threshold.py; the
max_blend_confidence sweep in diagnose_fullfile_regression.py): no
single fixed value serves both the synthetic sparse-radar/beacon
scenarios and real TSRD data well. Most strikingly,
diagnose_fullfile_regression.py found max_blend_confidence wants to be
near 1.0 for the sparse-radar headline but near 0.1 for config_169.h5's
band 1 (a correctly-locked staggered PRI, confidence 1.0, whose narrow
spikes still crowd out belief on an already-near-saturated band) --
and separately found that locked confidence isn't even stable within a
single real run (drifts 1.0 -> 0.791 late in the 815,948-step replay).
A static cap can't respond to that drift; a per-band LEARNED weight
can, in principle -- that's the bet this class makes.

MECHANISM: per band, w_belief[b] + w_pri[b] = 1.0, initialized
BELIEF-BIASED (0.8 / 0.2) rather than 50/50. This is a deliberate
cold-start guard: the periodicity expert only ever produces a nonzero
prediction once PRIAwareScheduler's own lock gating (8-hit threshold,
min_cycles) has already accepted a period, so the raw sample-starvation
risk is already handled upstream -- but a *freshly locked*, still
low-evidence periodicity estimate could still be wrong, and a belief-
biased prior means it has to prove itself correct over several
observations before it's trusted as much as belief, rather than
instantly overriding it the way a fixed high confidence_scale can.

score(b) = priority[b] * (w_belief[b]*belief[b]
                           + w_pri[b]*periodicity_weight*periodic(b))
           + ucb_bonus(b)

After every observation on a scanned band, both experts' RAW
[0,1] predictions (belief[b], and periodic(b) WITHOUT the
periodicity_weight scale-up -- that scale-up is a score boost, not a
probability estimate, and mixing it into the loss would unfairly
penalize the periodicity expert for periodicity_weight > 1) are scored
against the realized outcome with squared error, and weights are
updated multiplicatively:
    loss_X = (pred_X - outcome) ** 2
    w_X[b] *= exp(-eta * loss_X)
then renormalized to sum to 1, with a floor (default 0.05) on each so
an expert that goes cold for a while (e.g. after the confidence-drift
event found on real data) can still recover instead of being
permanently zeroed out.

SCOPE, STATED HONESTLY: this is a first-pass build. Squared-error loss
against a binary outcome turned out NOT to be safe as-is -- it has two
confirmed class-imbalance failure modes (pre-lock: an unlocked expert's
placeholder-0 prediction wins by never being scanned during an on-step;
post-lock: a genuinely-locked but low-duty periodic signal's frequent,
marginally-correct off-peak predictions still outweigh its rarer,
much-more-valuable on-peak wins). Both are fixed here: the pre-lock case
via the `locked` gate (choose_bands/`_hedge_update`), the post-lock case
via inverse-class-frequency loss reweighting (`_hedge_update`). This is
NOT the same thing as the full bandit-style/decision-relevant loss still
flagged below as deferred -- that would weight a LOSS by whether the two
experts' disagreement actually changed which band got scanned, a finer
distinction than class balance alone captures. `eta` has not been swept
against the four reference points (sparse-radar headline, beacon k=1/k=2,
PDW band-4 fractional-PRI, config_169.h5 band 1) the way confidence_scale
was swept against two -- this file ships a plausible default and an
explicit script to do that sweep, not a validated one.
"""
import math
from typing import List, Optional

from scan_scheduler_v3_pri import PRIAwareScheduler
from scan_scheduler_v4_persistent import PersistentPRIAwareScheduler


class HedgeBlendedPRIAwareScheduler(PersistentPRIAwareScheduler):
    """
    Blend, choose_bands, and _hedge_update all gate on confidence[b] > 0
    -- i.e. the learned weight only competes belief against periodicity
    once periodicity has an ACTUAL lock to offer, falling back to plain
    belief_pred (mirroring PRIAwareScheduler's own conf=0 behavior)
    otherwise. That gate is load-bearing, not cosmetic -- found via this
    class's own first validation pass (validate_hedge_blend.py), not
    guessed upfront: an unlocked periodicity expert always predicts
    exactly 0 (a structural placeholder, not a real prediction), and
    squared-error loss against a binary outcome rewards that "predict 0"
    placeholder perfectly on every OFF-step -- which for any low-duty
    band (most comms, most of the time) means the uninformative
    placeholder accumulates LOWER total loss than a genuinely calibrated
    but nonzero belief score, purely from class imbalance. Confirmed
    directly: without this gate, comm-1's capture crashed from
    PRIAware's 79.4% to 3.3% on the sparse-radar reference scenario,
    because the degenerate zero-predictor won the weight competition on
    a band it had nothing useful to say about.

    Rebased onto PersistentPRIAwareScheduler (v4), not PRIAwareScheduler
    (v3), for a reason found by multi-seeding this class's own default
    (multiseed_alpha_default.py), not designed in upfront: subclassing
    v3 directly meant inheriting v3's own known sample-starvation
    coin-flip on the sparse-radar scenario (30 seeds: PRIAware 50.0% +/-
    50.9% radar capture, bimodal -- locks fully or never, exactly the
    8-hit-threshold cliff v4 was built to fix). The single seed used
    throughout this class's earlier single-seed validation (seed=11)
    happened to be a "locks" seed, masking this entirely. Because this
    class's own choose_bands() fully replaces the parent's (needed for
    the Hedge blend), inheriting from v4 does NOT automatically pull in
    v4's characterization bonus the way normal method inheritance would
    -- v4's own choose_bands() is never called. The bonus term is
    re-added explicitly below, reusing the state v4's __init__/update()
    already provide (total_hits, required_hits, give_up_after_scans,
    char_bonus_c) via the now-corrected base class.
    """
    def __init__(self, n_bands, eta: float = 4.0,
                 initial_weight_belief: float = 0.8,
                 weight_floor: float = 0.05,
                 class_balance_alpha: float = 0.1,
                 **kwargs):
        # confidence_scale/max_blend_confidence are still accepted (via
        # **kwargs -> PRIAwareScheduler.__init__) because the underlying
        # PRI lock/confidence machinery (_update_pri_model etc.) is
        # untouched -- only the SCORE BLEND is replaced. Passing a
        # non-default max_blend_confidence here has no effect, since
        # choose_bands (overridden below) never reads self.confidence
        # for blending; it's harmless but pointless, not silently wrong.
        super().__init__(n_bands, **kwargs)
        self.eta = eta
        self.weight_floor = weight_floor
        assert 0.0 <= class_balance_alpha <= 1.0
        self.class_balance_alpha = class_balance_alpha
        assert 0.0 <= initial_weight_belief <= 1.0
        self.w_belief = [initial_weight_belief] * n_bands
        self.w_pri = [1.0 - initial_weight_belief] * n_bands
        # Raw [0,1] expert predictions made for each SCANNED band this
        # step, cached in choose_bands so update() can score them
        # against the realized outcome without recomputing (propagate()
        # has already advanced belief[b] by the time update() runs for
        # a DIFFERENT band in the same multi-channel step, so the
        # prediction must be captured at decision time, not looked up
        # after the fact).
        self._pending_pred: dict = {}
        # Per-band, per-class (on/off) observation counts, used only to
        # class-balance the Hedge loss (see _hedge_update) -- tracked
        # separately from scan_count/hit_times because those exist for
        # other purposes and mixing in this bookkeeping there would be
        # a needless coupling.
        self._class_on = [0] * n_bands
        self._class_off = [0] * n_bands

    def _raw_predictions(self, b, t):
        belief_pred = self.belief[b]
        periodic_raw = self._periodicity_score(b, t)  # already in [0,1], no periodicity_weight applied
        return belief_pred, periodic_raw

    def choose_bands(self, k):
        self.t += 1
        if self.t <= self.warmup_steps:
            for b in range(self.n_bands):
                self._propagate(b)
            return self._warmup_bands(k)
        for b in range(self.n_bands):
            self._propagate(b)
        scores = []
        preds = {}
        for b in range(self.n_bands):
            ucb_bonus = self.ucb_c * math.sqrt(math.log(self.t + 1) / (self.scan_count[b] + 1))
            belief_pred, periodic_raw = self._raw_predictions(b, self.t)
            locked = self.confidence[b] > 0
            preds[b] = (belief_pred, periodic_raw, locked)
            if locked:
                blended = (self.w_belief[b] * belief_pred
                           + self.w_pri[b] * self.periodicity_weight * periodic_raw)
            else:
                # Periodicity is a structural placeholder here (always 0,
                # not a real prediction) -- squared-error loss rewards
                # that "predict 0" placeholder on every off-step purely
                # by class imbalance, which would otherwise win the
                # weight competition against a genuinely calibrated but
                # nonzero belief score on any low-duty band (confirmed:
                # this crashed comm-1 from 79.4% to 3.3% on the
                # sparse-radar reference before this guard). Mirror
                # PRIAware's own conf=0 behavior exactly instead: full,
                # unweighted belief trust, no expert competition until
                # periodicity has an actual lock to compete with.
                blended = belief_pred
            # v4's characterization bonus, re-added explicitly since this
            # class's own choose_bands() fully replaces
            # PersistentPRIAwareScheduler's (v4's version is never
            # called) -- see class docstring for why this is here at
            # all. Formula and gating unchanged from v4: give a band
            # that hasn't yet accumulated required_hits confirmed ON
            # samples a persistent bonus that decays with ITS OWN hit
            # count (not total scan count, which the ordinary ucb_bonus
            # above already uses), bounded by give_up_after_scans so a
            # band with no real signal at all doesn't absorb the budget
            # forever.
            char_bonus = 0.0
            if (self.total_hits[b] < self.required_hits
                    and self.scan_count[b] < self.give_up_after_scans):
                char_bonus = self.char_bonus_c * math.sqrt(
                    math.log(self.t + 2) / (self.total_hits[b] + 1))
            scores.append(self.priority[b] * blended + ucb_bonus + char_bonus)
        order = sorted(range(self.n_bands), key=lambda b: scores[b], reverse=True)
        chosen = order[:k]
        # Only cache predictions for bands actually scanned -- update()
        # is only called for those, and dict stays small.
        for b in chosen:
            self._pending_pred[b] = preds[b]
        return chosen

    def _hedge_update(self, band, observed_on):
        if band not in self._pending_pred:
            return  # shouldn't happen outside warmup, but never crash on it
        belief_pred, periodic_pred, locked = self._pending_pred.pop(band)
        if not locked:
            # No real periodicity prediction was made at decision time --
            # nothing to score it against, and updating weights from a
            # placeholder 0 is exactly the class-imbalance trap this
            # guard exists to avoid. Leave weights untouched.
            return
        outcome = 1.0 if observed_on else 0.0
        # Class-balance the loss: an unlocked-then-locked LOW-DUTY
        # periodic signal's off-peak observations vastly outnumber its
        # on-peak ones, so raw per-observation squared-error lets the
        # far more frequent off-step class dominate total accumulated
        # loss even when periodicity's rare on-peak wins are individually
        # large and more valuable -- the same class-imbalance mechanism
        # the pre-lock `locked` gate fixed, recurring in a milder POST-
        # lock form. Confirmed directly: band 6 in the synthetic PDW
        # scenario is a genuinely, correctly-locked low-duty periodic
        # emitter (confidence 0.88, true PRI), yet w_pri[6] still
        # collapsed to the floor under the unweighted loss -- belief's
        # marginally-smaller off-peak error, repeated over far more
        # off-peak than on-peak observations, slowly outweighed
        # periodicity's much rarer but individually-correct on-peak
        # wins. That misallocation was traced (not just theorized) to
        # starving a DIFFERENT band (band 4) of the scan timing it
        # needed to clear its own min_cycles guard, even though band
        # 4's raw scan COUNT was nearly unchanged -- an emergent,
        # project-wide consequence of one band's weights converging
        # wrong. Reweighting each observation's loss by the inverse of
        # its own class's running frequency makes on-steps and off-steps
        # contribute EQUAL total loss mass regardless of a band's duty
        # cycle -- removing the volume imbalance itself, not papering
        # over its symptom. Laplace-smoothed (+1/+2) so early counts
        # don't produce an extreme class weight before either class has
        # enough samples to estimate its true frequency.
        #
        # FULL balancing (class_balance_alpha=1) recovered band 4 but
        # cost real band-1 (99.6% -> 94.7%) -- opposite duty profiles
        # want opposite amounts of correction. class_balance_alpha
        # linearly interpolates between UNWEIGHTED loss (alpha=0,
        # class_w == 1.0 always) and FULLY class-balanced loss (alpha=1,
        # class_w == the raw inverse-frequency weight), swept in
        # sweep_class_balance_alpha.py against all four references. The
        # relationship is sharply nonlinear, not a smooth trade-off:
        # band 4's lock is a THRESHOLD effect (alpha=0.02: never locks;
        # alpha=0.05: locks at the SAME confidence as full balancing,
        # 0.89) while real band-1's cost scales roughly continuously
        # with alpha (99.6% at 0.0 -> 98.5% at 0.05 -> 94.7% at 1.0).
        # Because a small alpha already buys the full band-4 fix, the
        # shipped default (0.1) sits just above that threshold with a
        # safety margin (0.05, measured on one seed, is too close to the
        # 0.02 failure point to trust as a default) -- band 4 fully
        # fixed, real band-1 at 98.0% rather than 94.7%.
        on_c, off_c = self._class_on[band], self._class_off[band]
        p_on = (on_c + 1) / (on_c + off_c + 2)
        p_off = 1.0 - p_on
        raw_class_w = 0.5 / p_on if observed_on else 0.5 / p_off
        class_w = 1.0 + self.class_balance_alpha * (raw_class_w - 1.0)
        if observed_on:
            self._class_on[band] += 1
        else:
            self._class_off[band] += 1
        loss_belief = class_w * (belief_pred - outcome) ** 2
        loss_pri = class_w * (periodic_pred - outcome) ** 2
        wb = self.w_belief[band] * math.exp(-self.eta * loss_belief)
        wp = self.w_pri[band] * math.exp(-self.eta * loss_pri)
        total = wb + wp
        if total <= 0:
            wb, wp = 0.5, 0.5
        else:
            wb, wp = wb / total, wp / total
        # Floor + renormalize so neither expert is ever permanently
        # zeroed out (lets a cold expert recover, e.g. after the
        # confidence-drift event found on real config_169.h5 data).
        wb = min(max(wb, self.weight_floor), 1.0 - self.weight_floor)
        wp = 1.0 - wb
        self.w_belief[band] = wb
        self.w_pri[band] = wp

    def update(self, band, observed_on):
        # super().update() now chains PersistentPRIAwareScheduler.update()
        # (increments total_hits) -> PRIAwareScheduler.update() (belief +
        # PRI/stagger model, hit_times, _update_pri_model) -- all of that
        # machinery is reused as-is; only the SCORE BLEND differs here.
        super().update(band, observed_on)
        if self.t > self.warmup_steps:
            self._hedge_update(band, observed_on)
