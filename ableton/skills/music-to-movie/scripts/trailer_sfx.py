"""Synthesise trailer sound design, tuned to the cue's key. No samples, no licences.

Usage: trailer_sfx.py <outdir> --root D [--only boom,impact,...]

Writes one 48 kHz stereo WAV per sound plus sfx.json: {name: {"file", "sync_s", "length_s"}}.
sync_s is the moment inside the file that belongs ON the picture event (an impact's sync is
its transient, a riser's is its END, a whoosh's is its loudest point). place_cue.py puts
each file at (event time - sync_s), so nothing here needs trimming in Live.

Sounds: boom (sub hit, soft), impact (boom + crack + long tail), impact_big, braam (low
brass-style blast on the root), braam_long, riser (noise + rising tone, cut dead at the hit),
riser_short, reverse (reverse-reverb swell into a hit), whoosh, sub_drop (pitch fall),
wind (looping storm bed, 12 s), shimmer (high airy pad for the quiet after a cut-out).
"""
import argparse, json, os
import numpy as np
import soundfile as sf
from scipy.signal import butter, sosfilt, fftconvolve

SR = 48000
NOTE = {"C": 0, "C#": 1, "Db": 1, "D": 2, "D#": 3, "Eb": 3, "E": 4, "F": 5, "F#": 6, "Gb": 6,
        "G": 7, "G#": 8, "Ab": 8, "A": 9, "A#": 10, "Bb": 10, "B": 11}
rng = np.random.default_rng(7)


def hz(root, octave):
    return 440.0 * 2 ** ((NOTE[root] + 12 * (octave + 1) - 69) / 12)


def t_(sec):
    return np.arange(int(sec * SR)) / SR


def filt(x, kind, f, order=2):
    return sosfilt(butter(order, np.asarray(f) / (SR / 2), kind, output="sos"), x, axis=0)


def noise(sec):
    return rng.standard_normal((int(sec * SR), 2))


def stereo(m, width=0.0):
    m = np.asarray(m)
    if m.ndim == 2:
        return m
    d = int(width * SR)
    return np.stack([m, np.concatenate([np.zeros(d), m[:len(m) - d]]) if d else m], 1)


def verb(x, sec=3.0, mix=0.35, bright=5000, dark=120):
    ir = noise(sec) * np.exp(-t_(sec) * 6.9 / sec)[:, None]
    ir = filt(filt(ir, "low", bright), "high", dark)
    ir /= np.sqrt((ir ** 2).sum(0)).max()
    wet = np.stack([fftconvolve(x[:, c], ir[:, c]) for c in (0, 1)], 1)
    dry = np.concatenate([x, np.zeros((len(wet) - len(x), 2))])
    return dry * (1 - mix) + wet * mix * 0.5


def norm(x, peak=0.89):
    return x / (np.abs(x).max() + 1e-12) * peak


def fade(x, a=0.005, r=0.05):
    x = x.copy()
    na, nr = int(a * SR), int(r * SR)
    if na: x[:na] *= np.linspace(0, 1, na)[:, None]
    if nr: x[-nr:] *= np.linspace(1, 0, nr)[:, None]
    return x


def boom(root, sec=3.0, f0=95, drive=1.5):
    t = t_(sec)
    f1 = hz(root, 1)                                   # settle on the key's low root
    f = f1 + (f0 - f1) * np.exp(-t * 18)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 2.2)
    thump = filt(noise(0.25), "low", 180) * np.exp(-t_(0.25) * 30)[:, None]
    x = stereo(np.tanh(s * drive))
    x[:len(thump)] += thump * 0.5
    return fade(x, 0.002, 0.3), 0.0


def impact(root, big=False):
    b, _ = boom(root, 4.0 if big else 3.0, 120 if big else 95, 2.5 if big else 1.6)
    crack = filt(noise(0.6), "band", [90, 2600 if big else 1800]) * np.exp(-t_(0.6) * 9)[:, None]
    body = filt(noise(1.6), "band", [45, 320]) * np.exp(-t_(1.6) * 3.5)[:, None]
    x = b.copy()
    x[:len(crack)] += crack * (0.9 if big else 0.6)
    x[:len(body)] += body * 0.8
    x = np.tanh(x * 1.3)
    return fade(verb(x, 5.0 if big else 3.5, 0.3, 3500 if big else 2500, 60), 0.001, 0.8), 0.0


def braam(root, sec=2.2):
    t = t_(sec)
    out = np.zeros((len(t), 2))
    bend = 1 - 0.035 * np.exp(-t * 9)                   # the scoop up into the note
    for octv, amp in ((1, 1.0), (2, 0.8), (3, 0.35)):
        for det, pan in ((-9, 0.2), (-3, 0.4), (0, 0.5), (4, 0.6), (10, 0.8)):
            f = hz(root, octv) * 2 ** (det / 1200) * bend
            ph = np.cumsum(f) / SR
            saw = 2 * (ph % 1) - 1
            out[:, 0] += saw * amp * (1 - pan); out[:, 1] += saw * amp * pan
        f5 = hz(root, octv) * 1.4983 * bend
        out += (2 * ((np.cumsum(f5) / SR) % 1) - 1)[:, None] * amp * 0.25
    env = np.minimum(1, t / 0.04) * np.where(t < sec * 0.55, 1, np.exp(-(t - sec * 0.55) * 4.5))
    growl = 1 + 0.25 * np.sin(2 * np.pi * 27 * t) * np.exp(-t * 1.5)
    x = np.tanh(out * (env * growl)[:, None] * 0.9)
    lo = filt(x, "low", 900, 2); hi = filt(x, "band", [900, 4200], 2)
    x = lo + hi * np.minimum(1, t / 0.25)[:, None] * 0.6   # brass opens up after the attack
    return fade(verb(filt(x, "high", 30), 3.5, 0.3, 4000, 80), 0.003, 0.6), 0.0


