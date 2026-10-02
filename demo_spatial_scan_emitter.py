"""
demo_spatial_scan_emitter.py
==============================
Sanity-checks SpatiallyScanningEmitter in isolation, before any
scheduler is built around it: wraps a SparsePeriodicEmitter (fast PRI,
band 5) in a slow rotation (scan_period=40, beam_dwell=6) and prints the
truth timeline, so the two-tier structure -- bursts of fast pulses
during each beam pass, long silence between passes -- is visible before
we ask any ML scheduler to learn it.

Run: python3 demo_spatial_scan_emitter.py
"""

from scan_scheduler_v3_pri import SparsePeriodicEmitter
from spatial_scan_emitter import SpatiallyScanningEmitter


def main():
    inner = SparsePeriodicEmitter("fixed-pri-radar", band=5, pri=3)
    scanning = SpatiallyScanningEmitter(inner, scan_period_steps=40, beam_dwell_steps=6)

    n_steps = 120
    timeline = []
    for t in range(n_steps):
        band, on = scanning.step(t)
        timeline.append("#" if on else ("." if scanning.in_beam else " "))

    print("Legend: '#' = pulse received  '.' = in-beam but PRI silent  ' ' = out of beam\n")
    for row_start in range(0, n_steps, 40):
        row = "".join(timeline[row_start:row_start + 40])
        print(f"t={row_start:4d}: {row}")

    hits = timeline.count("#")
    in_beam_steps = timeline.count("#") + timeline.count(".")
    print(f"\n{hits} pulses received over {n_steps} steps "
          f"({in_beam_steps} in-beam steps, {n_steps - in_beam_steps} out-of-beam steps)")
    print(f"Expected beam passes: {n_steps // 40} full rotations of 40 steps, "
          f"6 in-beam steps each -> ~{(n_steps // 40) * 6} in-beam steps")
    print(f"Within each pass, inner PRI=3 -> expect roughly beam_dwell/pri pulses per pass")


if __name__ == "__main__":
    main()
