"""The voicing each instrument really uses over each chord (from its stem's chroma).

Usage: voicings.py <plan.json> <out_voicings.json> <name>=<aligned stem.wav>:<n_notes> [...]
e.g. piano=Piano.wav:4 guitar=Guitar.wav:3

For each chord name in the section loops, averages the stem's chroma over every place
that chord plays and keeps the top n pitch classes (always including the root). Textbook
shapes sound generic; these make the parts sit like the original. Check the printout for
bleed (a note foreign to the chord leaking from another instrument) and override it in
the JSON by hand if needed.
"""
import json
import sys

import librosa
import numpy as np

from common import NAMES, parse_chord

SR, HOP = 22050, 512


def main():
    plan, out = json.load(open(sys.argv[1])), sys.argv[2]
    spb, fps = 60.0 / plan["bpm"], SR / HOP
    events = []
    for sec in plan["sections"]:
        a, b = sec["bars"]
        t, end, i = (a - 1) * 4.0, b * 4.0, 0
        while t < end and sec.get("loop"):
            ch, d = sec["loop"][i % len(sec["loop"])]
            if ch:
                events.append((t, min(d, end - t), ch))
            t += d
            i += 1
    result = {}
    for spec in sys.argv[3:]:
        key, rest = spec.split("=", 1)
        path, n = rest.rsplit(":", 1)
        y = librosa.load(path, sr=SR)[0]
        c = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("C2"))
        result[key] = {}
        for ch in sorted({e[2] for e in events}):
            m = np.mean([c[:, int(t * spb * fps):max(int((t + d) * spb * fps), int(t * spb * fps) + 1)].mean(1)
                         for t, d, c2 in events if c2 == ch], axis=0)
            top = [int(x) for x in np.argsort(m)[::-1][:int(n)]]
            root = parse_chord(ch)[0]
            if root not in top:
                top = [root] + top[:int(n) - 1]
            result[key][ch] = sorted(top)
        print(key, {ch: " ".join(NAMES[p] for p in v) for ch, v in result[key].items()})
    json.dump(result, open(out, "w"), indent=1)


if __name__ == "__main__":
    main()
