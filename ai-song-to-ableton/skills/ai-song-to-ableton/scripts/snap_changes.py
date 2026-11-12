"""Move a held part's chord changes to where its stem really changes chord.

Usage: snap_changes.py <parts.json> <part name> <aligned stem.wav> <bpm> [--window -4 8] [--out <name>] [--free]

chords.py works in half-bar slots, so its chart puts every change on beat 1 or 3. Songs
that change late (on "Lagos Rooftop" the Rhodes, guitar and bass all moved ~a beat after
the chart: Dm on beat 2, Em on beat 4) then get a MIDI part that switches chord a beat
before the record – "the MIDI doesn't follow the stem".

For every boundary between two different chords in the part, this tries each 16th in
[t + window_lo, t + window_hi] and keeps the split point where the stem's chroma best
matches old-chord-then-new-chord (each chord's own pitch classes as the template). Note
starts/ends at that boundary move with it; nothing else changes (pitches, velocities,
re-attacks of the same chord). Prints the shift histogram and the before/after chroma
agreement. Writes parts.json["parts"][<out>] (default: overwrite the part).
"""
import json
import sys
from collections import Counter, defaultdict

import librosa
import numpy as np

SR, HOP = 22050, 512


def stem_chroma16(path, bpm, n):
    y = librosa.load(path, sr=SR)[0]
    c = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=HOP)
    fps, step = SR / HOP, 15.0 / bpm  # a 16th in seconds
    out = np.zeros((n, 12))
    for i in range(n):
        a, z = int(i * step * fps), int((i + 1) * step * fps)
        if a >= c.shape[1]:
            break
        out[i] = c[:, a:max(z, a + 1)].mean(1)
    return out / (np.linalg.norm(out, axis=1, keepdims=True) + 1e-9)


def agreement(notes, ch, n):
    m = np.zeros((n, 12))
    for p, s, d, v in notes:
        m[int(round(s * 4)):min(n, int(round((s + d) * 4))), p % 12] += 1
    on = m.sum(1) > 0
    m = m / (np.linalg.norm(m, axis=1, keepdims=True) + 1e-9)
    return float((m[on] * ch[on]).sum(1).mean())


def main():
    args = sys.argv[1:]
    lo, hi, out = -4, 8, None
    free = "--free" in args
    args = [x for x in args if x != "--free"]
    if "--window" in args:
        i = args.index("--window")
        lo, hi = int(args[i + 1]), int(args[i + 2])
        args = args[:i] + args[i + 3:]
    if "--out" in args:
        i = args.index("--out")
        out = args[i + 1]
        args = args[:i] + args[i + 2:]
    parts_path, name, wav, bpm = args[0], args[1], args[2], float(args[3])
    parts = json.load(open(parts_path))
    notes = parts["parts"][name]
    n = int(parts["length_beats"] * 4) + 1
    ch = stem_chroma16(wav, bpm, n)

    # chords = groups of notes sharing a start (16th grid)
    groups = defaultdict(list)
    for nt in notes:
        groups[int(round(nt[1] * 4))].append(nt)
    starts = sorted(groups)
    pcs = {s: frozenset(p % 12 for p, *_ in groups[s]) for s in starts}

    def tmpl(ps):
        v = np.zeros(12)
        v[list(ps)] = 1
        return v / np.linalg.norm(v)

    moved, shifts, where = {}, Counter(), defaultdict(Counter)
    for a, b in zip(starts, starts[1:]):
        if pcs[a] == pcs[b]:
            continue
        ta, tb = tmpl(pcs[a]), tmpl(pcs[b])
        lo_i, hi_i = max(a + 1, b + lo), min(n - 1, b + hi)
        seg0, seg1 = max(a, b + lo - 4), min(n, b + hi + 4)
        best, best_s = b, -1e9
        for c in range(lo_i, hi_i + 1):
            s = (ch[seg0:c] @ ta).sum() + (ch[c:seg1] @ tb).sum()
            if s > best_s:
                best, best_s = c, s
        moved[b] = best
        shifts[best - b] += 1
        where[(pcs[b], b % 16)][best % 16] += 1

    # Consistent mode (default): every change of the same chord from the same charted spot
    # goes to that chord's MOST COMMON real spot – per-change fits jitter by a 16th or two,
    # which sounds sloppy on held chords. --free keeps each change's own fit.
    if not free:
        mode = {k: c.most_common(1)[0][0] for k, c in where.items()}
        for a, b in zip(starts, starts[1:]):
            if b in moved:
                tgt = mode[(pcs[b], b % 16)]
                d = (tgt - b % 16) % 16
                if d > 8:
                    d -= 16
                moved[b] = max(a + 1, b + d)

    def warp(t16):
        return moved.get(t16, t16)

    new = []
    for p, s, d, v in notes:
        s16, e16 = int(round(s * 4)), int(round((s + d) * 4))
        s2, e2 = warp(s16), warp(e16)
        if e2 > s2:
            new.append([p, s2 / 4.0, (e2 - s2) / 4.0, v])
    for (ps, pos), c in sorted(where.items(), key=lambda kv: (kv[0][1], sorted(kv[0][0]))):
        top = ", ".join(f"16th {k}: {v}" for k, v in c.most_common(3))
        print(f"  chord {sorted(ps)} charted at 16th {pos:>2} -> stem changes at {top}")
    before, after = agreement(notes, ch, n), agreement(new, ch, n)
    print(f"{name}: {len(moved)} chord changes; shift (16ths) histogram {dict(sorted(shifts.items()))}")
    print(f"chroma agreement with stem: before {before:.3f}  after {after:.3f}")
    parts["parts"][out or name] = new
    json.dump(parts, open(parts_path, "w"))


if __name__ == "__main__":
    main()
