"""Re-time a rhythmic part (bass, guitar stabs) to a held part's corrected chord changes.

Usage: follow_harmony.py <parts.json> <held before> <held after> <part> <bass|chord> <voicings.json> <stem.wav> <bpm> [--out <name>]

snap_changes.py fixes a HELD part by moving its chord boundaries. Rhythmic parts can't be
fixed that way (a stab or bass hit isn't a boundary), so this keeps their rhythm and
re-pitches every note whose chord differs between the old and the corrected timeline
(e.g. <held before> = "Keys", <held after> = "Keys v2"):
  bass   the new chord's root, in the octave of the part's own range (min..max of the part)
  chord  the pitch set this part already uses for that chord elsewhere (its real voicing)
Prints how many notes changed and the chroma agreement with the stem before/after.
"""
import json
import sys
from collections import Counter, defaultdict

import numpy as np

from snap_changes import agreement, stem_chroma16


def timeline(notes):
    g = defaultdict(set)
    for p, s, d, v in notes:
        g[int(round(s * 4))].add(p % 12)
    starts = sorted(g)
    return starts, {s: frozenset(g[s]) for s in starts}


def chord_at(tl, t16):
    starts, pcs = tl
    i = np.searchsorted(starts, t16, side="right") - 1
    return pcs[starts[i]] if i >= 0 else None


def main():
    args = sys.argv[1:]
    out = None
    if "--out" in args:
        i = args.index("--out")
        out = args[i + 1]
        args = args[:i] + args[i + 2:]
    parts_path, before, after, name, kind, vpath, wav, bpm = args
    parts = json.load(open(parts_path))
    held_v = json.load(open(vpath))
    old_tl, new_tl = timeline(parts["parts"][before]), timeline(parts["parts"][after])
    notes = parts["parts"][name]

    # held-part pitch set -> chord root, from the voicings file (same chord names as the plan)
    from common import parse_chord
    roots = {}
    for vname, table in held_v.items():
        for ch, pcl in table.items():
            roots.setdefault(frozenset(pcl), parse_chord(ch)[0])
    # the part's own voicing per held chord (most common pitch set at that chord's stabs)
    groups = defaultdict(list)
    for nt in notes:
        groups[int(round(nt[1] * 4))].append(nt)
    own = defaultdict(Counter)
    for s16, g in groups.items():
        c = chord_at(old_tl, s16)
        if c is not None:
            own[c][tuple(sorted(n[0] for n in g))] += 1
    lo = min(n[0] for n in notes)

    n = int(parts["length_beats"] * 4) + 1
    ch = stem_chroma16(wav, float(bpm), n)

    def fit(g):  # how well a note group matches the stem over its own span
        v = np.zeros(12)
        for p, *_ in g:
            v[p % 12] = 1
        a = int(round(g[0][1] * 4))
        z = max(a + 1, min(n, int(round((g[0][1] + g[0][2]) * 4))))
        return float((ch[a:z] @ (v / np.linalg.norm(v))).mean())

    # Per note group, the STEM decides: keep the old pitch or take the corrected chord's.
    # Don't assume every instrument shares one timing – on Lagos Rooftop the Rhodes and
    # guitar changed late but the bass landed the new root on the downbeat; re-pitching the
    # bass wholesale dropped its match from 0.49 to 0.34.
    new, changed = [], 0
    for s16, g in sorted(groups.items()):
        a, b = chord_at(old_tl, s16), chord_at(new_tl, s16)
        if a == b or b is None:
            new += g
            continue
        if kind == "bass":
            r = roots.get(b)
            alt = [[lo + (r - lo) % 12, s, d, v] for p, s, d, v in g] if r is not None else g
        else:
            if not own[b]:
                new += g
                continue
            shape = own[b].most_common(1)[0][0]
            s, d, v = g[0][1], g[0][2], g[0][3]
            alt = [[p, s, d, v] for p in shape]
        if fit(alt) > fit(g):
            new += alt
            changed += len(g)
        else:
            new += g
    print(f"{name}: {changed}/{len(notes)} notes re-pitched; agreement with stem "
          f"{agreement(notes, ch, n):.3f} -> {agreement(new, ch, n):.3f}")
    parts["parts"][out or name] = new
    json.dump(parts, open(parts_path, "w"))


if __name__ == "__main__":
    main()
