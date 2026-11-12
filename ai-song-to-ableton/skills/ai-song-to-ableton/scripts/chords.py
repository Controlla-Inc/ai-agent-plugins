"""Chord chart from audio: harmonic chroma of (instrumental − drums) + the bass stem's root.

Usage: chords.py <instrumental.wav> <drums.wav> <bass.wav> <bpm> <key> <out_chart.json>
key like "F#m" or "Eb". All files aligned (time 0 = beat 0).

Half-bar slots (the first song's real harmonic rhythm was 2 beats, not a bar); triads and
7ths only, extensions have to earn their place. Output: [[start_beat, dur, "F#m"|null], ...]
merged where identical. Read it, then let loops.py fold it into one loop per section –
the raw chart has one-off misreads.
"""
import json
import sys

import librosa
import numpy as np

from common import MAJOR, MINOR, NAMES, parse_chord

SR, HOP = 22050, 512
QUALS = {"": (0, 4, 7), "m": (0, 3, 7), "maj7": (0, 4, 7, 11), "m7": (0, 3, 7, 10), "7": (0, 4, 7, 10)}


def main():
    ins, drm, bas, bpm, key, out = sys.argv[1:7]
    bpm = float(bpm)
    tonic, q = parse_chord(key)
    scale = {(tonic + i) % 12 for i in (MINOR if q.startswith("m") else MAJOR)}
    spb = 60.0 / bpm
    y, d, b = (librosa.load(p, sr=SR)[0] for p in (ins, drm, bas))
    n = min(len(y), len(d), len(b))
    harm = librosa.effects.harmonic(y[:n] - d[:n])
    chroma = librosa.feature.chroma_cqt(y=harm, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("C2"))
    bchroma = librosa.feature.chroma_cqt(y=b[:n], sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("C1"), n_octaves=4)
    rms = librosa.feature.rms(y=harm, hop_length=HOP)[0]
    fps = SR / HOP
    seg, t, beats = [], 0.0, n / SR / spb
    while t + 2 <= beats:
        a, z = int(t * spb * fps), int((t + 2) * spb * fps)
        if rms[a:z].mean() < 0.15 * rms.mean():
            seg.append([t, 2.0, None])
            t += 2
            continue
        c = chroma[:, a:z].mean(1)
        c = c / (c.max() or 1)
        bc = bchroma[:, a:z].mean(1)
        best = (None, -1e9)
        for root in range(12):
            for qq, sh in QUALS.items():
                pcs = {(root + i) % 12 for i in sh}
                sc = sum(c[p] for p in pcs) / len(pcs) - 0.5 * sum(c[p] for p in range(12) if p not in pcs) / (12 - len(pcs))
                sc += 0.25 * bc[root] / (bc.max() or 1)
                sc += 0.05 if pcs <= scale else 0.0
                sc -= 0.03 * (len(sh) - 3)
                if sc > best[1]:
                    best = (NAMES[root] + qq, sc)
        seg.append([t, 2.0, best[0]])
        t += 2
    merged = []
    for s in seg:
        if merged and merged[-1][2] == s[2]:
            merged[-1][1] += s[1]
        else:
            merged.append(s)
    json.dump(merged, open(out, "w"))
    for s, dur, ch in merged:
        print(f"bar {int(s // 4) + 1:>3}.{int(s % 4) + 1}  {dur:>4.0f}  {ch or '–'}")


if __name__ == "__main__":
    main()
