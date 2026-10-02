"""
spatial_scan_emitter.py
=========================
Models the gap the codebase had zero coverage for: an emitter whose
antenna itself mechanically or electronically scans/rotates, so it is
only detectable during the brief window each rotation that its beam
points at the receiver -- a periodicity completely independent of, and
layered on top of, its own PRI or frequency-hopping pattern. This is
what the PS names twice: "spatially scanning ... emitters" and
"a periodic scan receiver."

Why a decorator, not a new Emitter subclass duplicating PRI logic:
every existing Emitter (MarkovEmitter, PeriodicEmitter,
SparsePeriodicEmitter, AgileEmitter) already answers "is this emitter
transmitting right now" -- that's orthogonal to "is its beam pointed at
us right now." SpatiallyScanningEmitter wraps any of them and ANDs a
beam-illumination gate on top, so it composes with the existing
population instead of re-implementing it.

Physical picture (mapped to real EW terms):
    scan_period_steps  -- steps per full antenna rotation/scan cycle
    beam_dwell_steps   -- of those, how many steps the mainbeam is
                          actually pointed at the receiver (the
                          "main-beam illumination time", MBIT)
    phase_offset       -- where in the rotation cycle we start (models
                          "we don't know where the radar's dish
                          happened to be pointed when we arrived")

A receiver only ever sees on = (inner emitter transmitting) AND
(beam pointed at receiver). AoA is untouched by this: the emitter's
true bearing from the receiver doesn't change as its beam sweeps --
only whether we're currently inside that beam does. (pdw_loader's AoA
field is the receiver's bearing measurement and stays exactly as
meaningful/noisy as before; this model only gates *whether* a pulse
reaches the receiver at all, not what AoA gets reported for it.)
"""

import random
from typing import Tuple

from scan_scheduler_prototype import Emitter


class SpatiallyScanningEmitter(Emitter):
    def __init__(self, inner: Emitter, scan_period_steps: int,
                 beam_dwell_steps: int, phase_offset: int = 0,
                 sidelobe_leak_prob: float = 0.0):
        """sidelobe_leak_prob: chance, on any OUT-of-beam step where the
        inner emitter is transmitting, that a sidelobe pulse still gets
        through. Models real antenna sidelobes rather than a perfect
        mainbeam-only gate. 0.0 (default) keeps the original hard gate.
        Low values (real sidelobes are typically 20-40dB down, i.e. a
        small fraction of mainbeam gain) should still read as
        "occasional, unreliable" to a scheduler -- not a second regular
        periodicity worth locking onto."""
        super().__init__(inner.name + "-scanning")
        if beam_dwell_steps > scan_period_steps:
            raise ValueError("beam_dwell_steps can't exceed scan_period_steps")
        if not 0.0 <= sidelobe_leak_prob <= 1.0:
            raise ValueError("sidelobe_leak_prob must be in [0, 1]")
        self.inner = inner
        self.scan_period_steps = scan_period_steps
        self.beam_dwell_steps = beam_dwell_steps
        self.phase_offset = phase_offset % scan_period_steps
        self.sidelobe_leak_prob = sidelobe_leak_prob
        self.in_beam = False  # last step's gate value, exposed for diagnostics/tests

    def _in_beam(self, t: int) -> bool:
        phase = (t + self.phase_offset) % self.scan_period_steps
        return phase < self.beam_dwell_steps

    def step(self, t: int) -> Tuple[int, bool]:
        band, transmitting = self.inner.step(t)
        self.in_beam = self._in_beam(t)
        visible = self.in_beam or (
            transmitting and self.sidelobe_leak_prob > 0.0
            and random.random() < self.sidelobe_leak_prob
        )
        self.band = band
        self.on = transmitting and visible
        return self.band, self.on
