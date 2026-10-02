"""
pdw_environment.py
===================
Adapts a PDW stream (ToA, CF, ...) — real TSRD data or the schema-faithful
synthetic stand-in from pdw_loader.py — into the exact same "band status
per scan step" interface that scan_scheduler_prototype.Environment uses.

This means RoundRobinScheduler, RandomScheduler, and BeliefScheduler, and
the run_episode()/metrics code, all run UNMODIFIED against real radar
data: only the environment changes.

Binning choices:
  - Frequency axis: split [freq_range_mhz] into n_bands equal-width
    channels (a receiver's fixed set of sub-bands to sweep/select from).
  - Time axis: split into fixed `dwell_us` windows (how long the receiver
    would sit on one band per scan step). A band is "ON" during a window
    if at least one pulse's centre frequency landed in it during that
    window.
"""

import numpy as np


class PDWReplayEnvironment:
    def __init__(self, pdw, n_bands: int = 8, dwell_us: float = 200.0,
                 freq_range_mhz=(0, 18000), t0_us: float = 0.0):
        """t0_us: ToA treated as step 0.

        Defaults to 0.0, which is the original behaviour and keeps every
        previously-recorded synthetic result byte-for-byte identical (the
        stand-in's first pulse lands within one PRI of t=0 anyway).

        It matters for real TSRD recordings, which do not start at zero:
        Validation/config_169.h5's first pulse is at ToA = 1.13 s, so
        `toa // dwell_us` would prepend ~56,000 guaranteed-empty scan
        steps at dwell=20us before any emitter can possibly appear. Those
        steps are free correctly-predicted silence for every scheduler and
        they inflate the interception denominator, so a real file should
        pass t0_us=toa.min() (PDWSource.t0_us does this).
        """
        self.n_bands = n_bands
        self.dwell_us = dwell_us
        self.t0_us = t0_us
        lo, hi = freq_range_mhz
        self.band_edges = np.linspace(lo, hi, n_bands + 1)

        if len(pdw) == 0:
            self.n_steps = 0
            self._status = np.zeros((0, n_bands), dtype=bool)
        else:
            toa = pdw["toa"] - t0_us
            cf = pdw["cf"]
            band_idx = np.clip(np.digitize(cf, self.band_edges) - 1, 0, n_bands - 1)
            step_idx = np.maximum((toa // dwell_us).astype(np.int64), 0)

            self.n_steps = int(step_idx.max()) + 1
            self._status = np.zeros((self.n_steps, n_bands), dtype=bool)
            self._status[step_idx, band_idx] = True

        self.t = 0

    @property
    def occupancy(self):
        """Fraction of steps each band is ON. Bands that are ON in 0% of
        steps are dead channels: a learned scheduler beats round-robin
        partly just by noticing them, which is a trivial win and worth
        separating from the real result when reporting."""
        if self.n_steps == 0:
            return np.zeros(self.n_bands)
        return self._status.mean(axis=0)

    def step(self):
        if self.t >= self.n_steps:
            row = np.zeros(self.n_bands, dtype=bool)
        else:
            row = self._status[self.t]
        self.t += 1
        return {b: bool(row[b]) for b in range(self.n_bands)}

    def next_transmission_after(self, band, step):
        """Ground-truth next step (strictly after `step`) at which `band`
        transmits, or None if it never does again in this episode.

        This reads the full truth grid, including steps the receiver
        never scanned -- it exists purely for offline evaluation of a
        scheduler's *predictions* against reality (e.g. "average
        intercept time error"). No scheduler ever calls this: they only
        ever see step()'s per-step dict, same as a real receiver that
        only knows what it was tuned to at the time.
        """
        if step + 1 >= self.n_steps:
            return None
        col = self._status[step + 1:, band]
        if not col.any():
            return None
        return step + 1 + int(np.argmax(col))
