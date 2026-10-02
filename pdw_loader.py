"""
pdw_loader.py
=============
Loads Pulse Descriptor Word (PDW) streams in the schema used by the Alan
Turing Institute's Turing Synthetic Radar Dataset (TSRD) / Turing
Deinterleaving Challenge:

    fields: ToA (Time of Arrival, us), CF (Centre Frequency, MHz),
            PW (Pulse Width, us), AoA (Angle of Arrival, deg),
            Amplitude (dB), and a ground-truth emitter label.

IMPORTANT — about real vs. synthetic data here:
This sandbox cannot reach huggingface.co (it's outside the network
allowlist) and the TSRD is gated behind a HuggingFace license/token
anyway, so it can't be downloaded from inside this environment.

`load_real_pulse_train()` below is written against the TSRD's own
published API (`turing_deinterleaving_challenge.PulseTrain.load`) and
will work as-is on YOUR machine once you've:
    pip install git+https://github.com/alan-turing-institute/turing-deinterleaving-challenge.git
    (and downloaded a .h5 pulse train per that repo's instructions)

`generate_synthetic_pdw_stream()` is a local stand-in that mimics the
*same PDW schema* (fixed-frequency constant-PRI emitters + frequency-
agile hoppers, interleaved) so the rest of the pipeline (binning,
scheduling, metrics) can be built and tested end-to-end right now,
then pointed at real data later with a one-line swap.
"""

import numpy as np


def load_real_pulse_train(h5_path: str):
    """
    Load a real TSRD pulse train.

    Reads the .h5 DIRECTLY with h5py (see pdw_source.read_h5_pulse_train)
    rather than going through `turing_deinterleaving_challenge.PulseTrain
    .load`. The file layout is plain -- `data` (N,5) float32, `labels`
    (N,1) int8, `metadata/...` attributes -- so the gated package buys
    nothing here, and depending on it was actively harmful: the old
    version raised ImportError when it was missing, and the caller in
    run_on_turing_dataset.py caught that and silently continued on
    synthetic data. A run that asked for a real file and got fake data
    without failing is worse than a run that crashes.

    Returns (pdw, labels, meta) where `pdw` is a structured array in the
    same dtype generate_synthetic_pdw_stream() returns, so everything
    downstream is unchanged.

    Raises PDWSourceError if the path is missing or unreadable.
    """
    from pdw_source import read_h5_pulse_train  # local import: avoids a cycle
    pdw, meta = read_h5_pulse_train(h5_path)
    return pdw, pdw["label"], meta


def generate_synthetic_pdw_stream(duration_us: float = 2_000_000, seed: int = 0):
    """
    Schema-faithful stand-in pulse train (NOT the real TSRD):
    returns a structured numpy array with fields
    ("toa", "cf", "pw", "aoa", "amp", "label"), sorted by ToA, spanning
    the 0-18 GHz band the real dataset's oracle ("stare") receiver covers.

    Includes both fixed-frequency constant-PRI emitters (typical
    search/comms radars) and frequency-agile hoppers (LPI/LPD-style
    threats), interleaved -- matching the mix of emitter behaviours the
    real challenge describes.
    """
    rng = np.random.default_rng(seed)
    pulses = []
    emitter_id = 0

    # Fixed-frequency, roughly-constant-PRI emitters.
    for cf, pri, pw, aoa in [
        (2400, 1000, 2.0, 30),
        (9200, 650, 1.2, 140),
        (14300, 1500, 3.0, 260),
    ]:
        t = rng.uniform(0, pri)
        while t < duration_us:
            pulses.append((t, cf + rng.normal(0, 0.5), pw,
                            aoa + rng.normal(0, 1), rng.uniform(-70, -40), emitter_id))
            t += pri * (1 + rng.normal(0, 0.02))  # small PRI jitter
        emitter_id += 1

    # Frequency-agile emitters: hop centre frequency pulse-to-pulse.
    for hop_bands, pri, pw, aoa in [
        ([500, 3300, 6100, 11800, 16200], 400, 0.8, 70),
        ([1800, 4700, 8600, 12900, 17000], 550, 1.0, 200),
    ]:
        t = rng.uniform(0, pri)
        while t < duration_us:
            cf = rng.choice(hop_bands) + rng.normal(0, 2)
            pulses.append((t, cf, pw, aoa + rng.normal(0, 3),
                            rng.uniform(-75, -45), emitter_id))
            t += pri * (1 + rng.normal(0, 0.1))
        emitter_id += 1

    pulses.sort(key=lambda p: p[0])
    dtype = [("toa", "f8"), ("cf", "f8"), ("pw", "f8"),
             ("aoa", "f8"), ("amp", "f8"), ("label", "i4")]
    return np.array(pulses, dtype=dtype)
