"""Per-bar level (dB) of each aligned stem – the map you read the song structure from.

Usage: bar_levels.py <bpm> <out.json> <name>=<aligned.wav> [...]

Prints one row per bar. Sections show up as blocks where the same instruments are
present (vocal in/out, drums drop, bass enters...). Write the section list yourself from
this table into plan.json – it is a judgement call, not something to automate blindly.
A stem counts as playing in a bar when it is within ~30 dB of its loudest bar and above
about -50 dB (bass: -40).
"""
import json
import sys

from common import bar_db, load_mono

SR = 22050


def main():
    bpm, out = float(sys.argv[1]), sys.argv[2]
    names, L = [], {}
    for spec in sys.argv[3:]:
        name, path = spec.split("=", 1)
        names.append(name)
        L[name] = bar_db(load_mono(path, SR), SR, bpm).round(1).tolist()
    n = max(len(v) for v in L.values())
    print("bar " + " ".join(f"{k[:7]:>7}" for k in names))
    for i in range(n):
        print(f"{i + 1:>3} " + " ".join(f"{L[k][i]:>7.0f}" if i < len(L[k]) else "      –" for k in names))
    json.dump(L, open(out, "w"))


if __name__ == "__main__":
    main()
