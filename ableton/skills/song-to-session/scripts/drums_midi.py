"""Drum MIDI from the drum stems (timing + velocity of the real performance).

Usage: drums_midi.py <parts.json> <bpm> <offset_s> kick=<kick.wav> snare=<snare.wav> [hats=<cymbals.wav>] [...]
Use the RAW (un-aligned) stems with the find_grid offset, or aligned stems with offset 0.

Notes: kick 36, snare 38, hats 42, open hat 46, crash 49, ride 51, clap 39, perc 37 –
the General MIDI slots, which is where make_rack.py puts the cloned samples. Starts
quantized to 1/16. The snare stem carries kick bleed: weak "snares" within 40 ms of a kick
are dropped. Writes parts.json["parts"]["Drums"].
"""
import json
import sys
from collections import Counter

import numpy as np

from common import onset_hits

NOTE = {"kick": 36, "snare": 38, "clap": 39, "perc": 37, "hats": 42, "openhat": 46, "crash": 49, "ride": 51}


def main():
    parts_path, bpm, off = sys.argv[1], float(sys.argv[2]), float(sys.argv[3])
    spb = 60.0 / bpm
    hits = {}
    for spec in sys.argv[4:]:
        k, path = spec.split("=", 1)
        hits[k] = onset_hits(path, off)
    if "kick" in hits and "snare" in hits:
        kt = np.array([t for t, _ in hits["kick"]])
        before = len(hits["snare"])
        hits["snare"] = [(t, v) for t, v in hits["snare"] if v >= 75 or not len(kt) or np.abs(kt - t).min() > 0.04]
        print(f"snare: dropped {before - len(hits['snare'])} kick-bleed hits")
    out, seen = [], set()
    for k, hs in hits.items():
        for t, v in hs:
            b = round(t / spb * 4) / 4
            if b < 0 or (NOTE[k], b) in seen:
                continue
            seen.add((NOTE[k], b))
            out.append([NOTE[k], b, 0.25, int(round(v))])
    out.sort(key=lambda n: (n[1], n[0]))
    try:
        data = json.load(open(parts_path))
    except FileNotFoundError:
        data = {"bpm": bpm, "parts": {}}
    data["parts"]["Drums"] = out
    data.setdefault("length_beats", int(np.ceil((out[-1][1] + 1) / 4) * 4) if out else 0)
    json.dump(data, open(parts_path, "w"))
    print(len(out), "hits", dict(Counter(n[0] for n in out)), "first", out[:4])


if __name__ == "__main__":
    main()