def riser(root, sec=1.6):
    t = t_(sec); u = t / sec
    n = noise(sec)
    out = np.zeros_like(n)
    for k in range(24):                                 # noise through a rising band, in slices
        a, b = int(k / 24 * len(t)), int((k + 1) / 24 * len(t))
        fc = 250 * 2 ** (5.0 * (k + 0.5) / 24)
        out[a:b] = filt(n[max(0, a - 2000):b], "band", [fc * 0.7, min(fc * 1.4, SR * 0.45)])[-(b - a):]
    f = hz(root, 3) * 2 ** (u * 1.0)                    # tone climbs an octave, lands on the root
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) + 0.5 * np.sin(2 * np.pi * np.cumsum(f * 1.4983) / SR)
    trem = 1 - 0.5 * (0.5 + 0.5 * np.sin(2 * np.pi * np.cumsum(4 + 20 * u ** 2) / SR)) * u
    x = (out * 0.8 + stereo(tone, 0.004) * 0.35) * (u ** 2.2 * trem)[:, None]
    return fade(x, 0.01, 0.004), sec


def reverse(root, sec=1.4):
    x, _ = impact(root)
    x = x[int(0.02 * SR):int((sec + 0.02) * SR)][::-1].copy()
    x *= (np.linspace(0, 1, len(x)) ** 1.5)[:, None]
    return fade(filt(x, "high", 90), 0.01, 0.003), len(x) / SR


def whoosh(sec=0.9):
    t = t_(sec); u = t / sec
    n = noise(sec); out = np.zeros_like(n)
    for k in range(18):
        a, b = int(k / 18 * len(t)), int((k + 1) / 18 * len(t))
        fc = 300 * 2 ** (3.2 * np.sin(np.pi * (k + 0.5) / 18))
        out[a:b] = filt(n[max(0, a - 2000):b], "band", [fc * 0.6, fc * 1.7])[-(b - a):]
    env = np.sin(np.pi * u) ** 2.5
    pan = 0.5 + 0.45 * np.cos(np.pi * u)
    out[:, 0] *= env * (1 - pan); out[:, 1] *= env * pan
    return fade(verb(out, 1.2, 0.2), 0.01, 0.2), sec * 0.5


def sub_drop(root, sec=1.6):
    t = t_(sec); u = t / sec
    f = hz(root, 2) * 2 ** (-1.6 * u)
    s = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.minimum(1, t / 0.03) * (1 - u) ** 0.6
    return fade(stereo(np.tanh(s * 1.6)), 0.005, 0.05), 0.0


def wind(sec=12.0):
    t = t_(sec)
    n = noise(sec)
    a = filt(n, "band", [180, 900]); b = filt(n, "band", [900, 3800]); c = filt(n, "low", 140)
    lfo = lambda r, p: 0.55 + 0.45 * np.sin(2 * np.pi * r * t + p)
    x = a * lfo(0.23, 0)[:, None] + b * 0.45 * lfo(0.41, 1.3)[:, None] + c * 1.2 * lfo(0.13, 2.1)[:, None]
    x[:, 1] = np.roll(x[:, 1], 311)
    return fade(x, 0.5, 0.5), 0.0


def shimmer(root, sec=4.0):
    t = t_(sec)
    x = np.zeros((len(t), 2))
    for i, (octv, ratio) in enumerate(((5, 1), (5, 1.4983), (6, 1), (6, 1.1892))):   # root, 5th, root, min 3rd
        f = hz(root, octv) * ratio
        for det in (-6, 5):
            s = np.sin(2 * np.pi * f * 2 ** (det / 1200) * t + i) * (0.6 + 0.4 * np.sin(2 * np.pi * (0.3 + 0.1 * i) * t))
            x[:, 0 if det < 0 else 1] += s / (1 + i)
    air = filt(noise(sec), "band", [5000, 11000]) * 0.08
    x = (x * 0.25 + air) * (np.minimum(1, t / 1.2) * np.minimum(1, (sec - t) / 1.2))[:, None]
    return verb(x, 4.0, 0.5, 9000, 400), 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("outdir"); ap.add_argument("--root", default="D"); ap.add_argument("--only", default="")
    a = ap.parse_args()
    os.makedirs(a.outdir, exist_ok=True)
    r = a.root
    voices = {"boom": lambda: boom(r), "impact": lambda: impact(r), "impact_big": lambda: impact(r, True),
              "braam": lambda: braam(r), "braam_long": lambda: braam(r, 3.6),
              "riser": lambda: riser(r), "riser_short": lambda: riser(r, 1.0),
              "reverse": lambda: reverse(r), "whoosh": whoosh, "sub_drop": lambda: sub_drop(r),
              "wind": wind, "shimmer": lambda: shimmer(r)}
    peaks = {"boom": 0.8, "wind": 0.35, "shimmer": 0.4, "whoosh": 0.6, "riser": 0.7, "riser_short": 0.7, "reverse": 0.7}
    only = [s for s in a.only.split(",") if s]
    manifest = {}
    for name, fn in voices.items():
        if only and name not in only:
            continue
        x, sync = fn()
        x = norm(x, peaks.get(name, 0.89))
        path = os.path.join(a.outdir, "SFX %s.wav" % name.replace("_", " "))
        sf.write(path, x.astype(np.float32), SR, subtype="PCM_24")
        manifest[name] = {"file": path, "sync_s": round(float(sync), 4), "length_s": round(len(x) / SR, 3)}
        print("%-12s sync %.2f s  length %.2f s  -> %s" % (name, sync, len(x) / SR, path))
    json.dump(manifest, open(os.path.join(a.outdir, "sfx.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
