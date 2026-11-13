"""Find the song's true tempo and where bar 1 beat 1 sits, from drum stems.

Usage: find_grid.py <kick.wav> <snare.wav> [cymbals.wav] [--hint BPM] [--range 60 180]

Do not trust the BPM from audio analysis or Song to MIDI: on the first song both were
wrong (123 and 92 for a 90.67 BPM track), and a coarse offset (0.375 s instead of
0.364 s) made every part land audibly ahead of the 1.

Method: onset times (backtrack=True – use the SAME setting anywhere else hits are
detected, or parts drift against the grid) are scored on a 1/16 grid for every
candidate tempo; the phase comes from the circular mean of the onsets. The downbeat
is the beat where kicks land on 1 & 3 and snares on 2 & 4.
Prints the top candidates (half/double tempo usually shows up too – pick the one whose
feel matches the genre / the hint) and the offset in seconds to trim from every stem.
"""
import argparse
import json

import librosa
import numpy as np

SR, HOP = 22050, 256


def onsets(path):
    y = librosa.load(path, sr=SR)[0]
    env = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    fr = librosa.onset.onset_detect(onset_envelope=env, sr=SR, hop_length=HOP, backtrack=True, delta=0.25)
    t = librosa.frames_to_time(fr, sr=SR, hop_length=HOP)
    w = env[np.minimum(fr + 2, len(env) - 1)]
    return t, w / (w.max() or 1)


def lock(t, w, period):
    """Resultant length (0..1) and phase (s) of onsets on a grid of the given period."""
    z = (w * np.exp(2j * np.pi * t / period)).sum() / (w.sum() or 1)
    return abs(z), (np.angle(z) / (2 * np.pi) * period) % period


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("kick")
    ap.add_argument("snare")
    ap.add_argument("cymbals", nargs="?")
    ap.add_argument("--hint", type=float)
    ap.add_argument("--range", type=float, nargs=2, default=(60, 180))
    a = ap.parse_args()

    kt, kw = onsets(a.kick)
    st, sw = onsets(a.snare)
    parts = [(kt, kw), (st, sw)]
    if a.cymbals:
        parts.append(onsets(a.cymbals))
    t = np.concatenate([p[0] for p in parts])
    w = np.concatenate([p[1] for p in parts])

    def score(bpm):
        return lock(t, w, 15.0 / bpm)[0]  # 1/16 grid

    coarse = np.arange(a.range[0], a.range[1], 0.05)
    s = np.array([score(b) for b in coarse])
    cands = []
    for i in np.argsort(s)[::-1]:
        b = coarse[i]
        if all(abs(b - c) > 1.0 for c in cands):
            cands.append(b)
        if len(cands) == 4:
            break
    results = []
    for b in cands:
        fine = np.arange(b - 0.1, b + 0.1, 0.002)
        bpm = float(fine[np.argmax([score(x) for x in fine])])
        beat = 60.0 / bpm
        r16, ph16 = lock(t, w, beat / 4)
        # which 16th is the beat itself: the kick+snare phase on the beat circle, snapped
        # to the nearest 16th of the (more precise) 1/16 phase
        _, phb = lock(np.concatenate([kt, st]), np.concatenate([kw, sw]), beat)
        k16 = round(((phb - ph16) % beat) / (beat / 4)) % 4
        beat_phase = (ph16 + k16 * beat / 4) % beat
        # downbeat: kick on 1 & 3, snare on 2 & 4
        def bar_fit(k):
            off = beat_phase + k * beat
            kb = np.round((kt - off) / beat).astype(int) % 4
            sb = np.round((st - off) / beat).astype(int) % 4
            return (kw * np.isin(kb, (0, 2))).sum() + (sw * np.isin(sb, (1, 3))).sum()
        k = max(range(4), key=bar_fit)
        offset = (beat_phase + k * beat) % (4 * beat)
        results.append({"bpm": round(bpm, 2), "offset_s": round(float(offset), 3), "grid_lock": round(float(r16), 3)})
    if a.hint:
        results.sort(key=lambda r: (abs(r["bpm"] - a.hint) > 3, -r["grid_lock"]))
    for r in results:
        print(f"{r['bpm']:>7.2f} BPM  bar 1 at {r['offset_s']:.3f} s  (grid lock {r['grid_lock']:.3f})")
    print(json.dumps(results[0]))


if __name__ == "__main__":
    main()
